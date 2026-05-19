"""Two-Tower 파인튜닝 스크립트

LGBMRanker를 teacher로 삼아 (시나리오 텍스트, 장소 텍스트) → cosine sim ≈ relevance 학습.

실행:
    cd data/
    python training/train_two_tower.py

출력:
    output/training/models/two_tower/  (tokenizer + model weights)
"""

# OpenMP/BLAS 스레딩 충돌 방지 (Windows LightGBM 데드락 픽스) — 반드시 모든 import 전에 설정
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")  # HF 네트워크 체크 방지

import logging
import random
import sys
import warnings

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from serving.ranker import _load_model, build_features, _MEETING_TYPE_MAP
from serving.two_tower import scenario_to_text, place_to_text, _PRETRAINED_NAME, _FINETUNED_PATH
from simulation.simulate import PURPOSES, MOOD_POOL

_LOG_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "output", "train_two_tower.log"))
os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── 설정 ────────────────────────────────────────────────────────────────────
N_SCENARIOS   = 200     # 시나리오 수
N_PLACES_PER  = 30      # 시나리오당 샘플링할 장소 수
EPOCHS        = 2
BATCH_SIZE    = 8       # CPU OOM 방지
LR            = 2e-5
SEED          = 42
# ─────────────────────────────────────────────────────────────────────────────

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

_PLACES_PATH   = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "output", "places.csv"))
_FEATURES_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "output", "features", "place_features.csv"))
_OUTPUT_DIR    = os.path.normpath(_FINETUNED_PATH)


# ── 데이터 준비 ───────────────────────────────────────────────────────────────

def _load_place_data() -> pd.DataFrame:
    places = pd.read_csv(
        _PLACES_PATH,
        usecols=["naver_place_id", "place_name", "category", "address"],
        dtype={"naver_place_id": str},
    )
    features = pd.read_csv(_FEATURES_PATH, dtype={"naver_place_id": str})
    overlap = [c for c in features.columns if c in places.columns and c != "naver_place_id"]
    features = features.drop(columns=overlap)
    df = places.merge(features, on="naver_place_id", how="inner")
    df = df.dropna(subset=["place_name", "lat", "lng"])
    logger.info(f"장소 데이터 로드: {len(df):,}개")
    return df.reset_index(drop=True)


def _make_scenario(purpose: str, time_slot: str, moods: list[str], center_lat: float, center_lng: float) -> dict:
    purpose_info = PURPOSES[purpose]
    return {
        "purpose": purpose,
        "purpose_cat": purpose_info["category"],
        "budget": sum(purpose_info["budget_range"]) // 2,
        "moods": moods,
        "time_slot": time_slot,
        "participants": [
            {"lat": center_lat + random.uniform(-0.02, 0.02), "lng": center_lng + random.uniform(-0.02, 0.02)}
            for _ in range(random.randint(3, 6))
        ],
        "center_lat": center_lat,
        "center_lng": center_lng,
    }


def generate_training_pairs(places_df: pd.DataFrame) -> list[dict]:
    warnings.filterwarnings("ignore", category=UserWarning, module="lightgbm")
    lgbm = _load_model()
    purposes    = list(PURPOSES.keys())
    time_slots  = ["점심", "저녁", "심야"]

    pairs = []
    for i in range(N_SCENARIOS):
        purpose   = random.choice(purposes)
        time_slot = random.choice(time_slots)
        n_moods   = random.randint(0, 2)
        moods     = random.sample(MOOD_POOL, k=n_moods)

        hub = places_df.sample(1).iloc[0]
        scenario = _make_scenario(purpose, time_slot, moods, hub["lat"], hub["lng"])

        purpose_cat = PURPOSES[purpose]["category"]
        cat_match = places_df[places_df["category_depth1"] == purpose_cat]
        cat_sample_n = min(N_PLACES_PER // 2, len(cat_match))
        other_n = N_PLACES_PER - cat_sample_n

        sampled = pd.concat([
            cat_match.sample(min(cat_sample_n, len(cat_match)), replace=False),
            places_df.sample(min(other_n, len(places_df)), replace=False),
        ]).drop_duplicates(subset=["naver_place_id"]).reset_index(drop=True)

        candidates = sampled[["naver_place_id", "place_name", "lat", "lng"]].to_dict("records")
        if not candidates:
            continue

        feat_df = build_features(candidates, scenario)
        raw_scores = lgbm.predict(feat_df)
        s_min, s_max = raw_scores.min(), raw_scores.max()
        norm_scores = (raw_scores - s_min) / (s_max - s_min) if s_max > s_min else np.full(len(raw_scores), 0.5)

        scenario_text = scenario_to_text(scenario)
        for j, cand in enumerate(candidates):
            place_text = place_to_text({
                "place_name": cand["place_name"],
                "category_name": sampled.iloc[j].get("category", ""),
                "address": sampled.iloc[j].get("address", ""),
            })
            pairs.append({
                "scenario_text": scenario_text,
                "place_text": place_text,
                "label": float(norm_scores[j]),
            })

        if (i + 1) % 100 == 0:
            logger.info(f"  시나리오 {i+1}/{N_SCENARIOS} — 누적 페어: {len(pairs):,}")

    logger.info(f"학습 페어 총 {len(pairs):,}개 생성")
    return pairs


# ── 데이터셋 ──────────────────────────────────────────────────────────────────

class PairDataset(Dataset):
    def __init__(self, pairs: list[dict], tokenizer, max_len: int = 128):
        self.pairs = pairs
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        p = self.pairs[idx]
        return p["scenario_text"], p["place_text"], torch.tensor(p["label"], dtype=torch.float)


def _collate(batch, tokenizer, max_len):
    scenarios, places, labels = zip(*batch)
    s_enc = tokenizer(list(scenarios), padding=True, truncation=True, max_length=max_len, return_tensors="pt")
    p_enc = tokenizer(list(places),   padding=True, truncation=True, max_length=max_len, return_tensors="pt")
    return s_enc, p_enc, torch.stack(labels)


# ── 모델 ─────────────────────────────────────────────────────────────────────

def mean_pool(hidden, attention_mask):
    mask = attention_mask.unsqueeze(-1).float()
    return (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


# ── 학습 ─────────────────────────────────────────────────────────────────────

def train():
    logger.info("=== Two-Tower 파인튜닝 시작 ===")
    places_df = _load_place_data()

    logger.info("학습 페어 생성 중...")
    pairs = generate_training_pairs(places_df)
    random.shuffle(pairs)

    tokenizer = AutoTokenizer.from_pretrained(_PRETRAINED_NAME, local_files_only=True)
    model     = AutoModel.from_pretrained(_PRETRAINED_NAME, local_files_only=True)
    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    logger.info(f"디바이스: {device}")

    dataset = PairDataset(pairs, tokenizer)
    loader  = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        collate_fn=lambda b: _collate(b, tokenizer, 64),
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    total_steps = len(loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=total_steps // 10, num_training_steps=total_steps)
    loss_fn = nn.MSELoss()

    model.train()
    for epoch in range(EPOCHS):
        total_loss = 0.0
        for step, (s_enc, p_enc, labels) in enumerate(loader):
            s_enc  = {k: v.to(device) for k, v in s_enc.items()}
            p_enc  = {k: v.to(device) for k, v in p_enc.items()}
            labels = labels.to(device)

            s_emb = mean_pool(model(**s_enc).last_hidden_state, s_enc["attention_mask"])
            p_emb = mean_pool(model(**p_enc).last_hidden_state, p_enc["attention_mask"])

            # L2 정규화 후 cosine sim
            s_norm = torch.nn.functional.normalize(s_emb, dim=-1)
            p_norm = torch.nn.functional.normalize(p_emb, dim=-1)
            cos_sim = (s_norm * p_norm).sum(dim=-1)   # (B,)

            # cosine sim(-1~1) → 0~1 스케일 맞춤
            cos_01 = (cos_sim + 1.0) / 2.0
            loss = loss_fn(cos_01, labels)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()
            if (step + 1) % 50 == 0:
                logger.info(f"  epoch {epoch+1}/{EPOCHS}  step {step+1}/{len(loader)}  loss={total_loss/(step+1):.4f}")

        logger.info(f"[Epoch {epoch+1}] avg loss = {total_loss/len(loader):.4f}")

    # 저장
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(_OUTPUT_DIR)
    tokenizer.save_pretrained(_OUTPUT_DIR)
    logger.info(f"모델 저장 완료: {_OUTPUT_DIR}")


if __name__ == "__main__":
    train()

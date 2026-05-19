"""Two-Tower 텍스트 기반 장소-시나리오 유사도 스코어러

카카오 API 장소처럼 naver_place_id 브릿지가 없는 장소에 대한 폴백 스코어러.
텍스트 임베딩 cosine 유사도로 "이 장소가 이 시나리오에 얼마나 맞나" 판단.

모델 우선순위:
  1. output/training/models/two_tower/ — train_two_tower.py로 파인튜닝된 모델
  2. klue/roberta-base              — 제로샷 (HuggingFace 캐시)
"""

import logging
import os
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

_FINETUNED_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "output", "training", "models", "two_tower")
)
_PRETRAINED_NAME = "klue/roberta-base"

_MOOD_KO = {
    "mood_quiet": "조용한",
    "mood_group": "단체",
    "mood_vibe": "분위기좋은",
    "mood_budget": "저렴한",
    "mood_private": "프라이빗",
}


@lru_cache(maxsize=1)
def _load_encoder():
    from transformers import AutoTokenizer, AutoModel
    model_path = _FINETUNED_PATH if os.path.isdir(_FINETUNED_PATH) else _PRETRAINED_NAME
    logger.info(f"Two-Tower 인코더 로드: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModel.from_pretrained(model_path)
    model.eval()
    return tokenizer, model


def _mean_pool(hidden, attention_mask):
    import torch
    mask = attention_mask.unsqueeze(-1).float()
    return (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)


def _encode(texts: list[str], tokenizer, model, batch_size: int = 32) -> np.ndarray:
    import torch
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = tokenizer(batch, padding=True, truncation=True, max_length=128, return_tensors="pt")
        with torch.no_grad():
            out = model(**enc)
        emb = _mean_pool(out.last_hidden_state, enc["attention_mask"])
        all_embeddings.append(emb.cpu().numpy())
    return np.vstack(all_embeddings)


def scenario_to_text(scenario: dict) -> str:
    purpose = scenario.get("purpose", "모임")
    time_slot = scenario.get("time_slot", "저녁")
    moods = scenario.get("moods", [])
    location = scenario.get("location_name", "")
    mood_str = " ".join(_MOOD_KO.get(m, m) for m in moods)
    parts = [purpose, "모임", time_slot, mood_str, location]
    return " ".join(p for p in parts if p).strip()


def place_to_text(candidate: dict) -> str:
    name = candidate.get("place_name", "")
    cat = candidate.get("category_name", "")
    addr = candidate.get("address", "")
    return f"{name} {cat} {addr}".strip()


def score_places(scenario: dict, candidates: list[dict]) -> list[float]:
    """시나리오 vs 후보 장소 텍스트 cosine 유사도 반환 (리스트 길이 == len(candidates))."""
    if not candidates:
        return []

    tokenizer, model = _load_encoder()

    scenario_text = scenario_to_text(scenario)
    place_texts = [place_to_text(c) for c in candidates]

    s_emb = _encode([scenario_text], tokenizer, model)[0]   # (D,)
    p_embs = _encode(place_texts, tokenizer, model)          # (N, D)

    s_norm = s_emb / (np.linalg.norm(s_emb) + 1e-9)
    p_norms = p_embs / (np.linalg.norm(p_embs, axis=1, keepdims=True) + 1e-9)
    scores = (p_norms @ s_norm).tolist()

    return scores

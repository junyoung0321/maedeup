"""리뷰 수집 완료 후 자동 파이프라인 실행
수순: 장소CSV재빌드 → normalize → morpheme → absa → sarcasm → sentiment_label → features → simulation
"""

import json
import os
import subprocess
import sys
import time

REVIEW_CHECKPOINT = "output/supplement_review_ids.json"
REVIEW_TARGET = 26588
LOG_PATH = "output/pipeline_auto.log"


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def wait_for_reviews():
    log(f"리뷰 수집 완료 대기 중... (목표: {REVIEW_TARGET:,}개)")
    while True:
        try:
            done = json.load(open(REVIEW_CHECKPOINT))
            cnt = len(done)
        except Exception:
            cnt = 0
        log(f"  현재 {cnt:,} / {REVIEW_TARGET:,} ({cnt/REVIEW_TARGET*100:.1f}%)")
        if cnt >= REVIEW_TARGET:
            log("리뷰 수집 완료 확인!")
            break
        time.sleep(300)  # 5분마다 체크


def rebuild_places_csv():
    log("places.csv 재빌드 시작 (raw 기반, rating>0 필터)")
    import ast
    import pandas as pd

    raw_dir = "output/raw"
    sup_meta = {}
    sup_data = json.load(open("output/place_ids/supplement_place_ids.json", encoding="utf-8"))
    for p in sup_data:
        pid = str(p["naver_place_id"])
        sup_meta[pid] = {
            "hub": p.get("hub", ""),
            "keyword": p.get("keyword", ""),
            "category_group": p.get("category_group", ""),
        }

    records = []
    raw_files = os.listdir(raw_dir)
    log(f"  raw 파일 {len(raw_files):,}개 처리 중...")

    for fname in raw_files:
        pid = fname.replace(".json", "")
        fpath = os.path.join(raw_dir, fname)
        try:
            d = json.load(open(fpath, encoding="utf-8"))
        except Exception:
            continue
        meta = sup_meta.get(pid, {})
        d["naver_place_id"] = pid
        d.setdefault("hub", meta.get("hub", ""))
        d.setdefault("keyword", meta.get("keyword", ""))
        d.setdefault("category_group", meta.get("category_group", ""))
        d.setdefault("review_total_verified", "")
        records.append(d)

    df = pd.DataFrame(records)
    df["naver_place_id"] = df["naver_place_id"].astype(str)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0)
    df = df.sort_values("rating", ascending=False).drop_duplicates(
        subset=["naver_place_id"], keep="first"
    )
    df = df[df["rating"] > 0].copy()

    cols = [
        "naver_place_id", "place_name", "category", "address", "lat", "lng",
        "rating", "review_count", "blog_review_count", "keyword_tags",
        "menu_prices", "business_hours", "review_texts",
        "hub", "keyword", "category_group", "review_total_verified",
    ]
    cols = [c for c in cols if c in df.columns]
    df[cols].to_csv("output/places.csv", index=False, encoding="utf-8-sig")

    # 리뷰 텍스트 통계
    places_with_rt = 0
    total_rt = 0
    for val in df["review_texts"]:
        if not val or str(val).strip() in ("", "[]", "nan", "None"):
            continue
        try:
            texts = ast.literal_eval(str(val))
            if isinstance(texts, list) and texts:
                places_with_rt += 1
                total_rt += len(texts)
        except Exception:
            pass

    log(f"  재빌드 완료: {len(df):,}개 장소")
    log(f"  review_texts 있는 장소: {places_with_rt:,} / 총 리뷰 문장: {total_rt:,}")


def run_step(name, cmd):
    log(f"[STEP] {name} 시작")
    result = subprocess.run(
        [sys.executable] + cmd,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    if result.returncode != 0:
        log(f"[ERROR] {name} 실패 (returncode={result.returncode})")
        sys.exit(1)
    log(f"[DONE] {name} 완료")


if __name__ == "__main__":
    log("=== 자동 파이프라인 시작 ===")

    # 0. 리뷰 수집 완료 대기
    wait_for_reviews()

    # 1. places.csv 재빌드
    rebuild_places_csv()

    # 2. 전처리 파이프라인
    run_step("normalize", ["run_normalize.py", "--no-spacing"])
    run_step("morpheme", ["run_morpheme.py"])
    run_step("absa", ["run_absa.py"])
    run_step("sarcasm", ["run_sarcasm.py"])
    run_step("sentiment_label", ["run_sentiment_label.py"])

    # 3. Feature 가공
    run_step("features", ["run_features.py"])

    # 4. 시뮬레이션 (pseudo-label 생성)
    run_step("simulation", ["run_simulation.py"])

    log("=== 전체 파이프라인 완료 ===")

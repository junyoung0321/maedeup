"""매듭 크롤링 작업 현황 자동 저장 스크립트
세션 시작 시 자동 실행 (SessionStart 훅) → 1시간마다 상태 파일 기록
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
SUMMARY_DIR = OUTPUT_DIR / "work_summaries"

CHECKPOINT_FILES = {
    "search_main":       OUTPUT_DIR / "place_ids" / "all_place_ids.json",
    "enriched_main":     OUTPUT_DIR / "enriched_ids_v2.json",
    "review_main":       OUTPUT_DIR / "review_collected_ids.json",
    "search_supplement": OUTPUT_DIR / "supplement_search_checkpoint.json",
    "enriched_supp":     OUTPUT_DIR / "supplement_enriched_ids.json",
    "review_supp":       OUTPUT_DIR / "supplement_review_ids.json",
}

LOG_FILES = {
    "search_main":     OUTPUT_DIR / "supplement_log.txt",
    "review_supp":     OUTPUT_DIR / "supplement_log_review.txt",
}

PLACES_CSV = OUTPUT_DIR / "places.csv"


def count_ids(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            # supplement_search_checkpoint 형식: {completed: [...], ...}
            for key in ("completed", "done", "ids"):
                if key in data:
                    return len(data[key])
            return len(data)
    except Exception:
        return -1


def read_last_lines(path: Path, n: int = 5) -> str:
    if not path.exists():
        return "(파일 없음)"
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # tqdm 진행률 라인만 필터링 (숫자% 포함 라인)
        progress_lines = [l.rstrip() for l in lines if "%" in l or "it/s" in l or "완료" in l or "checkpoint" in l]
        last = progress_lines[-n:] if len(progress_lines) >= n else progress_lines
        return "\n".join(last) if last else lines[-1].rstrip() if lines else "(비어있음)"
    except Exception as e:
        return f"(읽기 오류: {e})"


def supplement_search_progress() -> dict:
    """supplement_search_checkpoint.json에서 진행률 계산"""
    path = CHECKPOINT_FILES["search_supplement"]
    if not path.exists():
        return {"done": 0, "total": 5301, "pct": 0.0}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            done = len(data)
        elif isinstance(data, dict):
            done = len(data.get("completed", data.get("done", [])))
        else:
            done = 0
        total = 5301  # 93 hubs × 57 keywords
        return {"done": done, "total": total, "pct": done / total * 100}
    except Exception:
        return {"done": -1, "total": 5301, "pct": 0.0}


def csv_row_count() -> int:
    if not PLACES_CSV.exists():
        return 0
    try:
        with open(PLACES_CSV, encoding="utf-8-sig", errors="replace") as f:
            return sum(1 for _ in f) - 1  # 헤더 제외
    except Exception:
        return -1


def build_summary() -> str:
    now = datetime.now()
    lines = [
        f"# 매듭 크롤링 작업 현황",
        f"**기록 시각**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 체크포인트 현황",
        "",
        "| 단계 | 파일 | 완료 수 |",
        "|------|------|---------|",
    ]

    for key, path in CHECKPOINT_FILES.items():
        count = count_ids(path)
        label = {
            "search_main":       "메인 검색 (all_place_ids)",
            "enriched_main":     "메인 상세보강 (v2)",
            "review_main":       "메인 리뷰 수집",
            "search_supplement": "supplement 검색 체크포인트",
            "enriched_supp":     "supplement 상세보강",
            "review_supp":       "supplement 리뷰 수집",
        }.get(key, key)
        exists = "✅" if path.exists() else "❌"
        lines.append(f"| {label} | {exists} | {count if count >= 0 else 'ERR'} |")

    # supplement 검색 진행률
    sp = supplement_search_progress()
    lines += [
        "",
        "## supplement 검색 진행률",
        f"- 완료: {sp['done']} / {sp['total']} ({sp['pct']:.1f}%)",
    ]

    # supplement 리뷰 진행률
    review_done = count_ids(CHECKPOINT_FILES["review_supp"])
    lines += [
        "",
        "## supplement 리뷰 수집 진행률",
        f"- 체크포인트 기완료: {review_done}개",
        f"- (전체 대상 ~26,588개 기준 {review_done/26588*100:.1f}%)" if review_done > 0 else "",
    ]

    # 최종 CSV
    csv_count = csv_row_count()
    lines += [
        "",
        "## places.csv 현황",
        f"- 행 수: {csv_count}개",
        f"- 경로: {PLACES_CSV}",
    ]

    # 최근 로그
    lines += ["", "## 최근 로그 (리뷰 수집)"]
    lines.append("```")
    lines.append(read_last_lines(LOG_FILES["review_supp"], 8))
    lines.append("```")

    return "\n".join(lines)


def save_summary():
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = SUMMARY_DIR / f"{ts}.md"
    content = build_summary()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[work-summary] 저장: {path}", flush=True)
    return path


def main():
    interval_sec = 3600  # 1시간

    print(f"[work-summary] 시작 — {interval_sec // 60}분 간격으로 저장", flush=True)

    while True:
        try:
            save_summary()
        except Exception as e:
            print(f"[work-summary] 오류: {e}", flush=True)
        time.sleep(interval_sec)


if __name__ == "__main__":
    main()

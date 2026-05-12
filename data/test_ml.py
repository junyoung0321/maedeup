"""ML 추천 파이프라인 단독 검증 스크립트.
실행: python test_ml.py  (data/ 디렉토리에서)
"""
import sys, json, time, logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)  # serving 로그 숨김

sys.path.insert(0, str(Path(__file__).parent))
from serving.quick_recommend import quick_recommend

TESTS = [
    dict(location="홍대",     meeting_type="카페",  headcount=3,  date_time="내일 오후 3시"),
    dict(location="강남역",   meeting_type="식사",  headcount=5,  date_time="이번주 금요일 저녁"),
    dict(location="신촌",     meeting_type="술자리", headcount=4, date_time="오늘 밤"),
    dict(location="여의도",   meeting_type="회의",  headcount=6,  date_time="다음주 오전 10시"),
    dict(location=None,       meeting_type="식사",  headcount=2,  date_time=None),  # 위치 없음 edge case
]

SEP = "─" * 60

def fmt_result(result: dict, elapsed: float):
    sc = result["scenario"]
    meta = result["meta"]
    recs = result["recommendations"]

    print(f"  시나리오  : {sc['purpose']} | {sc['time_slot']} | {sc['location_name']} | {sc['headcount']}명")
    print(f"  후보수    : {meta['candidates_found']}곳  |  추천: {len(recs)}개  |  소요: {elapsed:.2f}s")

    if not recs:
        print("  ⚠ 추천 결과 없음 (후보 0)")
        return

    print(f"  {'순위':<3} {'장소명':<25} {'score':>6}  {'거리':<12}  이미지?")
    for r in recs:
        img = "O" if r.get("image_url") else "X"
        print(f"  {r['rank']:<3} {r['place_name']:<25} {r['score']:>6.4f}  {r.get('distance_label',''):<12}  {img}")
        if r.get("reasons"):
            print(f"       → {', '.join(r['reasons'][:3])}")

def main():
    print(SEP)
    print("  매듭 ML 추천 파이프라인 검증")
    print(SEP)

    all_ok = True
    for i, kwargs in enumerate(TESTS, 1):
        label = f"[{i}/{len(TESTS)}] location={kwargs['location']} / {kwargs['meeting_type']} / {kwargs['headcount']}명"
        print(f"\n{label}")
        try:
            t0 = time.time()
            result = quick_recommend(**kwargs, top_k=5)
            elapsed = time.time() - t0
            fmt_result(result, elapsed)

            # 기본 sanity check
            recs = result["recommendations"]
            if recs:
                scores = [r["score"] for r in recs]
                assert all(0.0 <= s <= 1.0 for s in scores), "score 범위 오류"
                assert scores == sorted(scores, reverse=True), "score 정렬 오류"
                assert all(r.get("place_name") for r in recs), "place_name 누락"
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            all_ok = False

    print(f"\n{SEP}")
    print(f"  결과: {'ALL PASS' if all_ok else 'FAIL'}")
    print(SEP)

if __name__ == "__main__":
    main()

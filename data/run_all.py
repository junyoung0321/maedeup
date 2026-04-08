"""전체 파이프라인: 검색 → 상세 → CSV"""

from run_search import main as search_main
from run_detail import main as detail_main


def main():
    print("=" * 60)
    print("[1/2] 장소 ID 수집")
    print("=" * 60)
    search_main()

    print("\n" + "=" * 60)
    print("[2/2] 장소 상세 수집")
    print("=" * 60)
    detail_main()

    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()

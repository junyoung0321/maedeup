# TODOS

## When2Meet 프라이버시 고려
- **What:** detail_date 파라미터가 멤버별 busy periods를 노출하므로, 상용화 시 프라이버시 동의 UI 필요
- **Why:** 현재 calendar API는 날짜별 이름만 노출하지만, detail_date는 시간대별 바쁜 시간을 보여줌. 졸프 데모에서는 문제없지만 민감한 데이터
- **Pros:** 사용자 동의 기반 데이터 공개로 프라이버시 보호
- **Cons:** 추가 UI + 동의 플로우 구현 필요
- **Context:** /plan-eng-review에서 Codex가 지적. 졸프 데모에서는 무시하되, 상용화 시 검토 필요
- **Depends on:** InfoPane 대개편 완료 후

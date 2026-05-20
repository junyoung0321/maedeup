/**
 * DB는 KST naive datetime을 'Z' 없이 ISO 직렬화해 응답한다
 * (예: "2026-05-25T18:00:00"). 브라우저의 `new Date()`는 TZ 없는
 * 문자열을 로컬 시간으로 해석 → KST(UTC+9) 브라우저에서는 as-is로 올바르게 표시.
 *
 * Fix (2026-05-20): 이전 'Z' 보강은 UTC로 강제 해석 → +9 이중 적용 →
 *   "오후 6:00"이 "오전 3:00"으로 잘못 표시되는 버그.
 * TZ 마커가 없으면 그대로 두어 로컬 시간(KST)으로 해석.
 * 이미 +HH:MM 또는 Z가 포함된 경우는 그대로 둔다.
 */
export function parseServerDate(value: string): Date {
  if (!value) return new Date(NaN);
  return new Date(value);  // KST naive → 로컬 시간(KST) 해석, 변환 없음
}

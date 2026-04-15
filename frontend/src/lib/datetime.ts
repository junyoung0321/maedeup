/**
 * Backend는 datetime을 naive UTC로 저장하고 ISO 직렬화 시 'Z' 없이 응답한다
 * (예: "2026-04-15T10:19:19.248105"). 브라우저의 `new Date()`는 TZ 없는
 * 문자열을 로컬 시간으로 해석하므로, 그대로 쓰면 KST 기준 9시간이 어긋난다.
 *
 * 이 헬퍼는 누락된 경우에만 'Z'를 붙여 항상 UTC로 해석되게 만든다.
 * 이미 +HH:MM 또는 Z가 포함된 경우는 그대로 둔다.
 */
export function parseServerDate(value: string): Date {
  if (!value) return new Date(NaN);
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(value);
  return new Date(hasTz ? value : `${value}Z`);
}

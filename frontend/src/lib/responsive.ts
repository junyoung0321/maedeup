/**
 * 뷰포트 폭에 따라 자연스럽게 스케일되는 폰트 크기 반환.
 * 기준: 1920px viewport에서 base, 960px viewport에서 min으로 수렴.
 * 공식: clamp(min, A px + B vw, base), where
 *   B = (base - min) / 9.6, A = 2*min - base
 *
 * 시연용 글로벌 폰트 스케일: `FS_SCALE` 한 값으로 모든 fs() 호출이 일괄 조정.
 * fs() 미사용 (hardcoded fontSize) 컴포넌트는 영향 없음.
 */
export const FS_SCALE = 1.5;

export function fs(base: number, min?: number): string {
  const scaledBase = base * FS_SCALE;
  const scaledMin = min === undefined ? undefined : min * FS_SCALE;
  const lo = scaledMin ?? Math.max(10, Math.round(scaledBase * 0.65 * 10) / 10);
  const b = Math.round(((scaledBase - lo) / 9.6) * 100) / 100;
  const a = Math.round((2 * lo - scaledBase) * 10) / 10;
  return `clamp(${lo}px, ${a}px + ${b}vw, ${scaledBase}px)`;
}

/** 동일 로직으로 간격/패딩 등 일반 px 값에 사용. */
export function sp(base: number, min?: number): string {
  return fs(base, min);
}

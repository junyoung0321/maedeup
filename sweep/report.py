"""스윕 결과 집계 + GO/NO-GO 합성 (스펙 §9)."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from sweep.transcript import RoomTranscript


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(1, math.ceil(p / 100.0 * len(s)))
    return s[k - 1]


@dataclass
class SweepReport:
    total: int
    passed: int
    failed: int
    p50_latency_s: float
    p95_latency_s: float
    violation_counts: dict[str, int] = field(default_factory=dict)
    scenario_results: dict[str, list[str]] = field(default_factory=dict)


def aggregate(rooms: list[RoomTranscript],
              scenario_results: dict[str, list[str]] | None = None) -> SweepReport:
    all_lat: list[float] = []
    vc: Counter[str] = Counter()
    passed = 0
    for r in rooms:
        all_lat.extend(r.latencies)
        if r.passed:
            passed += 1
        for v in r.violations:
            vc[v.code] += 1
    return SweepReport(
        total=len(rooms),
        passed=passed,
        failed=len(rooms) - passed,
        p50_latency_s=percentile(all_lat, 50),
        p95_latency_s=percentile(all_lat, 95),
        violation_counts=dict(vc),
        scenario_results=scenario_results or {},
    )


def go_no_go(report: SweepReport) -> str:
    """실패 0 + p95<8s + 시나리오 전원 PASS이면 GO, 아니면 NO-GO."""
    blockers: list[str] = []
    if report.failed > 0:
        blockers.append(f"{report.failed}/{report.total} 대화 불변조건 위반")
    if report.p95_latency_s > 8.0:
        blockers.append(f"p95 지연 {report.p95_latency_s:.2f}s > 8s")

    scenario_fail_count = sum(
        1 for failures in report.scenario_results.values() if failures
    )
    if scenario_fail_count > 0:
        blockers.append(f"정확성 시나리오 {scenario_fail_count}개 실패")

    verdict = "NO-GO" if blockers else "GO"
    lines = [
        f"# 견고성 스윗 결과: {verdict}",
        f"- 대화: {report.passed}/{report.total} PASS",
        f"- 지연: p50={report.p50_latency_s:.2f}s p95={report.p95_latency_s:.2f}s",
    ]
    if report.violation_counts:
        lines.append(f"- 위반: {report.violation_counts}")

    if report.scenario_results:
        lines.append("## 정확성 시나리오")
        for key in sorted(report.scenario_results):
            failures = report.scenario_results[key]
            status = "FAIL" if failures else "PASS"
            lines.append(f"- {key}: {status}")
            for f in failures:
                lines.append(f"  - {f}")

    if blockers:
        lines.append("## 차단 사유")
        lines += [f"- {b}" for b in blockers]
    return "\n".join(lines)

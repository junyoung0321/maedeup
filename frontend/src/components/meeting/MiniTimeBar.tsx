"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";

const BAR_START = 9;
const BAR_END = 22;
const SLOT_MIN = 30;
const TOTAL_SLOTS = ((BAR_END - BAR_START) * 60) / SLOT_MIN; // 26

interface MemberBusyPeriod {
  start: string;
  end: string;
}

interface Props {
  date: string; // "YYYY-MM-DD"
  roomId: string;
  /** AI 추천 시간대 (start_at/end_at ISO strings) */
  aiSlots?: { start_at: string; end_at: string }[];
}

function isBusyAt(periods: MemberBusyPeriod[], date: string, slotIdx: number): boolean {
  const slotStartMin = BAR_START * 60 + slotIdx * SLOT_MIN;
  const slotEndMin = slotStartMin + SLOT_MIN;

  for (const p of periods) {
    const ps = new Date(p.start);
    const pe = new Date(p.end);
    const pDate = `${ps.getFullYear()}-${String(ps.getMonth() + 1).padStart(2, "0")}-${String(ps.getDate()).padStart(2, "0")}`;

    if (pDate === date) {
      const psMin = ps.getHours() * 60 + ps.getMinutes();
      const peMin = pe.getHours() * 60 + pe.getMinutes();
      if (peMin === 0 && psMin === 0) return true; // all-day
      if (psMin < slotEndMin && peMin > slotStartMin) return true;
    }
  }
  return false;
}

function fmtHour(h: number): string {
  if (h <= 12) return `${h}`;
  return `${h - 12}`;
}

export default function MiniTimeBar({ date, roomId, aiSlots }: Props) {
  const [memberData, setMemberData] = useState<Record<string, MemberBusyPeriod[]> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const [y, m] = date.split("-").map(Number);
    apiFetch<{
      dates: Record<string, unknown>;
      member_busy_periods?: Record<string, MemberBusyPeriod[]>;
    }>(`/api/v1/calendar/free-slots?room_id=${roomId}&year=${y}&month=${m}&detail_date=${date}`)
      .then((data) => {
        if (cancelled) return;
        setMemberData(data.member_busy_periods ?? {});
      })
      .catch(() => {
        if (!cancelled) setMemberData({});
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [date, roomId]);

  // Per-slot aggregate: how many members are free
  const { slotAvail, memberCount } = useMemo(() => {
    if (!memberData) return { slotAvail: [], memberCount: 0 };
    const members = Object.entries(memberData);
    const cnt = members.length;
    const avail = Array.from({ length: TOTAL_SLOTS }, (_, i) => {
      if (cnt === 0) return 1; // no members → show all available
      const freeCount = members.filter(([, periods]) => !isBusyAt(periods, date, i)).length;
      return freeCount / cnt; // 0~1 ratio
    });
    return { slotAvail: avail, memberCount: cnt };
  }, [memberData, date]);

  // AI recommended slot indices
  const aiHighlight = useMemo(() => {
    const set = new Set<number>();
    if (!aiSlots) return set;
    for (const slot of aiSlots) {
      const st = new Date(slot.start_at);
      const en = new Date(slot.end_at);
      const sIdx = Math.max(0, (st.getHours() - BAR_START) * 2 + Math.floor(st.getMinutes() / SLOT_MIN));
      const eIdx = Math.min(TOTAL_SLOTS, (en.getHours() - BAR_START) * 2 + Math.floor(en.getMinutes() / SLOT_MIN));
      for (let i = sIdx; i < eIdx; i++) set.add(i);
    }
    return set;
  }, [aiSlots]);

  if (loading) {
    return (
      <div style={{ marginTop: 8, fontSize: 11, color: "#94a3b8", textAlign: "center" }}>
        시간대 조회 중...
      </div>
    );
  }

  // Find best available range for summary
  let bestStart = -1, bestLen = 0, curStart = -1, curLen = 0;
  for (let i = 0; i < TOTAL_SLOTS; i++) {
    if (slotAvail[i] >= 1) {
      if (curStart === -1) curStart = i;
      curLen++;
      if (curLen > bestLen) { bestStart = curStart; bestLen = curLen; }
    } else {
      curStart = -1; curLen = 0;
    }
  }

  const freeSlotCount = slotAvail.filter((v) => v >= 1).length;
  const fmtTime = (slotIdx: number) => {
    const totalMin = BAR_START * 60 + slotIdx * SLOT_MIN;
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    const ap = h < 12 ? "오전" : "오후";
    return `${ap} ${h <= 12 ? h : h - 12}:${String(m).padStart(2, "0")}`;
  };

  return (
    <div style={{ marginTop: 8 }}>
      {/* Hour labels */}
      <div style={{ display: "flex", marginBottom: 1 }}>
        {Array.from({ length: BAR_END - BAR_START }, (_, i) => (
          <div key={i} style={{
            width: `${100 / (BAR_END - BAR_START)}%`,
            fontSize: 8,
            color: "#94a3b8",
            textAlign: "left",
            fontFamily: "Inter, sans-serif",
          }}>
            {BAR_START + i}
          </div>
        ))}
      </div>
      {/* Availability bar */}
      <div style={{
        display: "flex",
        height: 22,
        borderRadius: 6,
        overflow: "hidden",
        border: "1px solid #e2e8f0",
      }}>
        {slotAvail.map((ratio, i) => {
          const isAi = aiHighlight.has(i);
          // Color: green intensity by availability ratio
          let bg: string;
          if (ratio >= 1) bg = "#22c55e";       // all available
          else if (ratio >= 0.5) bg = "#86efac"; // most available
          else if (ratio > 0) bg = "#fde68a";    // some available
          else bg = "#fdba74";                    // 다른 일정 겹침

          return (
            <div key={i} style={{
              flex: 1,
              background: bg,
              borderRight: i % 2 === 1 && i < TOTAL_SLOTS - 1 ? "1px solid rgba(0,0,0,0.06)" : "none",
              borderBottom: isAi ? "3px solid #3B82F6" : "none",
            }}
            title={`${fmtTime(i)} ${Math.round(ratio * 100)}% 가능${isAi ? " (AI 추천)" : ""}`}
            />
          );
        })}
      </div>
      {/* Legend */}
      <div style={{ display: "flex", gap: 8, marginTop: 4, fontSize: 9, color: "#64748b" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: "#22c55e", display: "inline-block" }} /> 전원
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: "#86efac", display: "inline-block" }} /> 대부분
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: "#fde68a", display: "inline-block" }} /> 일부
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: "#fdba74", display: "inline-block" }} /> 다른 일정
        </span>
        {aiHighlight.size > 0 && (
          <span style={{ display: "flex", alignItems: "center", gap: 2 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, borderBottom: "3px solid #3B82F6", display: "inline-block" }} /> AI추천
          </span>
        )}
      </div>
      {/* Summary */}
      <div style={{ marginTop: 3, fontSize: 11, color: "#475569" }}>
        {freeSlotCount > 0 ? (
          bestLen >= 2 ? (
            <span>
              전원 가능: <span style={{ fontWeight: 600, color: "#166534" }}>{fmtTime(bestStart)} ~ {fmtTime(bestStart + bestLen)}</span>
              {memberCount > 0 && <span style={{ color: "#94a3b8" }}> ({memberCount}명 기준)</span>}
            </span>
          ) : (
            <span>전원 가능 시간 {freeSlotCount * 30}분{memberCount > 0 && <span style={{ color: "#94a3b8" }}> ({memberCount}명 기준)</span>}</span>
          )
        ) : memberCount > 0 ? (
          <span style={{ color: "#dc2626" }}>전원 가능한 시간이 없습니다</span>
        ) : (
          <span style={{ color: "#94a3b8" }}>캘린더 연동 멤버 없음 (전체 가능으로 표시)</span>
        )}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { Clock } from "lucide-react";
import { useMeeting } from "@/contexts/MeetingContext";

// A3-3: TimeBar 상수 미러 (TimeBarSelector.tsx와 동기화 — C7 contract).
const HOUR_START = 9;
const SLOT_MINUTES = 30;
const TOTAL_SLOTS = 26; // (22-9)*60/30 = 26

function slotToTime(idx: number): string {
  const totalMinutes = HOUR_START * 60 + idx * SLOT_MINUTES;
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${h}:${m.toString().padStart(2, "0")}`;
}

interface HostTimeAdjustModalProps {
  snapshotHash: string;
  confirmedDate: string;
  memberCount: number;
  onConfirm: (chosenTime: { date: string; start_idx: number; end_idx: number }) => void;
  onCancel: () => void;
}

export default function HostTimeAdjustModal({
  snapshotHash: _snapshotHash,
  confirmedDate,
  memberCount,
  onConfirm,
  onCancel,
}: HostTimeAdjustModalProps) {
  const { peerTimeSelections, myTimeSelection } = useMeeting();

  // heatmap[i] = 슬롯 i에 가능한 멤버 수 (peer + my, 본인 중복 방지: peer는 self echo 안 받음)
  const heatmap = useMemo(() => {
    const counts = new Array(TOTAL_SLOTS).fill(0);
    for (const sel of Object.values(peerTimeSelections)) {
      if (!sel || sel.date !== confirmedDate) continue;
      const s = Math.max(0, sel.start);
      const e = Math.min(TOTAL_SLOTS - 1, sel.end);
      for (let i = s; i <= e; i++) counts[i]++;
    }
    if (myTimeSelection && myTimeSelection.date === confirmedDate) {
      const s = Math.max(0, myTimeSelection.start);
      const e = Math.min(TOTAL_SLOTS - 1, myTimeSelection.end);
      for (let i = s; i <= e; i++) counts[i]++;
    }
    return counts;
  }, [peerTimeSelections, myTimeSelection, confirmedDate]);

  // default range — 가장 긴 "전원 가능" 연속 segment, 없으면 첫 부분 가능 슬롯
  const defaultRange = useMemo(() => {
    let bestStart = -1, bestEnd = -1;
    let curStart = -1, curEnd = -1;
    for (let i = 0; i < TOTAL_SLOTS; i++) {
      if (heatmap[i] === memberCount) {
        if (curStart === -1) curStart = i;
        curEnd = i;
      } else {
        if (curStart !== -1 && (curEnd - curStart) > (bestEnd - bestStart)) {
          bestStart = curStart;
          bestEnd = curEnd;
        }
        curStart = -1;
        curEnd = -1;
      }
    }
    if (curStart !== -1 && (curEnd - curStart) > (bestEnd - bestStart)) {
      bestStart = curStart;
      bestEnd = curEnd;
    }
    if (bestStart === -1) {
      for (let i = 0; i < TOTAL_SLOTS; i++) {
        if (heatmap[i] > 0) return { start: i, end: i };
      }
      return { start: 0, end: 0 };
    }
    return { start: bestStart, end: bestEnd };
  }, [heatmap, memberCount]);

  const [startIdx, setStartIdx] = useState(defaultRange.start);
  const [endIdx, setEndIdx] = useState(defaultRange.end);

  // defaultRange 바뀌면 한 번만 동기화 (사용자가 드래그 중인 게 아니면)
  useEffect(() => {
    setStartIdx(defaultRange.start);
    setEndIdx(defaultRange.end);
  }, [defaultRange.start, defaultRange.end]);

  // start ≤ end 강제
  const handleStartChange = (v: number) => {
    setStartIdx(v);
    if (v > endIdx) setEndIdx(v);
  };
  const handleEndChange = (v: number) => {
    setEndIdx(v);
    if (v < startIdx) setStartIdx(v);
  };

  // 선택 범위 내 최소 가능 인원
  const minAvailableInRange = useMemo(() => {
    if (startIdx > endIdx) return 0;
    let m = memberCount;
    for (let i = startIdx; i <= endIdx; i++) m = Math.min(m, heatmap[i]);
    return m;
  }, [startIdx, endIdx, heatmap, memberCount]);

  const isValid = minAvailableInRange > 0;
  const isFullConsensus = minAvailableInRange === memberCount;

  return (
    <div
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 520,
          background: "#ffffff",
          borderRadius: 18,
          padding: "22px 22px 18px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Clock size={20} style={{ color: "#4f46e5" }} />
          <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#1e1b4b" }}>
            시간대 조율
          </h3>
        </div>
        <div style={{ fontSize: 13, color: "#475569", lineHeight: 1.5 }}>
          {confirmedDate} · 총 {memberCount}명 합산 가능 시간 — 슬라이더로 정밀 선택
        </div>

        {/* Heatmap */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${TOTAL_SLOTS}, 1fr)`, gap: 1 }}>
            {heatmap.map((count, i) => {
              let bg = "#e5e7eb";
              if (count === memberCount) bg = "#10b981";
              else if (count > 0) bg = "#fde68a";
              const inRange = i >= startIdx && i <= endIdx;
              return (
                <div
                  key={i}
                  title={`${slotToTime(i)} — ${count}/${memberCount}명 가능`}
                  style={{
                    height: 28,
                    background: bg,
                    outline: inRange ? "2px solid #3b82f6" : "none",
                    outlineOffset: -1,
                    transition: "outline 0.1s",
                  }}
                />
              );
            })}
          </div>
          {/* 시간 라벨 (2시간마다 = 4슬롯마다) */}
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${TOTAL_SLOTS}, 1fr)`, gap: 1, fontSize: 10, color: "#94a3b8" }}>
            {Array.from({ length: TOTAL_SLOTS }, (_, i) => (
              <div key={i} style={{ textAlign: "center", fontVariantNumeric: "tabular-nums" }}>
                {i % 4 === 0 ? slotToTime(i) : ""}
              </div>
            ))}
          </div>
        </div>

        {/* 범례 */}
        <div style={{ display: "flex", gap: 14, fontSize: 11, color: "#475569" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 12, height: 12, background: "#10b981", borderRadius: 2 }} /> 전원 가능
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 12, height: 12, background: "#fde68a", borderRadius: 2 }} /> 부분 가능
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 12, height: 12, background: "#e5e7eb", borderRadius: 2 }} /> 0명
          </span>
        </div>

        {/* 슬라이더 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label style={{ fontSize: 12, color: "#475569", display: "flex", justifyContent: "space-between" }}>
            <span>시작</span>
            <span style={{ fontWeight: 600, color: "#1e293b", fontVariantNumeric: "tabular-nums" }}>{slotToTime(startIdx)}</span>
          </label>
          <input
            type="range"
            min={0}
            max={TOTAL_SLOTS - 1}
            value={startIdx}
            onChange={(e) => handleStartChange(Number(e.target.value))}
            style={{ width: "100%", accentColor: "#4f46e5" }}
          />
          <label style={{ fontSize: 12, color: "#475569", display: "flex", justifyContent: "space-between" }}>
            <span>끝</span>
            <span style={{ fontWeight: 600, color: "#1e293b", fontVariantNumeric: "tabular-nums" }}>{slotToTime(endIdx + 1)}</span>
          </label>
          <input
            type="range"
            min={0}
            max={TOTAL_SLOTS - 1}
            value={endIdx}
            onChange={(e) => handleEndChange(Number(e.target.value))}
            style={{ width: "100%", accentColor: "#4f46e5" }}
          />
        </div>

        {/* 선택 정보 */}
        <div
          style={{
            padding: "10px 13px",
            borderRadius: 10,
            background: isFullConsensus ? "#ecfdf5" : isValid ? "#fef3c7" : "#fee2e2",
            border: `1px solid ${isFullConsensus ? "#86efac" : isValid ? "#fcd34d" : "#fca5a5"}`,
            fontSize: 13,
            color: isFullConsensus ? "#166534" : isValid ? "#92400e" : "#991b1b",
            lineHeight: 1.5,
          }}
        >
          {isFullConsensus
            ? `✅ 선택: ${slotToTime(startIdx)}~${slotToTime(endIdx + 1)} (${memberCount}명 모두 가능)`
            : isValid
              ? `⚠️ ${minAvailableInRange}명만 가능합니다 (${slotToTime(startIdx)}~${slotToTime(endIdx + 1)})`
              : `❌ 선택 범위에 가능한 멤버가 없습니다`}
        </div>

        {/* 버튼 */}
        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1,
              padding: "11px 14px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              background: "#ffffff",
              color: "#475569",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            취소
          </button>
          <button
            onClick={() => onConfirm({ date: confirmedDate, start_idx: startIdx, end_idx: endIdx })}
            disabled={!isValid}
            style={{
              flex: 2,
              padding: "11px 14px",
              borderRadius: 10,
              border: "none",
              background: isValid ? "#4f46e5" : "#cbd5e1",
              color: "#ffffff",
              fontSize: 14,
              fontWeight: 700,
              cursor: isValid ? "pointer" : "not-allowed",
              fontFamily: "inherit",
            }}
          >
            이 시간으로 확정
          </button>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import Calendar from "react-calendar";
import "react-calendar/dist/Calendar.css";

// ── 타입 ──────────────────────────────────────────────────

interface DayInfo {
  available: string[];
  busy: string[];
  unconnected: string[];
}

interface CalendarData {
  dates: Record<string, DayInfo>;
}

type CalendarValue = Date | null;

// ── 날짜 포맷 헬퍼 ────────────────────────────────────────

/** Date → "YYYY-MM-DD" (로컬 시각 기준) */
function toDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** "YYYY-MM-DD" → "3월 21일" */
function toKoreanDate(key: string): string {
  const [, m, d] = key.split("-");
  return `${Number(m)}월 ${Number(d)}일`;
}

// ── 날짜 상태 계산 ────────────────────────────────────────

type DotStatus = "green" | "red" | "none";

function getDotStatus(info: DayInfo | undefined): DotStatus {
  if (!info) return "none";
  const connected = info.available.length + info.busy.length;
  if (connected === 0) return "none";
  if (info.busy.length > 0) return "red";
  return "green";
}

// ── 서브 컴포넌트 ─────────────────────────────────────────

function StatusDot({ status }: { status: DotStatus }) {
  if (status === "none") return <span style={{ height: 6 }} />;
  return (
    <span
      style={{
        display: "block",
        width: 5,
        height: 5,
        borderRadius: "50%",
        background: status === "green" ? "#22c55e" : "#ef4444",
        flexShrink: 0,
      }}
    />
  );
}

function MemberList({
  label,
  names,
  color,
  icon,
}: {
  label: string;
  names: string[];
  color: string;
  icon: string;
}) {
  if (names.length === 0) return null;
  return (
    <div style={{ display: "flex", gap: 6, fontSize: 12, alignItems: "flex-start" }}>
      <span style={{ flexShrink: 0 }}>{icon}</span>
      <span style={{ color: "#555" }}>{label}:</span>
      <span style={{ color }}>{names.join(", ")}</span>
    </div>
  );
}

function DateDetail({
  dateKey,
  info,
}: {
  dateKey: string;
  info: DayInfo | undefined;
}) {
  return (
    <div
      style={{
        marginTop: 10,
        background: "#141414",
        border: "1px solid #222",
        borderRadius: 7,
        padding: "12px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, color: "#ddd", marginBottom: 2 }}>
        {toKoreanDate(dateKey)}
      </div>

      {!info || (info.available.length === 0 && info.busy.length === 0 && info.unconnected.length === 0) ? (
        <div style={{ fontSize: 12, color: "#444" }}>데이터 없음</div>
      ) : (
        <>
          <MemberList label="가능" names={info.available} color="#4ade80" icon="✅" />
          <MemberList label="불가능" names={info.busy} color="#f87171" icon="❌" />
          <MemberList label="미연동" names={info.unconnected} color="#555" icon="🔗" />
        </>
      )}
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────

export default function DataPane() {
  const [calendarData, setCalendarData] = useState<CalendarData | null>(null);
  const [selectedDate, setSelectedDate] = useState<CalendarValue>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFreeSlots = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("auth_token");
      const resp = await fetch("/api/v1/calendar/free-slots?room_id=room-1", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) throw new Error("가능한 시간대를 불러오지 못했습니다.");
      const data: CalendarData = await resp.json();
      setCalendarData(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const selectedKey = selectedDate ? toDateKey(selectedDate) : null;
  const selectedInfo = selectedKey && calendarData ? calendarData.dates[selectedKey] : undefined;

  return (
    <section
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
        borderLeft: "1px solid #1e1e1e",
      }}
    >
      {/* 패널 헤더 */}
      <header
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #222",
          fontWeight: 600,
          fontSize: 13,
          letterSpacing: "0.05em",
          color: "#aaa",
          textTransform: "uppercase",
          flexShrink: 0,
        }}
      >
        Data
      </header>

      {/* 스크롤 영역 */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "14px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {/* 캘린더 섹션 헤더 */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: 11, color: "#444", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            캘린더
          </div>
          <button
            onClick={fetchFreeSlots}
            disabled={loading}
            title="새로고침"
            style={{
              background: "transparent",
              border: "none",
              padding: "2px 4px",
              cursor: loading ? "not-allowed" : "pointer",
              lineHeight: 1,
              opacity: loading ? 0.5 : 0.7,
              fontSize: 13,
            }}
            onMouseEnter={(e) => { if (!loading) (e.currentTarget as HTMLButtonElement).style.opacity = "1"; }}
            onMouseLeave={(e) => { if (!loading) (e.currentTarget as HTMLButtonElement).style.opacity = "0.7"; }}
          >
            <span className={loading ? "maedeup-spinning" : ""}>🔄</span>
          </button>
        </div>

        {/* react-calendar */}
        <div
          style={{
            background: "#141414",
            border: "1px solid #1e1e1e",
            borderRadius: 8,
            padding: "10px 8px",
          }}
        >
          <Calendar
            locale="ko-KR"
            calendarType="US"
            value={selectedDate}
            onClickDay={(date: Date) =>
              setSelectedDate((prev) =>
                prev && toDateKey(prev) === toDateKey(date) ? null : date
              )
            }
            tileContent={({ date, view }: { date: Date; view: string }) => {
              if (view !== "month") return null;
              const status = getDotStatus(calendarData?.dates[toDateKey(date)]);
              return <StatusDot status={status} />;
            }}
            tileClassName={({ date, view }: { date: Date; view: string }) => {
              if (view !== "month") return null;
              return selectedDate && toDateKey(date) === toDateKey(selectedDate)
                ? "react-calendar__tile--active"
                : null;
            }}
          />
        </div>

        {/* 초기 로드 버튼 — 데이터 없을 때만 표시 */}
        {!calendarData && (
          <button
            onClick={fetchFreeSlots}
            disabled={loading}
            style={{
              width: "100%",
              padding: "9px",
              background: loading ? "#141414" : "#1a2233",
              border: "1px solid #2a3a4a",
              borderRadius: 7,
              color: loading ? "#444" : "#60a5fa",
              fontSize: 12,
              fontWeight: 500,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "조회 중..." : "가능한 시간 찾기"}
          </button>
        )}

        {/* 범례 */}
        {calendarData && (
          <div style={{ display: "flex", gap: 14, padding: "2px 2px" }}>
            <Legend color="#22c55e" label="모두 가능" />
            <Legend color="#ef4444" label="바쁜 멤버 있음" />
          </div>
        )}

        {/* 에러 */}
        {error && (
          <div style={{ fontSize: 12, color: "#ef4444" }}>{error}</div>
        )}

        {/* 날짜 상세 */}
        {selectedKey && (
          <DateDetail dateKey={selectedKey} info={selectedInfo} />
        )}

        {/* 빈 상태 */}
        {!calendarData && !loading && !error && (
          <div style={{ fontSize: 11, color: "#333", textAlign: "center", padding: "8px 0" }}>
            버튼을 눌러 멤버들의 일정을 확인하세요
          </div>
        )}

        {/* 이벤트 섹션 구분선 */}
        <div
          style={{
            borderTop: "1px solid #1a1a1a",
            paddingTop: 12,
            fontSize: 12,
            color: "#2a2a2a",
          }}
        >
          일정 · 장소 데이터 영역
        </div>
      </div>
    </section>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "#555" }}>
      <span
        style={{
          display: "block",
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: color,
          flexShrink: 0,
        }}
      />
      {label}
    </div>
  );
}

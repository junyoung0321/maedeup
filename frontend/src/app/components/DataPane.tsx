"use client";

import { useState, useEffect, useRef } from "react";
import Calendar from "react-calendar";
import "react-calendar/dist/Calendar.css";

// ── 카카오맵 전역 타입 ─────────────────────────────────────
declare global {
  interface Window {
    kakao: any;
  }
}

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

interface KakaoPlace {
  id: string;
  place_name: string;
  address_name: string;
  road_address_name: string;
  place_url: string;
  x: string; // longitude
  y: string; // latitude
}

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
  // ── 캘린더 상태 ──
  const [calendarData, setCalendarData] = useState<CalendarData | null>(null);
  const [selectedDate, setSelectedDate] = useState<CalendarValue>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── 장소 검색 상태 ──
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KakaoPlace[]>([]);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [confirmedId, setConfirmedId] = useState<string | null>(null);

  const mapRef = useRef<HTMLDivElement>(null);
  const kakaoMapRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);

  // ── 캘린더 ──────────────────────────────────────────────

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

  // ── 장소 검색 ─────────────────────────────────────────

  const searchPlaces = () => {
    if (!searchQuery.trim()) return;
    if (!window.kakao) {
      setSearchError("카카오맵 SDK가 아직 로딩 중입니다. 잠시 후 다시 시도해주세요.");
      return;
    }

    setSearchLoading(true);
    setSearchError(null);
    setSearchResults([]);
    setHighlightedId(null);

    window.kakao.maps.load(() => {
      const ps = new window.kakao.maps.services.Places();
      ps.keywordSearch(searchQuery, (data: KakaoPlace[], status: string) => {
        setSearchLoading(false);
        if (status === window.kakao.maps.services.Status.OK) {
          setSearchResults(data);
        } else if (status === window.kakao.maps.services.Status.ZERO_RESULT) {
          setSearchError("검색 결과가 없습니다.");
        } else {
          setSearchError("검색 중 오류가 발생했습니다.");
        }
      });
    });
  };

  // ── 지도 초기화 ───────────────────────────────────────

  useEffect(() => {
    if (searchResults.length === 0 || !mapRef.current) return;
    if (!window.kakao) return;

    window.kakao.maps.load(() => {
      if (!mapRef.current) return;

      const firstPlace = searchResults[0];
      const center = new window.kakao.maps.LatLng(
        parseFloat(firstPlace.y),
        parseFloat(firstPlace.x)
      );

      const map = new window.kakao.maps.Map(mapRef.current, {
        center,
        level: 5,
      });
      kakaoMapRef.current = map;

      // 기존 마커 제거
      markersRef.current.forEach((m) => m.setMap(null));

      // 마커 생성
      markersRef.current = searchResults.map((place) => {
        const position = new window.kakao.maps.LatLng(
          parseFloat(place.y),
          parseFloat(place.x)
        );
        const marker = new window.kakao.maps.Marker({ position, map });

        window.kakao.maps.event.addListener(marker, "click", () => {
          setHighlightedId(place.id);
          map.setCenter(position);
        });

        return marker;
      });

      // 전체 마커가 보이도록 bounds 설정
      if (searchResults.length > 1) {
        const bounds = new window.kakao.maps.LatLngBounds();
        searchResults.forEach((p) => {
          bounds.extend(new window.kakao.maps.LatLng(parseFloat(p.y), parseFloat(p.x)));
        });
        map.setBounds(bounds);
      }
    });
  }, [searchResults]);

  // ── 확정 ──────────────────────────────────────────────

  const confirmPlace = async (place: KakaoPlace) => {
    setConfirmingId(place.id);
    try {
      const token = localStorage.getItem("auth_token");
      const resp = await fetch("/api/v1/events/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          title: place.place_name,
          location_name: place.road_address_name || place.address_name,
          latitude: parseFloat(place.y),
          longitude: parseFloat(place.x),
          kakao_place_id: place.id,
          kakao_place_url: place.place_url,
          starts_at: new Date().toISOString(),
        }),
      });
      if (!resp.ok) throw new Error("저장 실패");
      setConfirmedId(place.id);
      setTimeout(() => setConfirmedId(null), 3000);
    } catch {
      // no-op
    } finally {
      setConfirmingId(null);
    }
  };

  // ── 렌더링 ─────────────────────────────────────────────

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
        {/* ── 캘린더 섹션 헤더 ── */}
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

        {/* 초기 로드 버튼 */}
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
        {error && <div style={{ fontSize: 12, color: "#ef4444" }}>{error}</div>}

        {/* 날짜 상세 */}
        {selectedKey && <DateDetail dateKey={selectedKey} info={selectedInfo} />}

        {/* 빈 상태 */}
        {!calendarData && !loading && !error && (
          <div style={{ fontSize: 11, color: "#333", textAlign: "center", padding: "8px 0" }}>
            버튼을 눌러 멤버들의 일정을 확인하세요
          </div>
        )}

        {/* ── 구분선 ── */}
        <div style={{ borderTop: "1px solid #1a1a1a", paddingTop: 12 }} />

        {/* ── 장소 검색 섹션 ── */}
        <div style={{ fontSize: 11, color: "#444", letterSpacing: "0.06em", textTransform: "uppercase" }}>
          장소 검색
        </div>

        {/* 검색 입력 */}
        <div style={{ display: "flex", gap: 6 }}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && searchPlaces()}
            placeholder="장소 키워드 입력"
            style={{
              flex: 1,
              background: "#141414",
              border: "1px solid #2a2a2a",
              borderRadius: 6,
              padding: "7px 10px",
              color: "#ddd",
              fontSize: 12,
              outline: "none",
            }}
          />
          <button
            onClick={searchPlaces}
            disabled={searchLoading || !searchQuery.trim()}
            style={{
              background: searchLoading ? "#141414" : "#1a2233",
              border: "1px solid #2a3a4a",
              borderRadius: 6,
              padding: "7px 12px",
              color: searchLoading ? "#444" : "#60a5fa",
              fontSize: 12,
              cursor: searchLoading || !searchQuery.trim() ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            {searchLoading ? "검색 중" : "검색"}
          </button>
        </div>

        {/* 검색 오류 */}
        {searchError && <div style={{ fontSize: 12, color: "#ef4444" }}>{searchError}</div>}

        {/* 검색 결과 카드 */}
        {searchResults.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {searchResults.map((place) => {
              const isHighlighted = highlightedId === place.id;
              const isConfirmed = confirmedId === place.id;
              const isConfirming = confirmingId === place.id;
              return (
                <div
                  key={place.id}
                  onClick={() => setHighlightedId(place.id)}
                  style={{
                    background: isHighlighted ? "#1a2a1a" : "#141414",
                    border: `1px solid ${isHighlighted ? "#22c55e44" : "#222"}`,
                    borderRadius: 7,
                    padding: "10px 12px",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                    transition: "border-color 0.15s",
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#ddd" }}>
                    {place.place_name}
                  </div>
                  <div style={{ fontSize: 11, color: "#555" }}>
                    {place.road_address_name || place.address_name}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 4 }}>
                    <a
                      href={place.place_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      style={{ fontSize: 11, color: "#3b82f6", textDecoration: "none" }}
                    >
                      카카오맵에서 보기 →
                    </a>
                    <button
                      onClick={(e) => { e.stopPropagation(); confirmPlace(place); }}
                      disabled={isConfirming}
                      style={{
                        background: isConfirmed ? "#14532d" : "#1a2233",
                        border: `1px solid ${isConfirmed ? "#22c55e" : "#2a3a4a"}`,
                        borderRadius: 5,
                        padding: "3px 10px",
                        color: isConfirmed ? "#4ade80" : "#60a5fa",
                        fontSize: 11,
                        cursor: isConfirming ? "not-allowed" : "pointer",
                        fontWeight: 500,
                      }}
                    >
                      {isConfirmed ? "저장됨 ✓" : isConfirming ? "저장 중..." : "확정"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 카카오맵 지도 */}
        {searchResults.length > 0 && (
          <div
            ref={mapRef}
            style={{
              width: "100%",
              height: 220,
              borderRadius: 8,
              border: "1px solid #222",
              overflow: "hidden",
              flexShrink: 0,
            }}
          />
        )}
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

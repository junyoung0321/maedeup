"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface NotificationItem {
  id: number;
  type: string;
  title: string;
  body: string | null;
  room_id: number | null;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

interface TypeVisual {
  icon: string;
  color: string;
}

const TYPE_VISUALS: Record<string, TypeVisual> = {
  MEETING_CONFIRMED: { icon: "📋", color: "#4f46e5" },
  VOTE_STARTED: { icon: "🗳️", color: "#f59e0b" },
  VOTE_ENDED: { icon: "✅", color: "#22c55e" },
  PLACE_RECOMMENDED: { icon: "📍", color: "#7c3aed" },
  NEW_MEMBER_JOINED: { icon: "👥", color: "#06b6d4" },
  FRIEND_REQUEST_RECEIVED: { icon: "👤", color: "#fb923c" },
  MEETING_IMMINENT: { icon: "🔔", color: "#ef4444" },
};

const DEFAULT_VISUAL: TypeVisual = { icon: "🔔", color: "#64748b" };

function formatRelativeKorean(isoUtc: string): string {
  // 백엔드는 naive UTC datetime(ISO)을 내려보낸다. 'Z' 붙여서 UTC로 파싱.
  const iso = isoUtc.endsWith("Z") ? isoUtc : `${isoUtc}Z`;
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const nowMs = Date.now();
  const diffMs = nowMs - then.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "방금";
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}시간 전`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay === 1) return "어제";
  if (diffDay < 7) return `${diffDay}일 전`;
  const m = then.getMonth() + 1;
  const d = then.getDate();
  return `${m}월 ${d}일`;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function NotificationPanel({ open, onClose }: Props) {
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [markingAll, setMarkingAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await apiFetch<NotificationItem[]>(
        "/api/v1/notifications?limit=20",
      );
      setItems(res);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      load();
    }
  }, [open, load]);

  const handleMarkAll = async () => {
    if (markingAll) return;
    setMarkingAll(true);
    // optimistic: 즉시 visual read 처리
    const nowIso = new Date().toISOString();
    setItems((prev) =>
      prev.map((n) => (n.read_at ? n : { ...n, read_at: nowIso })),
    );
    try {
      await apiFetch("/api/v1/notifications/read-all", { method: "POST" });
    } catch {
      // 실패 시 서버 상태 재조회로 되돌리기
      await load();
    } finally {
      setMarkingAll(false);
    }
  };

  const handleItemClick = async (n: NotificationItem) => {
    // optimistic read
    if (!n.read_at) {
      setItems((prev) =>
        prev.map((x) =>
          x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x,
        ),
      );
      apiFetch(`/api/v1/notifications/${n.id}/read`, { method: "POST" }).catch(
        () => {
          /* silent: 화면 상태 유지 */
        },
      );
    }
    if (n.room_id) {
      onClose();
      router.push(`/meeting/${n.room_id}`);
    }
  };

  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 90 }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: "absolute",
          top: 79,
          right: 80,
          width: 380,
          borderRadius: 20,
          background: "#ffffff",
          boxShadow: "0 10px 40px rgba(0,0,0,0.15)",
          border: "1px solid #e2e8f0",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "18px 20px 12px",
          }}
        >
          <span style={{ fontSize: 18, fontWeight: 600, color: "#111827" }}>
            알림
          </span>
          <button
            onClick={handleMarkAll}
            disabled={markingAll || items.every((n) => n.read_at)}
            style={{
              padding: "6px 12px",
              borderRadius: 8,
              border: "none",
              background: "#4f46e5",
              color: "#ffffff",
              fontSize: 11,
              fontWeight: 500,
              cursor:
                markingAll || items.every((n) => n.read_at)
                  ? "not-allowed"
                  : "pointer",
              opacity:
                markingAll || items.every((n) => n.read_at) ? 0.5 : 1,
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            }}
          >
            {markingAll ? "처리 중..." : "모두 읽음"}
          </button>
        </div>

        {/* Content */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            maxHeight: 400,
            overflowY: "auto",
          }}
        >
          {loading ? (
            <div
              style={{
                padding: "32px 20px",
                textAlign: "center",
                color: "#94a3b8",
                fontSize: 13,
              }}
            >
              불러오는 중...
            </div>
          ) : error ? (
            <div
              style={{
                padding: "32px 20px",
                textAlign: "center",
                color: "#ef4444",
                fontSize: 13,
              }}
            >
              알림을 불러올 수 없습니다
            </div>
          ) : items.length === 0 ? (
            <div
              style={{
                padding: "40px 20px",
                textAlign: "center",
                color: "#94a3b8",
                fontSize: 13,
                lineHeight: 1.5,
              }}
            >
              아직 받은 알림이 없어요
              <br />
              <span style={{ fontSize: 11, color: "#cbd5e1" }}>
                새 이벤트가 생기면 여기에 표시됩니다
              </span>
            </div>
          ) : (
            items.map((n) => {
              const visual = TYPE_VISUALS[n.type] ?? DEFAULT_VISUAL;
              const unread = n.read_at === null;
              return (
                <div
                  key={n.id}
                  onClick={() => handleItemClick(n)}
                  style={{
                    display: "flex",
                    gap: 12,
                    padding: "14px 20px",
                    cursor: "pointer",
                    borderBottom: "1px solid #f8fafc",
                    background: unread ? "#fafbff" : "transparent",
                  }}
                >
                  {/* Unread indicator + icon */}
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: unread ? visual.color : "#d1d5db",
                      marginTop: 6,
                      flexShrink: 0,
                    }}
                  />
                  <div
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      gap: 3,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "#111827",
                        lineHeight: 1.4,
                      }}
                    >
                      <span style={{ marginRight: 6 }}>{visual.icon}</span>
                      {n.title}
                    </span>
                    {n.body && (
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 400,
                          color: "#94a3b8",
                          lineHeight: 1.3,
                        }}
                      >
                        {n.body}
                      </span>
                    )}
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 400,
                        color: "#cbd5e1",
                        marginTop: 2,
                      }}
                    >
                      {formatRelativeKorean(n.created_at)}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

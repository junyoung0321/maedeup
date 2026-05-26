"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface LeaveResponse {
  room_id: number;
  cancelled_meeting_ids: number[];
  triggered_meeting_cancellation: boolean;
}

export default function LeaveRoomButton({ roomId }: { roomId: string }) {
  const router = useRouter();
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLeave = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch<LeaveResponse>(`/api/v1/rooms/${roomId}/leave`, {
        method: "POST",
      });
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "방을 나갈 수 없습니다");
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        type="button"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 14px",
          borderRadius: 20,
          border: "1px solid rgba(255,255,255,0.3)",
          background: "rgba(255,255,255,0.15)",
          color: "#ffffff",
          fontSize: 20,
          fontWeight: 600,
          cursor: "pointer",
          fontFamily: "Pretendard, sans-serif",
          backdropFilter: "blur(4px)",
        }}
      >
        <LogOut size={14} strokeWidth={2} />
        방 나가기
      </button>

      {showModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            fontFamily: "Pretendard, sans-serif",
          }}
          onClick={() => !submitting && setShowModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#ffffff",
              borderRadius: 16,
              padding: 24,
              width: 400,
              maxWidth: "calc(100vw - 32px)",
              boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
            }}
          >
            <h3 style={{ fontSize: 27, fontWeight: 700, color: "#0f172a", margin: 0, marginBottom: 12 }}>
              모임 방을 나가시겠어요?
            </h3>
            <ul style={{ margin: 0, padding: "0 0 0 18px", fontSize: 20, color: "#475569", lineHeight: 1.6 }}>
              <li>본인의 구글 캘린더에서 이 모임 일정이 제거됩니다.</li>
              <li>본인의 선호 정보 / 참여 기록이 삭제됩니다.</li>
              <li>
                <strong>호스트인 경우</strong> 모임 자체가 취소되며 모든 참여자의 캘린더 일정이 함께 제거됩니다.
              </li>
            </ul>

            {error && (
              <div style={{ marginTop: 12, fontSize: 18, color: "#ef4444" }}>{error}</div>
            )}

            <div style={{ display: "flex", gap: 8, marginTop: 20, justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowModal(false)}
                disabled={submitting}
                style={{
                  padding: "10px 18px",
                  borderRadius: 10,
                  border: "1px solid #cbd5e1",
                  background: "#ffffff",
                  color: "#475569",
                  fontSize: 20,
                  fontWeight: 600,
                  cursor: submitting ? "not-allowed" : "pointer",
                  fontFamily: "Pretendard, sans-serif",
                }}
              >
                취소
              </button>
              <button
                onClick={handleLeave}
                disabled={submitting}
                style={{
                  padding: "10px 18px",
                  borderRadius: 10,
                  border: "none",
                  background: "#ef4444",
                  color: "#ffffff",
                  fontSize: 20,
                  fontWeight: 600,
                  cursor: submitting ? "not-allowed" : "pointer",
                  fontFamily: "Pretendard, sans-serif",
                  opacity: submitting ? 0.6 : 1,
                }}
              >
                {submitting ? "나가는 중…" : "나가기"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

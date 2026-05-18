"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  CircleCheck,
  Calendar,
  Users,
  CalendarCheck,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Room, ProposalPayload } from "@/types";

function formatSlot(slot: Record<string, unknown> | null): string {
  if (!slot) return "";
  const date = (slot.date ?? slot.scheduled_date ?? slot.start_date ?? "") as string;
  const start = (slot.start_time ?? slot.time ?? "") as string;
  const end = (slot.end_time ?? "") as string;
  const day = (slot.day_of_week ?? slot.day ?? "") as string;

  if (date) {
    const datePart = day ? `${date} (${day})` : date;
    const timePart = start ? (end ? `${start}~${end}` : start) : "";
    return timePart ? `${datePart} ${timePart}` : datePart;
  }

  return Object.values(slot)
    .filter((v) => v !== null && v !== undefined && v !== "")
    .map(String)
    .join(" ");
}

function ScheduleConfirmPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [room, setRoom] = useState<Room | null>(null);
  const [proposal, setProposal] = useState<ProposalPayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<Room>(`/api/v1/rooms/${roomId}`)
      .then(setRoom)
      .catch(() => null);
    apiFetch<ProposalPayload | null>(`/api/v1/finalization/room/${roomId}`)
      .then(setProposal)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [authLoading, user, roomId]);

  const roomName = room?.name ?? "모임";
  const likeCount = proposal?.like_count ?? 0;
  const total = proposal?.total_eligible_voters ?? 0;
  const otherCount = proposal?.other_count ?? 0;

  return (
    <div
      className="relative flex flex-col bg-white"
      style={{ width: "100%", height: "844px", fontFamily: "Pretendard, sans-serif" }}
    >
      {/* Header */}
      <div
        className="flex items-center shrink-0"
        style={{ height: 56, padding: "0 16px", backgroundColor: "#fff", borderBottom: "1px solid #e2e8f0" }}
      >
        <ArrowLeft
          size={24}
          color="#1e293b"
          className="shrink-0 cursor-pointer"
          onClick={() => router.push(`/m/schedule?roomId=${roomId}`)}
        />
        <div className="flex flex-col justify-center flex-1" style={{ gap: 2, marginLeft: 12 }}>
          <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b", lineHeight: "22px" }}>
            {roomName}
          </span>
          <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8", lineHeight: "16px" }}>
            {room?.category ?? "모임"}
          </span>
        </div>
        <Menu size={24} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => router.push(`/m/meeting/detail?roomId=${roomId}`)} />
      </div>

      {/* Tab bar */}
      <div
        className="flex shrink-0"
        style={{ height: 44, backgroundColor: "#fff", borderBottom: "1px solid #e2e8f0" }}
      >
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          onClick={() => router.push(`/m/chat/schedule?roomId=${roomId}`)}
          style={{ fontSize: 14, fontWeight: 500, color: "#94a3b8" }}
        >
          채팅방
        </div>
        <div
          className="flex-1 flex items-center justify-center"
          style={{ fontSize: 14, fontWeight: 600, color: "#4f46e5", borderBottom: "2px solid #4f46e5" }}
        >
          캘린더
        </div>
      </div>

      {/* Content */}
      <div
        className="flex-1 flex flex-col"
        style={{ backgroundColor: "#f8fafc", padding: 20, gap: 20, overflowY: "auto" }}
      >
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 size={24} color="#4f46e5" className="animate-spin" />
          </div>
        ) : !proposal ? (
          <div
            style={{
              borderRadius: 16,
              backgroundColor: "#ffffff",
              border: "1px solid #e5e7eb",
              padding: 24,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 12,
            }}
          >
            <Calendar size={40} color="#c7d2fe" />
            <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>투표 데이터를 찾을 수 없습니다</span>
          </div>
        ) : (
          <>
            {/* Vote result card */}
            <div
              className="flex flex-col"
              style={{ borderRadius: 16, backgroundColor: "#fff", border: "1px solid #e5e7eb", padding: 20, gap: 16 }}
            >
              <div className="flex items-center" style={{ gap: 8 }}>
                <CircleCheck size={20} color="#22c55e" className="shrink-0" />
                <span style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>투표 결과</span>
              </div>
              <span style={{ fontSize: 13, fontWeight: 400, color: "#64748b", lineHeight: "18px" }}>
                {likeCount + otherCount >= total && total > 0
                  ? "모든 참여자가 투표를 완료했습니다"
                  : `${likeCount + otherCount}/${total}명이 투표에 참여했습니다`}
              </span>
              <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

              {/* Best slot */}
              <div
                className="flex flex-col"
                style={{ borderRadius: 12, backgroundColor: "#eef2ff", border: "1px solid #e0e7ff", padding: 16, gap: 8 }}
              >
                <div className="flex items-center" style={{ gap: 8 }}>
                  <Calendar size={16} color="#4f46e5" className="shrink-0" />
                  <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
                    {formatSlot(proposal.proposed_slot)}
                  </span>
                </div>
                <div className="flex items-center" style={{ gap: 8 }}>
                  <Users size={16} color="#4f46e5" className="shrink-0" />
                  <span style={{ fontSize: 13, fontWeight: 400, color: "#4f46e5" }}>
                    {likeCount}/{total}명 참여 가능
                  </span>
                </div>
                <div>
                  <span
                    style={{
                      display: "inline-block",
                      borderRadius: 999,
                      backgroundColor: "#4f46e5",
                      padding: "3px 10px",
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#fff",
                      lineHeight: "16px",
                    }}
                  >
                    최적 시간
                  </span>
                </div>
              </div>

              {/* Alternate slot */}
              {proposal.alternate_slot && (
                <div
                  className="flex flex-col"
                  style={{ borderRadius: 12, backgroundColor: "#f9fafb", border: "1px solid #e5e7eb", padding: 16, gap: 8 }}
                >
                  <div className="flex items-center" style={{ gap: 8 }}>
                    <Calendar size={16} color="#94a3b8" className="shrink-0" />
                    <span style={{ fontSize: 15, fontWeight: 500, color: "#374151" }}>
                      {formatSlot(proposal.alternate_slot)}
                    </span>
                  </div>
                  <div className="flex items-center" style={{ gap: 8 }}>
                    <Users size={16} color="#94a3b8" className="shrink-0" />
                    <span style={{ fontSize: 13, fontWeight: 400, color: "#94a3b8" }}>
                      {otherCount}/{total}명 선호
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Vote summary */}
            <div
              className="flex flex-col"
              style={{ borderRadius: 16, backgroundColor: "#fff", border: "1px solid #e5e7eb", padding: 20, gap: 12 }}
            >
              <span style={{ fontSize: 14, fontWeight: 700, color: "#1e293b" }}>투표 현황</span>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#22c55e", minWidth: 32 }}>찬성</span>
                <div
                  style={{ flex: 1, height: 8, borderRadius: 4, backgroundColor: "#e2e8f0", overflow: "hidden" }}
                >
                  <div
                    style={{
                      width: total > 0 ? `${(likeCount / total) * 100}%` : "0%",
                      height: "100%",
                      borderRadius: 4,
                      backgroundColor: "#22c55e",
                    }}
                  />
                </div>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#22c55e", minWidth: 32, textAlign: "right" }}>
                  {likeCount}/{total}
                </span>
              </div>
              {proposal.alternate_slot && (
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", minWidth: 32 }}>대안</span>
                  <div
                    style={{ flex: 1, height: 8, borderRadius: 4, backgroundColor: "#e2e8f0", overflow: "hidden" }}
                  >
                    <div
                      style={{
                        width: total > 0 ? `${(otherCount / total) * 100}%` : "0%",
                        height: "100%",
                        borderRadius: 4,
                        backgroundColor: "#94a3b8",
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", minWidth: 32, textAlign: "right" }}>
                    {otherCount}/{total}
                  </span>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Bottom area */}
      <div className="shrink-0" style={{ backgroundColor: "#fff", padding: 20, borderTop: "1px solid #e2e8f0" }}>
        <button
          className="flex items-center justify-center w-full cursor-pointer"
          onClick={() => router.push(`/m/chat/place?roomId=${roomId}`)}
          style={{ borderRadius: 12, backgroundColor: "#4f46e5", height: 48, gap: 8, border: "none" }}
        >
          <CalendarCheck size={18} color="#fff" />
          <span style={{ fontSize: 15, fontWeight: 600, color: "#fff" }}>이 시간으로 확정하기</span>
        </button>
      </div>

      {/* Home bar */}
      <div className="shrink-0 flex items-center justify-center" style={{ height: 20, backgroundColor: "#fff" }}>
        <div style={{ width: 134, height: 5, borderRadius: 999, backgroundColor: "#000000" }} />
      </div>
    </div>
  );
}

export default function ScheduleConfirmPage() {
  return (
    <Suspense fallback={null}>
      <ScheduleConfirmPageContent />
    </Suspense>
  );
}

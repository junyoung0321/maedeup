"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  Sparkles,
  Calendar,
  CheckCircle,
  Circle,
  Vote,
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

function ScheduleVotePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [room, setRoom] = useState<Room | null>(null);
  const [proposal, setProposal] = useState<ProposalPayload | null>(null);
  const [loadingProposal, setLoadingProposal] = useState(true);
  const [selectedVote, setSelectedVote] = useState<"like" | "other" | null>(null);
  const [voting, setVoting] = useState(false);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<Room>(`/api/v1/rooms/${roomId}`)
      .then(setRoom)
      .catch(() => null);
    apiFetch<ProposalPayload | null>(`/api/v1/finalization/room/${roomId}`)
      .then((p) => {
        setProposal(p);
        if (p?.my_vote) setSelectedVote(p.my_vote);
      })
      .catch(() => null)
      .finally(() => setLoadingProposal(false));
  }, [authLoading, user, roomId]);

  async function handleVote() {
    if (!proposal || !selectedVote || voting) return;
    setVoting(true);
    try {
      await apiFetch(`/api/v1/finalization/${proposal.proposal_id}/vote`, {
        method: "POST",
        body: JSON.stringify({ choice: selectedVote, room_id: Number(roomId) }),
      });
      router.push(`/m/schedule/confirm?roomId=${roomId}&proposalId=${proposal.proposal_id}`);
    } catch {
      setVoting(false);
    }
  }

  const roomName = room?.name ?? "모임";

  return (
    <div
      style={{
        width: 390,
        height: 844,
        overflow: "hidden",
        backgroundColor: "#ffffff",
        fontFamily: "Pretendard, sans-serif",
      }}
      className="flex flex-col mx-auto"
    >
      {/* 1. Header */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 56,
          backgroundColor: "#ffffff",
          padding: "0 16px",
          borderBottom: "1px solid #e2e8f0",
          gap: 12,
        }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push(`/m/chat/schedule?roomId=${roomId}`)} />
        <div className="flex-1 flex flex-col items-center" style={{ gap: 2 }}>
          <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b", textAlign: "center" }}>
            {roomName}
          </span>
          <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8", textAlign: "center" }}>
            {room?.category ?? "모임"}
          </span>
        </div>
        <Menu size={24} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/meeting/detail")} />
      </div>

      {/* 2. Tabs */}
      <div
        className="flex shrink-0"
        style={{ height: 44, backgroundColor: "#ffffff", borderBottom: "1px solid #e2e8f0" }}
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

      {/* 3. Content */}
      <div
        className="flex-1 flex flex-col overflow-y-auto"
        style={{ padding: "16px", gap: 16, backgroundColor: "#f8fafc" }}
      >
        {loadingProposal ? (
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
            <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>아직 일정 투표가 없습니다</span>
            <span style={{ fontSize: 13, color: "#94a3b8", textAlign: "center", lineHeight: 1.6 }}>
              채팅방에서 일정 조율을 시작하면{"\n"}AI가 자동으로 투표를 생성해드려요
            </span>
          </div>
        ) : (
          <>
            {/* AI Reason Card */}
            {proposal.reason && (
              <div
                style={{
                  borderRadius: 14,
                  background: "linear-gradient(-225deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
                  padding: "14px 16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  boxShadow: "0 4px 14px #4f46e520",
                }}
              >
                <div className="flex items-center" style={{ gap: 6 }}>
                  <Sparkles size={14} color="#ffffff" />
                  <span style={{ fontSize: 11, fontWeight: 600, color: "#ffffff" }}>AI 분석</span>
                </div>
                <span style={{ fontSize: 12, fontWeight: 400, color: "#ffffffcc", lineHeight: 1.6 }}>
                  {proposal.reason}
                </span>
              </div>
            )}

            {/* Vote status */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>일정 투표</span>
              <span style={{ fontSize: 12, color: "#94a3b8" }}>
                {proposal.like_count + proposal.other_count}/{proposal.total_eligible_voters}명 참여
              </span>
            </div>

            {/* Proposed slot — like */}
            <div
              onClick={() => setSelectedVote("like")}
              style={{
                borderRadius: 12,
                backgroundColor: selectedVote === "like" ? "#eef2ff" : "#ffffff",
                border: selectedVote === "like" ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
                padding: "14px 16px",
                display: "flex",
                alignItems: "center",
                gap: 12,
                cursor: "pointer",
              }}
            >
              {selectedVote === "like" ? (
                <CheckCircle size={20} color="#4f46e5" className="shrink-0" />
              ) : (
                <Circle size={20} color="#cbd5e1" className="shrink-0" />
              )}
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                  {formatSlot(proposal.proposed_slot)}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: "#4f46e5",
                      backgroundColor: "#eef2ff",
                      borderRadius: 999,
                      padding: "2px 8px",
                    }}
                  >
                    주요 제안
                  </span>
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>찬성 {proposal.like_count}명</span>
                </div>
              </div>
            </div>

            {/* Alternate slot — other */}
            {proposal.alternate_slot && (
              <div
                onClick={() => setSelectedVote("other")}
                style={{
                  borderRadius: 12,
                  backgroundColor: selectedVote === "other" ? "#eef2ff" : "#ffffff",
                  border: selectedVote === "other" ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
                  padding: "14px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  cursor: "pointer",
                }}
              >
                {selectedVote === "other" ? (
                  <CheckCircle size={20} color="#4f46e5" className="shrink-0" />
                ) : (
                  <Circle size={20} color="#cbd5e1" className="shrink-0" />
                )}
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                    {formatSlot(proposal.alternate_slot)}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: "#64748b",
                        backgroundColor: "#f1f5f9",
                        borderRadius: 999,
                        padding: "2px 8px",
                      }}
                    >
                      대안
                    </span>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>다른 시간 {proposal.other_count}명</span>
                  </div>
                </div>
              </div>
            )}

            {proposal.my_vote && (
              <span style={{ fontSize: 12, color: "#4f46e5", fontWeight: 500 }}>
                이미 투표하셨습니다. 변경할 수 있습니다.
              </span>
            )}
          </>
        )}
      </div>

      {/* 4. Button area */}
      {proposal && (
        <div
          className="shrink-0 flex items-center justify-center"
          style={{ backgroundColor: "#ffffff", padding: "12px 20px", borderTop: "1px solid #e2e8f0" }}
        >
          <button
            className="flex items-center justify-center w-full"
            onClick={handleVote}
            disabled={!selectedVote || voting}
            style={{
              height: 44,
              borderRadius: 12,
              backgroundColor: selectedVote && !voting ? "#4f46e5" : "#c7d2fe",
              gap: 8,
              border: "none",
              cursor: selectedVote && !voting ? "pointer" : "not-allowed",
            }}
          >
            {voting ? (
              <Loader2 size={18} color="#ffffff" className="animate-spin" />
            ) : (
              <Vote size={18} color="#ffffff" />
            )}
            <span style={{ fontSize: 14, fontWeight: 600, color: "#ffffff" }}>
              {voting ? "제출 중..." : "투표 제출"}
            </span>
          </button>
        </div>
      )}

      {/* 5. Home bar */}
      <div className="shrink-0 flex items-center justify-center" style={{ height: 20 }}>
        <div style={{ width: 134, height: 5, borderRadius: 100, backgroundColor: "#000000" }} />
      </div>
    </div>
  );
}

export default function ScheduleVotePage() {
  return (
    <Suspense fallback={null}>
      <ScheduleVotePageContent />
    </Suspense>
  );
}

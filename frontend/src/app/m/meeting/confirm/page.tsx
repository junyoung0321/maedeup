"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  ClipboardCheck,
  FileText,
  Calendar,
  MapPin,
  Users,
  TriangleAlert,
  CircleCheck,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Room, NearbyPlace } from "@/types";

interface ProposalPayload {
  proposal_id: string;
  proposed_slot: { start_time: string; end_time: string; [key: string]: unknown };
  reason?: string;
  total_eligible_voters: number;
  like_count: number;
}

interface MemberInfo {
  user_id: number;
  user_name: string;
}

interface PreferenceStatusResponse {
  total_members: number;
  submitted_count: number;
  all_submitted: boolean;
  preferences: MemberInfo[];
}

const AVATAR_COLORS = ["#818cf8", "#f472b6", "#fb923c", "#34d399", "#60a5fa", "#a78bfa"];

function avatarColor(id: number) {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}

function formatSlot(slot: { start_time: string; end_time: string }) {
  const start = new Date(slot.start_time);
  const end = new Date(slot.end_time);
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  const month = start.getMonth() + 1;
  const day = start.getDate();
  const dow = days[start.getDay()];
  const fmt = (h: number, m: number) => {
    const period = h < 12 ? "오전" : "오후";
    const hh = h % 12 || 12;
    return `${period} ${hh}:${String(m).padStart(2, "0")}`;
  };
  return `${month}월 ${day}일 (${dow}) ${fmt(start.getHours(), start.getMinutes())} ~ ${fmt(end.getHours(), end.getMinutes()).split(" ")[1]}`;
}

function MeetingConfirmPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [room, setRoom] = useState<Room | null>(null);
  const [proposal, setProposal] = useState<ProposalPayload | null>(null);
  const [place, setPlace] = useState<NearbyPlace | null>(null);
  const [members, setMembers] = useState<MemberInfo[]>([]);
  const [totalMembers, setTotalMembers] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("selectedPlace");
      if (raw) setPlace(JSON.parse(raw) as NearbyPlace);
    } catch {}
  }, []);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    Promise.all([
      apiFetch<Room>(`/api/v1/rooms/${roomId}`).catch(() => null),
      apiFetch<ProposalPayload>(`/api/v1/finalization/room/${roomId}`).catch(() => null),
      apiFetch<PreferenceStatusResponse>(`/api/v1/rooms/${roomId}/preferences`).catch(() => null),
    ]).then(([roomData, proposalData, prefData]) => {
      if (roomData) setRoom(roomData);
      if (proposalData) setProposal(proposalData);
      if (prefData) {
        setMembers(prefData.preferences ?? []);
        setTotalMembers(prefData.total_members ?? 0);
      }
    }).finally(() => setLoading(false));
  }, [authLoading, user, roomId]);

  async function handleConfirm() {
    if (!room || !proposal) return;
    setSubmitting(true);
    try {
      const body: Record<string, unknown> = {
        room_id: Number(roomId),
        title: room.name,
        scheduled_at: proposal.proposed_slot.start_time,
        end_at: proposal.proposed_slot.end_time,
        proposal_id: proposal.proposal_id,
      };
      if (place?.name) body.location_name = place.name;
      const result = await apiFetch<{ id: number }>("/api/v1/meetings/confirm", {
        method: "POST",
        body: JSON.stringify(body),
      });
      router.push(`/m/meeting/done?meetingId=${result.id}`);
    } catch {
      alert("모임 생성에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  const roomName = room?.name ?? "모임";
  const memberCount = totalMembers > 0 ? totalMembers : members.length;

  return (
    <div
      className="flex flex-col bg-white"
      style={{ width: "100%", height: "var(--m-screen-h)", fontFamily: "Pretendard, sans-serif" }}
    >
      {/* Header */}
      <div
        className="flex items-center shrink-0"
        style={{ height: 56, padding: "0 16px", borderBottom: "1px solid #e2e8f0", backgroundColor: "#fff" }}
      >
        <ArrowLeft
          size={24}
          color="#1e293b"
          className="shrink-0 cursor-pointer"
          onClick={() => router.push(`/m/place?roomId=${roomId}`)}
        />
        <div className="flex flex-col items-center flex-1" style={{ gap: 2 }}>
          <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b" }}>{roomName}</span>
          <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>
            {memberCount > 0 ? `${memberCount}명 참여 중` : "모임"}
          </span>
        </div>
        <Menu
          size={24}
          color="#64748b"
          className="shrink-0 cursor-pointer"
          onClick={() => router.push(`/m/meeting/detail?roomId=${roomId}`)}
        />
      </div>

      {/* Tabs */}
      <div className="flex shrink-0" style={{ height: 44, backgroundColor: "#fff", borderBottom: "1px solid #e2e8f0" }}>
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          style={{ fontSize: 14, fontWeight: 500, color: "#94a3b8" }}
          onClick={() => router.push(`/m/chat/place?roomId=${roomId}`)}
        >
          채팅방
        </div>
        <div
          className="flex-1 flex items-center justify-center"
          style={{ fontSize: 14, fontWeight: 600, color: "#4f46e5", borderBottom: "2px solid #4f46e5" }}
        >
          장소 선택
        </div>
      </div>

      {/* Content */}
      <div
        className="flex-1 flex flex-col overflow-y-auto"
        style={{ backgroundColor: "#f8fafc", padding: 20, gap: 20 }}
      >
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", paddingTop: 60 }}>
            <Loader2 size={24} color="#4f46e5" className="animate-spin" />
          </div>
        ) : (
          <>
            {/* Summary Card */}
            <div
              className="flex flex-col"
              style={{ borderRadius: 16, backgroundColor: "#fff", border: "1px solid #e5e7eb", padding: 20, gap: 16 }}
            >
              <div className="flex items-center" style={{ gap: 8 }}>
                <ClipboardCheck size={20} color="#4f46e5" />
                <span style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>모임 최종 확인</span>
              </div>
              <span style={{ fontSize: 13, fontWeight: 400, color: "#64748b" }}>아래 내용으로 모임을 생성합니다</span>
              <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

              <div className="flex items-center" style={{ gap: 10 }}>
                <FileText size={16} color="#94a3b8" className="shrink-0" />
                <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>모임명</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>{roomName}</span>
              </div>

              {/* Schedule box */}
              <div
                className="flex flex-col"
                style={{ borderRadius: 12, backgroundColor: "#eef2ff", border: "1px solid #e0e7ff", padding: 14, gap: 6 }}
              >
                <div className="flex items-center" style={{ gap: 8 }}>
                  <Calendar size={16} color="#4f46e5" />
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>확정된 일정</span>
                </div>
                <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
                  {proposal
                    ? formatSlot(proposal.proposed_slot as { start_time: string; end_time: string })
                    : "일정 정보 없음"}
                </span>
                {proposal && (
                  <span style={{ fontSize: 12, fontWeight: 400, color: "#4f46e5" }}>
                    {proposal.like_count}/{proposal.total_eligible_voters}명 참여 가능
                  </span>
                )}
              </div>

              {/* Place box */}
              <div
                className="flex flex-col"
                style={{ borderRadius: 12, backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0", padding: 14, gap: 6 }}
              >
                <div className="flex items-center" style={{ gap: 8 }}>
                  <MapPin size={16} color="#16a34a" />
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#16a34a" }}>확정된 장소</span>
                </div>
                <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
                  {place?.name ?? "장소 미정"}
                </span>
                {place?.address && (
                  <span style={{ fontSize: 12, fontWeight: 400, color: "#64748b" }}>{place.address}</span>
                )}
              </div>

              <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

              {members.length > 0 && (
                <>
                  <div className="flex items-center" style={{ gap: 8 }}>
                    <Users size={16} color="#94a3b8" />
                    <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}>참여자 ({memberCount}명)</span>
                  </div>
                  <div className="flex flex-wrap" style={{ gap: 8 }}>
                    {members.map((m) => (
                      <div key={m.user_id} className="flex flex-col items-center" style={{ gap: 4 }}>
                        <div
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: "50%",
                            backgroundColor: avatarColor(m.user_id),
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <span style={{ fontSize: 14, fontWeight: 600, color: "#fff" }}>
                            {m.user_name.charAt(0)}
                          </span>
                        </div>
                        <span style={{ fontSize: 10, fontWeight: 400, color: "#374151" }}>{m.user_name}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Warning card */}
            <div
              className="flex"
              style={{ borderRadius: 12, backgroundColor: "#fffbeb", border: "1px solid #fde68a", padding: 14, gap: 8 }}
            >
              <TriangleAlert size={16} color="#d97706" className="shrink-0" style={{ marginTop: 2 }} />
              <span style={{ fontSize: 12, fontWeight: 400, color: "#92400e", lineHeight: 1.5 }}>
                모임 생성 후에는 일정과 장소를 변경할 수 없습니다.{"\n"}신중하게 확인해주세요.
              </span>
            </div>
          </>
        )}
      </div>

      {/* Button area */}
      <div
        className="flex flex-col shrink-0"
        style={{ backgroundColor: "#fff", padding: 20, gap: 10, borderTop: "1px solid #e2e8f0" }}
      >
        <button
          className="flex items-center justify-center"
          onClick={handleConfirm}
          disabled={submitting || loading || !proposal}
          style={{
            borderRadius: 12,
            backgroundColor: submitting || loading || !proposal ? "#c7d2fe" : "#4f46e5",
            height: 48,
            gap: 8,
            border: "none",
            cursor: submitting || loading || !proposal ? "not-allowed" : "pointer",
          }}
        >
          {submitting
            ? <Loader2 size={18} color="#fff" className="animate-spin" />
            : <CircleCheck size={18} color="#fff" />}
          <span style={{ fontSize: 15, fontWeight: 600, color: "#fff" }}>
            {submitting ? "생성 중..." : "모임 생성하기"}
          </span>
        </button>
        <button
          className="flex items-center justify-center cursor-pointer"
          onClick={() => router.push(`/m/place?roomId=${roomId}`)}
          style={{ borderRadius: 12, backgroundColor: "#fff", border: "1px solid #e2e8f0", height: 40 }}
        >
          <span style={{ fontSize: 14, fontWeight: 500, color: "#64748b" }}>돌아가기</span>
        </button>
      </div>

      {/* Home bar */}
      <div className="flex items-center justify-center shrink-0" style={{ height: 20, backgroundColor: "#fff" }}>
        <div style={{ width: 134, height: 5, borderRadius: 100, backgroundColor: "#000000" }} />
      </div>
    </div>
  );
}

export default function MeetingConfirmPage() {
  return (
    <Suspense fallback={null}>
      <MeetingConfirmPageContent />
    </Suspense>
  );
}

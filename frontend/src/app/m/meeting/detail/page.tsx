"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  EllipsisVertical,
  CalendarDays,
  MapPin,
  Users,
  MessageCircle,
  LogOut,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Room } from "@/types";

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

const AVATAR_COLORS = ["#4f46e5", "#f59e0b", "#10b981", "#ec4899", "#6366f1", "#818cf8", "#f472b6", "#34d399"];

function avatarColor(id: number) {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}

function MeetingDetailPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [room, setRoom] = useState<Room | null>(null);
  const [members, setMembers] = useState<MemberInfo[]>([]);
  const [totalMembers, setTotalMembers] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    Promise.all([
      apiFetch<Room>(`/api/v1/rooms/${roomId}`).catch(() => null),
      apiFetch<PreferenceStatusResponse>(`/api/v1/rooms/${roomId}/preferences`).catch(() => null),
    ]).then(([roomData, prefData]) => {
      if (roomData) setRoom(roomData);
      if (prefData) {
        setMembers(prefData.preferences ?? []);
        setTotalMembers(prefData.total_members ?? 0);
      }
    }).finally(() => setLoading(false));
  }, [authLoading, user, roomId]);

  const roomName = room?.name ?? "모임";

  return (
    <div
      style={{
        width: "100%",
        height: "844px",
        background: "#ffffff",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 56,
          minHeight: 56,
          background: "#ffffff",
          padding: "0 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "0.5px solid #e2e8f0",
        }}
      >
        <ArrowLeft
          size={24}
          color="#1e293b"
          style={{ cursor: "pointer" }}
          onClick={() => router.back()}
        />
        <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b" }}>{roomName}</span>
        <EllipsisVertical size={24} color="#64748b" style={{ cursor: "pointer" }} onClick={() => alert("모임 설정 기능은 준비 중입니다")} />
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          background: "#f8fafc",
          padding: 20,
          gap: 20,
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", paddingTop: 60 }}>
            <Loader2 size={24} color="#4f46e5" className="animate-spin" />
          </div>
        ) : (
          <>
            {/* Cover */}
            <div
              style={{
                width: "100%",
                height: 180,
                borderRadius: 16,
                background: "linear-gradient(135deg, #e0e7ff, #c7d2fe)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                overflow: "hidden",
              }}
            >
              <span style={{ fontSize: 48 }}>📋</span>
            </div>

            {/* Info Card */}
            <div
              style={{
                borderRadius: 16,
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                padding: 20,
                display: "flex",
                flexDirection: "column",
                gap: 16,
              }}
            >
              <span style={{ fontSize: 20, fontWeight: 700, color: "#1e293b" }}>{roomName}</span>
              {room?.description && (
                <span style={{ fontSize: 14, color: "#64748b" }}>{room.description}</span>
              )}
              <div style={{ height: 1, background: "#e2e8f0" }} />
              {room?.category && (
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <CalendarDays size={20} color="#4f46e5" />
                  <span style={{ fontSize: 14, color: "#1e293b" }}>{room.category}</span>
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <MapPin size={20} color="#4f46e5" />
                <span style={{ fontSize: 14, color: "#94a3b8" }}>장소 미정</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <Users size={20} color="#4f46e5" />
                <span style={{ fontSize: 14, color: "#1e293b" }}>참여 멤버 {totalMembers > 0 ? totalMembers : members.length}명</span>
              </div>
            </div>

            {/* Members Card */}
            {members.length > 0 && (
              <div
                style={{
                  borderRadius: 16,
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 16, fontWeight: 600, color: "#1e293b" }}>참여 멤버</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#4f46e5" }}>
                    {totalMembers > 0 ? totalMembers : members.length}명
                  </span>
                </div>

                {members.map((m) => (
                  <div key={m.user_id} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: "50%",
                        background: avatarColor(m.user_id),
                        flexShrink: 0,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <span style={{ fontSize: 14, fontWeight: 600, color: "#ffffff" }}>
                        {m.user_name.charAt(0)}
                      </span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                      <span style={{ fontSize: 14, fontWeight: m.user_id === room?.created_by ? 600 : 500, color: "#1e293b" }}>
                        {m.user_name}{m.user_id === room?.created_by ? " (방장)" : ""}
                      </span>
                      <span style={{ fontSize: 12, color: m.user_id === room?.created_by ? "#4f46e5" : "#94a3b8" }}>
                        {m.user_id === room?.created_by ? "모임장" : "멤버"}
                      </span>
                    </div>
                  </div>
                ))}

                {totalMembers > members.length && (
                  <span style={{ fontSize: 12, color: "#94a3b8" }}>
                    + {totalMembers - members.length}명 더 (선호도 미입력)
                  </span>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom Bar */}
      <div
        style={{
          background: "#ffffff",
          padding: "16px 20px 34px",
          display: "flex",
          gap: 12,
          borderTop: "0.5px solid #e2e8f0",
        }}
      >
        <button
          onClick={() => router.push(`/m/chat/schedule?roomId=${roomId}`)}
          style={{
            flex: 1,
            height: 48,
            borderRadius: 12,
            border: "none",
            background: "#4f46e5",
            color: "#ffffff",
            fontSize: 15,
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            fontFamily: "Pretendard, sans-serif",
          }}
        >
          <MessageCircle size={20} color="#ffffff" />
          채팅방 입장
        </button>
        <button
          onClick={async () => {
            if (!confirm("모임에서 나가시겠습니까?")) return;
            try { await apiFetch(`/api/v1/rooms/${roomId}/leave`, { method: "POST" }); } catch { /* ignore */ }
            router.push("/m/explore");
          }}
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            background: "#ffffff",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <LogOut size={20} color="#ef4444" />
        </button>
      </div>
    </div>
  );
}

export default function MeetingDetailPage() {
  return (
    <Suspense fallback={null}>
      <MeetingDetailPageContent />
    </Suspense>
  );
}

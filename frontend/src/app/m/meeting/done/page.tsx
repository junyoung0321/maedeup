"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bell, User, Users, Calendar, MapPin, Share2, House, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

interface MeetingMember {
  id: number;
  name: string;
  picture?: string | null;
  is_guest?: boolean;
}

interface MeetingDetailResponse {
  id: number;
  room_id: number;
  room_name: string;
  title: string;
  scheduled_at: string;
  end_at?: string | null;
  location_name?: string | null;
  location_address?: string | null;
  members: MeetingMember[];
}

const AVATAR_COLORS = ["#c7d2fe", "#93c5fd", "#86efac", "#fca5a5", "#fde68a", "#818cf8", "#f472b6"];

function formatDatetime(iso: string) {
  const d = new Date(iso);
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const dow = days[d.getDay()];
  const h = d.getHours();
  const m = d.getMinutes();
  const period = h < 12 ? "오전" : "오후";
  const hh = h % 12 || 12;
  return `${month}월 ${day}일 (${dow}) ${period} ${hh}:${String(m).padStart(2, "0")}`;
}

function MeetingDonePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const meetingId = searchParams.get("meetingId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [meeting, setMeeting] = useState<MeetingDetailResponse | null>(null);
  const [loading, setLoading] = useState(!!meetingId);

  useEffect(() => {
    if (!meetingId || authLoading || !user) return;
    apiFetch<MeetingDetailResponse>(`/api/v1/meetings/${meetingId}`)
      .then(setMeeting)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [meetingId, authLoading, user]);

  const title = meeting?.title ?? meeting?.room_name ?? "모임";
  const locationDisplay = meeting?.location_name ?? "장소 미정";
  const members = meeting?.members ?? [];

  return (
    <div
      className="relative flex flex-col"
      style={{ width: 390, height: 844, overflow: "hidden", backgroundColor: "#ffffff" }}
    >
      {/* Header */}
      <div className="relative shrink-0" style={{ height: 56, backgroundColor: "#4f46e5" }}>
        <span
          className="absolute"
          style={{ left: 16, top: 16, fontFamily: "Pretendard, sans-serif", fontSize: 20, fontWeight: 700, color: "#ffffff", lineHeight: "24px" }}
        >
          매듭
        </span>
        <Bell
          className="absolute cursor-pointer"
          style={{ left: 314, top: 18, width: 22, height: 22 }}
          color="#ffffff"
          strokeWidth={2}
          onClick={() => router.push("/m/notifications")}
        />
        <User
          className="absolute cursor-pointer"
          style={{ left: 350, top: 18, width: 22, height: 22 }}
          color="#ffffff"
          strokeWidth={2}
          onClick={() => router.push("/m/profile")}
        />
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col justify-center items-center" style={{ padding: "0 20px", gap: 24 }}>
        {loading ? (
          <Loader2 size={32} color="#4f46e5" className="animate-spin" />
        ) : (
          <>
            {/* Title area */}
            <div className="flex flex-col items-center w-full" style={{ gap: 8 }}>
              <p
                className="w-full text-center whitespace-pre-line"
                style={{ fontFamily: "Pretendard, sans-serif", fontSize: 22, fontWeight: 700, color: "#0f172a", lineHeight: "32px", margin: 0 }}
              >
                {"모임이 성공적으로\n생성되었어요!"}
              </p>
              <p
                className="text-center"
                style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 400, color: "#64748b", margin: 0 }}
              >
                참여자들에게 초대 알림이 전송되었습니다
              </p>
            </div>

            {/* Summary card */}
            <div
              className="flex flex-col w-full"
              style={{ borderRadius: 16, backgroundColor: "#f8faff", border: "1px solid #e2e8f0", padding: 20, gap: 16 }}
            >
              <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 16, fontWeight: 700, color: "#1e293b" }}>
                모임 정보
              </span>
              <div style={{ height: 1, backgroundColor: "#e2e8f0" }} />

              {/* 모임명 */}
              <div className="flex items-center" style={{ gap: 10 }}>
                <Users style={{ width: 18, height: 18, flexShrink: 0 }} color="#4f46e5" strokeWidth={2} />
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 600, color: "#64748b", flexShrink: 0 }}>모임명</span>
                <span className="ml-auto" style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                  {title}
                </span>
              </div>

              {/* 일시 */}
              <div className="flex items-center" style={{ gap: 10 }}>
                <Calendar style={{ width: 18, height: 18, flexShrink: 0 }} color="#4f46e5" strokeWidth={2} />
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 600, color: "#64748b", flexShrink: 0 }}>일시</span>
                <span className="ml-auto" style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                  {meeting?.scheduled_at ? formatDatetime(meeting.scheduled_at) : "미정"}
                </span>
              </div>

              {/* 장소 */}
              <div className="flex items-center" style={{ gap: 10 }}>
                <MapPin style={{ width: 18, height: 18, flexShrink: 0 }} color="#4f46e5" strokeWidth={2} />
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 600, color: "#64748b", flexShrink: 0 }}>장소</span>
                <span className="ml-auto" style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                  {locationDisplay}
                </span>
              </div>

              {/* 참여자 */}
              <div className="flex items-center" style={{ gap: 10 }}>
                <User style={{ width: 18, height: 18, flexShrink: 0 }} color="#4f46e5" strokeWidth={2} />
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 600, color: "#64748b", flexShrink: 0 }}>참여자</span>
                <div className="flex ml-auto" style={{ paddingLeft: 6 }}>
                  {(members.length > 0 ? members : Array(5).fill(null)).slice(0, 7).map((m, i) => (
                    <div
                      key={m?.id ?? i}
                      className="rounded-full border-2 border-white"
                      style={{
                        width: 22,
                        height: 22,
                        backgroundColor: AVATAR_COLORS[i % AVATAR_COLORS.length],
                        marginLeft: i === 0 ? 0 : -6,
                        zIndex: 7 - i,
                        flexShrink: 0,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {m?.name && (
                        <span style={{ fontSize: 8, fontWeight: 600, color: "#1e293b" }}>
                          {m.name.charAt(0)}
                        </span>
                      )}
                    </div>
                  ))}
                  {members.length > 7 && (
                    <span style={{ fontSize: 11, color: "#64748b", marginLeft: 6, alignSelf: "center" }}>
                      +{members.length - 7}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Buttons */}
            <div className="flex flex-col w-full" style={{ gap: 12 }}>
              <button
                className="flex items-center justify-center w-full"
                onClick={() => {
                  const roomId = meeting?.room_id;
                  const link = roomId
                    ? `${window.location.origin}/m/chat/schedule?roomId=${roomId}`
                    : window.location.href;
                  navigator.clipboard?.writeText(link).catch(() => {});
                  alert("모임 링크가 복사되었습니다!");
                }}
                style={{ borderRadius: 12, backgroundColor: "#4f46e5", height: 48, gap: 8, border: "none", cursor: "pointer" }}
              >
                <Share2 style={{ width: 18, height: 18 }} color="#ffffff" strokeWidth={2} />
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 15, fontWeight: 600, color: "#ffffff" }}>
                  모임 공유하기
                </span>
              </button>
              <button
                className="flex items-center justify-center w-full"
                onClick={() => router.push("/m/explore")}
                style={{ borderRadius: 12, backgroundColor: "#ffffff", border: "1.5px solid #e2e8f0", height: 48, gap: 8, cursor: "pointer" }}
              >
                <House style={{ width: 18, height: 18 }} color="#4f46e5" strokeWidth={2} />
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 15, fontWeight: 600, color: "#4f46e5" }}>
                  모임 목록으로
                </span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function MeetingDonePage() {
  return (
    <Suspense fallback={null}>
      <MeetingDonePageContent />
    </Suspense>
  );
}

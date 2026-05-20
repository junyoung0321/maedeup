"use client";

import { useEffect, useState } from "react";
import { Check, Share2, List, Calendar, MapPin, Users } from "lucide-react";
import Avatar from "@/components/ui/Avatar";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useMeeting } from "@/contexts/MeetingContext";

interface MemberInfo {
  id: number;
  name: string;
  picture: string | null;
  is_guest: boolean;
}

interface MeetingDetail {
  id: number;
  room_id: number;
  room_name: string;
  title: string;
  scheduled_at: string;
  end_at: string | null;
  location_name: string | null;
  location_address: string | null;
  status: string;
  members: MemberInfo[];
}

const AVATAR_PALETTE = ["#818cf8", "#f472b6", "#34d399", "#fbbf24", "#60a5fa", "#fb7185", "#a78bfa", "#facc15"];

function colorForUserId(id: number): string {
  return AVATAR_PALETTE[id % AVATAR_PALETTE.length];
}

function formatMeetingDate(iso: string): string {
  // Fix (2026-05-18 hotfix): 백엔드는 naive UTC를 'Z' 없이 ISO로 직렬화 →
  //   new Date("2026-05-25T10:00:00")는 브라우저 local time으로 해석돼 KST 가정.
  //   결과: UTC 10:00가 "오전 10:00"으로 표시 (실제 KST 19:00 = "오후 7:00").
  //   timezone 마커가 없으면 'Z'(UTC) 명시해 강제로 UTC로 파싱.
  const hasTz = /[+-]\d{2}:?\d{2}$|Z$/.test(iso);
  const date = new Date(hasTz ? iso : iso + "Z");
  const y = date.getFullYear();
  const m = date.getMonth() + 1;
  const d = date.getDate();
  const dayNames = ["일", "월", "화", "수", "목", "금", "토"];
  const hours = date.getHours();
  const ampm = hours < 12 ? "오전" : "오후";
  const h = hours % 12 || 12;
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${y}년 ${m}월 ${d}일 (${dayNames[date.getDay()]}) ${ampm} ${h}:${min}`;
}

export default function CompletionPage() {
  const router = useRouter();
  const { confirmedMeetingId } = useMeeting();
  const [data, setData] = useState<MeetingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!confirmedMeetingId) {
      setLoading(false);
      setError("모임 정보를 불러올 수 없습니다");
      return;
    }
    setLoading(true);
    apiFetch<MeetingDetail>(`/api/v1/meetings/${confirmedMeetingId}`)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "모임 정보를 불러올 수 없습니다");
      })
      .finally(() => setLoading(false));
  }, [confirmedMeetingId]);

  const visibleMembers = (data?.members ?? []).slice(0, 2);
  const extraCount = Math.max(0, (data?.members.length ?? 0) - visibleMembers.length);

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center gap-8 py-12 relative"
      style={{ fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
    >
      {/* Confetti 장식 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute w-2 h-2 rounded-full bg-primary-600/10 top-[200px] left-[200px]" />
        <div className="absolute w-3 h-3 rounded-full bg-primary-400/15 top-[250px] right-[200px]" />
        <div className="absolute w-4 h-1.5 rounded bg-primary-100/25 top-[300px] left-[350px]" />
        <div className="absolute w-3.5 h-1 rounded bg-primary-100/20 top-[350px] right-[300px]" />
        <div className="absolute w-1.5 h-1.5 rounded-full bg-primary-600/10 bottom-[200px] left-[500px]" />
        <div className="absolute w-2.5 h-2.5 rounded-full bg-primary-400/10 bottom-[220px] right-[400px]" />
      </div>

      {/* 성공 아이콘 */}
      <div
        className="w-24 h-24 rounded-full flex items-center justify-center"
        style={{ background: "linear-gradient(135deg, #4f46e5, #818cf8)" }}
      >
        <Check className="w-12 h-12 text-white" strokeWidth={3} />
      </div>

      <div className="text-center">
        <h2
          className="text-[28px]"
          style={{ fontWeight: 300, color: "#0f172a", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
        >
          모임이 성공적으로 생성되었어요!
        </h2>
        <p
          className="text-[16px] mt-2"
          style={{ fontWeight: 300, color: "#64748b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
        >
          참여자들에게 초대 알림이 전송되었습니다
        </p>
      </div>

      {/* 요약 카드 */}
      <div
        className="w-[480px]"
        style={{
          background: "#f8faff",
          borderRadius: 16,
          border: "1px solid #e2e8f0",
          padding: 28,
        }}
      >
        <h3
          className="text-[18px] mb-5"
          style={{ fontWeight: 300, color: "#1e293b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
        >
          모임 정보
        </h3>

        {loading ? (
          <div className="text-[14px]" style={{ color: "#94a3b8" }}>불러오는 중…</div>
        ) : error || !data ? (
          <div className="text-[14px]" style={{ color: "#ef4444" }}>{error ?? "모임 정보를 불러올 수 없습니다"}</div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* 모임명 */}
            <div className="flex items-center gap-3">
              <Calendar className="w-5 h-5 shrink-0" style={{ color: "#64748b" }} />
              <div className="flex items-baseline gap-3">
                <span
                  className="text-[14px]"
                  style={{ fontWeight: 300, color: "#64748b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
                >
                  모임명
                </span>
                <span
                  className="text-[14px]"
                  style={{ fontWeight: 300, color: "#1e293b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
                >
                  {data.room_name || data.title}
                </span>
              </div>
            </div>

            {/* 일시 */}
            <div className="flex items-center gap-3">
              <Calendar className="w-5 h-5 shrink-0" style={{ color: "#64748b" }} />
              <div className="flex items-baseline gap-3">
                <span
                  className="text-[14px]"
                  style={{ fontWeight: 300, color: "#64748b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
                >
                  일시
                </span>
                <span
                  className="text-[14px]"
                  style={{ fontWeight: 300, color: "#1e293b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
                >
                  {formatMeetingDate(data.scheduled_at)}
                </span>
              </div>
            </div>

            {/* 장소 */}
            <div className="flex items-center gap-3">
              <MapPin className="w-5 h-5 shrink-0" style={{ color: "#64748b" }} />
              <div className="flex items-baseline gap-3">
                <span
                  className="text-[14px]"
                  style={{ fontWeight: 300, color: "#64748b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
                >
                  장소
                </span>
                <span
                  className="text-[14px]"
                  style={{ fontWeight: 300, color: "#1e293b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
                >
                  {data.location_name ?? "장소 미정"}
                </span>
              </div>
            </div>

            {/* 참여자 */}
            <div className="flex items-center gap-3">
              <Users className="w-5 h-5 shrink-0" style={{ color: "#64748b" }} />
              <div className="flex items-center gap-3">
                <span
                  className="text-[14px]"
                  style={{ fontWeight: 300, color: "#64748b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
                >
                  참여자
                </span>
                <div className="flex items-center">
                  <div className="flex -space-x-2">
                    {visibleMembers.map((m) => (
                      <Avatar key={m.id} name={m.name} color={colorForUserId(m.id)} size="sm" />
                    ))}
                  </div>
                  {extraCount > 0 && (
                    <span
                      className="text-[11px] ml-1"
                      style={{ fontWeight: 300, color: "#64748b", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
                    >
                      +{extraCount}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 버튼 행 */}
      <div className="flex gap-4">
        <button
          className="flex items-center justify-center rounded-xl transition-colors hover:opacity-90"
          style={{
            fontSize: 15,
            fontWeight: 300,
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            color: "#ffffff",
            backgroundColor: "#4f46e5",
            padding: "12px 24px",
          }}
        >
          <Share2 className="w-4 h-4 mr-2 inline" />
          모임 공유하기
        </button>
        <button
          className="flex items-center justify-center rounded-xl transition-colors hover:opacity-90"
          style={{
            fontSize: 15,
            fontWeight: 300,
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            color: "#4f46e5",
            backgroundColor: "#ffffff",
            border: "1px solid #4f46e5",
            padding: "12px 24px",
          }}
          onClick={() => router.push("/")}
        >
          <List className="w-4 h-4 mr-2 inline" />
          모임 목록으로
        </button>
      </div>
    </div>
  );
}

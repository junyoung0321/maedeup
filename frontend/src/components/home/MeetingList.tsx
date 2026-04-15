"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { Room, MeetingItem } from "@/types";

const CATEGORY_MAP: Record<string, { badge: string; badgeColor: string }> = {
  study:  { badge: "스터디",  badgeColor: "#4f46e5" },
  dining: { badge: "식사",    badgeColor: "#059669" },
  sports: { badge: "스포츠",  badgeColor: "#ea580c" },
  hobby:  { badge: "취미",    badgeColor: "#7c3aed" },
};

function mapRoom(room: Room): MeetingItem {
  const cat = room.category ? CATEGORY_MAP[room.category] : null;
  return {
    id: String(room.id),
    name: room.name,
    schedule: room.description ?? "일정 조율중",
    badge: cat?.badge ?? "진행중",
    badgeColor: cat?.badgeColor ?? "#4f46e5",
  };
}

export default function MeetingList() {
  const router = useRouter();
  const [meetings, setMeetings] = useState<MeetingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiFetch<Room[]>("/api/v1/rooms/")
      .then((data) => {
        setMeetings(data.map(mapRoom));
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  return (
    <div className="bg-white rounded-[20px] p-5 flex flex-col border border-[#e2e8f0] shadow-[0_4px_2.7px_rgba(0,0,0,0.25)]" style={{ height: 620 }}>
      {/* Header */}
      <h3 className="text-[27px] font-medium text-black">참여중인 모임</h3>
      <p className="text-[18px] font-medium text-[#9f9f9f] mt-1 mb-5">
        내가 참여중인 모임들을 한눈에 볼 수 있어요
      </p>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#94a3b8] text-sm">
          불러오는 중...
        </div>
      ) : error ? (
        <div className="flex-1 flex items-center justify-center text-[#ef4444] text-sm">
          모임 정보를 불러올 수 없습니다
        </div>
      ) : meetings.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-[#94a3b8] text-sm">
          참여중인 모임이 없어요
        </div>
      ) : (
        <div className="flex flex-col gap-[26px] flex-1 overflow-y-auto min-h-0">
          {meetings.map((meeting) => (
            <div
              key={meeting.id}
              onClick={() => router.push(`/meeting/${meeting.id}`)}
              className="bg-[#f9fafb] rounded-[12px] p-3 flex items-center gap-3 cursor-pointer hover:bg-[#f1f5f9] transition-colors shrink-0"
              style={{ height: 103 }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-[20px] font-semibold text-[#111827]">
                    {meeting.name}
                  </p>
                  <span
                    className="px-2 py-0.5 rounded-full text-[11px] font-medium text-white shrink-0"
                    style={{ backgroundColor: meeting.badgeColor }}
                  >
                    {meeting.badge}
                  </span>
                </div>
                <p className="text-[15px] text-[#6b7280] mt-0.5">
                  {meeting.schedule}
                </p>
              </div>
              {meeting.badge === "지난 일정" && (
                <button
                  onClick={(e) => { e.stopPropagation(); router.push(`/meeting/${meeting.id}`); }}
                  className="animate-float shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-full text-white text-[12px] font-semibold"
                  style={{ background: "linear-gradient(135deg, #4338ca, #4f46e5)" }}
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  지난 일정 다시 잡기
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

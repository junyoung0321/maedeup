"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { parseServerDate } from "@/lib/datetime";
import type { UpcomingMeetingData } from "@/types";

function formatSchedule(scheduledAt: string): string {
  const date = parseServerDate(scheduledAt);
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const weekday = weekdays[date.getDay()];
  const hours = date.getHours();
  const minutes = date.getMinutes();
  const ampm = hours < 12 ? "오전" : "오후";
  const displayHour = hours % 12 || 12;
  const minuteStr = minutes > 0 ? `:${String(minutes).padStart(2, "0")}` : "";
  return `${month}/${day} (${weekday}) ${ampm} ${displayHour}${minuteStr}`;
}

function getTimeLeft(scheduledAt: string): { h: number; m: number; s: number } | null {
  const diff = parseServerDate(scheduledAt).getTime() - Date.now();
  if (diff <= 0) return null;
  const totalSeconds = Math.floor(diff / 1000);
  return {
    h: Math.floor(totalSeconds / 3600),
    m: Math.floor((totalSeconds % 3600) / 60),
    s: totalSeconds % 60,
  };
}

export default function UpcomingMeeting() {
  const router = useRouter();
  const [meeting, setMeeting] = useState<UpcomingMeetingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeLeft, setTimeLeft] = useState<{ h: number; m: number; s: number } | null>(null);

  // F-(upcoming refresh): mount 시 fetch + window focus / visibility change 시 재fetch.
  // explore page로 돌아올 때 (다른 페이지에서 모임 confirm 후) 최신 maedeup이 노출되도록.
  useEffect(() => {
    let cancelled = false;
    const fetchMeeting = () => {
      apiFetch<UpcomingMeetingData | null>("/api/v1/meetings/upcoming")
        .then((data) => {
          if (cancelled) return;
          setMeeting(data);
          if (data) setTimeLeft(getTimeLeft(data.scheduled_at));
        })
        .catch(() => {
          if (!cancelled) setMeeting(null);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };
    fetchMeeting();
    const onFocus = () => fetchMeeting();
    const onVisibility = () => {
      if (document.visibilityState === "visible") fetchMeeting();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    if (!meeting) return;
    const timer = setInterval(() => {
      setTimeLeft(getTimeLeft(meeting.scheduled_at));
    }, 1000);
    return () => clearInterval(timer);
  }, [meeting]);

  const pad = (n: number) => String(n).padStart(2, "0");

  if (loading) {
    return (
      <div className="relative w-full max-w-full h-full">
        <div className="border border-[#e5e7eb] rounded-[24px] p-6 flex items-center justify-center shadow-sm h-full" style={{ minHeight: 416, background: "#f9fafb" }}>
          <span className="text-[#94a3b8] text-sm">불러오는 중...</span>
        </div>
      </div>
    );
  }

  if (!meeting) {
    return (
      <div className="relative w-full max-w-full h-full">
        <div className="border border-[#e5e7eb] rounded-[24px] p-6 flex flex-col items-center justify-center gap-3 h-full" style={{ minHeight: 416, background: "linear-gradient(to bottom, #ffffff, #f5f3ff)" }}>
          <span className="text-[33px] font-semibold text-[#94a3b8]">예정된 모임이 없어요</span>
          <button
            onClick={() => router.push("/meeting/new")}
            className="px-6 py-2.5 rounded-full bg-[#4f46e5] text-white text-[21px] font-semibold hover:bg-[#4338ca] transition-colors"
          >
            모임 만들기
          </button>
        </div>
      </div>
    );
  }

  const timerStr = timeLeft ? `${pad(timeLeft.h)}:${pad(timeLeft.m)}:${pad(timeLeft.s)}` : "00:00:00";
  const isPast = !timeLeft;
  const remainingTime = timeLeft ?? { h: 0, m: 0, s: 0 };

  return (
    <div className="relative w-full max-w-full">
      {/* Pink callout bubble */}
      <div
        className="absolute -top-6 left-6 px-5 py-2.5 rounded-[20px] text-white text-[30px] font-semibold whitespace-nowrap z-10 animate-float"
        style={{ backgroundColor: "#fa35a4" }}
      >
        가장 먼저 다가오는 모임이에요!
        <div
          className="absolute left-8 -bottom-2 w-0 h-0"
          style={{
            borderLeft: "8px solid transparent",
            borderRight: "8px solid transparent",
            borderTop: "8px solid #fa35a4",
          }}
        />
      </div>

      {/* Card */}
      <div
        className="border border-[#e5e7eb] rounded-[24px] p-6 flex overflow-hidden shadow-[0_4px_3px_rgba(79,70,229,0.25)] h-full"
        style={{ minHeight: 416, background: "linear-gradient(to bottom, #ffffff, #f5f3ff)" }}
      >
        {/* Left info */}
        <div className="flex-1 flex flex-col justify-center pr-4">
          <h3 className="text-[45px] font-semibold text-[#0f172a]" style={{ lineHeight: 1.08 }}>
            {meeting.title}
          </h3>
          <p className="text-[30px] font-semibold text-[#334155] mt-2">
            {formatSchedule(meeting.scheduled_at)}
            {meeting.location_name ? ` · ${meeting.location_name}` : ""}
          </p>
          <p className="text-[27px] text-[#64748b] mt-1">
            {isPast ? "모임 시간이 지났어요" : `시작까지 ${remainingTime.h > 0 ? `${remainingTime.h}시간 ` : ""}${remainingTime.m}분`}
          </p>
          {meeting.location_address && (
            <p className="text-[21px] text-[#94a3b8] mt-2">{meeting.location_address}</p>
          )}
        </div>

        {/* Right purple gradient column */}
        <div
          className="w-[264px] rounded-[16px] flex flex-col items-center justify-center gap-3 shrink-0 p-[14px]"
          style={{ background: "linear-gradient(180deg, #6366f1 0%, #4f46e5 100%)" }}
        >
          <span className="text-[#ddd6fe] text-[17px] font-bold tracking-widest uppercase">
            {isPast ? "STARTED" : "START IN"}
          </span>
          <span className="text-white text-[42px] font-extrabold tracking-wider">
            {timerStr}
          </span>
          <div className="flex flex-col gap-2 w-full mt-2">
            <button
              onClick={() => router.push(`/meeting/${meeting.id}`)}
              className="w-full py-2 rounded-[10px] bg-white text-[#4f46e5] text-[21px] font-bold hover:bg-white/90 transition-colors"
            >
              바로 입장
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

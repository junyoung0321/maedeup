"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function UpcomingMeeting() {
  const router = useRouter();
  const [timeLeft, setTimeLeft] = useState({ h: 1, m: 20, s: 0 });

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        let { h, m, s } = prev;
        if (s > 0) {
          s--;
        } else if (m > 0) {
          m--;
          s = 59;
        } else if (h > 0) {
          h--;
          m = 59;
          s = 59;
        }
        return { h, m, s };
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const pad = (n: number) => String(n).padStart(2, "0");
  const timerStr = `${pad(timeLeft.h)}:${pad(timeLeft.m)}:${pad(timeLeft.s)}`;

  return (
    <div className="relative" style={{ width: 569 }}>
      {/* Pink callout bubble */}
      <div
        className="absolute -top-12 left-6 px-5 py-2.5 rounded-[20px] text-white text-[20px] font-semibold whitespace-nowrap z-10 animate-float"
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
        className="border border-[#e5e7eb] rounded-[24px] p-6 flex overflow-hidden shadow-[0_4px_3px_rgba(79,70,229,0.25)]" style={{ height: 320, background: "linear-gradient(to bottom, #ffffff, #f5f3ff)" }}
      >
        {/* Left info */}
        <div className="flex-1 flex flex-col justify-center pr-4">
          <h3
            className="text-[30px] font-semibold text-[#0f172a]"
            style={{ lineHeight: 1.08 }}
          >
            카카오톡 기획 스터디
          </h3>
          <p className="text-[20px] font-semibold text-[#334155] mt-2">
            오늘 20:00 · 온라인
          </p>
          <p className="text-[18px] text-[#64748b] mt-1">
            참여 3/6명 · 시작까지 1시간 20분
          </p>
          <div className="flex gap-2 mt-4">
            <span className="px-3 py-1 rounded-full text-[13px] font-medium bg-[#eef2ff] text-[#3730a3]">
              응답률 82%
            </span>
            <span className="px-3 py-1 rounded-full text-[13px] font-medium bg-[#ecfeff] text-[#0f766e]">
              추천 기반
            </span>
          </div>
        </div>

        {/* Right purple gradient column */}
        <div
          className="w-[176px] rounded-[16px] flex flex-col items-center justify-center gap-3 shrink-0 p-[14px]"
          style={{
            background: "linear-gradient(180deg, #6366f1 0%, #4f46e5 100%)",
          }}
        >
          <span className="text-[#ddd6fe] text-[11px] font-bold tracking-widest uppercase">
            START IN
          </span>
          <span className="text-white text-[28px] font-extrabold tracking-wider">
            {timerStr}
          </span>
          <div className="flex flex-col gap-2 w-full mt-2">
            <button
              onClick={() => router.push("/meeting/upcoming-1/schedule")}
              className="w-full py-2 rounded-[10px] bg-white text-[#4f46e5] text-[14px] font-bold hover:bg-white/90 transition-colors"
            >
              바로 입장
            </button>
            <button className="w-full py-2 rounded-[10px] bg-white/30 text-white text-[13px] font-semibold hover:bg-white/40 transition-colors">
              일정 보기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

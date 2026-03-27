"use client";

import { Check, Share2, List, Calendar, MapPin, Users } from "lucide-react";
import Avatar from "@/components/ui/Avatar";
import { useRouter } from "next/navigation";

export default function CompletionPage() {
  const router = useRouter();

  const meetingInfo = {
    title: "졸업 프로젝트 회의",
    date: "2026년 3월 23일 (월) 오후 3:00",
    location: "강남역 스타벅스 3층",
    members: [
      { name: "김준영", color: "#818cf8" },
      { name: "정은빈", color: "#f472b6" },
      { name: "한도이", color: "#34d399" },
      { name: "가인영", color: "#fbbf24" },
    ],
  };

  const visibleMembers = meetingInfo.members.slice(0, 2);
  const extraCount = meetingInfo.members.length - visibleMembers.length;

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
                {meetingInfo.title}
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
                {meetingInfo.date}
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
                {meetingInfo.location}
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
                    <Avatar key={m.name} name={m.name} color={m.color} size="sm" />
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

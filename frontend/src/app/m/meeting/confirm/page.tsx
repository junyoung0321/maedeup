"use client";

import { useRouter } from "next/navigation";
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
} from "lucide-react";

const avatars = [
  { name: "우진", color: "#818cf8" },
  { name: "서연", color: "#f472b6" },
  { name: "민준", color: "#fb923c" },
  { name: "수아", color: "#34d399" },
  { name: "지호", color: "#60a5fa" },
];

export default function MeetingConfirmPage() {
  const router = useRouter();
  return (
    <div
      className="flex flex-col bg-white overflow-hidden"
      style={{ width: 390, height: 844, fontFamily: "Pretendard, sans-serif" }}
    >
      {/* Header */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 56,
          padding: "0 16px",
          borderBottom: "1px solid #e2e8f0",
          backgroundColor: "#fff",
        }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/place")} />
        <div className="flex flex-col items-center flex-1" style={{ gap: 2 }}>
          <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b" }}>
            졸업 프로젝트 회의
          </span>
          <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>
            5명 참여 중
          </span>
        </div>
        <Menu size={24} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/meeting/detail")} />
      </div>

      {/* Tabs */}
      <div
        className="flex shrink-0"
        style={{
          height: 44,
          backgroundColor: "#fff",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          style={{ fontSize: 14, fontWeight: 500, color: "#94a3b8" }}
          onClick={() => router.push("/m/chat/place")}
        >
          채팅방
        </div>
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "#4f46e5",
            borderBottom: "2px solid #4f46e5",
          }}
        >
          장소 선택
        </div>
      </div>

      {/* Content */}
      <div
        className="flex-1 flex flex-col overflow-y-auto"
        style={{ backgroundColor: "#f8fafc", padding: 20, gap: 20 }}
      >
        {/* Summary Card */}
        <div
          className="flex flex-col"
          style={{
            borderRadius: 16,
            backgroundColor: "#fff",
            border: "1px solid #e5e7eb",
            padding: 20,
            gap: 16,
          }}
        >
          {/* Title row */}
          <div className="flex items-center" style={{ gap: 8 }}>
            <ClipboardCheck size={20} color="#4f46e5" />
            <span style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>
              모임 최종 확인
            </span>
          </div>

          <span style={{ fontSize: 13, fontWeight: 400, color: "#64748b" }}>
            아래 내용으로 모임을 생성합니다
          </span>

          {/* Divider */}
          <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

          {/* Name row */}
          <div className="flex items-center" style={{ gap: 10 }}>
            <FileText size={16} color="#94a3b8" className="shrink-0" />
            <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>
              모임명
            </span>
            <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
              졸업 프로젝트 회의
            </span>
          </div>

          {/* Schedule box */}
          <div
            className="flex flex-col"
            style={{
              borderRadius: 12,
              backgroundColor: "#eef2ff",
              border: "1px solid #e0e7ff",
              padding: 14,
              gap: 6,
            }}
          >
            <div className="flex items-center" style={{ gap: 8 }}>
              <Calendar size={16} color="#4f46e5" />
              <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>
                확정된 일정
              </span>
            </div>
            <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
              3월 23일 (월) 오후 3:00 ~ 5:00
            </span>
            <span style={{ fontSize: 12, fontWeight: 400, color: "#4f46e5" }}>
              5/5명 참여 가능
            </span>
          </div>

          {/* Place box */}
          <div
            className="flex flex-col"
            style={{
              borderRadius: 12,
              backgroundColor: "#f0fdf4",
              border: "1px solid #bbf7d0",
              padding: 14,
              gap: 6,
            }}
          >
            <div className="flex items-center" style={{ gap: 8 }}>
              <MapPin size={16} color="#16a34a" />
              <span style={{ fontSize: 12, fontWeight: 600, color: "#16a34a" }}>
                확정된 장소
              </span>
            </div>
            <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
              을지로 골목식당
            </span>
            <span style={{ fontSize: 12, fontWeight: 400, color: "#64748b" }}>
              서울 중구 을지로 12길
            </span>
          </div>

          {/* Divider */}
          <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

          {/* Participants */}
          <div className="flex items-center" style={{ gap: 8 }}>
            <Users size={16} color="#94a3b8" />
            <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
              참여자 (5명)
            </span>
          </div>

          {/* Avatar row */}
          <div className="flex" style={{ gap: 8 }}>
            {avatars.map((a) => (
              <div
                key={a.name}
                className="flex flex-col items-center"
                style={{ gap: 4 }}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "50%",
                    backgroundColor: a.color,
                  }}
                />
                <span style={{ fontSize: 10, fontWeight: 400, color: "#374151" }}>
                  {a.name}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Warning card */}
        <div
          className="flex"
          style={{
            borderRadius: 12,
            backgroundColor: "#fffbeb",
            border: "1px solid #fde68a",
            padding: 14,
            gap: 8,
          }}
        >
          <TriangleAlert size={16} color="#d97706" className="shrink-0" style={{ marginTop: 2 }} />
          <span
            style={{
              fontSize: 12,
              fontWeight: 400,
              color: "#92400e",
              lineHeight: 1.5,
            }}
          >
            모임 생성 후에는 일정과 장소를 변경할 수 없습니다.
            {"\n"}신중하게 확인해주세요.
          </span>
        </div>
      </div>

      {/* Button area */}
      <div
        className="flex flex-col shrink-0"
        style={{
          backgroundColor: "#fff",
          padding: 20,
          gap: 10,
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <button
          className="flex items-center justify-center cursor-pointer"
          onClick={() => router.push("/m/meeting/done")}
          style={{
            borderRadius: 12,
            backgroundColor: "#4f46e5",
            height: 48,
            gap: 8,
            border: "none",
          }}
        >
          <CircleCheck size={18} color="#fff" />
          <span style={{ fontSize: 15, fontWeight: 600, color: "#fff" }}>
            모임 생성하기
          </span>
        </button>
        <button
          className="flex items-center justify-center cursor-pointer"
          onClick={() => router.push("/m/place")}
          style={{
            borderRadius: 12,
            backgroundColor: "#fff",
            border: "1px solid #e2e8f0",
            height: 40,
          }}
        >
          <span style={{ fontSize: 14, fontWeight: 500, color: "#64748b" }}>
            돌아가기
          </span>
        </button>
      </div>

      {/* Home bar */}
      <div
        className="flex items-center justify-center shrink-0"
        style={{ height: 20, backgroundColor: "#fff" }}
      >
        <div
          style={{
            width: 134,
            height: 5,
            borderRadius: 100,
            backgroundColor: "#000000",
          }}
        />
      </div>
    </div>
  );
}

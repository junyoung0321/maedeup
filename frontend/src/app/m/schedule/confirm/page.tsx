"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  CircleCheck,
  Calendar,
  Users,
  CalendarCheck,
} from "lucide-react";

const participants = [
  { name: "정우진", color: "#818cf8" },
  { name: "이서연", color: "#f472b6" },
  { name: "김민준", color: "#fb923c" },
  { name: "최수아", color: "#34d399" },
  { name: "박지호", color: "#60a5fa" },
];

export default function ScheduleConfirmPage() {
  const router = useRouter();
  return (
    <div
      className="relative flex flex-col bg-white"
      style={{
        width: 390,
        height: 844,
        overflow: "hidden",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 56,
          padding: "0 16px",
          backgroundColor: "#fff",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/schedule")} />
        <div
          className="flex flex-col justify-center flex-1"
          style={{ gap: 2, marginLeft: 12 }}
        >
          <span
            style={{
              fontSize: 17,
              fontWeight: 600,
              color: "#1e293b",
              lineHeight: "22px",
            }}
          >
            졸업 프로젝트 회의
          </span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 400,
              color: "#94a3b8",
              lineHeight: "16px",
            }}
          >
            5명 참여 중
          </span>
        </div>
        <Menu size={24} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/meeting/detail")} />
      </div>

      {/* Tab bar */}
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
          onClick={() => router.push("/m/chat/schedule")}
          style={{
            fontSize: 14,
            fontWeight: 500,
            color: "#94a3b8",
          }}
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
          캘린더
        </div>
      </div>

      {/* Content */}
      <div
        className="flex-1 flex flex-col"
        style={{
          backgroundColor: "#f8fafc",
          padding: 20,
          gap: 20,
          overflowY: "auto",
        }}
      >
        {/* Vote result card */}
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
            <CircleCheck size={20} color="#22c55e" className="shrink-0" />
            <span
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: "#1e293b",
              }}
            >
              투표 결과
            </span>
          </div>

          <span
            style={{
              fontSize: 13,
              fontWeight: 400,
              color: "#64748b",
              lineHeight: "18px",
            }}
          >
            모든 참여자가 투표를 완료했습니다
          </span>

          {/* Divider */}
          <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

          {/* Best slot */}
          <div
            className="flex flex-col"
            style={{
              borderRadius: 12,
              backgroundColor: "#eef2ff",
              border: "1px solid #e0e7ff",
              padding: 16,
              gap: 8,
            }}
          >
            <div className="flex items-center" style={{ gap: 8 }}>
              <Calendar size={16} color="#4f46e5" className="shrink-0" />
              <span
                style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: "#1e293b",
                }}
              >
                3/23 (월) 오후 3:00~5:00
              </span>
            </div>
            <div className="flex items-center" style={{ gap: 8 }}>
              <Users size={16} color="#4f46e5" className="shrink-0" />
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 400,
                  color: "#4f46e5",
                }}
              >
                5/5명 참여 가능
              </span>
            </div>
            <div>
              <span
                style={{
                  display: "inline-block",
                  borderRadius: 999,
                  backgroundColor: "#4f46e5",
                  padding: "3px 10px",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#fff",
                  lineHeight: "16px",
                }}
              >
                최적 시간
              </span>
            </div>
          </div>

          {/* Second slot */}
          <div
            className="flex flex-col"
            style={{
              borderRadius: 12,
              backgroundColor: "#f9fafb",
              border: "1px solid #e5e7eb",
              padding: 16,
              gap: 8,
            }}
          >
            <div className="flex items-center" style={{ gap: 8 }}>
              <Calendar size={16} color="#94a3b8" className="shrink-0" />
              <span
                style={{
                  fontSize: 15,
                  fontWeight: 500,
                  color: "#374151",
                }}
              >
                3/24 (화) 오후 2:00~4:00
              </span>
            </div>
            <div className="flex items-center" style={{ gap: 8 }}>
              <Users size={16} color="#94a3b8" className="shrink-0" />
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 400,
                  color: "#94a3b8",
                }}
              >
                4/5명 참여 가능
              </span>
            </div>
          </div>
        </div>

        {/* Participant card */}
        <div
          className="flex flex-col"
          style={{
            borderRadius: 16,
            backgroundColor: "#fff",
            border: "1px solid #e5e7eb",
            padding: 20,
            gap: 12,
          }}
        >
          <span
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            참여자 투표 현황
          </span>

          {participants.map((p) => (
            <div
              key={p.name}
              className="flex items-center"
              style={{ gap: 10 }}
            >
              {/* Avatar */}
              <div
                className="shrink-0 flex items-center justify-center"
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  backgroundColor: p.color,
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#fff",
                }}
              >
                {p.name.charAt(0)}
              </div>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 400,
                  color: "#374151",
                }}
              >
                {p.name}
              </span>
              <div className="flex-1" />
              <CircleCheck size={16} color="#22c55e" className="shrink-0" />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 400,
                  color: "#22c55e",
                }}
              >
                투표완료
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom area */}
      <div
        className="shrink-0"
        style={{
          backgroundColor: "#fff",
          padding: 20,
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <button
          className="flex items-center justify-center w-full cursor-pointer"
          onClick={() => router.push("/m/chat/place")}
          style={{
            borderRadius: 12,
            backgroundColor: "#4f46e5",
            height: 48,
            gap: 8,
            border: "none",
          }}
        >
          <CalendarCheck size={18} color="#fff" />
          <span
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: "#fff",
            }}
          >
            이 시간으로 확정하기
          </span>
        </button>
      </div>

      {/* Home bar */}
      <div
        className="shrink-0 flex items-center justify-center"
        style={{ height: 20, backgroundColor: "#fff" }}
      >
        <div
          style={{
            width: 134,
            height: 5,
            borderRadius: 999,
            backgroundColor: "#000000",
          }}
        />
      </div>
    </div>
  );
}

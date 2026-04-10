"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  Sparkles,
  ChevronRight,
  Send,
  Loader2,
} from "lucide-react";

export default function ScheduleChatPage() {
  const router = useRouter();
  return (
    <div
      className="relative mx-auto flex flex-col bg-white overflow-hidden"
      style={{ width: 390, height: 844 }}
    >
      {/* 1. Chat Header */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 56,
          padding: "0 16px",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/explore")} />
        <div className="flex-1 flex flex-col items-center gap-[2px]">
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 17,
              fontWeight: 600,
              color: "#1e293b",
            }}
          >
            졸업 프로젝트 회의
          </span>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 400,
              color: "#94a3b8",
            }}
          >
            5명 참여 중
          </span>
        </div>
        <Menu size={24} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/meeting/detail")} />
      </div>

      {/* 2. Tab Bar */}
      <div
        className="flex shrink-0"
        style={{
          height: 44,
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 14,
            fontWeight: 600,
            color: "#4f46e5",
            borderBottom: "2px solid #4f46e5",
          }}
        >
          채팅방
        </div>
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          onClick={() => router.push("/m/schedule")}
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 14,
            fontWeight: 500,
            color: "#94a3b8",
          }}
        >
          캘린더
        </div>
      </div>

      {/* 3. AI Banner */}
      <div
        className="flex items-center justify-center shrink-0"
        style={{
          height: 40,
          background: "#eef2ff",
          borderBottom: "1px solid #e0e7ff",
          gap: 6,
        }}
      >
        <Sparkles size={14} color="#4f46e5" />
        <span
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 12,
            fontWeight: 600,
            color: "#4f46e5",
          }}
        >
          AI가 일정 조율을 시작했습니다
        </span>
        <ChevronRight size={14} color="#4f46e5" />
      </div>

      {/* 4. Message Area */}
      <div
        className="flex-1 flex flex-col overflow-y-auto"
        style={{
          background: "#f8fafc",
          padding: "12px 16px",
          gap: 16,
        }}
      >
        {/* Message 1 - 정우진 (left) */}
        <div className="flex items-end" style={{ gap: 8 }}>
          <div
            className="shrink-0 flex items-center justify-center"
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              background: "#818cf8",
            }}
          >
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 500,
                color: "#ffffff",
              }}
            >
              J
            </span>
          </div>
          <div className="flex flex-col" style={{ gap: 4 }}>
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 11,
                fontWeight: 400,
                color: "#94a3b8",
              }}
            >
              정우진
            </span>
            <div
              style={{
                borderRadius: "16px 16px 16px 6px",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                padding: "10px 14px",
              }}
            >
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 13,
                  fontWeight: 400,
                  color: "#1e293b",
                }}
              >
                다음 주 회의 언제 할까요?
              </span>
            </div>
          </div>
        </div>

        {/* Message 2 - 이서연 (left) */}
        <div className="flex items-end" style={{ gap: 8 }}>
          <div
            className="shrink-0 flex items-center justify-center"
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              background: "#f472b6",
            }}
          >
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 500,
                color: "#ffffff",
              }}
            >
              S
            </span>
          </div>
          <div className="flex flex-col" style={{ gap: 4 }}>
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 11,
                fontWeight: 400,
                color: "#94a3b8",
              }}
            >
              이서연
            </span>
            <div
              style={{
                borderRadius: "16px 16px 16px 6px",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                padding: "10px 14px",
              }}
            >
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 13,
                  fontWeight: 400,
                  color: "#1e293b",
                }}
              >
                저는 화요일이나 수요일이 좋아요
              </span>
            </div>
          </div>
        </div>

        {/* Message 3 - My message (right) */}
        <div className="flex justify-end">
          <div
            style={{
              borderRadius: "16px 16px 6px 16px",
              background: "#4f46e5",
              padding: "10px 14px",
            }}
          >
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 400,
                color: "#ffffff",
              }}
            >
              저도 화요일 괜찮아요
            </span>
          </div>
        </div>

        {/* AI Card */}
        <div
          style={{
            borderRadius: 16,
            background: "linear-gradient(-225deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
            padding: "16px 18px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            boxShadow: "0 4px 14px #4f46e520",
          }}
        >
          <div className="flex items-center" style={{ gap: 6 }}>
            <Sparkles size={16} color="#ffffff" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 11,
                fontWeight: 600,
                color: "#ffffff",
              }}
            >
              AI 어시스턴트
            </span>
          </div>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 16,
              fontWeight: 700,
              color: "#ffffff",
            }}
          >
            일정 조율을 시작하겠습니다
          </span>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 400,
              color: "#ffffffcc",
              lineHeight: 1.5,
              whiteSpace: "pre-line",
            }}
          >
            {"채팅 내용을 분석하여 모임원들의\n가능한 시간대를 정리하고 있어요."}
          </span>
          <div style={{ height: 1, background: "#ffffff30" }} />
          <div className="flex items-center" style={{ gap: 6 }}>
            <Loader2 size={12} color="#ffffff" className="animate-spin" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 11,
                fontWeight: 400,
                color: "#ffffff",
              }}
            >
              분석 중...
            </span>
          </div>
        </div>
      </div>

      {/* 5. Input Bar */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 60,
          background: "#ffffff",
          borderTop: "1px solid #e2e8f0",
          padding: "0 12px",
          gap: 8,
        }}
      >
        <div
          className="flex-1 flex items-center"
          style={{
            height: 40,
            borderRadius: 20,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "0 16px",
            boxShadow: "0 2px 4px #0000001a",
          }}
        >
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 14,
              fontWeight: 400,
              color: "#94a3b8",
            }}
          >
            메세지를 입력하세요
          </span>
        </div>
        <div
          className="flex items-center justify-center shrink-0 cursor-pointer"
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            background: "#4f46e5",
          }}
        >
          <Send size={16} color="#ffffff" />
        </div>
      </div>

      {/* 6. Home Indicator */}
      <div
        className="flex items-center justify-center shrink-0"
        style={{ height: 20, background: "#ffffff" }}
      >
        <div
          style={{
            width: 134,
            height: 5,
            borderRadius: 3,
            background: "#000000",
          }}
        />
      </div>
    </div>
  );
}

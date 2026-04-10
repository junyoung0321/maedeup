"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  Sparkles,
  ChevronRight,
  MapPin,
  Send,
} from "lucide-react";

export default function PlaceChatPage() {
  const router = useRouter();
  return (
    <div
      className="relative mx-auto flex flex-col bg-white"
      style={{ width: 390, height: 844, overflow: "clip" }}
    >
      {/* 1. Chat Header */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 56,
          padding: "0 16px",
          borderBottom: "1px solid #e2e8f0",
          backgroundColor: "#ffffff",
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
          backgroundColor: "#ffffff",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <button
          className="flex-1 flex items-center justify-center"
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 14,
            fontWeight: 600,
            color: "#4f46e5",
            borderBottom: "2px solid #4f46e5",
          }}
        >
          채팅방
        </button>
        <button
          className="flex-1 flex items-center justify-center"
          onClick={() => router.push("/m/place")}
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 14,
            fontWeight: 500,
            color: "#94a3b8",
          }}
        >
          장소 선택
        </button>
      </div>

      {/* 3. AI Banner */}
      <div
        className="flex items-center justify-center shrink-0"
        style={{
          height: 40,
          backgroundColor: "#eef2ff",
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
          AI가 장소 추천을 시작했습니다
        </span>
        <ChevronRight size={14} color="#4f46e5" />
      </div>

      {/* 4. Message Area */}
      <div
        className="flex-1 flex flex-col overflow-y-auto"
        style={{
          backgroundColor: "#f8fafc",
          padding: "12px 16px",
          gap: 16,
        }}
      >
        {/* Msg 1 - 정우진 */}
        <div className="flex items-end" style={{ gap: 8 }}>
          <div
            className="shrink-0 flex items-center justify-center"
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              backgroundColor: "#818cf8",
            }}
          >
            <span
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: 13,
                fontWeight: 700,
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
                backgroundColor: "#ffffff",
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
                회의 장소 어디로 할까요?
              </span>
            </div>
          </div>
        </div>

        {/* Msg 2 - 이서연 */}
        <div className="flex items-end" style={{ gap: 8 }}>
          <div
            className="shrink-0 flex items-center justify-center"
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              backgroundColor: "#f472b6",
            }}
          >
            <span
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: 13,
                fontWeight: 700,
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
                backgroundColor: "#ffffff",
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
                강남역 근처가 좋을 것 같아요
              </span>
            </div>
          </div>
        </div>

        {/* Msg 3 - Right (Me) */}
        <div className="flex justify-end">
          <div
            style={{
              borderRadius: "16px 16px 6px 16px",
              backgroundColor: "#4f46e5",
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
              저도 강남이 편해요
            </span>
          </div>
        </div>

        {/* Msg 4 - 김민준 */}
        <div className="flex items-end" style={{ gap: 8 }}>
          <div
            className="shrink-0 flex items-center justify-center"
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              backgroundColor: "#fb923c",
            }}
          >
            <span
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: 13,
                fontWeight: 700,
                color: "#ffffff",
              }}
            >
              M
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
              김민준
            </span>
            <div
              style={{
                borderRadius: "16px 16px 16px 6px",
                backgroundColor: "#ffffff",
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
                카페나 스터디룸이면 좋겠어요
              </span>
            </div>
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
                fontSize: 13,
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
            장소 추천을 시작하겠습니다
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
            {"채팅 내용을 분석하여 강남역 근처\n카페와 스터디룸을 찾고 있어요."}
          </span>
          <div style={{ height: 1, backgroundColor: "#ffffff30" }} />
          <div className="flex items-center" style={{ gap: 6 }}>
            <MapPin size={14} color="#ffffff" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 400,
                color: "#ffffff",
              }}
            >
              장소 검색 중...
            </span>
          </div>
        </div>
      </div>

      {/* 5. Input Bar */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 60,
          backgroundColor: "#ffffff",
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
            backgroundColor: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "0 16px",
            boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
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
        <button
          className="shrink-0 flex items-center justify-center"
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            backgroundColor: "#4f46e5",
          }}
        >
          <Send size={16} color="#ffffff" />
        </button>
      </div>

      {/* 6. Home Bar */}
      <div
        className="flex items-center justify-center shrink-0"
        style={{ height: 20, backgroundColor: "#ffffff" }}
      >
        <div
          style={{
            width: 134,
            height: 5,
            borderRadius: 3,
            backgroundColor: "#000000",
          }}
        />
      </div>
    </div>
  );
}

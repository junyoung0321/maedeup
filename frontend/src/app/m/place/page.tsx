"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  Sparkles,
  Radar,
  UtensilsCrossed,
  MapPin,
} from "lucide-react";

export default function PlaceRecommendPage() {
  const router = useRouter();
  return (
    <div
      className="relative mx-auto flex flex-col bg-white"
      style={{ width: 390, height: 844, overflow: "clip" }}
    >
      {/* 1. Header */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 56,
          padding: "0 16px",
          borderBottom: "1px solid #e2e8f0",
          backgroundColor: "#ffffff",
        }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/chat/place")} />
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

      {/* 2. Tabs */}
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
          onClick={() => router.push("/m/chat/place")}
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 14,
            fontWeight: 500,
            color: "#94a3b8",
          }}
        >
          채팅방
        </button>
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
          장소 선택
        </button>
      </div>

      {/* 3. Content */}
      <div
        className="flex-1 flex flex-col overflow-y-auto"
        style={{
          padding: "14px 16px 16px 16px",
          gap: 14,
        }}
      >
        {/* Detect Banner */}
        <div
          className="flex items-center shrink-0"
          style={{
            height: 32,
            borderRadius: 16,
            backgroundColor: "#eef2ff",
            padding: "0 12px",
            gap: 6,
          }}
        >
          <Radar size={14} color="#4f46e5" className="shrink-0" />
          <span
            style={{
              fontFamily: "Inter, sans-serif",
              fontSize: 10,
              fontWeight: 600,
              color: "#4f46e5",
            }}
          >
            채팅방에서 장소 관련 대화가 감지되었습니다
          </span>
        </div>

        {/* AI Card */}
        <div
          style={{
            borderRadius: 14,
            background: "linear-gradient(-225deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
            padding: "14px 16px",
            display: "flex",
            flexDirection: "column",
            gap: 8,
            boxShadow: "0 4px 14px #4f46e520",
          }}
        >
          <div className="flex items-center" style={{ gap: 6 }}>
            <Sparkles size={16} color="#ffffff" />
            <span
              style={{
                fontFamily: "Inter, sans-serif",
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
              fontSize: 15,
              fontWeight: 700,
              color: "#ffffff",
            }}
          >
            모임 장소를 추천해드리겠습니다
          </span>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 11,
              fontWeight: 400,
              color: "#ffffffcc",
              lineHeight: 1.5,
              whiteSpace: "pre-line",
            }}
          >
            {"채팅 내용을 분석하여 근처 맛집과\n모임 장소를 찾아보았어요."}
          </span>
        </div>

        {/* List Header */}
        <div className="flex items-center" style={{ gap: 6 }}>
          <UtensilsCrossed size={16} color="#4f46e5" />
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 14,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            추천 장소
          </span>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 500,
              color: "#94a3b8",
            }}
          >
            4곳
          </span>
        </div>

        {/* Restaurant List */}
        <div className="flex flex-col" style={{ gap: 12, overflow: "hidden" }}>
          {/* Card 1 */}
          <div
            onClick={() => router.push("/m/place/detail")}
            style={{
              borderRadius: 12,
              backgroundColor: "#ffffff",
              border: "1px solid #e2e8f0",
              boxShadow: "0 2px 6px #0000001a",
              overflow: "hidden",
              cursor: "pointer",
            }}
          >
            {/* Image placeholder */}
            <div
              style={{
                height: 100,
                width: "100%",
                background: "linear-gradient(135deg, #d4c5a9 0%, #c4b597 50%, #b8a98a 100%)",
              }}
            />
            {/* Body */}
            <div
              className="flex flex-col"
              style={{ padding: "10px 12px", gap: 6 }}
            >
              {/* Name row */}
              <div className="flex items-center justify-between">
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 14,
                    fontWeight: 700,
                    color: "#1e293b",
                  }}
                >
                  을지로 골목식당
                </span>
                <span
                  style={{
                    fontFamily: "Inter, sans-serif",
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#f59e0b",
                  }}
                >
                  ⭐ 4.5
                </span>
              </div>
              {/* Tag row */}
              <div className="flex items-center" style={{ gap: 6 }}>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 10,
                    fontWeight: 500,
                    color: "#4f46e5",
                    backgroundColor: "#eef2ff",
                    borderRadius: 10,
                    padding: "3px 8px",
                  }}
                >
                  한식
                </span>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 10,
                    fontWeight: 500,
                    color: "#16a34a",
                    backgroundColor: "#f0fdf4",
                    borderRadius: 10,
                    padding: "3px 8px",
                  }}
                >
                  단체석
                </span>
              </div>
              {/* Address */}
              <div className="flex items-center" style={{ gap: 4 }}>
                <MapPin size={12} color="#94a3b8" className="shrink-0" />
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 11,
                    fontWeight: 400,
                    color: "#64748b",
                  }}
                >
                  서울 중구 을지로 12길
                </span>
              </div>
            </div>
          </div>

          {/* Card 2 */}
          <div
            onClick={() => router.push("/m/place/detail")}
            style={{
              borderRadius: 12,
              backgroundColor: "#ffffff",
              border: "1px solid #e2e8f0",
              boxShadow: "0 2px 6px #0000001a",
              overflow: "hidden",
              cursor: "pointer",
            }}
          >
            {/* Image placeholder */}
            <div
              style={{
                height: 100,
                width: "100%",
                background: "linear-gradient(135deg, #8b7355 0%, #a0896d 50%, #6b5b45 100%)",
              }}
            />
            {/* Body */}
            <div
              className="flex flex-col"
              style={{ padding: "10px 12px", gap: 6 }}
            >
              {/* Name row */}
              <div className="flex items-center justify-between">
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 14,
                    fontWeight: 700,
                    color: "#1e293b",
                  }}
                >
                  모모스 커피
                </span>
                <span
                  style={{
                    fontFamily: "Inter, sans-serif",
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#f59e0b",
                  }}
                >
                  ⭐ 4.3
                </span>
              </div>
              {/* Tag row */}
              <div className="flex items-center" style={{ gap: 6 }}>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 10,
                    fontWeight: 500,
                    color: "#4f46e5",
                    backgroundColor: "#eef2ff",
                    borderRadius: 10,
                    padding: "3px 8px",
                  }}
                >
                  카페
                </span>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 10,
                    fontWeight: 500,
                    color: "#ea580c",
                    backgroundColor: "#fff7ed",
                    borderRadius: 10,
                    padding: "3px 8px",
                  }}
                >
                  조용함
                </span>
              </div>
              {/* Address */}
              <div className="flex items-center" style={{ gap: 4 }}>
                <MapPin size={12} color="#94a3b8" className="shrink-0" />
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 11,
                    fontWeight: 400,
                    color: "#64748b",
                  }}
                >
                  서울 성동구 성수이로
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Share2,
  Star,
  MapPin,
  Phone,
  Clock3,
  Wallet,
  Sparkles,
  CheckCircle,
  Circle,
} from "lucide-react";

export default function PlaceDetailPage() {
  const router = useRouter();
  return (
    <div
      className="relative flex flex-col bg-white overflow-hidden"
      style={{ width: 390, height: 844 }}
    >
      {/* Header */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 56,
          padding: "0 16px",
          borderBottom: "1px solid #e2e8f0",
          backgroundColor: "#ffffff",
        }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/place")} />
        <div className="flex flex-col items-center flex-1 gap-[2px]">
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 17,
              fontWeight: 600,
              color: "#1e293b",
            }}
          >
            장소 상세
          </span>
        </div>
        <Share2 size={22} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => { navigator.clipboard?.writeText(window.location.href); alert("링크가 복사되었습니다!"); }} />
      </div>

      {/* Hero Image */}
      <div
        className="shrink-0 w-full"
        style={{
          height: 220,
          background:
            "linear-gradient(135deg, #b8976a 0%, #8b7355 50%, #6b5842 100%)",
        }}
      />

      {/* Content */}
      <div
        className="flex flex-col flex-1 overflow-y-auto"
        style={{
          backgroundColor: "#ffffff",
          padding: 20,
          gap: 16,
        }}
      >
        {/* Name + Rating row */}
        <div className="flex items-center justify-between">
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 22,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            을지로 골목식당
          </span>
          <div className="flex items-center" style={{ gap: 4 }}>
            <Star size={18} color="#f59e0b" fill="#f59e0b" />
            <span
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: 16,
                fontWeight: 700,
                color: "#f59e0b",
              }}
            >
              4.5
            </span>
          </div>
        </div>

        {/* Tag row */}
        <div className="flex items-center" style={{ gap: 8 }}>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 500,
              color: "#4f46e5",
              backgroundColor: "#eef2ff",
              borderRadius: 999,
              padding: "4px 10px",
            }}
          >
            한식
          </span>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 500,
              color: "#d97706",
              backgroundColor: "#fef3c7",
              borderRadius: 999,
              padding: "4px 10px",
            }}
          >
            단체석
          </span>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 500,
              color: "#059669",
              backgroundColor: "#ecfdf5",
              borderRadius: 999,
              padding: "4px 10px",
            }}
          >
            주차가능
          </span>
        </div>

        {/* Divider */}
        <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

        {/* Info section */}
        <div className="flex flex-col" style={{ gap: 12 }}>
          {[
            { icon: MapPin, text: "서울 중구 을지로 12길" },
            { icon: Phone, text: "02-2267-1234" },
            { icon: Clock3, text: "영업시간: 11:00 ~ 22:00 (월~토)" },
            { icon: Wallet, text: "인당 평균 15,000원" },
          ].map(({ icon: Icon, text }, i) => (
            <div key={i} className="flex items-center" style={{ gap: 10 }}>
              <Icon size={16} color="#94a3b8" className="shrink-0" />
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 14,
                  fontWeight: 400,
                  color: "#374151",
                }}
              >
                {text}
              </span>
            </div>
          ))}
        </div>

        {/* Divider */}
        <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

        {/* AI Recommend card */}
        <div
          className="flex flex-col"
          style={{
            borderRadius: 12,
            backgroundColor: "#f5f3ff",
            border: "1px solid #e0e7ff",
            padding: 16,
            gap: 8,
          }}
        >
          <div className="flex items-center" style={{ gap: 6 }}>
            <Sparkles size={16} color="#4f46e5" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#4f46e5",
              }}
            >
              AI 추천 이유
            </span>
          </div>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 13,
              fontWeight: 400,
              color: "#374151",
              lineHeight: 1.6,
            }}
          >
            {"모임 인원 5명에 적합한 단체석이 있으며,\n강남역에서 도보 10분 거리로 접근성이 좋습니다.\n평점 4.5로 리뷰 만족도가 높습니다."}
          </span>
        </div>

        {/* Divider */}
        <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

        {/* Vote section */}
        <div className="flex flex-col" style={{ gap: 8 }}>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 14,
              fontWeight: 600,
              color: "#1e293b",
            }}
          >
            참여자 투표 현황
          </span>

          {/* Vote bar row */}
          <div className="flex items-center" style={{ gap: 10 }}>
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 600,
                color: "#22c55e",
              }}
            >
              찬성
            </span>
            <div
              className="flex-1"
              style={{
                height: 8,
                borderRadius: 4,
                backgroundColor: "#e2e8f0",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: "80%",
                  height: "100%",
                  borderRadius: 4,
                  backgroundColor: "#22c55e",
                }}
              />
            </div>
            <span
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: 12,
                fontWeight: 600,
                color: "#22c55e",
              }}
            >
              4/5
            </span>
          </div>

          {/* Avatar row */}
          <div className="flex items-start" style={{ gap: 8 }}>
            {[
              { bg: "#818cf8", voted: true },
              { bg: "#f472b6", voted: true },
              { bg: "#fb923c", voted: true },
              { bg: "#34d399", voted: true },
              { bg: "#60a5fa", voted: false },
            ].map(({ bg, voted }, i) => (
              <div
                key={i}
                className="flex flex-col items-center"
                style={{ gap: 3 }}
              >
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    backgroundColor: bg,
                  }}
                />
                {voted ? (
                  <CheckCircle size={12} color="#22c55e" />
                ) : (
                  <Circle size={12} color="#cbd5e1" />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Button area */}
      <div
        className="shrink-0"
        style={{
          backgroundColor: "#ffffff",
          padding: "12px 20px",
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <button
          className="flex items-center justify-center w-full cursor-pointer"
          onClick={() => router.push("/m/meeting/confirm")}
          style={{
            borderRadius: 12,
            backgroundColor: "#4f46e5",
            height: 48,
            gap: 8,
            border: "none",
          }}
        >
          <MapPin size={18} color="#ffffff" />
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 15,
              fontWeight: 600,
              color: "#ffffff",
            }}
          >
            이 장소로 선택하기
          </span>
        </button>
      </div>

      {/* Home bar */}
      <div
        className="flex items-center justify-center shrink-0"
        style={{ height: 20, backgroundColor: "#ffffff" }}
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

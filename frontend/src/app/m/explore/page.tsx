"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  User,
  Sparkles,
  Clock3,
  MapPin,
  Plus,
} from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";
import QuickMatchPopup from "@/components/home/QuickMatchPopup";
import AiPlacePopup from "@/components/home/AiPlacePopup";

export default function ExplorePage() {
  const router = useRouter();
  const [quickMatchOpen, setQuickMatchOpen] = useState(false);
  const [aiPlaceOpen, setAiPlaceOpen] = useState(false);
  return (
    <div
      style={{
        width: 390,
        height: 1090,
        overflow: "clip",
        background: "#ffffffff",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 56,
          minHeight: 56,
          background: "#4f46e5",
          padding: "0 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 20,
            fontWeight: 700,
            color: "#ffffff",
          }}
        >
          매듭
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Bell size={22} color="#ffffff" style={{ cursor: "pointer" }} onClick={() => router.push("/m/notifications")} />
          <User size={22} color="#ffffff" style={{ cursor: "pointer" }} onClick={() => router.push("/m/profile")} />
        </div>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          background: "#f8fafc",
          padding: 20,
          gap: 20,
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* A) AI Recommend Card */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 16,
            gap: 12,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={18} color="#4f46e5" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 16,
                fontWeight: 700,
                color: "#1e293b",
              }}
            >
              AI 추천 모임
            </span>
          </div>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 400,
              color: "#64748b",
            }}
          >
            관심사와 일정에 맞는 모임을 추천해드려요
          </span>
          <div style={{ display: "flex", gap: 10 }}>
            {/* Card 1 - 빠른 모임 매칭 */}
            <div
              onClick={() => setQuickMatchOpen(true)}
              style={{
                flex: 1,
                borderRadius: 12,
                background: "linear-gradient(-220deg, #4f46e5, #7c3aed)",
                padding: 12,
                gap: 8,
                display: "flex",
                flexDirection: "column",
                cursor: "pointer",
              }}
            >
              <Clock3 size={20} color="#ffffff" />
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#ffffff",
                }}
              >
                빠른 모임 매칭
              </span>
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 11,
                  fontWeight: 400,
                  color: "#ffffffcc",
                }}
              >
                지금 가능한 친구와 바로 만나기
              </span>
            </div>
            {/* Card 2 - AI 장소 추천 */}
            <div
              onClick={() => setAiPlaceOpen(true)}
              style={{
                flex: 1,
                borderRadius: 12,
                background: "linear-gradient(-215deg, #0ea5e9, #22c55e)",
                padding: 12,
                gap: 8,
                display: "flex",
                flexDirection: "column",
                cursor: "pointer",
              }}
            >
              <MapPin size={20} color="#ffffff" />
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#ffffff",
                }}
              >
                AI 장소 추천
              </span>
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 11,
                  fontWeight: 400,
                  color: "#ffffffcc",
                }}
              >
                모임에 딱 맞는 장소 찾기
              </span>
            </div>
          </div>
        </div>

        {/* B) Upcoming Card */}
        <div
          onClick={() => router.push("/m/chat/schedule")}
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 16,
            gap: 12,
            display: "flex",
            flexDirection: "column",
            cursor: "pointer",
          }}
        >
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 14,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            가장 임박한 모임
          </span>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 16,
                  fontWeight: 700,
                  color: "#1e293b",
                }}
              >
                팀 프로젝트 회의
              </span>
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 12,
                  fontWeight: 400,
                  color: "#64748b",
                }}
              >
                4월 6일 (일) 오후 3:00
              </span>
            </div>
            <div
              style={{
                borderRadius: 20,
                background: "#4f46e5",
                padding: "6px 12px",
              }}
            >
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "#ffffff",
                }}
              >
                D-2
              </span>
            </div>
          </div>
          {/* Avatar row */}
          <div style={{ display: "flex", alignItems: "center" }}>
            {[
              { bg: "#818cf8" },
              { bg: "#f472b6" },
              { bg: "#fb923c" },
            ].map((avatar, i) => (
              <div
                key={i}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: avatar.bg,
                  border: "2px solid #ffffff",
                  marginLeft: i === 0 ? 0 : -8,
                  zIndex: 3 - i,
                }}
              />
            ))}
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: "#e2e8f0",
                border: "2px solid #ffffff",
                marginLeft: -8,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 0,
              }}
            >
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 10,
                  fontWeight: 600,
                  color: "#64748b",
                }}
              >
                +2
              </span>
            </div>
          </div>
        </div>

        {/* C) Joined Meetings Section */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 16,
            gap: 12,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 14,
                fontWeight: 700,
                color: "#1e293b",
              }}
            >
              참여중인 모임
            </span>
            <span
              onClick={() => router.push("/m/chat")}
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 500,
                color: "#4f46e5",
                cursor: "pointer",
              }}
            >
              전체보기
            </span>
          </div>

          {/* Meeting Items */}
          {[
            {
              name: "기획 스터디",
              chipText: "진행중",
              chipColor: "#4f46e5",
              chipBg: "#eef2ff",
              desc: "매주 화요일 20:00 · 온라인",
              members: "3 / 6명 참여",
              dday: "D-3",
              ddayColor: "#ef4444",
            },
            {
              name: "주말 등산 모임",
              chipText: "참여예정",
              chipColor: "#059669",
              chipBg: "#ecfdf5",
              desc: "매달 둘째 토요일 · 남한산",
              members: "5 / 10명 참여",
              dday: "D-10",
              ddayColor: "#3b82f6",
            },
            {
              name: "영어 회화 모임",
              chipText: "모집중",
              chipColor: "#ea580c",
              chipBg: "#fff7ed",
              desc: "매주 수요일 19:00 · 강남",
              members: "7 / 12명 참여",
              dday: "D-7",
              ddayColor: "#ea580c",
            },
          ].map((item, i) => (
            <div
              key={i}
              onClick={() => router.push("/m/chat/schedule")}
              style={{
                borderRadius: 12,
                background: "#f9fafb",
                border: "1px solid #e5e7eb",
                padding: 12,
                gap: 8,
                display: "flex",
                flexDirection: "column",
                cursor: "pointer",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 15,
                    fontWeight: 600,
                    color: "#111827",
                  }}
                >
                  {item.name}
                </span>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 11,
                    fontWeight: 500,
                    color: item.chipColor,
                    background: item.chipBg,
                    borderRadius: 999,
                    padding: "3px 8px",
                  }}
                >
                  {item.chipText}
                </span>
              </div>
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 11,
                  fontWeight: 400,
                  color: "#6b7280",
                }}
              >
                {item.desc}
              </span>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 11,
                    fontWeight: 400,
                    color: "#6b7280",
                  }}
                >
                  {item.members}
                </span>
                <span
                  style={{
                    fontFamily: "Inter, sans-serif",
                    fontSize: 12,
                    fontWeight: 600,
                    color: item.ddayColor,
                  }}
                >
                  {item.dday}
                </span>
              </div>
            </div>
          ))}

          {/* Create Button */}
          <button
            onClick={() => router.push("/m/meeting/new")}
            style={{
              borderRadius: 10,
              background: "#4f46e5",
              height: 40,
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              border: "none",
              cursor: "pointer",
            }}
          >
            <Plus size={16} color="#ffffff" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#ffffff",
              }}
            >
              새 모임 만들기
            </span>
          </button>
        </div>
      </div>

      {/* Tab Bar */}
      <MobileTabBar active="홈" variant="pill" />

      {/* Popups */}
      <QuickMatchPopup open={quickMatchOpen} onClose={() => setQuickMatchOpen(false)} />
      <AiPlacePopup open={aiPlaceOpen} onClose={() => setAiPlaceOpen(false)} />
    </div>
  );
}

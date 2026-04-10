"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  EllipsisVertical,
  Sparkles,
  Calendar,
  MapPin,
  Users,
  Send,
  TriangleAlert,
  CalendarDays,
  Megaphone,
} from "lucide-react";

export default function AiChatPage() {
  const router = useRouter();

  return (
    <div
      style={{
        width: 390,
        height: 844,
        overflow: "clip",
        background: "#ffffff",
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
          background: "#ffffff",
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <ArrowLeft
          size={24}
          color="#1e293b"
          style={{ cursor: "pointer" }}
          onClick={() => router.back()}
        />
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
          }}
        >
          <Sparkles size={20} color="#4f46e5" />
          <span style={{ fontSize: 17, fontWeight: 700, color: "#1e293b" }}>AI 비서</span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "#4f46e5",
              background: "#eef2ff",
              borderRadius: 10,
              padding: "0 8px",
              height: 20,
              display: "flex",
              alignItems: "center",
            }}
          >
            Beta
          </span>
        </div>
        <EllipsisVertical size={24} color="#64748b" style={{ cursor: "pointer" }} onClick={() => alert("AI 비서 설정은 준비 중입니다")} />
      </div>

      {/* Message Area */}
      <div
        style={{
          flex: 1,
          background: "#f8fafc",
          padding: 16,
          gap: 16,
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* Welcome Card */}
        <div
          style={{
            borderRadius: 16,
            background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
            padding: 20,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <Sparkles size={28} color="#ffffff" />
          <span style={{ fontSize: 18, fontWeight: 700, color: "#ffffff" }}>
            안녕하세요! AI 비서입니다
          </span>
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", lineHeight: 1.5 }}>
            {"모임 일정 조율, 장소 추천, 빠른 매칭 등\n무엇이든 도와드릴게요 😊"}
          </span>
        </div>

        {/* Quick Actions */}
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { icon: Calendar, label: "일정 잡기", color: "#4f46e5" },
            { icon: MapPin, label: "장소 추천", color: "#0ea5e9" },
            { icon: Users, label: "모임 매칭", color: "#7c3aed" },
          ].map((btn) => (
            <div
              key={btn.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                borderRadius: 20,
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                cursor: "pointer",
              }}
            >
              <btn.icon size={14} color={btn.color} />
              <span style={{ fontSize: 13, color: btn.color }}>{btn.label}</span>
            </div>
          ))}
        </div>

        {/* AI Greeting */}
        <div style={{ display: "flex", gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Sparkles size={16} color="#ffffff" />
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, color: "#94a3b8" }}>AI 비서</span>
            <div
              style={{
                borderRadius: "0 16px 16px 16px",
                background: "#ffffff",
                border: "0.5px solid #e2e8f0",
                padding: 12,
              }}
            >
              <span style={{ fontSize: 14, color: "#1e293b" }}>
                안녕하세요! 무엇이든 물어보세요 😊
              </span>
            </div>
            <span style={{ fontSize: 11, color: "#94a3b8" }}>오전 9:30</span>
          </div>
        </div>

        {/* User Message */}
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
            <div
              style={{
                borderRadius: "16px 0 16px 16px",
                background: "#4f46e5",
                padding: 12,
              }}
            >
              <span style={{ fontSize: 14, color: "#ffffff" }}>
                {"지금 기억해야 할 공지나\n중요한 일정 있어?"}
              </span>
            </div>
            <span style={{ fontSize: 11, color: "#94a3b8" }}>오전 9:31</span>
          </div>
        </div>

        {/* AI Response with reminders */}
        <div style={{ display: "flex", gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Sparkles size={16} color="#ffffff" />
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, color: "#94a3b8" }}>AI 비서</span>
            <div
              style={{
                borderRadius: "0 16px 16px 16px",
                background: "#ffffff",
                border: "0.5px solid #e2e8f0",
                padding: 14,
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              <span style={{ fontSize: 14, color: "#1e293b" }}>
                네! 확인해봤어요. 지금 기억하셔야 할 것들이 있어요 📋
              </span>

              {/* Reminder 1 - Urgent */}
              <div
                style={{
                  borderRadius: 12,
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  padding: 12,
                  display: "flex",
                  gap: 10,
                }}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: "#fee2e2",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <TriangleAlert size={16} color="#ef4444" />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: "#ef4444",
                        background: "#fee2e2",
                        borderRadius: 4,
                        padding: "1px 6px",
                      }}
                    >
                      긴급
                    </span>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                    졸업 프로젝트 중간발표
                  </span>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    발표자료 제출 마감 1시간 전
                  </span>
                </div>
              </div>

              {/* Reminder 2 - Vote */}
              <div
                style={{
                  borderRadius: 12,
                  background: "#eff6ff",
                  border: "1px solid #bfdbfe",
                  padding: 12,
                  display: "flex",
                  gap: 10,
                }}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: "#dbeafe",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <CalendarDays size={16} color="#3b82f6" />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: "#3b82f6",
                        background: "#dbeafe",
                        borderRadius: 4,
                        padding: "1px 6px",
                      }}
                    >
                      투표
                    </span>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                    주말 등산 모임 장소 투표
                  </span>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    아직 투표하지 않았어요 — 3명 참여 중
                  </span>
                </div>
              </div>

              {/* Reminder 3 - Announcement */}
              <div
                style={{
                  borderRadius: 12,
                  background: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  padding: 12,
                  display: "flex",
                  gap: 10,
                }}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: "#dcfce7",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Megaphone size={16} color="#16a34a" />
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: "#16a34a",
                        background: "#dcfce7",
                        borderRadius: 4,
                        padding: "1px 6px",
                      }}
                    >
                      공지
                    </span>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                    이번 주 주제: 여행 영어
                  </span>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    모임장 박지호님이 공지했어요
                  </span>
                </div>
              </div>

              <span style={{ fontSize: 13, color: "#64748b" }}>
                총 3건의 알림이 있어요. 자세히 볼까요?
              </span>
            </div>
            <span style={{ fontSize: 11, color: "#94a3b8" }}>오전 9:31</span>
          </div>
        </div>
      </div>

      {/* Input Bar */}
      <div
        style={{
          height: 60,
          background: "#ffffff",
          padding: "0 12px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <div
          style={{
            flex: 1,
            height: 40,
            borderRadius: 20,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "0 16px",
            display: "flex",
            alignItems: "center",
          }}
        >
          <span style={{ fontSize: 14, color: "#94a3b8" }}>AI 비서에게 물어보세요...</span>
        </div>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            background: "#4f46e5",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <Send size={18} color="#ffffff" />
        </div>
      </div>

      {/* Home Indicator */}
      <div
        style={{
          height: 20,
          background: "#ffffff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{ width: 134, height: 5, borderRadius: 3, background: "#000000" }} />
      </div>
    </div>
  );
}

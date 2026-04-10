"use client";

import { useState, useEffect } from "react";
import { apiFetchWithFallback } from "@/lib/api";
import {
  Users,
  Search,
  CalendarClock,
  CalendarDays,
  Vote,
  Sparkles,
  MapPin,
  PenLine,
  ChevronRight,
} from "lucide-react";

interface Member {
  name: string;
  color: string;
}

const AVATAR_PALETTE = [
  "#818cf8", "#f472b6", "#fb923c", "#34d399", "#fbbf24",
  "#60a5fa", "#a78bfa", "#f87171", "#4ade80", "#facc15",
];

import type { FriendInfo } from "@/types";

interface Props {
  invitedMembers: Set<string>;
  scheduleMethod: "ai" | "manual" | "vote";
  placeMethod: "ai" | "manual" | "vote";
  onToggleMember: (name: string) => void;
  onScheduleMethodChange: (v: "ai" | "manual" | "vote") => void;
  onPlaceMethodChange: (v: "ai" | "manual" | "vote") => void;
  onCancel: () => void;
  onCreate: () => void;
}

export default function CreateInviteSettings({
  invitedMembers,
  scheduleMethod,
  placeMethod,
  onToggleMember,
  onScheduleMethodChange,
  onPlaceMethodChange,
  onCancel,
  onCreate,
}: Props) {
  const selectedCount = invitedMembers.size;
  const [members, setMembers] = useState<Member[]>([]);
  const [loadingFriends, setLoadingFriends] = useState(true);

  useEffect(() => {
    apiFetchWithFallback<FriendInfo[]>("/api/v1/users/friends", [])
      .then((friends) => {
        setMembers(
          friends.map((f, i) => ({
            name: f.name,
            color: AVATAR_PALETTE[i % AVATAR_PALETTE.length],
          }))
        );
      })
      .finally(() => setLoadingFriends(false));
  }, []);

  return (
    <div
      style={{
        width: 666,
        borderRadius: 20,
        border: "1px solid #e2e8f0",
        boxShadow: "0 4px 3.5px rgba(0,0,0,0.08)",
        background: "#fff",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "14px 24px",
          background: "linear-gradient(135deg, #4338ca, #4f46e5)",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <Users style={{ width: 22, height: 22, color: "#ffffff" }} />
        <span
          style={{
            fontSize: 19,
            fontWeight: 500,
            color: "#ffffff",
            letterSpacing: 0.5,
          }}
        >
          참여자 및 설정
        </span>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 0,
        }}
      >
        {/* 참여자 초대 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <label style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>
            참여자 초대
          </label>

          {/* 검색 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 14px",
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              background: "#ffffff",
            }}
          >
            <Search style={{ width: 16, height: 16, color: "#94a3b8" }} />
            <span style={{ fontSize: 13, fontWeight: 400, color: "#94a3b8" }}>
              이름 또는 이메일로 검색
            </span>
          </div>

          {/* 멤버 리스트 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {loadingFriends ? (
              <span style={{ fontSize: 13, color: "#94a3b8", padding: "8px 14px" }}>
                친구 목록 불러오는 중...
              </span>
            ) : members.length === 0 ? (
              <span style={{ fontSize: 13, color: "#94a3b8", padding: "8px 14px" }}>
                아직 친구가 없어요
              </span>
            ) : (
              members.map((member) => {
                const isSelected = invitedMembers.has(member.name);
                return (
                  <div
                    key={member.name}
                    onClick={() => onToggleMember(member.name)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      padding: "8px 14px",
                      borderRadius: 10,
                      cursor: "pointer",
                      background: isSelected ? "#eef2ff" : "transparent",
                    }}
                  >
                    {/* Avatar */}
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: "50%",
                        background: member.color,
                        flexShrink: 0,
                      }}
                    />
                    {/* Name */}
                    <span
                      style={{
                        flex: 1,
                        fontSize: 14,
                        fontWeight: 500,
                        color: "#111827",
                      }}
                    >
                      {member.name}
                    </span>
                    {/* Checkbox */}
                    <div
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: 6,
                        border: isSelected ? "none" : "2px solid #d1d5db",
                        background: isSelected ? "#4f46e5" : "#ffffff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      {isSelected && (
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path
                            d="M3 7L6 10L11 4"
                            stroke="#ffffff"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* 선택됨 카운트 */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "0 14px" }}>
            <Users style={{ width: 16, height: 16, color: "#4f46e5" }} />
            <span style={{ fontSize: 13, fontWeight: 500, color: "#4f46e5" }}>
              {selectedCount}명 선택됨
            </span>
          </div>
        </div>

        {/* 구분선 */}
        <div style={{ height: 1, background: "#e2e8f0", margin: "20px 0" }} />

        {/* 일정 설정 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>
            일정 설정
          </label>
          <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>
            AI가 참여자 일정을 분석하여 최적 시간을 추천합니다
          </span>

          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
            {/* AI 자동 추천 */}
            <div
              onClick={() => onScheduleMethodChange("ai")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "12px 16px",
                borderRadius: 12,
                border: scheduleMethod === "ai" ? "2px solid #4f46e5" : "1px solid #e2e8f0",
                background: scheduleMethod === "ai" ? "#eef2ff" : "#ffffff",
                cursor: "pointer",
              }}
            >
              <CalendarClock style={{ width: 18, height: 18, color: scheduleMethod === "ai" ? "#4f46e5" : "#94a3b8" }} />
              <span
                style={{
                  flex: 1,
                  fontSize: 14,
                  fontWeight: 500,
                  color: scheduleMethod === "ai" ? "#4f46e5" : "#374151",
                }}
              >
                AI 자동 추천
              </span>
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  border: scheduleMethod === "ai" ? "6px solid #4f46e5" : "2px solid #d1d5db",
                  background: "#ffffff",
                  flexShrink: 0,
                }}
              />
            </div>

            {/* 직접 날짜 선택 */}
            <div
              onClick={() => onScheduleMethodChange("manual")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "12px 16px",
                borderRadius: 12,
                border: scheduleMethod === "manual" ? "2px solid #4f46e5" : "1px solid #e2e8f0",
                background: scheduleMethod === "manual" ? "#eef2ff" : "#ffffff",
                cursor: "pointer",
              }}
            >
              <CalendarDays style={{ width: 18, height: 18, color: scheduleMethod === "manual" ? "#4f46e5" : "#94a3b8" }} />
              <span
                style={{
                  flex: 1,
                  fontSize: 14,
                  fontWeight: 500,
                  color: scheduleMethod === "manual" ? "#4f46e5" : "#374151",
                }}
              >
                직접 날짜 선택
              </span>
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  border: scheduleMethod === "manual" ? "6px solid #4f46e5" : "2px solid #d1d5db",
                  background: "#ffffff",
                  flexShrink: 0,
                }}
              />
            </div>

            {/* 투표로 결정 */}
            <div
              onClick={() => onScheduleMethodChange("vote")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "12px 16px",
                borderRadius: 12,
                border: scheduleMethod === "vote" ? "2px solid #4f46e5" : "1px solid #e2e8f0",
                background: scheduleMethod === "vote" ? "#eef2ff" : "#ffffff",
                cursor: "pointer",
              }}
            >
              <Vote style={{ width: 18, height: 18, color: scheduleMethod === "vote" ? "#4f46e5" : "#94a3b8" }} />
              <span
                style={{
                  flex: 1,
                  fontSize: 14,
                  fontWeight: 500,
                  color: scheduleMethod === "vote" ? "#4f46e5" : "#374151",
                }}
              >
                투표로 결정
              </span>
              <div
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  border: scheduleMethod === "vote" ? "6px solid #4f46e5" : "2px solid #d1d5db",
                  background: "#ffffff",
                  flexShrink: 0,
                }}
              />
            </div>
          </div>
        </div>

        {/* 구분선 */}
        <div style={{ height: 1, background: "#e2e8f0", margin: "20px 0" }} />

        {/* 장소 설정 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <label style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>
            장소 설정
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            {/* AI 추천 */}
            <div
              onClick={() => onPlaceMethodChange("ai")}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                padding: "16px 0",
                borderRadius: 14,
                border: placeMethod === "ai" ? "2px solid #4f46e5" : "1px solid #e2e8f0",
                background: placeMethod === "ai" ? "#eef2ff" : "#ffffff",
                cursor: "pointer",
              }}
            >
              <Sparkles style={{ width: 22, height: 22, color: placeMethod === "ai" ? "#4f46e5" : "#94a3b8" }} />
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: placeMethod === "ai" ? "#4f46e5" : "#64748b",
                }}
              >
                AI 추천
              </span>
            </div>

            {/* 직접 입력 */}
            <div
              onClick={() => onPlaceMethodChange("manual")}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                padding: "16px 0",
                borderRadius: 14,
                border: placeMethod === "manual" ? "2px solid #4f46e5" : "1px solid #e2e8f0",
                background: placeMethod === "manual" ? "#eef2ff" : "#ffffff",
                cursor: "pointer",
              }}
            >
              <MapPin style={{ width: 22, height: 22, color: placeMethod === "manual" ? "#4f46e5" : "#94a3b8" }} />
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: placeMethod === "manual" ? "#4f46e5" : "#64748b",
                }}
              >
                직접 입력
              </span>
            </div>

            {/* 투표 */}
            <div
              onClick={() => onPlaceMethodChange("vote")}
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                padding: "16px 0",
                borderRadius: 14,
                border: placeMethod === "vote" ? "2px solid #4f46e5" : "1px solid #e2e8f0",
                background: placeMethod === "vote" ? "#eef2ff" : "#ffffff",
                cursor: "pointer",
              }}
            >
              <Vote style={{ width: 22, height: 22, color: placeMethod === "vote" ? "#4f46e5" : "#94a3b8" }} />
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: placeMethod === "vote" ? "#4f46e5" : "#64748b",
                }}
              >
                투표
              </span>
            </div>
          </div>
        </div>

        {/* 구분선 */}
        <div style={{ height: 1, background: "#e2e8f0", margin: "20px 0" }} />

        {/* 하단 버튼 */}
        <div style={{ display: "flex", gap: 12 }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1,
              padding: "14px 0",
              borderRadius: 14,
              border: "1px solid #e2e8f0",
              background: "#ffffff",
              color: "#374151",
              fontSize: 15,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            }}
          >
            취소
          </button>
          <button
            onClick={onCreate}
            style={{
              flex: 1,
              padding: "14px 0",
              borderRadius: 14,
              border: "none",
              background: "linear-gradient(135deg, #4338ca, #4f46e5)",
              color: "#ffffff",
              fontSize: 15,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
            }}
          >
            모임 생성
            <ChevronRight style={{ width: 18, height: 18, color: "#ffffff" }} />
          </button>
        </div>
      </div>
    </div>
  );
}

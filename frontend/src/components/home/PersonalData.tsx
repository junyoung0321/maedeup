"use client";

import { useCallback, useEffect, useState } from "react";
import {
  User,
  Pencil,
  Calendar,
  Utensils,
  AlertCircle,
  MapPin,
  MapPinOff,
  Clock,
  Car,
  Sparkles,
  Plus,
  X,
  ChevronRight,
} from "lucide-react";
import PersonalDataModal from "./PersonalDataModal";
import { apiFetch } from "@/lib/api";
import type {
  PersonalDataCategory,
  PersonalDataSource,
  UserProfile,
} from "@/types";

interface CategoryConfig {
  key: PersonalDataCategory;
  label: string;
  icon: typeof Calendar;
  iconBg: string;
  iconColor: string;
  rowBg: string;
  borderColor: string;
}

const CATEGORY_CONFIG: CategoryConfig[] = [
  {
    key: "food_restrictions",
    label: "음식 제한",
    icon: AlertCircle,
    iconBg: "#fee2e2",
    iconColor: "#dc2626",
    rowBg: "#fef7f7",
    borderColor: "#fecaca",
  },
  {
    key: "food_preferences",
    label: "음식 취향",
    icon: Utensils,
    iconBg: "#fef3c7",
    iconColor: "#d97706",
    rowBg: "#fffbf5",
    borderColor: "#fde68a",
  },
  {
    key: "liked_areas",
    label: "선호 지역",
    icon: MapPin,
    iconBg: "#dcfce7",
    iconColor: "#16a34a",
    rowBg: "#f0fdf8",
    borderColor: "#bbf7d0",
  },
  {
    key: "disliked_areas",
    label: "회피 지역",
    icon: MapPinOff,
    iconBg: "#f1f5f9",
    iconColor: "#64748b",
    rowBg: "#f8fafc",
    borderColor: "#e2e8f0",
  },
  {
    key: "time_preference",
    label: "선호 시간",
    icon: Clock,
    iconBg: "#eef2ff",
    iconColor: "#4f46e5",
    rowBg: "#f6f8ff",
    borderColor: "#c7d2fe",
  },
  {
    key: "transport_mode",
    label: "이동 수단",
    icon: Car,
    iconBg: "#e0f2fe",
    iconColor: "#2563eb",
    rowBg: "#f0f9ff",
    borderColor: "#bae6fd",
  },
];

function summarizeValue(value: unknown): {
  text: string;
  badge?: string;
  empty: boolean;
} {
  if (value === null || value === undefined) {
    return { text: "아직 비어있음", empty: true };
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return { text: "아직 비어있음", empty: true };
    return {
      text: value.join(" · "),
      badge: value.length > 1 ? `${value.length}건` : undefined,
      empty: false,
    };
  }
  if (typeof value === "string") {
    if (value.trim() === "") return { text: "아직 비어있음", empty: true };
    return { text: value, empty: false };
  }
  return { text: String(value), empty: false };
}

function formatKstShort(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("ko-KR", {
      timeZone: "Asia/Seoul",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function PersonalData() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalFocusCategory, setModalFocusCategory] =
    useState<PersonalDataCategory | null>(null);

  const [receiptsCategory, setReceiptsCategory] =
    useState<PersonalDataCategory | null>(null);
  const [receipts, setReceipts] = useState<PersonalDataSource | null>(null);
  const [receiptsLoading, setReceiptsLoading] = useState(false);

  const [showOnboardingToast, setShowOnboardingToast] = useState(false);

  const fetchProfile = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch<UserProfile>("/api/v1/users/me");
      setProfile(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "프로필을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchProfile();
    // 탭 포커스 복귀 시 refetch — 모임 종료 후 홈 돌아오면 personal data 즉시 반영.
    const onVis = () => {
      if (!document.hidden) void fetchProfile();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [fetchProfile]);

  // 첫 ✨ 발견 시 1회성 안내 토스트 (per-browser localStorage).
  useEffect(() => {
    if (!profile) return;
    const isAi = profile.is_ai_filled ?? {};
    const anyAi = Object.values(isAi).some((v) => v === true);
    if (!anyAi) return;
    if (typeof window === "undefined") return;
    if (window.localStorage.getItem("first_ai_fill_seen")) return;
    setShowOnboardingToast(true);
    window.localStorage.setItem("first_ai_fill_seen", "1");
  }, [profile]);

  const openModal = (cat?: PersonalDataCategory) => {
    setModalFocusCategory(cat ?? null);
    setModalOpen(true);
  };

  const handleModalClose = (didSave: boolean) => {
    setModalOpen(false);
    setModalFocusCategory(null);
    if (didSave) void fetchProfile();
  };

  const showReceipts = useCallback(async (cat: PersonalDataCategory) => {
    setReceiptsCategory(cat);
    setReceiptsLoading(true);
    setReceipts(null);
    try {
      const data = await apiFetch<PersonalDataSource | null>(
        `/api/v1/users/me/personal-data/source/${cat}`,
      );
      setReceipts(data);
    } catch {
      setReceipts(null);
    } finally {
      setReceiptsLoading(false);
    }
  }, []);

  const closeReceipts = () => {
    setReceiptsCategory(null);
    setReceipts(null);
  };

  const isAiFilled = (cat: PersonalDataCategory): boolean =>
    Boolean(profile?.is_ai_filled?.[cat]);

  const valueOf = (cat: PersonalDataCategory): unknown => {
    if (!profile) return null;
    return (profile as unknown as Record<string, unknown>)[cat];
  };

  return (
    <>
      <div
        className="bg-white rounded-[20px] p-5 flex flex-col h-full border border-[#e2e8f0] shadow-[0_4px_10.5px_rgba(0,0,0,0.08)] relative"
        style={{ width: 414, minHeight: 490 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-[#7c3aed]" />
            <span className="text-[16px] font-bold text-[#1e293b]">
              내 개인 데이터
            </span>
          </div>
          <Pencil
            className="w-4 h-4 text-[#94a3b8] cursor-pointer hover:text-[#64748b]"
            onClick={() => openModal()}
          />
        </div>
        <p className="text-[11px] text-[#94a3b8] mb-3">
          어시스턴트가 참고하는 나의 정보 · ✨는 AI가 대화에서 학습한 항목
        </p>

        {/* 첫 AI 학습 toast */}
        {showOnboardingToast && (
          <div
            className="rounded-lg p-3 mb-3 flex items-start gap-2 animate-fade-in"
            style={{
              background: "linear-gradient(135deg, #ede9fe 0%, #f3e8ff 100%)",
              border: "1px solid #c4b5fd",
            }}
          >
            <Sparkles
              className="w-4 h-4 mt-0.5 shrink-0"
              style={{ color: "#7c3aed" }}
            />
            <div className="flex-1">
              <p className="text-[12px] font-semibold text-[#5b21b6] mb-0.5">
                AI가 대화에서 정보를 학습했습니다
              </p>
              <p className="text-[11px] text-[#6d28d9]">
                ✨ 마크가 붙은 항목 클릭 시 출처를 볼 수 있어요.
              </p>
            </div>
            <X
              className="w-4 h-4 text-[#7c3aed] cursor-pointer shrink-0"
              onClick={() => setShowOnboardingToast(false)}
            />
          </div>
        )}

        {/* loading / error */}
        {loading && (
          <div className="flex-1 flex items-center justify-center text-[12px] text-[#94a3b8]">
            불러오는 중…
          </div>
        )}
        {!loading && error && (
          <div className="flex-1 flex items-center justify-center text-[12px] text-[#ef4444] px-4 text-center">
            {error}
          </div>
        )}

        {/* 카드 리스트 */}
        {!loading && !error && profile && (
          <div className="flex flex-col gap-2 flex-1 overflow-y-auto pr-0.5">
            {/* Calendar — read-only 표시. 편집은 settings에서. */}
            <div
              className="flex items-center gap-3 rounded-[12px] px-3 py-2 border"
              style={{ backgroundColor: "#f8faff", borderColor: "#e0e7ff" }}
            >
              <div
                className="w-9 h-9 rounded-[10px] flex items-center justify-center shrink-0"
                style={{ backgroundColor: "#ede9fe" }}
              >
                <Calendar className="w-4 h-4" style={{ color: "#7c3aed" }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold text-[#1e293b]">
                  구글 캘린더
                </p>
                <p className="text-[11px] text-[#64748b] truncate">
                  {profile.calendar_consent
                    ? "연동됨 · 어시스턴트가 일정 참고"
                    : "미연동 — 설정에서 연결"}
                </p>
              </div>
              <span
                className="px-2 py-0.5 rounded-full text-[10px] font-medium shrink-0"
                style={{
                  backgroundColor: profile.calendar_consent
                    ? "#dcfce7"
                    : "#f1f5f9",
                  color: profile.calendar_consent ? "#16a34a" : "#94a3b8",
                }}
              >
                {profile.calendar_consent ? "연동" : "미연동"}
              </span>
            </div>

            {/* 6 personal data 카테고리 */}
            {CATEGORY_CONFIG.map((cfg) => {
              const Icon = cfg.icon;
              const v = valueOf(cfg.key);
              const summary = summarizeValue(v);
              const ai = isAiFilled(cfg.key);
              return (
                <div
                  key={cfg.key}
                  className="flex items-center gap-3 rounded-[12px] px-3 py-2 border cursor-pointer hover:shadow-sm transition-shadow"
                  style={{
                    backgroundColor: cfg.rowBg,
                    borderColor: cfg.borderColor,
                  }}
                  onClick={() => openModal(cfg.key)}
                >
                  <div
                    className="w-9 h-9 rounded-[10px] flex items-center justify-center shrink-0"
                    style={{ backgroundColor: cfg.iconBg }}
                  >
                    <Icon className="w-4 h-4" style={{ color: cfg.iconColor }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1">
                      <p className="text-[13px] font-semibold text-[#1e293b]">
                        {cfg.label}
                      </p>
                      {ai && (
                        <button
                          type="button"
                          aria-label="AI가 학습한 항목 — 클릭 시 출처"
                          onClick={(e) => {
                            e.stopPropagation();
                            void showReceipts(cfg.key);
                          }}
                          className="inline-flex items-center justify-center rounded-full hover:bg-purple-50"
                          style={{ width: 18, height: 18 }}
                        >
                          <Sparkles
                            className="w-3 h-3"
                            style={{ color: "#a855f7" }}
                          />
                        </button>
                      )}
                    </div>
                    <p
                      className={
                        summary.empty
                          ? "text-[11px] text-[#94a3b8] truncate italic"
                          : "text-[11px] text-[#64748b] truncate"
                      }
                    >
                      {summary.text}
                    </p>
                  </div>
                  {summary.badge && (
                    <span
                      className="px-2 py-0.5 rounded-full text-[10px] font-medium shrink-0"
                      style={{
                        backgroundColor: cfg.iconBg,
                        color: cfg.iconColor,
                      }}
                    >
                      {summary.badge}
                    </span>
                  )}
                  <ChevronRight className="w-3.5 h-3.5 text-[#cbd5e1] shrink-0" />
                </div>
              );
            })}
          </div>
        )}

        {/* Add 버튼 */}
        <button
          onClick={() => openModal()}
          className="mt-3 w-full flex items-center justify-center gap-1.5 py-2 rounded-[12px] border border-dashed border-[#c4b5fd] text-[#7c3aed] text-[12px] font-semibold hover:bg-purple-50 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          데이터 추가하기
        </button>
      </div>

      {/* Receipts 모달 */}
      {receiptsCategory && (
        <div
          onClick={closeReceipts}
          className="fixed inset-0 z-[120] flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.35)" }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl shadow-2xl w-[420px] p-5 relative"
          >
            <button
              onClick={closeReceipts}
              aria-label="close"
              className="absolute top-3 right-3 w-7 h-7 rounded-full bg-[#f1f5f9] flex items-center justify-center hover:bg-[#e2e8f0]"
            >
              <X className="w-3.5 h-3.5 text-[#64748b]" />
            </button>
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-4 h-4" style={{ color: "#a855f7" }} />
              <span className="text-[15px] font-bold text-[#1e293b]">
                AI 학습 출처
              </span>
            </div>
            {receiptsLoading && (
              <p className="text-[12px] text-[#94a3b8]">출처 불러오는 중…</p>
            )}
            {!receiptsLoading && !receipts && (
              <p className="text-[12px] text-[#94a3b8]">
                이 항목은 사용자가 직접 입력한 값이거나 출처 기록이 없습니다.
              </p>
            )}
            {!receiptsLoading && receipts && (
              <div className="flex flex-col gap-3">
                <div className="rounded-lg p-3 bg-[#faf5ff] border border-[#e9d5ff]">
                  <p className="text-[11px] text-[#7c3aed] font-medium mb-1">
                    {receipts.source_room_name ?? "모임"} ·{" "}
                    {formatKstShort(receipts.created_at)}
                  </p>
                  <p className="text-[13px] text-[#1e293b] leading-relaxed">
                    “{receipts.content.source_quote || "(원문 없음)"}”
                  </p>
                </div>
                <div className="text-[11px] text-[#64748b] leading-relaxed">
                  → 위 발화에서{" "}
                  <span className="font-semibold">
                    {Array.isArray(receipts.content.value)
                      ? receipts.content.value.join(", ")
                      : receipts.content.value}
                  </span>{" "}
                  를 추출했습니다 (확신도{" "}
                  {Math.round(receipts.content.confidence * 100)}%).
                </div>
                <p className="text-[10px] text-[#94a3b8]">
                  잘못된 정보면 카드 클릭 → 직접 수정 시 ✨가 사라지고 사용자
                  입력으로 변경됩니다.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {profile && (
        <PersonalDataModal
          open={modalOpen}
          onClose={handleModalClose}
          initialProfile={profile}
          focusCategory={modalFocusCategory}
        />
      )}

      <style jsx>{`
        @keyframes fade-in {
          from {
            opacity: 0;
            transform: translateY(-4px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }
      `}</style>
    </>
  );
}

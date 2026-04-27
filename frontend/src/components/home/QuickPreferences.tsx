"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  SlidersHorizontal,
  Shield,
  Calendar,
  Utensils,
  MapPin,
  Clock,
  ExternalLink,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { UserProfile } from "@/types";

type ShareToggleField =
  | "share_food_data"
  | "share_location_data"
  | "share_schedule_data";

interface ToggleConfig {
  field: ShareToggleField;
  label: string;
  desc: string;
  icon: typeof Calendar;
  iconColor: string;
}

// 4개 토글: 1개는 calendar_consent (read-only redirect), 3개는 share consent (PATCH).
const SHARE_TOGGLES: ToggleConfig[] = [
  {
    field: "share_food_data",
    label: "음식 정보 활용",
    desc: "음식 제한 / 취향 → 모임 장소 추천 반영",
    icon: Utensils,
    iconColor: "#d97706",
  },
  {
    field: "share_location_data",
    label: "지역 정보 활용",
    desc: "선호 / 회피 지역 → 위치 기반 점수",
    icon: MapPin,
    iconColor: "#16a34a",
  },
  {
    field: "share_schedule_data",
    label: "시간·이동수단 활용",
    desc: "선호 시간대 / 이동수단 → 슬롯 추천",
    icon: Clock,
    iconColor: "#4f46e5",
  },
];

export default function QuickPreferences() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingField, setPendingField] = useState<ShareToggleField | null>(null);

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
    const onVis = () => {
      if (!document.hidden) void fetchProfile();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [fetchProfile]);

  const handleToggle = async (field: ShareToggleField) => {
    if (!profile || pendingField !== null) return;
    const current = profile[field] ?? true;
    const next = !current;

    // optimistic — UI 즉시 반영, 실패 시 원복
    setProfile({ ...profile, [field]: next });
    setPendingField(field);
    try {
      await apiFetch("/api/v1/users/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({ [field]: next }),
      });
    } catch (e) {
      setProfile({ ...profile, [field]: current });
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setPendingField(null);
    }
  };

  const calendarOn = Boolean(profile?.calendar_consent);

  return (
    <div
      className="bg-white rounded-[20px] p-6 flex flex-col h-full border border-[#e2e8f0] shadow-[0_4px_10.5px_rgba(0,0,0,0.08)]"
      style={{ width: 414, minHeight: 490 }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <SlidersHorizontal className="w-4 h-4 text-[#4f46e5]" />
        <span className="text-[16px] font-bold text-[#1e293b]">
          빠른 선호 설정
        </span>
      </div>
      <p className="text-[11px] text-[#94a3b8] mb-4">
        어시스턴트가 모임 추천 시 어떤 데이터를 활용할지 카테고리별로 토글
      </p>

      <div className="h-px bg-[#e2e8f0] mb-4" />

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

      {!loading && !error && profile && (
        <div className="flex flex-col gap-4 flex-1">
          {/* Calendar — read-only state + click to settings (OAuth flow) */}
          <button
            onClick={() => router.push("/settings")}
            className="flex items-center justify-between text-left hover:bg-[#f8faff] -mx-2 px-2 py-1 rounded-lg transition-colors"
          >
            <div className="flex items-start gap-2.5">
              <Calendar
                className="w-4 h-4 mt-0.5 shrink-0"
                style={{ color: "#7c3aed" }}
              />
              <div>
                <p className="text-[13px] font-semibold text-[#1e293b] flex items-center gap-1">
                  캘린더 자동 동기화
                  <ExternalLink className="w-3 h-3 text-[#94a3b8]" />
                </p>
                <p className="text-[11px] text-[#94a3b8]">
                  {calendarOn
                    ? "구글 캘린더 연동됨 — 일정 자동 참고"
                    : "미연동 — 클릭해서 설정에서 연결"}
                </p>
              </div>
            </div>
            <div
              className="relative w-11 h-6 rounded-full shrink-0 ml-3"
              style={{ backgroundColor: calendarOn ? "#4f46e5" : "#e2e8f0" }}
            >
              <div
                className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow"
                style={{
                  transform: calendarOn ? "translateX(22px)" : "translateX(2px)",
                }}
              />
            </div>
          </button>

          {/* 3 share toggles */}
          {SHARE_TOGGLES.map((cfg) => {
            const Icon = cfg.icon;
            const isOn = profile[cfg.field] ?? true;
            const pending = pendingField === cfg.field;
            return (
              <div
                key={cfg.field}
                className="flex items-center justify-between"
              >
                <div className="flex items-start gap-2.5">
                  <Icon
                    className="w-4 h-4 mt-0.5 shrink-0"
                    style={{ color: cfg.iconColor }}
                  />
                  <div>
                    <p className="text-[13px] font-semibold text-[#1e293b]">
                      {cfg.label}
                    </p>
                    <p className="text-[11px] text-[#94a3b8]">{cfg.desc}</p>
                  </div>
                </div>
                <button
                  onClick={() => handleToggle(cfg.field)}
                  disabled={pending}
                  className="relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0 ml-3 disabled:opacity-60"
                  style={{
                    backgroundColor: isOn ? "#4f46e5" : "#e2e8f0",
                  }}
                  aria-pressed={isOn}
                  aria-label={`${cfg.label} ${isOn ? "끄기" : "켜기"}`}
                >
                  <div
                    className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200"
                    style={{
                      transform: isOn ? "translateX(22px)" : "translateX(2px)",
                    }}
                  />
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div className="h-px bg-[#e2e8f0] mt-4 mb-3" />

      {/* Privacy note */}
      <div className="flex items-start gap-2 bg-[#f8faff] rounded-[12px] px-3 py-2.5">
        <Shield className="w-3.5 h-3.5 text-[#4f46e5] shrink-0 mt-0.5" />
        <p className="text-[10px] text-[#64748b] leading-relaxed">
          개인 데이터는 본인 화면에만 보입니다. AI는 모임 추천 시 이 데이터를
          비공개로 합성하며, 토글이 OFF인 카테고리는 합성에서 제외됩니다.
        </p>
      </div>
    </div>
  );
}

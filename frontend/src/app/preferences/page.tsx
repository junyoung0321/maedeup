"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Calendar,
  AlertCircle,
  Utensils,
  MapPin,
  MapPinOff,
  Clock,
  Car,
  Sparkles,
  Shield,
  Save,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import {
  ChipListEditor,
  FreeformTextEditor,
  PresetMultiSelect,
  PresetSingleSelect,
} from "@/components/personal-data/Editors";
import type { UserProfile } from "@/types";

const FOOD_PREFERENCE_OPTIONS = [
  "한식",
  "양식",
  "일식",
  "중식",
  "카페",
  "술집",
  "기타",
] as const;
const TRANSPORT_OPTIONS = ["대중교통", "자차", "도보", "기타"] as const;

type FormState = {
  food_restrictions: string[];
  food_preferences: string[];
  liked_areas: string[];
  disliked_areas: string[];
  time_preference: string;
  transport_mode: string;
};

function buildFormState(p: UserProfile): FormState {
  return {
    food_restrictions: p.food_restrictions ?? [],
    food_preferences: p.food_preferences ?? [],
    liked_areas: p.liked_areas ?? [],
    disliked_areas: p.disliked_areas ?? [],
    time_preference: p.time_preference ?? "",
    transport_mode: p.transport_mode ?? "",
  };
}

function arrayEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

export default function PreferencesPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const initialFormRef = useRef<FormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pendingToggle, setPendingToggle] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch<UserProfile>("/api/v1/users/me");
      setProfile(data);
      const fs = buildFormState(data);
      setForm(fs);
      initialFormRef.current = fs;
    } catch (e) {
      setError(e instanceof Error ? e.message : "프로필을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/");
      return;
    }
    void fetchProfile();
  }, [authLoading, user, router, fetchProfile]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2400);
    return () => window.clearTimeout(t);
  }, [toast]);

  const changedFields = useMemo(() => {
    if (!form || !initialFormRef.current) return {};
    const initial = initialFormRef.current;
    const out: Partial<FormState> = {};
    if (!arrayEqual(form.food_restrictions, initial.food_restrictions))
      out.food_restrictions = form.food_restrictions;
    if (!arrayEqual(form.food_preferences, initial.food_preferences))
      out.food_preferences = form.food_preferences;
    if (!arrayEqual(form.liked_areas, initial.liked_areas))
      out.liked_areas = form.liked_areas;
    if (!arrayEqual(form.disliked_areas, initial.disliked_areas))
      out.disliked_areas = form.disliked_areas;
    if (form.time_preference !== initial.time_preference)
      out.time_preference = form.time_preference;
    if (form.transport_mode !== initial.transport_mode)
      out.transport_mode = form.transport_mode;
    return out;
  }, [form]);

  const hasChanges = Object.keys(changedFields).length > 0;

  const handleSave = async () => {
    if (saving || !hasChanges) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiFetch<UserProfile>(
        "/api/v1/users/me/preferences",
        {
          method: "PATCH",
          body: JSON.stringify(changedFields),
        },
      );
      setProfile(updated);
      const fs = buildFormState(updated);
      setForm(fs);
      initialFormRef.current = fs;
      setToast("저장됐습니다");
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  // Share consent toggles (ON/OFF — PATCH /me/preferences with single bool)
  const toggleShare = async (
    field: "share_food_data" | "share_location_data" | "share_schedule_data",
  ) => {
    if (!profile || pendingToggle) return;
    const current = profile[field] ?? true;
    const next = !current;
    setProfile({ ...profile, [field]: next });
    setPendingToggle(field);
    try {
      await apiFetch("/api/v1/users/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({ [field]: next }),
      });
    } catch (e) {
      setProfile({ ...profile, [field]: current });
      setError(e instanceof Error ? e.message : "토글 저장 실패");
    } finally {
      setPendingToggle(null);
    }
  };

  // Calendar consent toggle (PATCH /me/consent — JWT 갱신)
  const toggleCalendar = async () => {
    if (!profile || pendingToggle) return;
    const current = Boolean(profile.calendar_consent);
    const next = !current;
    setProfile({ ...profile, calendar_consent: next });
    setPendingToggle("calendar_consent");
    try {
      const resp = await apiFetch<{ token: string; calendar_consent: boolean }>(
        "/api/v1/users/me/consent",
        { method: "PATCH", body: JSON.stringify({ calendar_consent: next }) },
      );
      if (typeof window !== "undefined" && resp.token) {
        window.localStorage.setItem("auth_token", resp.token);
      }
      setProfile((p) =>
        p ? { ...p, calendar_consent: resp.calendar_consent } : p,
      );
    } catch (e) {
      setProfile((p) => (p ? { ...p, calendar_consent: current } : p));
      setError(e instanceof Error ? e.message : "캘린더 토글 실패");
    } finally {
      setPendingToggle(null);
    }
  };

  if (authLoading || loading || !form || !profile) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Header />
        <main className="mx-auto max-w-[860px] px-4 sm:px-6 py-8">
          <p className="text-sm text-slate-400">불러오는 중…</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="mx-auto max-w-[860px] px-4 sm:px-6 py-8 sm:py-12 flex flex-col gap-6 pb-32">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold text-slate-900">
            선호도 관리
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            AI가 모임 추천 시 활용하는 개인 데이터를 직접 편집합니다. ✨ 마크는 AI가
            대화에서 학습한 항목 — 직접 수정하면 ✨가 사라지고 사용자 입력으로 변경됩니다.
          </p>
        </div>

        {/* AI 활용 동의 (toggles) */}
        <Section title="AI 활용 동의" icon={Shield} iconColor="#4f46e5">
          <ToggleRow
            label="캘린더 자동 동기화"
            desc={
              profile.calendar_consent
                ? "구글 캘린더 일정 → AI 추천에 반영"
                : "AI 추천 시 캘린더 미참고"
            }
            on={profile.calendar_consent}
            disabled={pendingToggle === "calendar_consent"}
            onToggle={toggleCalendar}
          />
          <ToggleRow
            label="음식 정보 활용"
            desc="음식 제한 / 취향 → 모임 장소 추천 반영"
            on={profile.share_food_data ?? true}
            disabled={pendingToggle === "share_food_data"}
            onToggle={() => void toggleShare("share_food_data")}
          />
          <ToggleRow
            label="지역 정보 활용"
            desc="선호 / 회피 지역 → 위치 기반 점수"
            on={profile.share_location_data ?? true}
            disabled={pendingToggle === "share_location_data"}
            onToggle={() => void toggleShare("share_location_data")}
          />
          <ToggleRow
            label="시간·이동수단 활용"
            desc="선호 시간대 / 이동수단 → 슬롯 추천"
            on={profile.share_schedule_data ?? true}
            disabled={pendingToggle === "share_schedule_data"}
            onToggle={() => void toggleShare("share_schedule_data")}
          />
        </Section>

        {/* 6 카테고리 — 풀 페이지 편집 */}
        <Section title="음식 정보" icon={Utensils} iconColor="#d97706">
          <ChipListEditor
            label={
              aiBadge("음식 제한", profile.is_ai_filled?.food_restrictions)
                .label
            }
            hint="알레르기 / 못 먹는 음식 — 예: 갑각류 알레르기, 매운 거"
            values={form.food_restrictions}
            onChange={(next) =>
              setForm({ ...form, food_restrictions: next })
            }
            accentColor="#dc2626"
          />
          <PresetMultiSelect
            label={
              aiBadge("음식 취향", profile.is_ai_filled?.food_preferences)
                .label
            }
            options={FOOD_PREFERENCE_OPTIONS as readonly string[]}
            values={form.food_preferences}
            onToggle={(v) =>
              setForm({
                ...form,
                food_preferences: form.food_preferences.includes(v)
                  ? form.food_preferences.filter((x) => x !== v)
                  : [...form.food_preferences, v],
              })
            }
            accentColor="#d97706"
            accentBg="#fef3c7"
          />
        </Section>

        <Section title="지역 정보" icon={MapPin} iconColor="#16a34a">
          <ChipListEditor
            label={
              aiBadge("선호 지역", profile.is_ai_filled?.liked_areas).label
            }
            hint="자주 가고 싶은 동네 — 예: 강남, 홍대, 신촌"
            values={form.liked_areas}
            onChange={(next) => setForm({ ...form, liked_areas: next })}
            accentColor="#16a34a"
          />
          <ChipListEditor
            label={
              aiBadge("회피 지역", profile.is_ai_filled?.disliked_areas).label
            }
            hint="멀어서 / 안 가고 싶은 지역 — 예: 분당, 일산"
            values={form.disliked_areas}
            onChange={(next) => setForm({ ...form, disliked_areas: next })}
            accentColor="#64748b"
          />
        </Section>

        <Section title="시간·이동" icon={Clock} iconColor="#4f46e5">
          <FreeformTextEditor
            label={
              aiBadge("선호 시간대", profile.is_ai_filled?.time_preference)
                .label
            }
            hint='자유 텍스트 — 예: "주말 오후", "평일 저녁 7시 이후", "월수금 점심"'
            value={form.time_preference}
            onChange={(v) => setForm({ ...form, time_preference: v })}
            accentColor="#4f46e5"
          />
          <PresetSingleSelect
            label={
              aiBadge("이동 수단", profile.is_ai_filled?.transport_mode).label
            }
            options={TRANSPORT_OPTIONS as readonly string[]}
            value={form.transport_mode}
            onChange={(v) => setForm({ ...form, transport_mode: v })}
            accentColor="#2563eb"
            accentBg="#e0f2fe"
          />
        </Section>

        {error && <p className="text-sm text-red-500">{error}</p>}
      </main>

      {/* Sticky save bar */}
      {hasChanges && (
        <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur border-t border-slate-200 shadow-[0_-4px_20px_rgba(0,0,0,0.06)]">
          <div className="mx-auto max-w-[860px] px-4 sm:px-6 py-3 flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">
              {Object.keys(changedFields).length}개 항목 변경 — 직접 수정한 항목은 ✨가
              사라집니다
            </p>
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold hover:bg-[#4338ca] disabled:bg-[#c7d2fe] disabled:cursor-not-allowed"
            >
              <Save className="w-4 h-4" />
              {saving ? "저장 중…" : "저장하기"}
            </button>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed top-20 right-4 z-50 bg-emerald-600 text-white text-sm font-medium px-4 py-2 rounded-xl shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}

function aiBadge(label: string, isAi?: boolean): { label: React.ReactNode } {
  if (!isAi) return { label };
  return {
    label: (
      <span className="inline-flex items-center gap-1.5">
        {label}
        <Sparkles className="w-3.5 h-3.5" style={{ color: "#a855f7" }} />
      </span>
    ),
  };
}

function Section({
  title,
  icon: Icon,
  iconColor,
  children,
}: {
  title: string;
  icon: typeof Calendar;
  iconColor: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6 flex flex-col gap-5">
      <div className="flex items-center gap-2">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: `${iconColor}1a` }}
        >
          <Icon className="w-4 h-4" style={{ color: iconColor }} />
        </div>
        <h2 className="text-base sm:text-lg font-bold text-slate-900">{title}</h2>
      </div>
      <div className="flex flex-col gap-6">{children}</div>
    </section>
  );
}

function ToggleRow({
  label,
  desc,
  on,
  disabled,
  onToggle,
}: {
  label: string;
  desc: string;
  on: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900">{label}</p>
        <p className="text-[11px] text-slate-500 mt-0.5">{desc}</p>
      </div>
      <button
        onClick={onToggle}
        disabled={disabled}
        className="relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0 disabled:opacity-60"
        style={{ backgroundColor: on ? "#4f46e5" : "#e2e8f0" }}
        aria-pressed={on}
      >
        <div
          className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200"
          style={{ transform: on ? "translateX(22px)" : "translateX(2px)" }}
        />
      </button>
    </div>
  );
}

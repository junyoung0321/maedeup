"use client";

import { useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import { apiFetch } from "@/lib/api";
import type { UserProfile } from "@/types";

const FOOD_OPTIONS = ["한식", "양식", "일식", "중식", "카페", "술집", "기타"] as const;

interface FormState {
  home_base: string;
  food_preferences: string[];
  food_preference_note: string;
}

type ToastState =
  | { type: "success"; message: string }
  | { type: "error"; message: string }
  | null;

const EMPTY_FORM: FormState = {
  home_base: "",
  food_preferences: [],
  food_preference_note: "",
};

export default function UserPreferencesForm() {
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState>(null);

  useEffect(() => {
    let active = true;

    const fetchProfile = async () => {
      try {
        setLoading(true);
        setLoadError(null);
        const profile = await apiFetch<UserProfile>("/api/v1/users/me");
        if (!active) return;
        setForm({
          home_base: profile.home_base ?? "",
          food_preferences: profile.food_preferences ?? [],
          food_preference_note: profile.food_preference_note ?? "",
        });
      } catch (error) {
        if (!active) return;
        setLoadError(error instanceof Error ? error.message : "설정 정보를 불러오지 못했습니다.");
      } finally {
        if (active) setLoading(false);
      }
    };

    void fetchProfile();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2400);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const toggleFoodPreference = (value: string) => {
    setForm((current) => ({
      ...current,
      food_preferences: current.food_preferences.includes(value)
        ? current.food_preferences.filter((item) => item !== value)
        : [...current.food_preferences, value],
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setSaveError(null);
      const updated = await apiFetch<UserProfile>("/api/v1/users/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({
          home_base: form.home_base.trim() || null,
          food_preferences: form.food_preferences,
          food_preference_note: form.food_preference_note.trim() || null,
        }),
      });

      setForm({
        home_base: updated.home_base ?? "",
        food_preferences: updated.food_preferences ?? [],
        food_preference_note: updated.food_preference_note ?? "",
      });
      setToast({ type: "success", message: "설정이 저장되었습니다." });
    } catch (error) {
      const message = error instanceof Error ? error.message : "설정 저장에 실패했습니다.";
      setSaveError(message);
      setToast({ type: "error", message });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center text-slate-500 shadow-sm">
        설정 정보를 불러오는 중입니다...
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="rounded-3xl border border-rose-200 bg-rose-50 p-8 text-sm text-rose-700 shadow-sm">
        <p className="font-medium">설정 정보를 불러오지 못했습니다.</p>
        <p className="mt-2">{loadError}</p>
      </div>
    );
  }

  return (
    <div className="relative rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
      {toast && (
        <div
          className={`absolute right-6 top-6 rounded-2xl px-4 py-3 text-sm font-medium shadow-lg ${
            toast.type === "success"
              ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border border-rose-200 bg-rose-50 text-rose-700"
          }`}
        >
          {toast.message}
        </div>
      )}

      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-slate-900">선호도 설정</h2>
        <p className="mt-2 text-sm text-slate-500">자주 가는 지역과 음식 취향을 저장해 두면 추천에 활용할 수 있습니다.</p>
      </div>

      <div className="space-y-8">
        <section>
          <label htmlFor="home_base" className="mb-3 block text-sm font-medium text-slate-700">
            홈 베이스
          </label>
          <input
            id="home_base"
            type="text"
            value={form.home_base}
            onChange={(event) => setForm((current) => ({ ...current, home_base: event.target.value }))}
            placeholder="주소 (예: 서울 강남구)"
            className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-primary-600 focus:ring-2 focus:ring-primary-100"
          />
        </section>

        <section>
          <span className="mb-3 block text-sm font-medium text-slate-700">음식 취향</span>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {FOOD_OPTIONS.map((option) => {
              const checked = form.food_preferences.includes(option);
              return (
                <label
                  key={option}
                  className={`flex cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition ${
                    checked
                      ? "border-primary-600 bg-primary-50 text-primary-700"
                      : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleFoodPreference(option)}
                    className="h-4 w-4 accent-[#4f46e5]"
                  />
                  <span>{option}</span>
                </label>
              );
            })}
          </div>
        </section>

        <section>
          <label htmlFor="food_preference_note" className="mb-3 block text-sm font-medium text-slate-700">
            음식 메모
          </label>
          <textarea
            id="food_preference_note"
            value={form.food_preference_note}
            onChange={(event) => setForm((current) => ({ ...current, food_preference_note: event.target.value }))}
            placeholder="기타 음식 관련 메모 (예: 매운 음식 못 먹음)"
            rows={4}
            className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-primary-600 focus:ring-2 focus:ring-primary-100"
          />
        </section>
      </div>

      {saveError && <p className="mt-6 text-sm text-rose-600">{saveError}</p>}

      <div className="mt-8 flex justify-end">
        <Button onClick={handleSave} disabled={saving} className="min-w-[140px] disabled:cursor-not-allowed disabled:opacity-70">
          {saving ? "저장 중..." : "저장"}
        </Button>
      </div>
    </div>
  );
}

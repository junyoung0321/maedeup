"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  X,
  AlertCircle,
  Utensils,
  MapPin,
  MapPinOff,
  Clock,
  Car,
  Plus,
  Check,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { PersonalDataCategory, UserProfile } from "@/types";

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

const TABS: {
  key: PersonalDataCategory;
  label: string;
  icon: typeof AlertCircle;
  color: string;
  bgColor: string;
  borderColor: string;
}[] = [
  {
    key: "food_restrictions",
    label: "음식 제한",
    icon: AlertCircle,
    color: "#dc2626",
    bgColor: "#fee2e2",
    borderColor: "#dc2626",
  },
  {
    key: "food_preferences",
    label: "음식 취향",
    icon: Utensils,
    color: "#d97706",
    bgColor: "#fef3c7",
    borderColor: "#eab308",
  },
  {
    key: "liked_areas",
    label: "선호 지역",
    icon: MapPin,
    color: "#16a34a",
    bgColor: "#f0fdf4",
    borderColor: "#22c55e",
  },
  {
    key: "disliked_areas",
    label: "회피 지역",
    icon: MapPinOff,
    color: "#64748b",
    bgColor: "#f1f5f9",
    borderColor: "#94a3b8",
  },
  {
    key: "time_preference",
    label: "선호 시간",
    icon: Clock,
    color: "#4f46e5",
    bgColor: "#eef2ff",
    borderColor: "#4f46e5",
  },
  {
    key: "transport_mode",
    label: "이동 수단",
    icon: Car,
    color: "#2563eb",
    bgColor: "#e0f2fe",
    borderColor: "#2563eb",
  },
];

type FormState = {
  food_restrictions: string[];
  food_preferences: string[];
  liked_areas: string[];
  disliked_areas: string[];
  time_preference: string;
  transport_mode: string;
};

interface Props {
  open: boolean;
  onClose: (didSave: boolean) => void;
  initialProfile: UserProfile;
  focusCategory: PersonalDataCategory | null;
}

function buildFormState(profile: UserProfile): FormState {
  return {
    food_restrictions: profile.food_restrictions ?? [],
    food_preferences: profile.food_preferences ?? [],
    liked_areas: profile.liked_areas ?? [],
    disliked_areas: profile.disliked_areas ?? [],
    time_preference: profile.time_preference ?? "",
    transport_mode: profile.transport_mode ?? "",
  };
}

function arrayEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

export default function PersonalDataModal({
  open,
  onClose,
  initialProfile,
  focusCategory,
}: Props) {
  const [activeCategory, setActiveCategory] = useState<PersonalDataCategory>(
    "food_restrictions",
  );
  const [form, setForm] = useState<FormState>(() => buildFormState(initialProfile));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initialFormRef = useRef<FormState>(buildFormState(initialProfile));

  // Modal이 열릴 때 form/activeCategory를 reset.
  useEffect(() => {
    if (!open) return;
    const fresh = buildFormState(initialProfile);
    setForm(fresh);
    initialFormRef.current = fresh;
    setActiveCategory(focusCategory ?? "food_restrictions");
    setError(null);
  }, [open, initialProfile, focusCategory]);

  const changedFields = useMemo(() => {
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

  const updateList = (
    cat: "food_restrictions" | "liked_areas" | "disliked_areas",
    next: string[],
  ) => setForm((s) => ({ ...s, [cat]: next }));

  const toggleFoodPreference = (value: string) => {
    setForm((s) => ({
      ...s,
      food_preferences: s.food_preferences.includes(value)
        ? s.food_preferences.filter((x) => x !== value)
        : [...s.food_preferences, value],
    }));
  };

  const setTimePreference = (v: string) =>
    setForm((s) => ({ ...s, time_preference: v }));

  const setTransportMode = (v: string) =>
    setForm((s) => ({ ...s, transport_mode: v }));

  const handleSave = async () => {
    if (saving) return;
    if (!hasChanges) {
      onClose(false);
      return;
    }
    try {
      setSaving(true);
      setError(null);
      await apiFetch("/api/v1/users/me/preferences", {
        method: "PATCH",
        body: JSON.stringify(changedFields),
      });
      onClose(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  const activeTab = TABS.find((t) => t.key === activeCategory) ?? TABS[0];

  return (
    <div
      onClick={() => onClose(false)}
      className="fixed inset-0 z-[100] flex items-center justify-center px-4 sm:px-0"
      style={{ background: "rgba(0,0,0,0.35)" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-3xl shadow-2xl flex flex-col overflow-hidden w-full max-w-[560px]"
        style={{
          maxHeight: "85vh",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-[#f1f5f9]">
          <div className="flex items-center gap-2.5">
            <activeTab.icon
              className="w-5 h-5"
              style={{ color: activeTab.color }}
            />
            <span className="text-[19px] font-bold text-[#111827]">
              개인 데이터 편집
            </span>
          </div>
          <button
            onClick={() => onClose(false)}
            aria-label="close"
            className="w-8 h-8 rounded-full bg-[#f1f5f9] flex items-center justify-center hover:bg-[#e2e8f0]"
          >
            <X className="w-4 h-4 text-[#64748b]" />
          </button>
        </div>

        {/* Tabs */}
        <div className="px-6 pt-4 pb-2 border-b border-[#f1f5f9]">
          <div className="grid grid-cols-3 gap-2">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const active = activeCategory === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveCategory(tab.key)}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-xl border transition-colors text-[12.5px] font-semibold"
                  style={{
                    borderColor: active ? tab.borderColor : "#e2e8f0",
                    backgroundColor: active ? tab.bgColor : "#ffffff",
                    color: active ? tab.color : "#64748b",
                    borderWidth: active ? 2 : 1,
                  }}
                >
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {activeCategory === "food_restrictions" && (
            <ChipListEditor
              label="알레르기 / 못 먹는 음식"
              hint="예: 갑각류 알레르기, 매운 거, 회"
              values={form.food_restrictions}
              onChange={(next) => updateList("food_restrictions", next)}
              accentColor="#dc2626"
            />
          )}

          {activeCategory === "food_preferences" && (
            <PresetMultiSelect
              label="좋아하는 음식 카테고리"
              options={FOOD_PREFERENCE_OPTIONS as readonly string[]}
              values={form.food_preferences}
              onToggle={toggleFoodPreference}
              accentColor="#d97706"
              accentBg="#fef3c7"
            />
          )}

          {activeCategory === "liked_areas" && (
            <ChipListEditor
              label="자주 가고 싶은 동네/지역"
              hint="예: 강남, 홍대, 신촌"
              values={form.liked_areas}
              onChange={(next) => updateList("liked_areas", next)}
              accentColor="#16a34a"
            />
          )}

          {activeCategory === "disliked_areas" && (
            <ChipListEditor
              label="멀어서 / 안 가고 싶은 지역"
              hint="예: 분당, 일산"
              values={form.disliked_areas}
              onChange={(next) => updateList("disliked_areas", next)}
              accentColor="#64748b"
            />
          )}

          {activeCategory === "time_preference" && (
            <FreeformTextEditor
              label="선호 시간대"
              hint='예: "주말 오후", "평일 저녁 7시 이후", "월수금 점심"'
              value={form.time_preference}
              onChange={setTimePreference}
              accentColor="#4f46e5"
            />
          )}

          {activeCategory === "transport_mode" && (
            <PresetSingleSelect
              label="이동 수단"
              options={TRANSPORT_OPTIONS as readonly string[]}
              value={form.transport_mode}
              onChange={setTransportMode}
              accentColor="#2563eb"
              accentBg="#e0f2fe"
            />
          )}
        </div>

        {error && (
          <div className="px-6 pb-2">
            <p className="text-[12px] text-[#dc2626]">{error}</p>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-[#f1f5f9]">
          <p className="text-[11px] text-[#94a3b8]">
            {hasChanges
              ? `${Object.keys(changedFields).length}개 항목 변경 — 직접 수정한 항목은 ✨가 사라집니다`
              : "변경 사항 없음"}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => onClose(false)}
              disabled={saving}
              className="px-5 py-2 rounded-xl border border-[#e2e8f0] bg-white text-[14px] font-medium text-[#64748b] hover:bg-[#f8fafc] disabled:opacity-50"
            >
              취소
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="px-6 py-2 rounded-xl bg-[#4f46e5] text-white text-[14px] font-medium hover:bg-[#4338ca] disabled:bg-[#c7d2fe] disabled:cursor-not-allowed"
            >
              {saving ? "저장 중…" : "저장하기"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function ChipListEditor({
  label,
  hint,
  values,
  onChange,
  accentColor,
}: {
  label: string;
  hint: string;
  values: string[];
  onChange: (next: string[]) => void;
  accentColor: string;
}) {
  const [draft, setDraft] = useState("");

  const add = () => {
    const trimmed = draft.trim();
    if (!trimmed) return;
    if (values.includes(trimmed)) {
      setDraft("");
      return;
    }
    onChange([...values, trimmed]);
    setDraft("");
  };

  const remove = (idx: number) =>
    onChange(values.filter((_, i) => i !== idx));

  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-[14px] font-bold text-[#111827] mb-1">{label}</p>
        <p className="text-[11px] text-[#94a3b8]">{hint}</p>
      </div>

      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder="입력 후 Enter 또는 + 버튼"
          className="flex-1 px-3 py-2 rounded-xl border border-[#e2e8f0] outline-none text-[14px] focus:border-[#a1a1aa]"
        />
        <button
          onClick={add}
          className="px-4 rounded-xl text-white text-[13px] font-semibold flex items-center gap-1"
          style={{ backgroundColor: accentColor }}
        >
          <Plus className="w-3.5 h-3.5" />
          추가
        </button>
      </div>

      <div className="flex flex-wrap gap-2 min-h-[40px] p-2 rounded-xl bg-[#f8fafc] border border-dashed border-[#e2e8f0]">
        {values.length === 0 && (
          <span className="text-[12px] text-[#94a3b8] italic">
            아직 추가된 항목이 없습니다
          </span>
        )}
        {values.map((v, i) => (
          <span
            key={`${v}-${i}`}
            className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-[12px] font-medium"
            style={{ backgroundColor: `${accentColor}1a`, color: accentColor }}
          >
            {v}
            <button
              onClick={() => remove(i)}
              className="hover:opacity-70"
              aria-label={`${v} 삭제`}
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}

function PresetMultiSelect({
  label,
  options,
  values,
  onToggle,
  accentColor,
  accentBg,
}: {
  label: string;
  options: readonly string[];
  values: string[];
  onToggle: (v: string) => void;
  accentColor: string;
  accentBg: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[14px] font-bold text-[#111827]">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = values.includes(opt);
          return (
            <button
              key={opt}
              onClick={() => onToggle(opt)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-[13px] font-medium transition-colors"
              style={{
                backgroundColor: active ? accentBg : "#f8fafc",
                color: active ? accentColor : "#64748b",
                border: `1px solid ${active ? accentColor : "#e2e8f0"}`,
              }}
            >
              {active && <Check className="w-3 h-3" />}
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PresetSingleSelect({
  label,
  options,
  value,
  onChange,
  accentColor,
  accentBg,
}: {
  label: string;
  options: readonly string[];
  value: string;
  onChange: (v: string) => void;
  accentColor: string;
  accentBg: string;
}) {
  const isCustom = value !== "" && !options.includes(value);
  const [customDraft, setCustomDraft] = useState(isCustom ? value : "");

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[14px] font-bold text-[#111827]">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = value === opt && !isCustom;
          return (
            <button
              key={opt}
              onClick={() => {
                onChange(opt);
                setCustomDraft("");
              }}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-[13px] font-medium transition-colors"
              style={{
                backgroundColor: active ? accentBg : "#f8fafc",
                color: active ? accentColor : "#64748b",
                border: `1px solid ${active ? accentColor : "#e2e8f0"}`,
              }}
            >
              {active && <Check className="w-3 h-3" />}
              {opt}
            </button>
          );
        })}
        <button
          onClick={() => onChange("")}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-[13px] font-medium transition-colors"
          style={{
            backgroundColor: value === "" ? "#f1f5f9" : "#f8fafc",
            color: "#64748b",
            border: "1px solid #e2e8f0",
          }}
        >
          미설정
        </button>
      </div>
      {isCustom && (
        <input
          value={customDraft}
          onChange={(e) => {
            setCustomDraft(e.target.value);
            onChange(e.target.value);
          }}
          placeholder="기타 직접 입력"
          className="px-3 py-2 rounded-xl border outline-none text-[14px]"
          style={{ borderColor: accentColor }}
        />
      )}
    </div>
  );
}

function FreeformTextEditor({
  label,
  hint,
  value,
  onChange,
  accentColor,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  accentColor: string;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-[14px] font-bold text-[#111827] mb-1">{label}</p>
        <p className="text-[11px] text-[#94a3b8]">{hint}</p>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        placeholder="자연어로 자유롭게 입력하세요"
        className="px-3 py-2 rounded-xl border border-[#e2e8f0] outline-none text-[14px] resize-none focus:border-[#a1a1aa]"
        style={{ caretColor: accentColor }}
      />
      <p className="text-[10px] text-[#94a3b8]">
        AI는 이 텍스트를 그대로 읽고 추천에 반영합니다 — 시간/요일을 자유 형식으로
        적어도 됩니다.
      </p>
    </div>
  );
}

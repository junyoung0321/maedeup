"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import { Plus, X, Check } from "lucide-react";

// PersonalDataModal과 /preferences 페이지가 공유하는 4개 editor.
// 동일한 UX/시멘틱을 두 surface에서 똑같이 쓰기 위해 분리.

export function ChipListEditor({
  label,
  hint,
  values,
  onChange,
  accentColor,
}: {
  label: ReactNode;
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

export function PresetMultiSelect({
  label,
  options,
  values,
  onToggle,
  accentColor,
  accentBg,
}: {
  label: ReactNode;
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

export function PresetSingleSelect({
  label,
  options,
  value,
  onChange,
  accentColor,
  accentBg,
}: {
  label: ReactNode;
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

export function FreeformTextEditor({
  label,
  hint,
  value,
  onChange,
  accentColor,
}: {
  label: ReactNode;
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

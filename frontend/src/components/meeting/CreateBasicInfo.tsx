"use client";

import { Camera } from "lucide-react";
import { ClipboardList } from "lucide-react";

const categories = ["스터디", "식사", "운동", "여행", "회의", "기타"];

interface Props {
  name: string;
  description: string;
  category: string;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onCategoryChange: (v: string) => void;
}

export default function CreateBasicInfo({
  name,
  description,
  category,
  onNameChange,
  onDescriptionChange,
  onCategoryChange,
}: Props) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        maxWidth: 900,
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
          padding: "16px 24px",
          background: "linear-gradient(135deg, #4338ca, #4f46e5)",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <ClipboardList style={{ width: 20, height: 20, color: "#ffffff" }} />
        <span
          style={{
            fontSize: 29,
            fontWeight: 500,
            color: "#ffffff",
            letterSpacing: 0.5,
          }}
        >
          모임 기본 정보
        </span>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          padding: 24,
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        {/* 모임 이름 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label
            style={{
              fontSize: 21,
              fontWeight: 600,
              color: "#111827",
            }}
          >
            모임 이름
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="스터디 모임, 점심 약속 등"
            style={{
              padding: "12px 16px",
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              outline: "none",
              fontSize: 21,
              fontWeight: 400,
              color: "#1e293b",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              background: "#ffffff",
            }}
          />
        </div>

        {/* 모임 설명 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label
            style={{
              fontSize: 21,
              fontWeight: 600,
              color: "#111827",
            }}
          >
            모임 설명
          </label>
          <textarea
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            placeholder="모임에 대해 간단히 설명해주세요"
            rows={3}
            style={{
              padding: "12px 16px",
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              outline: "none",
              fontSize: 21,
              fontWeight: 400,
              color: "#1e293b",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              background: "#ffffff",
              resize: "none",
            }}
          />
        </div>

        {/* 카테고리 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label
            style={{
              fontSize: 21,
              fontWeight: 600,
              color: "#111827",
            }}
          >
            카테고리
          </label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {categories.map((cat) => {
              const isSelected = category === cat;
              return (
                <button
                  key={cat}
                  onClick={() => onCategoryChange(cat)}
                  style={{
                    padding: "6px 16px",
                    borderRadius: 20,
                    border: isSelected ? "none" : "1px solid #e2e8f0",
                    background: isSelected ? "#4f46e5" : "#ffffff",
                    color: isSelected ? "#ffffff" : "#64748b",
                    fontSize: 20,
                    fontWeight: 500,
                    cursor: "pointer",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                >
                  {cat}
                </button>
              );
            })}
          </div>
        </div>

        {/* 커버 이미지 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label
            style={{
              fontSize: 21,
              fontWeight: 600,
              color: "#111827",
            }}
          >
            커버 이미지
          </label>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              padding: "40px 0",
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              background: "#f8fafc",
              cursor: "pointer",
            }}
          >
            <Camera style={{ width: 28, height: 28, color: "#94a3b8" }} />
            <span style={{ fontSize: 20, fontWeight: 400, color: "#94a3b8" }}>
              이미지 추가
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Search,
  Minus,
  Plus,
  Check,
  ImageIcon,
} from "lucide-react";

const categories = ["스터디", "식사", "운동", "여행", "회의", "기타"] as const;

const people = [
  { name: "김민수", email: "minsu@email.com", color: "#818cf8", checked: true },
  { name: "이서연", email: "seoyeon@email.com", color: "#f472b6", checked: false },
  { name: "박준혁", email: "junhyuk@email.com", color: "#fb923c", checked: true },
];

export default function MeetingNewPage() {
  const router = useRouter();
  const [selectedCategory, setSelectedCategory] = useState<string>("스터디");
  const [checkedPeople, setCheckedPeople] = useState<Record<string, boolean>>(
    Object.fromEntries(people.map((p) => [p.email, p.checked]))
  );
  const [count, setCount] = useState(10);

  const togglePerson = (email: string) => {
    setCheckedPeople((prev) => ({ ...prev, [email]: !prev[email] }));
  };

  const decrement = () => setCount((c) => Math.max(2, c - 1));
  const increment = () => setCount((c) => Math.min(50, c + 1));

  return (
    <div
      className="relative flex flex-col overflow-hidden"
      style={{
        width: 390,
        height: 1090,
        backgroundColor: "#ffffffff",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        className="relative shrink-0"
        style={{ height: 56, backgroundColor: "#4f46e5" }}
      >
        <ArrowLeft
          size={20}
          color="white"
          className="absolute cursor-pointer"
          style={{ left: 16, top: 18 }}
          onClick={() => router.push("/m/explore")}
        />
        <span
          className="absolute"
          style={{
            left: 160,
            top: 15,
            fontSize: 18,
            fontWeight: 600,
            color: "white",
          }}
        >
          모임 생성
        </span>
      </div>

      {/* Scroll content */}
      <div
        className="flex flex-col flex-1 overflow-y-auto"
        style={{ padding: 20, gap: 24, backgroundColor: "#ffffff" }}
      >
        {/* Section 1 - 모임 기본 정보 */}
        <div className="flex flex-col" style={{ gap: 14 }}>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            모임 기본 정보
          </span>

          {/* Name input */}
          <div
            style={{
              borderRadius: 10,
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              padding: "14px 16px",
            }}
          >
            <span
              style={{
                fontSize: 14,
                fontWeight: 400,
                color: "#94a3b8",
              }}
            >
              스터디 모임, 점심 약속 등
            </span>
          </div>

          {/* Description input */}
          <div
            style={{
              borderRadius: 10,
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              padding: "14px 16px",
              height: 72,
            }}
          >
            <span
              style={{
                fontSize: 14,
                fontWeight: 400,
                color: "#94a3b8",
              }}
            >
              모임 설명을 입력하세요
            </span>
          </div>

          {/* Category chips */}
          <div className="flex flex-wrap" style={{ gap: 8 }}>
            {categories.map((cat) => {
              const selected = cat === selectedCategory;
              return (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  style={{
                    borderRadius: 20,
                    backgroundColor: selected ? "#4f46e5" : "#f8fafc",
                    border: selected ? "none" : "1px solid #e2e8f0",
                    padding: "8px 16px",
                    fontSize: 13,
                    fontWeight: selected ? 600 : 500,
                    color: selected ? "#ffffff" : "#64748b",
                    cursor: "pointer",
                    fontFamily: "Pretendard, sans-serif",
                  }}
                >
                  {cat}
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 2 - 참여자 초대 */}
        <div className="flex flex-col" style={{ gap: 12 }}>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            참여자 초대
          </span>

          {/* Search */}
          <div
            className="flex items-center"
            style={{
              borderRadius: 10,
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              padding: "10px 14px",
              gap: 8,
            }}
          >
            <Search size={16} color="#94a3b8" />
            <span
              style={{
                fontSize: 13,
                fontWeight: 400,
                color: "#94a3b8",
              }}
            >
              이름 또는 이메일로 검색
            </span>
          </div>

          {/* People list */}
          <div className="flex flex-col">
            {people.map((person) => {
              const isChecked = checkedPeople[person.email];
              return (
                <div
                  key={person.email}
                  className="flex items-center"
                  style={{ padding: "10px 0", gap: 12 }}
                  onClick={() => togglePerson(person.email)}
                >
                  {/* Avatar */}
                  <div
                    className="shrink-0"
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "50%",
                      backgroundColor: person.color,
                    }}
                  />

                  {/* Info */}
                  <div className="flex flex-col flex-1" style={{ gap: 2 }}>
                    <span
                      style={{
                        fontSize: 14,
                        fontWeight: 600,
                        color: "#1e293b",
                      }}
                    >
                      {person.name}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 400,
                        color: "#94a3b8",
                      }}
                    >
                      {person.email}
                    </span>
                  </div>

                  {/* Checkbox */}
                  <div
                    className="flex items-center justify-center shrink-0"
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: 6,
                      backgroundColor: isChecked ? "#4f46e5" : "#ffffff",
                      border: isChecked ? "none" : "1.5px solid #d1d5db",
                      cursor: "pointer",
                    }}
                  >
                    {isChecked && <Check size={14} color="white" />}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Section 3 - 최대 인원 설정 */}
        <div className="flex flex-col" style={{ gap: 14 }}>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            최대 인원 설정
          </span>

          {/* Counter row */}
          <div className="flex items-center" style={{ gap: 12 }}>
            {/* Minus */}
            <button
              onClick={decrement}
              className="flex items-center justify-center shrink-0"
              style={{
                width: 40,
                height: 40,
                borderRadius: 20,
                backgroundColor: "#f1f5f9",
                border: "1px solid #e2e8f0",
                cursor: "pointer",
              }}
            >
              <Minus size={18} color="#64748b" />
            </button>

            {/* Count display */}
            <div
              className="flex items-center justify-center flex-1"
              style={{
                borderRadius: 12,
                backgroundColor: "#f8fafc",
                border: "1px solid #e2e8f0",
                height: 48,
              }}
            >
              <span
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  color: "#1e293b",
                }}
              >
                {count}명
              </span>
            </div>

            {/* Plus */}
            <button
              onClick={increment}
              className="flex items-center justify-center shrink-0"
              style={{
                width: 40,
                height: 40,
                borderRadius: 20,
                backgroundColor: "#eef2ff",
                border: "1px solid #c7d2fe",
                cursor: "pointer",
              }}
            >
              <Plus size={18} color="#4f46e5" />
            </button>
          </div>

          <span
            style={{
              fontSize: 11,
              fontWeight: 400,
              color: "#94a3b8",
            }}
          >
            최소 2명 ~ 최대 50명까지 설정할 수 있습니다
          </span>
        </div>

        {/* Section 4 - 커버 이미지 */}
        <div className="flex flex-col" style={{ gap: 14 }}>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            커버 이미지
          </span>

          {/* Upload area */}
          <div
            className="flex flex-col items-center justify-center"
            style={{
              borderRadius: 16,
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              height: 140,
              gap: 8,
            }}
          >
            <ImageIcon size={32} color="#cbd5e1" />
            <span
              style={{
                fontSize: 13,
                fontWeight: 400,
                color: "#94a3b8",
              }}
            >
              이미지를 업로드하세요
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 400,
                color: "#cbd5e1",
              }}
            >
              권장 크기: 390 x 200px
            </span>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div
        className="shrink-0"
        style={{
          backgroundColor: "#ffffff",
          borderTop: "1px solid #f1f5f9",
          padding: "12px 20px 24px 20px",
        }}
      >
        <button
          className="w-full"
          style={{
            borderRadius: 14,
            background: "linear-gradient(90deg, #4f46e5, #6366f1)",
            padding: "16px 0",
            fontSize: 16,
            fontWeight: 700,
            color: "#ffffff",
            border: "none",
            cursor: "pointer",
            fontFamily: "Pretendard, sans-serif",
          }}
          onClick={() => router.push("/m/chat/schedule")}
        >
          모임 생성
        </button>
      </div>
    </div>
  );
}

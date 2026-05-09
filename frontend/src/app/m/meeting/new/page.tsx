"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Search,
  Minus,
  Plus,
  Check,
  ImageIcon,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

const categories = ["스터디", "식사", "운동", "여행", "회의", "기타"] as const;

interface FriendInfo {
  id: number;
  name: string;
  email: string;
  picture?: string | null;
}

const AVATAR_COLORS = [
  "#818cf8",
  "#f472b6",
  "#fb923c",
  "#34d399",
  "#60a5fa",
  "#a78bfa",
];

export default function MeetingNewPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [selectedCategory, setSelectedCategory] = useState<string>("스터디");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [count, setCount] = useState(10);
  const [friends, setFriends] = useState<FriendInfo[]>([]);
  const [checkedPeople, setCheckedPeople] = useState<Record<string, boolean>>({});
  const [creating, setCreating] = useState(false);
  const [inviteQuery, setInviteQuery] = useState("");

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/m/login");
      return;
    }
    apiFetch<FriendInfo[]>("/api/v1/users/friends")
      .then((data) => {
        setFriends(data);
        setCheckedPeople(Object.fromEntries(data.map((f) => [f.email, false])));
      })
      .catch(() => {});
  }, [authLoading, user, router]);

  const togglePerson = (email: string) =>
    setCheckedPeople((prev) => ({ ...prev, [email]: !prev[email] }));

  const filteredFriends = inviteQuery.trim()
    ? friends.filter(
        (f) =>
          f.name.toLowerCase().includes(inviteQuery.toLowerCase()) ||
          f.email.toLowerCase().includes(inviteQuery.toLowerCase())
      )
    : friends;

  const decrement = () => setCount((c) => Math.max(2, c - 1));
  const increment = () => setCount((c) => Math.min(50, c + 1));

  const handleCreate = async () => {
    if (!name.trim()) {
      alert("모임 이름을 입력하세요");
      return;
    }
    setCreating(true);
    try {
      const selectedEmails = friends
        .filter((f) => checkedPeople[f.email])
        .map((f) => f.email);
      const data = await apiFetch<{ id: number }>("/api/v1/rooms/", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          category: selectedCategory,
          member_emails: selectedEmails,
        }),
      });
      router.push(`/m/chat/schedule?roomId=${data.id}`);
    } catch (e) {
      alert(`모임 생성 실패: ${e instanceof Error ? e.message : "오류 발생"}`);
    } finally {
      setCreating(false);
    }
  };

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
          <span style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>
            모임 기본 정보
          </span>

          {/* Name input */}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="스터디 모임, 점심 약속 등"
            style={{
              borderRadius: 10,
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              padding: "14px 16px",
              fontSize: 14,
              fontWeight: 400,
              color: "#1e293b",
              fontFamily: "Pretendard, sans-serif",
              outline: "none",
              width: "100%",
              boxSizing: "border-box",
            }}
          />

          {/* Description input */}
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="모임 설명을 입력하세요"
            rows={3}
            style={{
              borderRadius: 10,
              backgroundColor: "#f8fafc",
              border: "1px solid #e2e8f0",
              padding: "14px 16px",
              fontSize: 14,
              fontWeight: 400,
              color: "#1e293b",
              fontFamily: "Pretendard, sans-serif",
              outline: "none",
              width: "100%",
              boxSizing: "border-box",
              resize: "none",
            }}
          />

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
          <span style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>
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
            <input
              value={inviteQuery}
              onChange={(e) => setInviteQuery(e.target.value)}
              placeholder="이름 또는 이메일로 검색"
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                background: "transparent",
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 400,
                color: "#1e293b",
              }}
            />
          </div>

          {/* People list */}
          <div className="flex flex-col">
            {filteredFriends.length === 0 ? (
              <span style={{ fontSize: 13, color: "#94a3b8", padding: "8px 0" }}>
                {friends.length === 0 ? "친구 목록이 없습니다" : "검색 결과가 없습니다"}
              </span>
            ) : (
              filteredFriends.map((friend, i) => {
                const isChecked = !!checkedPeople[friend.email];
                return (
                  <div
                    key={friend.email}
                    className="flex items-center"
                    style={{ padding: "10px 0", gap: 12 }}
                    onClick={() => togglePerson(friend.email)}
                  >
                    {/* Avatar */}
                    <div
                      className="shrink-0"
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: "50%",
                        backgroundColor: AVATAR_COLORS[i % AVATAR_COLORS.length],
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "#ffffff",
                        fontSize: 14,
                        fontWeight: 600,
                      }}
                    >
                      {friend.name.charAt(0)}
                    </div>

                    {/* Info */}
                    <div className="flex flex-col flex-1" style={{ gap: 2 }}>
                      <span
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: "#1e293b",
                        }}
                      >
                        {friend.name}
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 400,
                          color: "#94a3b8",
                        }}
                      >
                        {friend.email}
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
              })
            )}
          </div>
        </div>

        {/* Section 3 - 최대 인원 설정 */}
        <div className="flex flex-col" style={{ gap: 14 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>
            최대 인원 설정
          </span>

          {/* Counter row */}
          <div className="flex items-center" style={{ gap: 12 }}>
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

            <div
              className="flex items-center justify-center flex-1"
              style={{
                borderRadius: 12,
                backgroundColor: "#f8fafc",
                border: "1px solid #e2e8f0",
                height: 48,
              }}
            >
              <span style={{ fontSize: 20, fontWeight: 700, color: "#1e293b" }}>
                {count}명
              </span>
            </div>

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

          <span style={{ fontSize: 11, fontWeight: 400, color: "#94a3b8" }}>
            최소 2명 ~ 최대 50명까지 설정할 수 있습니다
          </span>
        </div>

        {/* Section 4 - 커버 이미지 */}
        <div className="flex flex-col" style={{ gap: 14 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#1e293b" }}>
            커버 이미지
          </span>

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
            <span style={{ fontSize: 13, fontWeight: 400, color: "#94a3b8" }}>
              이미지를 업로드하세요
            </span>
            <span style={{ fontSize: 11, fontWeight: 400, color: "#cbd5e1" }}>
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
          disabled={creating}
          style={{
            borderRadius: 14,
            background: creating
              ? "#a5b4fc"
              : "linear-gradient(90deg, #4f46e5, #6366f1)",
            padding: "16px 0",
            fontSize: 16,
            fontWeight: 700,
            color: "#ffffff",
            border: "none",
            cursor: creating ? "not-allowed" : "pointer",
            fontFamily: "Pretendard, sans-serif",
          }}
          onClick={handleCreate}
        >
          {creating ? "생성 중…" : "모임 생성"}
        </button>
      </div>
    </div>
  );
}

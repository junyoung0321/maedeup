"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Props {
  roomId: string;
  onJoined: () => void;
}

/**
 * 방 링크로 로그인 없이 진입한 사용자에게 이름 입력 + 게스트 가입을 받는 게이트.
 * 가입 성공 시 localStorage에 JWT 저장 후 상위 페이지를 재렌더(onJoined 콜백).
 */
export default function GuestJoinGate({ roomId, onJoined }: Props) {
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("이름을 입력해주세요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const resp = await apiFetch<{ token: string }>(
        `/api/v1/rooms/${roomId}/guest-join`,
        {
          method: "POST",
          body: JSON.stringify({ display_name: trimmed }),
          noAuth: true,
        },
      );
      localStorage.setItem("auth_token", resp.token);
      onJoined();
    } catch (e) {
      setError(e instanceof Error ? e.message : "참여에 실패했어요");
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg,#eef2ff 0%,#fdf4ff 100%)",
        padding: 20,
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      <form
        onSubmit={handleJoin}
        style={{
          width: "100%",
          maxWidth: 400,
          padding: "32px 28px",
          background: "#ffffff",
          borderRadius: 20,
          boxShadow: "0 20px 60px rgba(79,70,229,0.15)",
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <UserPlus style={{ width: 26, height: 26, color: "#4f46e5" }} />
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "#1e1b4b", margin: 0 }}>
            모임에 참여하기
          </h1>
        </div>
        <p style={{ fontSize: 14, color: "#64748b", margin: 0, lineHeight: 1.5 }}>
          이름만 입력하면 바로 참여할 수 있어요. 로그인 없이 일정 조율에 참여 가능합니다.
        </p>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>
            이름 또는 닉네임
          </span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="홍길동"
            maxLength={32}
            autoFocus
            style={{
              padding: "12px 14px",
              borderRadius: 10,
              border: "1px solid #e2e8f0",
              fontSize: 14,
              color: "#0f172a",
              outline: "none",
              fontFamily: "inherit",
            }}
          />
        </label>
        {error && (
          <div
            role="alert"
            style={{
              padding: "10px 12px",
              background: "#fee2e2",
              color: "#991b1b",
              borderRadius: 10,
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={submitting}
          style={{
            padding: "12px 14px",
            borderRadius: 10,
            border: "none",
            background: submitting ? "#a5b4fc" : "#4f46e5",
            color: "#ffffff",
            fontSize: 15,
            fontWeight: 700,
            cursor: submitting ? "not-allowed" : "pointer",
            fontFamily: "inherit",
          }}
        >
          {submitting ? "참여 중…" : "게스트로 참여"}
        </button>
        <p style={{ fontSize: 12, color: "#94a3b8", margin: 0, textAlign: "center" }}>
          계정이 있다면{" "}
          <a href="/" style={{ color: "#4f46e5", textDecoration: "underline" }}>
            로그인
          </a>
          해서 참여할 수도 있어요.
        </p>
      </form>
    </div>
  );
}

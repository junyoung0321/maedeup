"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

function decodeJwt(token: string): { calendar_consent?: boolean; exp: number } {
  const payload = token.split(".")[1];
  return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
}

export default function ConsentPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      router.replace("/");
      return;
    }
    try {
      const decoded = decodeJwt(token);
      if (decoded.calendar_consent) {
        router.replace("/");
      }
    } catch {
      router.replace("/");
    }
  }, [router]);

  const handleConsent = async (consent: boolean) => {
    setLoading(true);
    const token = localStorage.getItem("auth_token");

    if (consent) {
      try {
        const data = await apiFetch<{ token: string }>("/api/v1/users/me/consent", {
          method: "PATCH",
          body: JSON.stringify({ calendar_consent: true }),
        });
        localStorage.setItem("auth_token", data.token);
      } catch {
        // 동의 저장 실패해도 메인으로 이동
      }
    }

    router.replace("/");
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0d0d0d",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
    >
      <div
        style={{
          background: "#141414",
          border: "1px solid #222",
          borderRadius: "12px",
          padding: "36px 40px",
          maxWidth: "480px",
          width: "100%",
        }}
      >
        {/* 헤더 */}
        <div style={{ marginBottom: "28px" }}>
          <div style={{ fontWeight: 700, fontSize: "20px", color: "#e8e8e8", marginBottom: "6px" }}>
            매듭
          </div>
          <div style={{ fontSize: "15px", color: "#bbb", fontWeight: 600 }}>
            서비스 이용을 위한 정보 수집 동의
          </div>
        </div>

        {/* 수집 항목 */}
        <div
          style={{
            background: "#1a1a1a",
            border: "1px solid #2a2a2a",
            borderRadius: "8px",
            padding: "20px",
            marginBottom: "20px",
          }}
        >
          <div style={{ fontSize: "12px", color: "#666", marginBottom: "14px", letterSpacing: "0.05em" }}>
            매듭은 다음 정보를 수집합니다
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <ConsentItem
              label="구글 계정 기본 정보"
              detail="이름, 이메일, 프로필 사진"
            />
            <ConsentItem
              label="구글 캘린더 바쁜 시간대"
              detail="일정 제목/내용은 수집하지 않습니다"
            />
          </div>
        </div>

        {/* 수집 목적 & 보유 기간 */}
        <div style={{ marginBottom: "28px", display: "flex", flexDirection: "column", gap: "8px" }}>
          <InfoRow label="수집 목적" value="모임 가능 시간 자동 조율" />
          <InfoRow label="보유 기간" value="서비스 탈퇴 시 즉시 삭제" />
        </div>

        {/* 버튼 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <button
            onClick={() => handleConsent(true)}
            disabled={loading}
            style={{
              width: "100%",
              padding: "13px",
              background: "#2563eb",
              border: "none",
              borderRadius: "8px",
              color: "#fff",
              fontSize: "14px",
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "처리 중..." : "동의하고 시작하기"}
          </button>
          <button
            onClick={() => handleConsent(false)}
            disabled={loading}
            style={{
              width: "100%",
              padding: "13px",
              background: "transparent",
              border: "1px solid #333",
              borderRadius: "8px",
              color: "#666",
              fontSize: "14px",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            거부 (채팅만 사용)
          </button>
        </div>

        <div style={{ marginTop: "16px", fontSize: "11px", color: "#444", textAlign: "center", lineHeight: 1.6 }}>
          거부 시 캘린더 연동 없이 채팅 기능만 이용 가능합니다.
        </div>
      </div>
    </div>
  );
}

function ConsentItem({ label, detail }: { label: string; detail: string }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
      <span style={{ color: "#22c55e", fontSize: "14px", marginTop: "1px", flexShrink: 0 }}>✓</span>
      <div>
        <div style={{ fontSize: "13px", color: "#ddd", fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: "12px", color: "#666", marginTop: "2px" }}>{detail}</div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", gap: "8px", fontSize: "12px" }}>
      <span style={{ color: "#555", minWidth: "72px" }}>{label}</span>
      <span style={{ color: "#888" }}>{value}</span>
    </div>
  );
}

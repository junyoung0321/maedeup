"use client";

import { useEffect } from "react";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: Props) {
  useEffect(() => {
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        background: "#f8fafc",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      <span style={{ fontSize: 56, lineHeight: 1 }}>😵</span>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: "#111827", margin: 0 }}>
        오류가 발생했어요
      </h1>
      <p style={{ fontSize: 14, color: "#94a3b8", margin: 0, textAlign: "center" }}>
        일시적인 문제일 수 있어요. 다시 시도해 보세요.
      </p>
      <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
        <button
          onClick={reset}
          style={{
            padding: "10px 24px",
            borderRadius: 10,
            background: "#4f46e5",
            color: "#ffffff",
            fontSize: 14,
            fontWeight: 600,
            border: "none",
            cursor: "pointer",
          }}
        >
          다시 시도
        </button>
        <a
          href="/"
          style={{
            padding: "10px 24px",
            borderRadius: 10,
            background: "#ffffff",
            color: "#4f46e5",
            fontSize: 14,
            fontWeight: 600,
            border: "1px solid #e2e8f0",
            textDecoration: "none",
          }}
        >
          홈으로
        </a>
      </div>
    </div>
  );
}

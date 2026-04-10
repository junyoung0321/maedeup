"use client";

import { AlertCircle, RefreshCw } from "lucide-react";

interface Props {
  message?: string;
  onRetry?: () => void;
}

export default function ErrorState({
  message = "데이터를 불러올 수 없습니다",
  onRetry,
}: Props) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        padding: 32,
        flex: 1,
      }}
    >
      <AlertCircle size={32} color="#ef4444" />
      <span
        style={{
          fontSize: 14,
          color: "#64748b",
          textAlign: "center",
          fontFamily: "Pretendard, sans-serif",
        }}
      >
        {message}
      </span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 16px",
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            background: "#ffffff",
            color: "#4f46e5",
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
            fontFamily: "Pretendard, sans-serif",
          }}
        >
          <RefreshCw size={14} />
          다시 시도
        </button>
      )}
    </div>
  );
}

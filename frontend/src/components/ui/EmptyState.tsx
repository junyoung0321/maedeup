"use client";

import { LucideIcon } from "lucide-react";

interface Props {
  icon?: LucideIcon;
  message: string;
  sub?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export default function EmptyState({ icon: Icon, message, sub, action }: Props) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "40px 24px",
        flex: 1,
      }}
    >
      {Icon && <Icon size={28} color="#cbd5e1" strokeWidth={1.5} />}
      <span
        style={{
          fontSize: 14,
          color: "#94a3b8",
          textAlign: "center",
          fontFamily: "Pretendard, sans-serif",
        }}
      >
        {message}
      </span>
      {sub && (
        <span
          style={{
            fontSize: 12,
            color: "#cbd5e1",
            textAlign: "center",
            fontFamily: "Pretendard, sans-serif",
          }}
        >
          {sub}
        </span>
      )}
      {action && (
        <button
          onClick={action.onClick}
          style={{
            marginTop: 8,
            padding: "8px 18px",
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
          {action.label}
        </button>
      )}
    </div>
  );
}

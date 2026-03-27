"use client";

import { useState } from "react";
import { X, Users, Link2, Copy, MessageSquare, Mail, Share2 } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function InviteModal({ open, onClose }: Props) {
  const [email, setEmail] = useState("");
  const inviteCode = "MDUP-XK9F";
  const inviteLink = "maedeup.app/invite/8uf3XkMFGx";

  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 100, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: 480, borderRadius: 24, background: "#ffffff", boxShadow: "0 20px 60px rgba(0,0,0,0.2)", display: "flex", flexDirection: "column", overflow: "hidden", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 28px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Users style={{ width: 20, height: 20, color: "#4f46e5" }} />
            <span style={{ fontSize: 20, fontWeight: 600, color: "#111827" }}>모임 초대</span>
          </div>
          <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: "50%", border: "none", background: "#f1f5f9", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
            <X style={{ width: 16, height: 16, color: "#64748b" }} />
          </button>
        </div>

        {/* Description */}
        <div style={{ padding: "0 28px" }}>
          <span style={{ fontSize: 13, fontWeight: 400, color: "#94a3b8" }}>
            친구 및 지인 또는 코드를 공유하여 친구를 모임에 초대하세요
          </span>
        </div>

        {/* Content */}
        <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 20 }}>
          {/* 초대 링크 */}
          <div>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8, display: "block" }}>초대 링크</span>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                value={inviteLink}
                readOnly
                style={{ flex: 1, padding: "10px 14px", borderRadius: 10, border: "1px solid #e2e8f0", outline: "none", fontSize: 13, color: "#64748b", fontFamily: "Pretendard Variable, Pretendard, sans-serif", background: "#f8fafc" }}
              />
              <button style={{ padding: "10px 20px", borderRadius: 10, border: "none", background: "#4f46e5", color: "#ffffff", fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
                복사
              </button>
            </div>
          </div>

          {/* 초대 코드 */}
          <div>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8, display: "block" }}>초대 코드</span>
            <div
              style={{
                padding: "20px",
                borderRadius: 16,
                border: "2px dashed #22c55e",
                background: "#f0fdf4",
                textAlign: "center",
              }}
            >
              <span style={{ fontSize: 28, fontWeight: 700, color: "#111827", letterSpacing: 4, fontFamily: "monospace" }}>
                {inviteCode}
              </span>
            </div>
          </div>

          {/* 공유하기 */}
          <div>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 10, display: "block" }}>공유하기</span>
            <div style={{ display: "flex", gap: 8 }}>
              {[
                { icon: Link2, label: "링크복사", color: "#4f46e5", bg: "#eef2ff" },
                { icon: Copy, label: "코드", color: "#eab308", bg: "#fefce8" },
                { icon: MessageSquare, label: "남긴 톡사", color: "#64748b", bg: "#f8fafc" },
                { icon: Mail, label: "이메일", color: "#64748b", bg: "#f8fafc" },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.label}
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 6,
                      padding: "14px 0",
                      borderRadius: 12,
                      border: "1px solid #e2e8f0",
                      background: item.bg,
                      cursor: "pointer",
                      fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                    }}
                  >
                    <Icon style={{ width: 20, height: 20, color: item.color }} />
                    <span style={{ fontSize: 11, fontWeight: 500, color: item.color }}>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

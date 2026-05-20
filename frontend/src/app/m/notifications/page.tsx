"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Settings, Calendar, Users, Sparkles, Vote, Bell } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { LucideIcon } from "lucide-react";

interface NotificationResponse {
  id: number;
  type: string;
  title: string;
  body?: string | null;
  room_id?: number | null;
  payload?: Record<string, unknown> | null;
  read_at?: string | null;
  created_at: string;
}

interface NotificationSection {
  label: string;
  items: NotificationResponse[];
}

function getIconAndColor(type: string): { Icon: LucideIcon; bg: string } {
  if (type.includes("schedule") || type.includes("meeting")) return { Icon: Calendar, bg: "#4f46e5" };
  if (type.includes("join") || type.includes("member")) return { Icon: Users, bg: "#22c55e" };
  if (type.includes("ai") || type.includes("place") || type.includes("recommend")) return { Icon: Sparkles, bg: "#7c3aed" };
  if (type.includes("vote") || type.includes("finali")) return { Icon: Vote, bg: "#f59e0b" };
  return { Icon: Bell, bg: "#64748b" };
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "어제";
  if (days < 7) return `${days}일 전`;
  return new Date(iso).toLocaleDateString("ko-KR", { month: "long", day: "numeric" });
}

function groupNotifications(items: NotificationResponse[]): NotificationSection[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const weekStart = todayStart - 6 * 86400000;

  const today: NotificationResponse[] = [];
  const thisWeek: NotificationResponse[] = [];
  const older: NotificationResponse[] = [];

  for (const n of items) {
    const t = new Date(n.created_at).getTime();
    if (t >= todayStart) today.push(n);
    else if (t >= weekStart) thisWeek.push(n);
    else older.push(n);
  }

  const sections: NotificationSection[] = [];
  if (today.length > 0) sections.push({ label: "오늘", items: today });
  if (thisWeek.length > 0) sections.push({ label: "이번 주", items: thisWeek });
  if (older.length > 0) sections.push({ label: "이전", items: older });
  return sections;
}

function NotificationsPageContent() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [sections, setSections] = useState<NotificationSection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !user) return;
    apiFetch<NotificationResponse[]>("/api/v1/notifications")
      .then((data) => setSections(groupNotifications(data)))
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [authLoading, user]);

  return (
    <div
      style={{
        width: "100%",
        height: "844px",
        background: "#ffffff",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 56,
          minHeight: 56,
          background: "#ffffff",
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <ArrowLeft size={24} color="#1e293b" style={{ cursor: "pointer" }} onClick={() => router.back()} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
          <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b" }}>알림</span>
        </div>
        <Settings size={22} color="#64748b" style={{ cursor: "pointer" }} onClick={() => alert("알림 설정 기능은 준비 중입니다")} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, background: "#f8fafc", display: "flex", flexDirection: "column", overflowY: "auto" }}>
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", paddingTop: 60 }}>
            <span style={{ fontSize: 13, color: "#94a3b8" }}>불러오는 중...</span>
          </div>
        ) : sections.length === 0 ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", paddingTop: 60 }}>
            <span style={{ fontSize: 14, color: "#94a3b8" }}>새로운 알림이 없습니다</span>
          </div>
        ) : (
          sections.map((section) => (
            <div key={section.label}>
              <div style={{ padding: "12px 20px" }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8" }}>{section.label}</span>
              </div>
              {section.items.map((item) => {
                const { Icon, bg } = getIconAndColor(item.type);
                const isUnread = !item.read_at;
                return (
                  <div
                    key={item.id}
                    onClick={() => item.room_id ? router.push(`/m/meeting/detail?roomId=${item.room_id}`) : undefined}
                    style={{
                      display: "flex",
                      gap: 12,
                      padding: "14px 20px",
                      background: isUnread ? "#eef2ff" : "#ffffff",
                      borderBottom: "1px solid #f1f5f9",
                      cursor: item.room_id ? "pointer" : "default",
                    }}
                  >
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: 18,
                        background: bg,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <Icon size={18} color="#ffffff" />
                    </div>
                    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
                      <span style={{ fontSize: 14, fontWeight: isUnread ? 600 : 500, color: "#1e293b", lineHeight: 1.4 }}>
                        {item.title}
                      </span>
                      {item.body && (
                        <span style={{ fontSize: 12, color: "#64748b" }}>{item.body}</span>
                      )}
                      <span style={{ fontSize: 11, color: "#94a3b8" }}>{relativeTime(item.created_at)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function NotificationsPage() {
  return (
    <Suspense fallback={null}>
      <NotificationsPageContent />
    </Suspense>
  );
}

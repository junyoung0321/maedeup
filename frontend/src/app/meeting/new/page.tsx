"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import CreateBasicInfo from "@/components/meeting/CreateBasicInfo";
import CreateInviteSettings from "@/components/meeting/CreateInviteSettings";
import { API_BASE_URL } from "@/lib/api";

export interface MeetingFormState {
  name: string;
  description: string;
  category: string;
  coverImage: string | null;
  invitedMembers: Set<string>;
  scheduleMethod: "ai" | "manual" | "vote";
  placeMethod: "ai" | "manual" | "vote";
}

export default function CreateMeetingPage() {
  const router = useRouter();
  const [form, setForm] = useState<MeetingFormState>({
    name: "",
    description: "",
    category: "스터디",
    coverImage: null,
    invitedMembers: new Set(),
    scheduleMethod: "ai",
    placeMethod: "ai",
  });

  const updateForm = (updates: Partial<Omit<MeetingFormState, "invitedMembers">>) => {
    setForm((prev) => ({ ...prev, ...updates }));
  };

  const toggleMember = (name: string) => {
    setForm((prev) => {
      const next = new Set(prev.invitedMembers);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return { ...prev, invitedMembers: next };
    });
  };

  const handleCreate = async () => {
    const token = localStorage.getItem("auth_token");
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/rooms/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          name: form.name,
          description: form.description,
          category: form.category,
          member_names: Array.from(form.invitedMembers),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`모임 생성 실패: ${err.detail ?? res.statusText}`);
        return;
      }
      const data = await res.json();
      router.push(`/meeting/${data.id}/schedule`);
    } catch {
      alert("모임 생성 중 오류가 발생했습니다.");
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
      <Header />
      <main
        style={{
          display: "flex",
          justifyContent: "center",
          gap: 28,
          padding: "32px 40px",
          maxWidth: 1440,
          margin: "0 auto",
        }}
      >
        <CreateBasicInfo
          name={form.name}
          description={form.description}
          category={form.category}
          onNameChange={(v) => updateForm({ name: v })}
          onDescriptionChange={(v) => updateForm({ description: v })}
          onCategoryChange={(v) => updateForm({ category: v })}
        />
        <CreateInviteSettings
          invitedMembers={form.invitedMembers}
          scheduleMethod={form.scheduleMethod}
          placeMethod={form.placeMethod}
          onToggleMember={toggleMember}
          onScheduleMethodChange={(v) => updateForm({ scheduleMethod: v })}
          onPlaceMethodChange={(v) => updateForm({ placeMethod: v })}
          onCancel={() => router.back()}
          onCreate={handleCreate}
        />
      </main>
    </div>
  );
}

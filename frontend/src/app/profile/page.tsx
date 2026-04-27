"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  User as UserIcon,
  Mail,
  Calendar,
  Users as UsersIcon,
  CheckCircle2,
  XCircle,
  LogOut,
  ChevronRight,
} from "lucide-react";
import Header from "@/components/layout/Header";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { UserProfile } from "@/types";

interface FriendInfo {
  id: number;
  name: string;
  email: string;
  picture?: string | null;
}

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading: authLoading, logout } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [friendCount, setFriendCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/");
      return;
    }
    let active = true;
    (async () => {
      try {
        const [me, friends] = await Promise.all([
          apiFetch<UserProfile>("/api/v1/users/me"),
          apiFetch<FriendInfo[]>("/api/v1/users/friends").catch(() => [] as FriendInfo[]),
        ]);
        if (!active) return;
        setProfile(me);
        setFriendCount(friends.length);
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : "프로필을 불러오지 못했습니다.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [authLoading, user, router]);

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Header />
        <main className="mx-auto max-w-[760px] px-4 sm:px-6 py-8">
          <p className="text-sm text-slate-400">불러오는 중…</p>
        </main>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Header />
        <main className="mx-auto max-w-[760px] px-4 sm:px-6 py-8">
          <p className="text-sm text-red-500">{error ?? "프로필을 불러오지 못했습니다."}</p>
        </main>
      </div>
    );
  }

  const joinedDate = new Date().toLocaleDateString("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "long",
    day: "numeric",
  }); // /me 응답에 created_at 없음 — 향후 백엔드에서 노출하면 교체

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="mx-auto max-w-[760px] px-4 sm:px-6 py-8 sm:py-12 flex flex-col gap-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold text-slate-900">내 프로필</h1>
          <p className="mt-1 text-sm text-slate-500">
            계정 정보와 기본 통계를 확인합니다.
          </p>
        </div>

        {/* Identity card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 flex items-center gap-4 sm:gap-6">
          <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-[#4f46e5] flex items-center justify-center overflow-hidden shrink-0">
            {profile.picture ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={profile.picture} alt="" className="w-full h-full object-cover" />
            ) : (
              <UserIcon className="w-8 h-8 sm:w-10 sm:h-10 text-white" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-lg sm:text-xl font-bold text-slate-900 truncate">
              {profile.name}
            </p>
            <div className="mt-1 flex items-center gap-1.5 text-sm text-slate-500 truncate">
              <Mail className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{profile.email}</span>
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <StatCard
            icon={UsersIcon}
            label="친구"
            value={friendCount === null ? "-" : `${friendCount}명`}
            color="#16a34a"
          />
          <StatCard
            icon={Calendar}
            label="가입일"
            value={joinedDate}
            color="#7c3aed"
            small
          />
          <StatCard
            icon={profile.calendar_consent ? CheckCircle2 : XCircle}
            label="구글 캘린더"
            value={profile.calendar_consent ? "연동됨" : "미연동"}
            color={profile.calendar_consent ? "#16a34a" : "#94a3b8"}
          />
        </div>

        {/* Quick links */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <LinkRow
            label="선호도 관리"
            sub="개인 데이터 6 카테고리 편집 + AI 활용 동의"
            onClick={() => router.push("/preferences")}
          />
          <LinkRow
            label="설정"
            sub="기본 위치, 음식 메모 등"
            onClick={() => router.push("/settings")}
          />
          <LinkRow
            label="도움말"
            sub="기능 안내 / 자주 묻는 질문"
            onClick={() => router.push("/help")}
          />
        </div>

        {/* Logout */}
        <button
          onClick={logout}
          className="self-start inline-flex items-center gap-2 px-4 py-2 rounded-xl text-[#dc2626] border border-[#fecaca] bg-white hover:bg-[#fef2f2] transition-colors text-sm font-medium"
        >
          <LogOut className="w-4 h-4" />
          로그아웃
        </button>
      </main>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
  small,
}: {
  icon: typeof UserIcon;
  label: string;
  value: string;
  color: string;
  small?: boolean;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 flex items-center gap-3">
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
        style={{ backgroundColor: `${color}1a` }}
      >
        <Icon className="w-5 h-5" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] text-slate-500 font-medium">{label}</p>
        <p
          className={`font-bold text-slate-900 truncate ${small ? "text-[13px]" : "text-base"}`}
        >
          {value}
        </p>
      </div>
    </div>
  );
}

function LinkRow({
  label,
  sub,
  onClick,
}: {
  label: string;
  sub: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition-colors text-left border-b border-slate-100 last:border-b-0"
    >
      <div>
        <p className="text-sm font-semibold text-slate-900">{label}</p>
        <p className="text-[11px] text-slate-500 mt-0.5">{sub}</p>
      </div>
      <ChevronRight className="w-4 h-4 text-slate-400 shrink-0" />
    </button>
  );
}

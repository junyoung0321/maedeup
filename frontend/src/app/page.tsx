"use client";

import { useAuth } from "@/hooks/useAuth";
import LoginPage from "@/components/auth/LoginPage";
import ExplorePage from "@/components/home/ExplorePage";

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-slate-400">로딩 중...</p>
      </div>
    );
  }

  if (!user) return <LoginPage />;
  return <ExplorePage />;
}

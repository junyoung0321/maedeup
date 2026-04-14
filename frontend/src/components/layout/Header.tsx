"use client";

import { useState } from "react";
import Link from "next/link";
import { Bell, User, Menu } from "lucide-react";
import StepIndicator, { Step } from "./StepIndicator";
import NotificationPanel from "@/components/home/NotificationPanel";
import ProfileDropdown from "@/components/home/ProfileDropdown";

interface HeaderProps {
  showSteps?: boolean;
  currentStep?: Step;
}

export default function Header({ showSteps = false, currentStep = "schedule" }: HeaderProps) {
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  return (
    <header>
      <div className="h-[79px] bg-primary-600 flex items-center justify-between px-7 relative">
        <span className="text-white text-[30px] font-normal tracking-wide" style={{ fontFamily: "Pretendard, sans-serif" }}>
          매듭 : AI 모임 플래너
        </span>
        {showSteps && (
          <div className="absolute left-1/2 -translate-x-1/2">
            <StepIndicator currentStep={currentStep} />
          </div>
        )}
        <div className="flex items-center gap-3">
          <Link
            href="/settings"
            className="rounded-full border border-white/20 px-4 py-2 text-sm font-medium text-white/80 transition hover:border-white/40 hover:text-white"
          >
            설정
          </Link>
          <Bell
            className="w-10 h-10 text-white/70 cursor-pointer hover:text-white"
            onClick={() => { setNotifOpen(!notifOpen); setProfileOpen(false); }}
          />
          <User
            className="w-10 h-10 text-white/70 cursor-pointer hover:text-white"
            onClick={() => { setProfileOpen(!profileOpen); setNotifOpen(false); }}
          />
          <Menu className="w-[38px] h-[38px] text-white/70 cursor-pointer hover:text-white" />
        </div>
      </div>
      <NotificationPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
      <ProfileDropdown open={profileOpen} onClose={() => setProfileOpen(false)} />
    </header>
  );
}

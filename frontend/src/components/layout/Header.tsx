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
      <div className="h-[64px] sm:h-[79px] bg-primary-600 flex items-center justify-between px-4 sm:px-7 relative">
        <span
          className="text-white text-[18px] sm:text-[24px] lg:text-[30px] font-normal tracking-wide truncate"
          style={{ fontFamily: "Pretendard, sans-serif" }}
        >
          <span className="lg:hidden">매듭</span>
          <span className="hidden lg:inline">매듭 : AI 모임 플래너</span>
        </span>
        {showSteps && (
          <div className="absolute left-1/2 -translate-x-1/2 hidden lg:block">
            <StepIndicator currentStep={currentStep} />
          </div>
        )}
        <div className="flex items-center gap-2 sm:gap-3">
          <Link
            href="/settings"
            className="hidden sm:inline-flex rounded-full border border-white/20 px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-white/80 transition hover:border-white/40 hover:text-white"
          >
            설정
          </Link>
          <Bell
            className="w-7 h-7 sm:w-9 sm:h-9 lg:w-10 lg:h-10 text-white/70 cursor-pointer hover:text-white"
            onClick={() => { setNotifOpen(!notifOpen); setProfileOpen(false); }}
          />
          <User
            className="w-7 h-7 sm:w-9 sm:h-9 lg:w-10 lg:h-10 text-white/70 cursor-pointer hover:text-white"
            onClick={() => { setProfileOpen(!profileOpen); setNotifOpen(false); }}
          />
          <Menu className="w-7 h-7 sm:w-[34px] sm:h-[34px] lg:w-[38px] lg:h-[38px] text-white/70 cursor-pointer hover:text-white" />
        </div>
      </div>
      <NotificationPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
      <ProfileDropdown open={profileOpen} onClose={() => setProfileOpen(false)} />
    </header>
  );
}

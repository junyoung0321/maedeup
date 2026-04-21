"use client";

import { useState } from "react";
import Link from "next/link";
import { Bell, User, Menu } from "lucide-react";
import StepIndicator, { Step } from "./StepIndicator";
import NotificationPanel from "@/components/home/NotificationPanel";
import ProfileDropdown from "@/components/home/ProfileDropdown";
import MenuPanel from "@/components/home/MenuPanel";

interface HeaderProps {
  showSteps?: boolean;
  currentStep?: Step;
  children?: React.ReactNode;
}

export default function Header({ showSteps = false, currentStep = "schedule", children }: HeaderProps) {
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header>
      <div
        className="h-[79px] bg-primary-600 items-center px-[clamp(12px,1.5vw,28px)] gap-3 grid"
        style={{ gridTemplateColumns: "auto 1fr auto" }}
      >
        <span
          className="text-white font-normal tracking-wide whitespace-nowrap"
          style={{ fontFamily: "Pretendard, sans-serif", fontSize: "clamp(18px, 6px + 1.25vw, 30px)" }}
        >
          매듭 : AI 모임 플래너
        </span>
        <div className="flex items-center justify-center min-w-0 overflow-hidden">
          {showSteps && <StepIndicator currentStep={currentStep} />}
        </div>
        <div className="flex items-center gap-3 justify-self-end">
          {children}
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
          <Menu className="w-[38px] h-[38px] text-white/70 cursor-pointer hover:text-white" onClick={() => { setMenuOpen(!menuOpen); setNotifOpen(false); setProfileOpen(false); }} />
        </div>
      </div>
      <NotificationPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
      <ProfileDropdown open={profileOpen} onClose={() => setProfileOpen(false)} />
      <MenuPanel open={menuOpen} onClose={() => setMenuOpen(false)} />
    </header>
  );
}

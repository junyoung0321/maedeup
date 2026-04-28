"use client";

import { useRouter } from "next/navigation";
import { User, UserCircle, Settings, SlidersHorizontal, HelpCircle, LogOut } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

interface Props {
  open: boolean;
  onClose: () => void;
}

interface MenuItem {
  icon: typeof User;
  label: string;
  route?: string;
  color: string;
  action?: "logout";
}

const MENU_ITEMS: MenuItem[] = [
  { icon: UserCircle, label: "내 프로필", route: "/profile", color: "#374151" },
  { icon: Settings, label: "설정", route: "/settings", color: "#374151" },
  { icon: SlidersHorizontal, label: "선호도 관리", route: "/preferences", color: "#374151" },
  { icon: HelpCircle, label: "도움말", route: "/help", color: "#374151" },
  { icon: LogOut, label: "로그아웃", action: "logout", color: "#ef4444" },
];

export default function ProfileDropdown({ open, onClose }: Props) {
  const { user, logout } = useAuth();
  const router = useRouter();

  if (!open) return null;

  const handleClick = (item: MenuItem) => {
    if (item.action === "logout") {
      logout();
      return;
    }
    if (item.route) {
      onClose();
      router.push(item.route);
    }
  };

  return (
    <div onClick={onClose} className="fixed inset-0 z-[90]">
      <div
        onClick={(e) => e.stopPropagation()}
        className="absolute top-[64px] sm:top-[79px] right-3 sm:right-7 w-[220px] rounded-2xl bg-white shadow-[0_10px_40px_rgba(0,0,0,0.15)] border border-slate-200 flex flex-col overflow-hidden"
        style={{ fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
      >
        {/* User info */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-slate-100">
          <div className="w-10 h-10 rounded-full bg-[#4f46e5] flex items-center justify-center shrink-0 overflow-hidden">
            {user?.picture ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={user.picture}
                alt="profile"
                className="w-10 h-10 object-cover"
              />
            ) : (
              <User className="w-5 h-5 text-white" />
            )}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-semibold text-[#111827] truncate">
              {user?.name ?? ""}
            </span>
            <span className="text-[11px] text-[#94a3b8] truncate">
              {user?.email ?? ""}
            </span>
          </div>
        </div>

        {/* Menu items */}
        <div className="flex flex-col py-1.5">
          {MENU_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                onClick={() => handleClick(item)}
                className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-slate-50 transition-colors text-left"
                style={{ fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
              >
                <Icon className="w-4 h-4 shrink-0" style={{ color: item.color }} />
                <span
                  className="text-[13px] font-medium"
                  style={{ color: item.color }}
                >
                  {item.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

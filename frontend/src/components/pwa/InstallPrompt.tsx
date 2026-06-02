"use client";

import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISS_KEY = "maedeup_install_dismissed_at";
const DISMISS_DAYS = 7;

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // iOS Safari
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

function recentlyDismissed(): boolean {
  try {
    const at = localStorage.getItem(DISMISS_KEY);
    if (!at) return false;
    return Date.now() - Number(at) < DISMISS_DAYS * 864e5;
  } catch {
    return false;
  }
}

export default function InstallPrompt() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [iosHint, setIosHint] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isStandalone() || recentlyDismissed()) return;

    const onBIP = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", onBIP);

    const onInstalled = () => setVisible(false);
    window.addEventListener("appinstalled", onInstalled);

    // iOS는 beforeinstallprompt 미지원 → 수동 안내
    const ua = window.navigator.userAgent.toLowerCase();
    const isIOS = /iphone|ipad|ipod/.test(ua) && !/crios|fxios/.test(ua);
    if (isIOS) {
      setIosHint(true);
      setVisible(true);
    }

    return () => {
      window.removeEventListener("beforeinstallprompt", onBIP);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!visible) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {
      /* ignore */
    }
    setVisible(false);
  };

  const install = async () => {
    if (!deferred) return;
    await deferred.prompt();
    const choice = await deferred.userChoice;
    if (choice.outcome === "accepted") setVisible(false);
    else dismiss();
    setDeferred(null);
  };

  return (
    <div
      role="dialog"
      aria-label="앱 설치 안내"
      style={{ paddingBottom: "max(env(safe-area-inset-bottom), 12px)" }}
      className="pointer-events-none fixed inset-x-0 bottom-0 z-[9999] flex justify-center px-3"
    >
      <div className="pointer-events-auto mb-3 flex w-full max-w-[380px] items-center gap-3 rounded-2xl border border-indigo-100 bg-white px-4 py-3 shadow-[0_8px_30px_rgba(79,70,229,0.18)]">
        <div className="flex h-11 w-11 flex-none items-center justify-center rounded-xl bg-indigo-600 text-white">
          {/* 매듭 연결고리 마크 */}
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
            <circle cx="9" cy="9" r="4.2" stroke="#fff" strokeWidth="2" />
            <circle cx="15" cy="15" r="4.2" stroke="#fff" strokeWidth="2" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-bold leading-tight text-slate-900">매듭 앱으로 설치</div>
          <div className="mt-0.5 truncate text-[12.5px] text-slate-500">
            {iosHint ? "공유 → ‘홈 화면에 추가’" : "홈 화면에 추가하고 앱처럼 사용하세요"}
          </div>
        </div>
        {!iosHint && (
          <button
            onClick={install}
            className="flex-none rounded-xl bg-indigo-600 px-3.5 py-2 text-[13px] font-semibold text-white active:scale-95"
          >
            설치
          </button>
        )}
        <button
          onClick={dismiss}
          aria-label="닫기"
          className="flex-none rounded-lg p-1.5 text-slate-400 active:bg-slate-100"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}

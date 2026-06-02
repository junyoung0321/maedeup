"use client";

import InstallPrompt from "@/components/pwa/InstallPrompt";

// 모바일 앱뷰 셸.
// - 실제 폰/설치형(PWA·TWA): 풀스크린(100dvh, 풀너비) + 노치/홈 세이프에어리어.
// - 데스크탑(md+): 390px 프레임 미리보기 유지(시연/개발용).
export default function MobileLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-center min-h-[100dvh] bg-gray-100 md:bg-gray-100">
      <div
        className="relative w-full min-h-[100dvh] overflow-x-hidden bg-white md:w-[390px] md:min-h-[844px] md:shadow-xl"
        style={{
          // 노치/홈 인디케이터 안전영역 — 비노치 기기에선 0
          paddingTop: "env(safe-area-inset-top)",
          paddingBottom: "env(safe-area-inset-bottom)",
        }}
      >
        {children}
        <InstallPrompt />
      </div>
    </div>
  );
}

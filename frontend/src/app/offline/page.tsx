import type { Metadata } from "next";

export const metadata: Metadata = { title: "오프라인 · 매듭" };

export default function OfflinePage() {
  return (
    <main
      className="flex min-h-[100dvh] flex-col items-center justify-center bg-white px-8 text-center"
      style={{ paddingTop: "env(safe-area-inset-top)", paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-[22px] bg-indigo-600 shadow-lg">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden>
          <circle cx="9" cy="9" r="4.2" stroke="#fff" strokeWidth="2" />
          <circle cx="15" cy="15" r="4.2" stroke="#fff" strokeWidth="2" />
        </svg>
      </div>
      <h1 className="text-[20px] font-extrabold text-slate-900">인터넷 연결이 끊겼어요</h1>
      <p className="mt-2 max-w-[280px] text-[14px] leading-relaxed text-slate-500">
        매듭은 실시간 모임 조율 앱이라 인터넷이 필요해요. 연결을 확인하고 다시 시도해 주세요.
      </p>
      <a
        href="/m"
        className="mt-7 rounded-2xl bg-indigo-600 px-6 py-3 text-[15px] font-semibold text-white active:scale-95"
      >
        다시 시도
      </a>
    </main>
  );
}

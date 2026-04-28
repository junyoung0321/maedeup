"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function MeetingError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    console.error("Meeting page error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center max-w-md mx-auto px-6">
        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-amber-100 flex items-center justify-center">
          <span className="text-2xl">⚠</span>
        </div>
        <h2 className="text-xl font-semibold text-slate-900 mb-2">
          모임 정보를 불러올 수 없어요
        </h2>
        <p className="text-sm text-slate-500 mb-6">
          네트워크 연결을 확인하거나 다시 시도해 주세요.
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="px-6 py-2.5 rounded-full bg-[#4f46e5] text-white text-sm font-semibold hover:bg-[#4338ca] transition-colors"
          >
            다시 시도
          </button>
          <button
            onClick={() => router.push("/")}
            className="px-6 py-2.5 rounded-full border border-slate-300 text-slate-700 text-sm font-semibold hover:bg-slate-100 transition-colors"
          >
            홈으로
          </button>
        </div>
      </div>
    </div>
  );
}

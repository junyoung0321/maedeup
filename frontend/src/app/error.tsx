"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center max-w-md mx-auto px-6">
        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-red-100 flex items-center justify-center">
          <span className="text-2xl">!</span>
        </div>
        <h2 className="text-xl font-semibold text-slate-900 mb-2">
          문제가 발생했어요
        </h2>
        <p className="text-sm text-slate-500 mb-6">
          일시적인 오류일 수 있어요. 다시 시도해 주세요.
        </p>
        <button
          onClick={reset}
          className="px-6 py-2.5 rounded-full bg-[#4f46e5] text-white text-sm font-semibold hover:bg-[#4338ca] transition-colors"
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}

"use client";

import { Calendar, Bot, Users } from "lucide-react";

export default function LoginPage() {
  const handleGoogleLogin = () => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    window.location.href = `${apiBase}/auth/google`;
  };

  return (
    <div
      className="flex h-screen items-center justify-center bg-gradient-to-br from-[#4f46e5] via-[#6366f1] to-[#818cf8]"
      style={{ fontFamily: "Pretendard, sans-serif" }}
    >
      <div className="flex flex-col items-center w-full max-w-[440px] px-6">
        {/* 로고 + 타이틀 */}
        <h1 className="text-white text-[52px] font-semibold mb-3">매듭</h1>
        <p className="text-white/80 text-[18px] font-light text-center mb-10">
          AI와 함께하는 똑똑한 모임 일정 조율
        </p>

        {/* 로그인 카드 */}
        <div className="w-full bg-white rounded-[24px] shadow-2xl p-8">
          <h2 className="text-[#0f172a] text-[26px] font-semibold text-center mb-2">
            시작하기
          </h2>
          <p className="text-[#64748b] text-[14px] font-light text-center mb-8">
            구글 계정으로 간편하게 시작하세요
          </p>

          <button
            onClick={handleGoogleLogin}
            className="w-full h-[52px] bg-white border-[1.5px] border-[#e2e8f0] rounded-[14px] flex items-center justify-center gap-3 hover:bg-slate-50 hover:border-[#cbd5e1] transition-all"
          >
            <svg width="20" height="20" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
            <span className="text-[#334155] text-[16px] font-medium">Google로 계속하기</span>
          </button>

          <p className="text-[#94a3b8] text-[11px] font-light text-center mt-6 leading-[1.6]">
            계속 진행하면 서비스 이용약관 및 개인정보 처리방침에
            동의하는 것으로 간주됩니다.
          </p>
        </div>

        {/* 하단 기능 소개 */}
        <div className="flex items-center gap-8 mt-10">
          {[
            { icon: Calendar, text: "스마트 일정 조율" },
            { icon: Bot, text: "AI 개인 비서" },
            { icon: Users, text: "실시간 그룹 채팅" },
          ].map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-center gap-2">
              <Icon className="w-4 h-4 text-white/60" />
              <span className="text-white/70 text-[13px] font-light">{text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

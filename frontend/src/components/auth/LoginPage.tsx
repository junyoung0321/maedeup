"use client";

import { Calendar, Bot, Users } from "lucide-react";

export default function LoginPage() {
  const handleGoogleLogin = () => {
    window.location.href = "http://localhost:8000/auth/google";
  };

  return (
    <div className="flex h-screen bg-white" style={{ fontFamily: "Pretendard, sans-serif" }}>
      {/* 좌측 패널 - 보라색 그라데이션 */}
      <div className="flex-1 bg-gradient-to-br from-[#4f46e5] via-[#6366f1] to-[#818cf8] flex flex-col items-center justify-center px-16 relative overflow-hidden">
        <h1 className="text-white text-[48px] font-medium mb-6">매듭</h1>
        <p className="text-white text-[20px] font-light text-center mb-10 w-[500px]">
          AI와 함께하는 똑똑한 모임 일정 조율
        </p>
        <div className="flex flex-col gap-4">
          {[
            { icon: Calendar, text: "스마트 일정 조율" },
            { icon: Bot, text: "AI 개인 비서" },
            { icon: Users, text: "실시간 그룹 채팅" },
          ].map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-center gap-3">
              <div className="w-6 h-6 bg-white/20 rounded flex items-center justify-center">
                <Icon className="w-4 h-4 text-white" />
              </div>
              <span className="text-white text-[15px] font-light">{text}</span>
            </div>
          ))}
        </div>

        {/* 하단 장식 프레임 */}
        <div className="mt-12 w-[600px] h-[200px] bg-white/15 rounded-[20px] relative overflow-hidden">
          <div className="absolute top-[30px] left-[40px] w-[120px] h-[90px] bg-white/10 rounded-xl" />
          <div className="absolute top-[10px] left-[55px] w-[90px] h-[20px] bg-white/10 rounded-md" />
          <div className="absolute top-[50px] left-[220px] w-[160px] h-[50px] bg-white/10 rounded-2xl" />
          <div className="absolute top-[115px] left-[250px] w-[140px] h-[45px] bg-white/10 rounded-2xl" />
          <div className="absolute top-[40px] left-[440px] w-[80px] h-[80px] bg-white/5 rounded-full" />
          <div className="absolute top-[100px] left-[490px] w-[50px] h-[50px] bg-white/5 rounded-full" />
        </div>
      </div>

      {/* 우측 패널 - 흰색 로그인 폼 */}
      <div className="flex-1 bg-white flex flex-col items-center justify-center">
        <h2 className="text-[#1e293b] text-[28px] font-medium mb-8">매듭</h2>
        <div className="flex flex-col items-center gap-2 mb-10">
          <h3 className="text-[#0f172a] text-[32px] font-medium">로그인</h3>
          <p className="text-[#64748b] text-[15px] font-light">구글 계정으로 간편하게 시작하세요</p>
        </div>

        <button
          onClick={handleGoogleLogin}
          className="w-[320px] h-[52px] bg-white border-[1.5px] border-[#e2e8f0] rounded-[12px] flex items-center justify-center gap-3 hover:bg-slate-50 transition-colors"
        >
          <svg width="20" height="20" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
          </svg>
          <span className="text-[#334155] text-[16px] font-normal">Google로 계속하기</span>
        </button>

        <div className="flex items-center gap-4 w-[320px] my-6">
          <div className="flex-1 h-px bg-[#e2e8f0]" />
          <span className="text-[#94a3b8] text-[13px] font-light">또는</span>
          <div className="flex-1 h-px bg-[#e2e8f0]" />
        </div>

        <button className="w-[320px] h-[48px] bg-[#f8fafc] border border-[#e2e8f0] rounded-[12px] text-[#64748b] text-[15px] font-light hover:bg-slate-100 transition-colors">
          회원가입 하기
        </button>

        <p className="text-[#94a3b8] text-[12px] font-light text-center mt-8 leading-[1.6] w-[320px]">
          계속 진행하면 서비스 이용약관 및 개인정보 처리방침에
          <br />
          동의하는 것으로 간주됩니다.
        </p>
      </div>
    </div>
  );
}

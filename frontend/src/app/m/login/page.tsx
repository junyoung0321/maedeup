"use client";

import { useRouter } from "next/navigation";

export default function MobileLoginPage() {
  const router = useRouter();
  return (
    <div className="flex flex-col" style={{ width: "100%", height: "var(--m-screen-h)" }}>
      {/* Top Half - Gradient */}
      <div
        className="flex flex-col items-center justify-center"
        style={{
          height: 420,
          background:
            "linear-gradient(180deg, #4f46e5 0%, #6366f1 50%, #818cf8 100%)",
          gap: 20,
        }}
      >
        <span
          className="text-white"
          style={{ fontSize: 48, fontWeight: 800 }}
        >
          매듭
        </span>
        <span style={{ fontSize: 15, fontWeight: 500, color: "#ffffffcc" }}>
          AI와 함께하는 똑똑한 모임 일정 조율
        </span>
        <div className="flex flex-row" style={{ gap: 8 }}>
          {["AI 일정 조율", "장소 추천", "실시간 채팅"].map((label) => (
            <span
              key={label}
              style={{
                background: "#ffffff22",
                borderRadius: 20,
                padding: "6px 14px",
                fontSize: 12,
                fontWeight: 600,
                color: "#ffffffdd",
              }}
            >
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Bottom Half - White */}
      <div
        className="flex flex-col items-center justify-center flex-1 bg-white"
        style={{ padding: "32px 28px 24px 28px", gap: 20 }}
      >
        {/* Brand */}
        <span style={{ fontSize: 24, fontWeight: 800, color: "#4f46e5" }}>
          매듭
        </span>

        {/* Title Section */}
        <div
          className="flex flex-col items-center"
          style={{ gap: 6 }}
        >
          <span style={{ fontSize: 22, fontWeight: 700, color: "#1e293b" }}>
            로그인
          </span>
          <span style={{ fontSize: 14, fontWeight: 400, color: "#64748b" }}>
            모임을 더 쉽게 만들어보세요
          </span>
        </div>

        {/* Google Button */}
        <button
          className="flex flex-row items-center justify-center w-full bg-white cursor-pointer"
          style={{
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            padding: "14px 0",
            gap: 10,
          }}
          onClick={() => {
            const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
            localStorage.setItem("mobile_flow", "true");
            window.location.href = `${apiBase}/auth/google`;
          }}
        >
          <span
            style={{
              fontFamily: "Inter, sans-serif",
              fontSize: 20,
              fontWeight: 700,
              color: "#4285f4",
            }}
          >
            G
          </span>
          <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
            Google로 시작하기
          </span>
        </button>

        {/* Divider */}
        <div
          className="flex flex-row items-center w-full"
          style={{ gap: 12 }}
        >
          <div
            className="flex-1"
            style={{ height: 1, background: "#e2e8f0" }}
          />
          <span style={{ fontSize: 12, fontWeight: 500, color: "#94a3b8" }}>
            또는
          </span>
          <div
            className="flex-1"
            style={{ height: 1, background: "#e2e8f0" }}
          />
        </div>

        {/* Guest Button */}
        <button
          className="flex items-center justify-center w-full cursor-pointer"
          style={{
            borderRadius: 12,
            background: "#f8fafc",
            padding: "14px 0",
            border: "none",
          }}
          onClick={() => router.push("/m/explore")}
        >
          <span style={{ fontSize: 15, fontWeight: 500, color: "#64748b" }}>
            게스트로 둘러보기
          </span>
        </button>

        {/* Terms */}
        <span
          className="text-center"
          style={{ fontSize: 11, fontWeight: 400, color: "#94a3b8" }}
        >
          계속 진행하면 이용약관 및 개인정보처리방침에 동의하게 됩니다.
        </span>
      </div>
    </div>
  );
}

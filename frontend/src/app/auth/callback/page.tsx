"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

function decodeJwt(token: string): { calendar_consent?: boolean; exp: number } {
  const payload = token.split(".")[1];
  return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
}

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");

    if (!token) {
      router.replace("/");
      return;
    }

    localStorage.setItem("auth_token", token);

    try {
      const decoded = decodeJwt(token);
      // 이미 캘린더 동의를 한 유저는 동의 화면 스킵
      if (decoded.calendar_consent) {
        router.replace("/");
      } else {
        router.replace("/consent");
      }
    } catch {
      router.replace("/");
    }
  }, [router]);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background: "#0d0d0d",
        color: "#555",
        fontSize: "13px",
      }}
    >
      로그인 처리 중...
    </div>
  );
}

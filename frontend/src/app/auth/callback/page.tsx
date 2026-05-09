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

    const isMobile = localStorage.getItem("mobile_flow") === "true";
    localStorage.removeItem("mobile_flow");

    try {
      const decoded = decodeJwt(token);
      if (decoded.calendar_consent) {
        router.replace(isMobile ? "/m/" : "/");
      } else {
        router.replace(isMobile ? "/m/consent" : "/consent");
      }
    } catch {
      router.replace(isMobile ? "/m/" : "/");
    }
  }, [router]);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background: "var(--color-bg)",
        color: "var(--color-text-dim)",
        fontSize: "var(--font-size-base)",
      }}
    >
      로그인 처리 중...
    </div>
  );
}

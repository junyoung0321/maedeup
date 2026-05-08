"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, User, ShieldCheck, Check, CircleCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";

function decodeJwt(token: string): { calendar_consent?: boolean; exp: number } {
  const payload = token.split(".")[1];
  return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
}

export default function ConsentPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) { router.replace("/m/login"); return; }
    try {
      const decoded = decodeJwt(token);
      if (decoded.calendar_consent) router.replace("/m/explore");
    } catch {
      router.replace("/m/login");
    }
  }, [router]);

  const handleConsent = async (consent: boolean) => {
    setLoading(true);
    if (consent) {
      try {
        const data = await apiFetch<{ token: string }>("/api/v1/users/me/consent", {
          method: "PATCH",
          body: JSON.stringify({ calendar_consent: true }),
        });
        localStorage.setItem("auth_token", data.token);
      } catch {
        // 동의 저장 실패해도 진행
      }
    }
    router.replace("/m/explore");
  };

  return (
    <div
      className="flex flex-col overflow-hidden"
      style={{
        width: 390,
        height: 844,
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between shrink-0"
        style={{
          height: 56,
          backgroundColor: "#4f46e5",
          padding: "0 20px",
        }}
      >
        <span
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: "#ffffff",
          }}
        >
          매듭
        </span>
        <div className="flex items-center" style={{ gap: 16 }}>
          <Bell size={22} color="#ffffff" strokeWidth={2} style={{ cursor: "pointer" }} onClick={() => router.push("/m/notifications")} />
          <User size={22} color="#ffffff" strokeWidth={2} style={{ cursor: "pointer" }} onClick={() => router.push("/m/profile")} />
        </div>
      </div>

      {/* Content Area */}
      <div
        className="flex flex-col flex-1"
        style={{
          backgroundColor: "#f8fafc",
          padding: "32px 24px",
          gap: 24,
          overflowY: "auto",
        }}
      >
        {/* Title Section */}
        <div
          className="flex flex-col items-center"
          style={{ gap: 8 }}
        >
          <ShieldCheck size={40} color="#4f46e5" strokeWidth={2} />
          <span
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            정보 수집 동의
          </span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 400,
              color: "#64748b",
            }}
          >
            서비스 이용을 위해 아래 정보를 수집합니다
          </span>
        </div>

        {/* Info Card */}
        <div
          className="flex flex-col"
          style={{
            borderRadius: 16,
            backgroundColor: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 20,
            gap: 16,
          }}
        >
          <span
            style={{
              fontSize: 12,
              fontWeight: 500,
              color: "#64748b",
            }}
          >
            매듭은 다음 정보를 수집합니다
          </span>

          {/* Item 1 */}
          <div className="flex items-start" style={{ gap: 12 }}>
            <div
              className="flex items-center justify-center shrink-0"
              style={{
                width: 20,
                height: 20,
                backgroundColor: "#eef2ff",
                borderRadius: 10,
              }}
            >
              <Check size={12} color="#4f46e5" strokeWidth={2.5} />
            </div>
            <div className="flex flex-col" style={{ gap: 2 }}>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "#1e293b",
                }}
              >
                구글 계정 기본 정보
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 400,
                  color: "#94a3b8",
                }}
              >
                이름, 이메일, 프로필 사진
              </span>
            </div>
          </div>

          {/* Divider */}
          <div
            style={{
              height: 1,
              backgroundColor: "#f1f5f9",
            }}
          />

          {/* Item 2 */}
          <div className="flex items-start" style={{ gap: 12 }}>
            <div
              className="flex items-center justify-center shrink-0"
              style={{
                width: 20,
                height: 20,
                backgroundColor: "#eef2ff",
                borderRadius: 10,
              }}
            >
              <Check size={12} color="#4f46e5" strokeWidth={2.5} />
            </div>
            <div className="flex flex-col" style={{ gap: 2 }}>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: "#1e293b",
                }}
              >
                구글 캘린더 바쁜 시간대
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 400,
                  color: "#94a3b8",
                }}
              >
                일정 제목/내용은 수집하지 않습니다
              </span>
            </div>
          </div>
        </div>

        {/* Info Section */}
        <div
          className="flex flex-col"
          style={{ gap: 4, padding: "0 4px" }}
        >
          <span
            style={{
              fontSize: 12,
              fontWeight: 400,
              color: "#94a3b8",
            }}
          >
            수집 목적: 모임 가능 시간 자동 조율
          </span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 400,
              color: "#94a3b8",
            }}
          >
            보유 기간: 서비스 탈퇴 시 즉시 삭제
          </span>
        </div>

        {/* Agree Button */}
        <button
          className="flex items-center justify-center w-full shrink-0"
          style={{
            borderRadius: 12,
            backgroundColor: "#4f46e5",
            height: 48,
            gap: 8,
            border: "none",
            cursor: "pointer",
            opacity: loading ? 0.7 : 1,
          }}
          disabled={loading}
          onClick={() => handleConsent(true)}
        >
          <CircleCheck size={18} color="#ffffff" strokeWidth={2} />
          <span
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: "#ffffff",
            }}
          >
            {loading ? "처리 중…" : "동의하고 시작하기"}
          </span>
        </button>

        {/* Deny Button */}
        <button
          className="flex items-center justify-center w-full shrink-0"
          style={{
            borderRadius: 12,
            backgroundColor: "#ffffff",
            border: "1px solid #e2e8f0",
            height: 44,
            cursor: loading ? "not-allowed" : "pointer",
          }}
          disabled={loading}
          onClick={() => handleConsent(false)}
        >
          <span
            style={{
              fontSize: 14,
              fontWeight: 500,
              color: "#64748b",
            }}
          >
            거부 (채팅만 사용)
          </span>
        </button>

        {/* Footer */}
        <span
          className="text-center"
          style={{
            fontSize: 10,
            fontWeight: 400,
            color: "#94a3b8",
          }}
        >
          거부 시 캘린더 연동 없이 채팅 기능만 이용 가능합니다.
        </span>
      </div>
    </div>
  );
}

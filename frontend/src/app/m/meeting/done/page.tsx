"use client";

import { useRouter } from "next/navigation";
import { Bell, User, Users, Calendar, MapPin, Share2, House } from "lucide-react";

export default function MeetingDonePage() {
  const router = useRouter();
  return (
    <div
      className="relative flex flex-col"
      style={{
        width: 390,
        height: 844,
        overflow: "hidden",
        backgroundColor: "#ffffffff",
      }}
    >
      {/* Header */}
      <div
        className="relative shrink-0"
        style={{ height: 56, backgroundColor: "#4f46e5" }}
      >
        <span
          className="absolute"
          style={{
            left: 16,
            top: 16,
            fontFamily: "Pretendard, sans-serif",
            fontSize: 20,
            fontWeight: 700,
            color: "#ffffff",
            lineHeight: "24px",
          }}
        >
          매듭
        </span>
        <Bell
          className="absolute cursor-pointer"
          style={{ left: 314, top: 18, width: 22, height: 22 }}
          color="#ffffff"
          strokeWidth={2}
          onClick={() => router.push("/m/notifications")}
        />
        <User
          className="absolute cursor-pointer"
          style={{ left: 350, top: 18, width: 22, height: 22 }}
          color="#ffffff"
          strokeWidth={2}
          onClick={() => router.push("/m/profile")}
        />
      </div>

      {/* Main content */}
      <div
        className="flex flex-1 flex-col justify-center items-center"
        style={{ padding: "0 20px", gap: 24 }}
      >
        {/* Title area */}
        <div className="flex flex-col items-center w-full" style={{ gap: 8 }}>
          <p
            className="w-full text-center whitespace-pre-line"
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 22,
              fontWeight: 700,
              color: "#0f172a",
              lineHeight: "32px",
              margin: 0,
            }}
          >
            {"모임이 성공적으로\n생성되었어요!"}
          </p>
          <p
            className="text-center"
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 14,
              fontWeight: 400,
              color: "#64748b",
              margin: 0,
            }}
          >
            참여자들에게 초대 알림이 전송되었습니다
          </p>
        </div>

        {/* Summary card */}
        <div
          className="flex flex-col w-full"
          style={{
            borderRadius: 16,
            backgroundColor: "#f8faff",
            border: "1px solid #e2e8f0",
            padding: 20,
            gap: 16,
          }}
        >
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 16,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            모임 정보
          </span>
          <div style={{ height: 1, backgroundColor: "#e2e8f0" }} />

          {/* Row 1 - 모임명 */}
          <div className="flex items-center" style={{ gap: 10 }}>
            <Users style={{ width: 18, height: 18, flexShrink: 0 }} color="#4f46e5" strokeWidth={2} />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#64748b",
                flexShrink: 0,
              }}
            >
              모임명
            </span>
            <span
              className="ml-auto"
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#1e293b",
              }}
            >
              졸업 프로젝트 회의
            </span>
          </div>

          {/* Row 2 - 일시 */}
          <div className="flex items-center" style={{ gap: 10 }}>
            <Calendar style={{ width: 18, height: 18, flexShrink: 0 }} color="#4f46e5" strokeWidth={2} />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#64748b",
                flexShrink: 0,
              }}
            >
              일시
            </span>
            <span
              className="ml-auto"
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#1e293b",
              }}
            >
              3월 23일 (월) 오후 3:00
            </span>
          </div>

          {/* Row 3 - 장소 */}
          <div className="flex items-center" style={{ gap: 10 }}>
            <MapPin style={{ width: 18, height: 18, flexShrink: 0 }} color="#4f46e5" strokeWidth={2} />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#64748b",
                flexShrink: 0,
              }}
            >
              장소
            </span>
            <span
              className="ml-auto"
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#1e293b",
              }}
            >
              강남역 스타벅스 3층
            </span>
          </div>

          {/* Row 4 - 참여자 */}
          <div className="flex items-center" style={{ gap: 10 }}>
            <User style={{ width: 18, height: 18, flexShrink: 0 }} color="#4f46e5" strokeWidth={2} />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#64748b",
                flexShrink: 0,
              }}
            >
              참여자
            </span>
            <div className="flex ml-auto" style={{ paddingLeft: 6 }}>
              {["#c7d2fe", "#93c5fd", "#86efac", "#fca5a5", "#fde68a"].map(
                (color, i) => (
                  <div
                    key={i}
                    className="rounded-full border-2 border-white"
                    style={{
                      width: 22,
                      height: 22,
                      backgroundColor: color,
                      marginLeft: i === 0 ? 0 : -6,
                      zIndex: 5 - i,
                      flexShrink: 0,
                    }}
                  />
                )
              )}
            </div>
          </div>
        </div>

        {/* Button column */}
        <div className="flex flex-col w-full" style={{ gap: 12 }}>
          {/* Share button */}
          <button
            className="flex items-center justify-center w-full"
            onClick={() => alert("모임 링크가 복사되었습니다!")}
            style={{
              borderRadius: 12,
              backgroundColor: "#4f46e5",
              height: 48,
              gap: 8,
              border: "none",
              cursor: "pointer",
            }}
          >
            <Share2 style={{ width: 18, height: 18 }} color="#ffffff" strokeWidth={2} />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 15,
                fontWeight: 600,
                color: "#ffffff",
              }}
            >
              모임 공유하기
            </span>
          </button>

          {/* Home button */}
          <button
            className="flex items-center justify-center w-full"
            onClick={() => router.push("/m/explore")}
            style={{
              borderRadius: 12,
              backgroundColor: "#ffffff",
              border: "1.5px solid #e2e8f0",
              height: 48,
              gap: 8,
              cursor: "pointer",
            }}
          >
            <House style={{ width: 18, height: 18 }} color="#4f46e5" strokeWidth={2} />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 15,
                fontWeight: 600,
                color: "#4f46e5",
              }}
            >
              모임 목록으로
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}

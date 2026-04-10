"use client";

import Link from "next/link";

const pages = [
  { href: "/m/login", label: "M 1.0 로그인", desc: "Google OAuth 로그인" },
  { href: "/m/consent", label: "M 1.1 동의", desc: "정보 수집 동의" },
  { href: "/m/friends", label: "M 2.0 친구", desc: "친구 목록" },
  { href: "/m/explore", label: "M 2.1 모임 탐색", desc: "홈 / AI 추천 모임" },
  { href: "/m/meeting/new", label: "M 2.2 모임 생성", desc: "새 모임 만들기" },
  { href: "/m/chat/schedule", label: "M 3.0a 일정 조율 채팅", desc: "채팅 + AI 일정 분석" },
  { href: "/m/chat/place", label: "M 3.0b 장소 조율 채팅", desc: "채팅 + AI 장소 추천" },
  { href: "/m/schedule", label: "M 3.1 일정 조율", desc: "캘린더 투표" },
  { href: "/m/schedule/confirm", label: "M 3.1b 일정 확정", desc: "투표 결과 확인" },
  { href: "/m/place", label: "M 3.2 장소 조율", desc: "AI 장소 추천 목록" },
  { href: "/m/place/detail", label: "M 3.2c 장소 상세", desc: "장소 상세 정보" },
  { href: "/m/meeting/confirm", label: "M 3.2b 모임 확정", desc: "모임 최종 확인" },
  { href: "/m/meeting/done", label: "M 3.3 생성 완료", desc: "모임 생성 성공" },
  { href: "/m/calendar", label: "M 4.0 캘린더", desc: "월별 캘린더" },
  { href: "/m/profile", label: "M 5.0 프로필", desc: "프로필 / 설정" },
  { href: "/m/chat", label: "M 6.0 채팅 목록", desc: "AI 비서 + 모임 채팅 리스트" },
  { href: "/m/chat/ai", label: "M 6.1 AI 비서 채팅", desc: "AI 비서 대화" },
  { href: "/m/notifications", label: "M 7.0 알림", desc: "알림 목록" },
  { href: "/m/meeting/detail", label: "M 8.0 모임 상세", desc: "모임 정보 + 멤버" },
];

export default function MobileIndex() {
  return (
    <div className="flex flex-col gap-3 p-6">
      <div className="mb-2">
        <h1
          style={{
            fontSize: 28,
            fontWeight: 800,
            color: "#4f46e5",
            fontFamily: "'Pretendard Variable', Pretendard, sans-serif",
          }}
        >
          매듭 모바일 웹뷰
        </h1>
        <p style={{ fontSize: 14, color: "#64748b", marginTop: 4 }}>
          {pages.length}개 모바일 페이지 목록
        </p>
      </div>
      {pages.map((p) => (
        <Link
          key={p.href}
          href={p.href}
          className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3 transition hover:border-indigo-300 hover:bg-indigo-50"
        >
          <div>
            <span
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: "#1e293b",
                fontFamily: "'Pretendard Variable', Pretendard, sans-serif",
              }}
            >
              {p.label}
            </span>
            <p style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>
              {p.desc}
            </p>
          </div>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#cbd5e1"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m9 18 6-6-6-6" />
          </svg>
        </Link>
      ))}
    </div>
  );
}

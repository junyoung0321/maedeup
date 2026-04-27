"use client";

import { useState } from "react";
import {
  HelpCircle,
  Bot,
  Calendar,
  Sparkles,
  Shield,
  Users,
  ChevronDown,
} from "lucide-react";
import Header from "@/components/layout/Header";

interface Section {
  icon: typeof HelpCircle;
  iconColor: string;
  title: string;
  body: React.ReactNode;
}

const SECTIONS: Section[] = [
  {
    icon: HelpCircle,
    iconColor: "#4f46e5",
    title: "매듭이 뭔가요?",
    body: (
      <p>
        매듭은 친구들과 모임을 잡을 때 일정·장소를 AI가 함께 조율해주는 앱입니다.
        모임방에서 자유롭게 대화하면 AI가 맥락을 이해해서 투표 카드, 장소 추천, 최종
        매듭 카드까지 자동으로 만들어줍니다. 채팅 도중 사용자가 한 말(못 먹는 음식,
        선호 지역 등)을 AI가 기억해서 다음 추천에 반영합니다.
      </p>
    ),
  },
  {
    icon: Bot,
    iconColor: "#7c3aed",
    title: "비서 어시스턴트는 모임방의 AI와 어떻게 다른가요?",
    body: (
      <ul className="list-disc pl-5 space-y-1.5">
        <li>
          <span className="font-semibold">모임방 AI</span> — 룸 단위. 친구들과
          대화 중에 일정/장소를 함께 정리. 투표 카드, 장소 추천 카드 같은 결과물을 만듦.
        </li>
        <li>
          <span className="font-semibold">홈 비서 어시스턴트</span> — 사용자 단위.
          1:1 대화. 내 일정, 친구, 개인 데이터를 기반으로 질문에 답함. 모임 생성은
          하지 않음 (안내만).
        </li>
      </ul>
    ),
  },
  {
    icon: Sparkles,
    iconColor: "#a855f7",
    title: "✨ 마크는 무슨 의미인가요?",
    body: (
      <>
        <p>
          AI가 모임 채팅에서 자동으로 학습해 채운 항목입니다. 예를 들어 모임방에서
          “나 갑각류 못 먹어”라고 발화하면 모임 종료 시점에 음식 제한 칸에 ✨와 함께
          “갑각류 알레르기”가 추가됩니다.
        </p>
        <p className="mt-2">
          ✨를 클릭하면 어느 모임 / 어느 발화에서 학습됐는지 출처가 보입니다. 잘못된
          내용이면 카드 클릭 → 직접 수정하면 ✨가 사라지고 사용자 입력으로 변경됩니다.
        </p>
      </>
    ),
  },
  {
    icon: Shield,
    iconColor: "#16a34a",
    title: "내 데이터는 어떻게 보호되나요?",
    body: (
      <ul className="list-disc pl-5 space-y-1.5">
        <li>개인 데이터는 본인 화면에서만 보입니다. 친구 화면엔 절대 노출되지 않습니다.</li>
        <li>
          AI는 모임 추천 시점에만 멤버들의 데이터를 비공개로 합성합니다 — 추천
          reasoning에서 "갑각류 회피 고려" 같은 익명 형태로만 표시되며, 누가 어떤
          제약을 가졌는지는 식별되지 않습니다.
        </li>
        <li>
          빠른 선호 설정 / 선호도 관리에서 카테고리별 활용 동의를 끄면 해당
          카테고리는 추천 합성에서 제외됩니다 (값은 유지, 합성 시 skip).
        </li>
      </ul>
    ),
  },
  {
    icon: Calendar,
    iconColor: "#2563eb",
    title: "구글 캘린더 연동은 어떻게 하나요?",
    body: (
      <>
        <p>
          처음 로그인할 때 “캘린더 접근 동의”에서 허용하면 연동됩니다. 연동 후 빠른
          선호 설정 / 선호도 관리의 토글로 AI가 캘린더를 참고할지 끄고 켤 수 있습니다.
        </p>
        <p className="mt-2 text-[11px] text-slate-500">
          토글을 OFF해도 OAuth 토큰 자체는 유지됩니다 — 다시 ON하면 즉시 작동.
          OAuth 자체를 해지하려면 구글 계정 설정 → 보안 → 매듭 액세스 권한 제거.
        </p>
      </>
    ),
  },
  {
    icon: Users,
    iconColor: "#ec4899",
    title: "모임은 어떻게 만드나요?",
    body: (
      <ul className="list-disc pl-5 space-y-1.5">
        <li>홈 화면 하단 “모임 생성” 버튼 → 새 모임방 생성.</li>
        <li>친구를 초대하고 채팅으로 자유롭게 대화. 날짜·장소 후보가 나오면 AI가 투표 카드를 자동으로 띄웁니다.</li>
        <li>투표 결과 + 장소 추천이 모이면 AI가 “매듭 카드”를 만들어 모임을 확정합니다.</li>
      </ul>
    ),
  },
  {
    icon: HelpCircle,
    iconColor: "#0ea5e9",
    title: "자주 묻는 질문",
    body: (
      <div className="space-y-3">
        <div>
          <p className="font-semibold text-slate-900">
            Q. AI가 잘못된 정보를 기억했어요. 어떻게 수정하나요?
          </p>
          <p className="text-slate-600 text-[13px] mt-0.5">
            홈의 “내 개인 데이터” 카드 클릭 → 해당 카테고리 직접 수정 → 저장. ✨는
            자동으로 사라지고 사용자 입력으로 표시됩니다.
          </p>
        </div>
        <div>
          <p className="font-semibold text-slate-900">
            Q. 비서 대화 기록을 지우고 싶어요.
          </p>
          <p className="text-slate-600 text-[13px] mt-0.5">
            홈의 비서 어시스턴트 패널 헤더의 휴지통 아이콘 → 확인 시 전체 삭제.
          </p>
        </div>
        <div>
          <p className="font-semibold text-slate-900">
            Q. 친구가 보낸 모임 초대는 어디서 보나요?
          </p>
          <p className="text-slate-600 text-[13px] mt-0.5">
            홈 화면 우상단 종 아이콘(알림) → 모임 초대 알림 클릭 → 해당 방으로 이동.
          </p>
        </div>
      </div>
    ),
  },
];

export default function HelpPage() {
  const [openIdx, setOpenIdx] = useState<Set<number>>(new Set([0]));

  const toggle = (idx: number) => {
    setOpenIdx((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="mx-auto max-w-[760px] px-4 sm:px-6 py-8 sm:py-12 flex flex-col gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold text-slate-900">
            도움말
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            매듭의 주요 기능과 데이터 보호 정책을 설명합니다.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          {SECTIONS.map((s, idx) => {
            const Icon = s.icon;
            const isOpen = openIdx.has(idx);
            return (
              <div
                key={s.title}
                className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden"
              >
                <button
                  onClick={() => toggle(idx)}
                  className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-slate-50 transition-colors"
                  aria-expanded={isOpen}
                >
                  <div
                    className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                    style={{ backgroundColor: `${s.iconColor}1a` }}
                  >
                    <Icon className="w-4.5 h-4.5" style={{ color: s.iconColor }} />
                  </div>
                  <span className="flex-1 text-sm sm:text-base font-semibold text-slate-900">
                    {s.title}
                  </span>
                  <ChevronDown
                    className={`w-4 h-4 text-slate-400 transition-transform ${
                      isOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 text-[13px] sm:text-sm text-slate-700 leading-relaxed border-t border-slate-100 pt-4">
                    {s.body}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-[11px] text-slate-400 text-center mt-4">
          더 자세한 문의는 졸업 시연 담당자에게 연락해주세요.
        </p>
      </main>
    </div>
  );
}

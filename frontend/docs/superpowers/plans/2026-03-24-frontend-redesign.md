# 매듭 프론트엔드 전면 리디자인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pencil.pen 디자인 5개 화면을 Tailwind CSS 기반으로 구현하여 기존 다크 테마를 전면 교체한다.

**Architecture:** Next.js 14 App Router + Tailwind CSS + TypeScript. 기존 인라인 스타일/CSS 변수를 Tailwind 유틸리티 클래스로 대체. 목(mock) 데이터로 UI를 먼저 완성하고, 기존 WebSocket 훅/인증 훅은 유지한다.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, Lucide React (아이콘), Pretendard (폰트)

**Spec:** `docs/superpowers/specs/2026-03-24-frontend-redesign-design.md`

**Project Root:** `C:\Users\user\OneDrive - koreatech.ac.kr\바탕 화면\26-1\졸설\cursor_meeting_service\maedeup\frontend`

---

## File Map

### 생성할 파일

```
# Tailwind 설정
tailwind.config.ts
postcss.config.js

# Mock 데이터
src/mocks/friends.ts
src/mocks/meetings.ts
src/mocks/recommendations.ts
src/mocks/calendar.ts
src/mocks/places.ts
src/mocks/chatMessages.ts

# UI 공통 컴포넌트
src/components/ui/Avatar.tsx
src/components/ui/Badge.tsx
src/components/ui/Button.tsx
src/components/ui/Card.tsx

# 레이아웃 컴포넌트
src/components/layout/Header.tsx
src/components/layout/StepIndicator.tsx

# 홈 (모임 탐색) 컴포넌트
src/components/home/ExplorePage.tsx
src/components/home/AiRecommendCard.tsx
src/components/home/FriendList.tsx
src/components/home/MeetingList.tsx
src/components/home/MiniCalendar.tsx

# 미팅 생성 플로우 컴포넌트
src/components/meeting/ChatPane.tsx
src/components/meeting/AiAssistantPane.tsx
src/components/meeting/CalendarPane.tsx
src/components/meeting/PlaceDetailPane.tsx
src/components/meeting/CompletionPage.tsx

# 채팅 컴포넌트
src/components/chat/ChatBubble.tsx
src/components/chat/ChatInput.tsx

# 라우트 페이지
src/app/meeting/[id]/schedule/page.tsx
src/app/meeting/[id]/place/page.tsx
src/app/meeting/[id]/done/page.tsx
```

### 수정할 파일

```
src/app/globals.css           → Tailwind directives로 교체
src/app/layout.tsx            → Tailwind + Pretendard 폰트 설정
src/app/page.tsx              → 인증 분기 (로그인 / 모임 탐색)
src/components/auth/LoginPage.tsx → 좌우 분할 리디자인
```

### 삭제할 파일

```
src/components/agent/AgentPane.tsx
src/components/meeting/DataPane.tsx
src/components/social/SocialPane.tsx
src/components/chat/ChatMessageBubble.tsx
src/components/chat/ChatInputBar.tsx
```

---

## Task 1: Tailwind CSS 설치 및 기본 설정

**Files:**
- Create: `tailwind.config.ts`
- Create: `postcss.config.js`
- Modify: `src/app/globals.css`
- Modify: `src/app/layout.tsx`

- [ ] **Step 1: Tailwind CSS + 의존성 설치**

```bash
cd "C:\Users\user\OneDrive - koreatech.ac.kr\바탕 화면\26-1\졸설\cursor_meeting_service\maedeup\frontend"
npm install -D tailwindcss postcss autoprefixer
npm install lucide-react
npx tailwindcss init -p --ts
```

- [ ] **Step 2: tailwind.config.ts 작성**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f8faff",
          100: "#c7d2fe",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
        },
        accent: {
          50: "#cff9fe",
          100: "#a2f4fd",
          300: "#5ed3e8",
          400: "#22d3ee",
        },
      },
      fontFamily: {
        pretendard: ["Pretendard", "Noto Sans KR", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
```

- [ ] **Step 3: globals.css를 Tailwind directives로 교체**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@font-face {
  font-family: "Pretendard";
  src: url("/Pretendard-Black.otf") format("opentype");
  font-weight: 900;
  font-display: swap;
}

body {
  font-family: "Pretendard", "Noto Sans KR", sans-serif;
}
```

- [ ] **Step 4: layout.tsx 수정 — Tailwind 적용**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "매듭 (Maedeup)",
  description: "AI와 함께하는 똑똑한 모임 일정 조율",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-white font-pretendard antialiased">
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 5: dev 서버 실행하여 Tailwind 동작 확인**

```bash
npm run dev
```

브라우저에서 `localhost:3000` 접속, 페이지가 흰색 배경으로 뜨면 성공.

- [ ] **Step 6: 커밋**

```bash
git add tailwind.config.ts postcss.config.js src/app/globals.css src/app/layout.tsx package.json package-lock.json
git commit -m "chore: Tailwind CSS 설치 및 기본 설정"
```

---

## Task 2: Mock 데이터 생성

**Files:**
- Create: `src/mocks/friends.ts`
- Create: `src/mocks/meetings.ts`
- Create: `src/mocks/recommendations.ts`
- Create: `src/mocks/calendar.ts`
- Create: `src/mocks/places.ts`
- Create: `src/mocks/chatMessages.ts`

- [ ] **Step 1: src/mocks/friends.ts**

```typescript
export interface Friend {
  id: string;
  name: string;
  color: string;
  online: boolean;
}

export const mockFriends: Friend[] = [
  { id: "1", name: "김준영", color: "#818cf8", online: true },
  { id: "2", name: "정은빈", color: "#f472b6", online: true },
  { id: "3", name: "한도이", color: "#34d399", online: false },
  { id: "4", name: "가인영", color: "#fbbf24", online: true },
  { id: "5", name: "김의탁", color: "#60a5fa", online: false },
  { id: "6", name: "유윤영", color: "#a78bfa", online: true },
  { id: "7", name: "최태헌", color: "#f87171", online: false },
  { id: "8", name: "최성은", color: "#4ade80", online: true },
];
```

- [ ] **Step 2: src/mocks/meetings.ts**

```typescript
export interface Meeting {
  id: string;
  name: string;
  emoji: string;
  memberCount: number;
  category: string;
}

export const mockMeetings: Meeting[] = [
  { id: "1", name: "자바 스터디", emoji: "☕", memberCount: 5, category: "스터디" },
  { id: "2", name: "파왕 볼스 팀", emoji: "🎳", memberCount: 8, category: "운동" },
  { id: "3", name: "혼술 의식", emoji: "🍺", memberCount: 3, category: "친목" },
  { id: "4", name: "걸어 회의 팀", emoji: "🚶", memberCount: 4, category: "업무" },
  { id: "5", name: "수영 7월 근육", emoji: "🏊", memberCount: 6, category: "운동" },
];
```

- [ ] **Step 3: src/mocks/recommendations.ts**

```typescript
export interface Recommendation {
  id: string;
  title: string;
  description: string;
  time: string;
  memberCount: number;
  type: "schedule" | "place" | "activity";
}

export const mockRecommendations: Recommendation[] = [
  {
    id: "1",
    title: "카카오톡 기획 스터디",
    description: "오후 2시 60분 · 온라인",
    time: "01:20:00",
    memberCount: 4,
    type: "schedule",
  },
  {
    id: "2",
    title: "서현 후 금요일 추천 장소",
    description: "강남역 3번 출구 인근",
    time: "02:45:00",
    memberCount: 6,
    type: "place",
  },
  {
    id: "3",
    title: "지금 바로로 연락 가능",
    description: "참여 가능한 멤버 확인",
    time: "",
    memberCount: 3,
    type: "activity",
  },
];
```

- [ ] **Step 4: src/mocks/calendar.ts**

```typescript
export interface CalendarEvent {
  id: string;
  title: string;
  date: string;
  startTime: string;
  endTime: string;
  color: string;
}

export const mockCalendarEvents: CalendarEvent[] = [
  { id: "1", title: "과고 2기3 팀 세미나 2:00 ~ 6:00", date: "2026-03-23", startTime: "14:00", endTime: "18:00", color: "#818cf8" },
  { id: "2", title: "1/24일 해 보러 3:45 ~ 5:00", date: "2026-03-24", startTime: "15:45", endTime: "17:00", color: "#f59e0b" },
  { id: "3", title: "팀 점심 12:00 ~ 13:30", date: "2026-03-25", startTime: "12:00", endTime: "13:30", color: "#34d399" },
];
```

- [ ] **Step 5: src/mocks/places.ts**

```typescript
export interface Place {
  id: string;
  name: string;
  category: string;
  rating: number;
  distance: string;
  address: string;
  phone: string;
  menu: { name: string; price: number }[];
  imageUrl?: string;
}

export const mockPlaces: Place[] = [
  {
    id: "1",
    name: "을지로 풀무식당",
    category: "한식",
    rating: 4.5,
    distance: "1~2인터뷰",
    address: "서울 강남구 역삼동 828-3 1~2",
    phone: "02-1234-5678",
    menu: [
      { name: "돼지국밥 양식", price: 12000 },
      { name: "해물찜 양식", price: 15000 },
      { name: "김치찌개", price: 12500 },
    ],
  },
  {
    id: "2",
    name: "을지로 블루식당",
    category: "한식",
    rating: 4.2,
    distance: "500m",
    address: "서울 강남구 역삼동 112-5",
    phone: "02-5678-1234",
    menu: [
      { name: "된장찌개", price: 9000 },
      { name: "불고기 정식", price: 13000 },
    ],
  },
];
```

- [ ] **Step 6: src/mocks/chatMessages.ts**

```typescript
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  sender: string;
  content: string;
  timestamp: string;
}

export const mockSocialMessages: ChatMessage[] = [
  { id: "1", role: "user", sender: "김준영", content: "지금 회사 연해 끝나요?", timestamp: "14:30" },
  { id: "2", role: "user", sender: "정은빈", content: "저는 다음주에 점도 가능해요.", timestamp: "14:31" },
  { id: "3", role: "user", sender: "김준영", content: "저도 다음주에 다 가능합니다!", timestamp: "14:32" },
  { id: "4", role: "user", sender: "정은빈", content: "강남이나 논현 어때요?", timestamp: "14:33" },
  { id: "5", role: "user", sender: "한도이", content: "그럼 강남에서 봐요?", timestamp: "14:34" },
  { id: "6", role: "user", sender: "김준영", content: "네 좋습니다!", timestamp: "14:35" },
  { id: "7", role: "user", sender: "정은빈", content: "시간은 언제가 좋을까요?", timestamp: "14:36" },
  { id: "8", role: "user", sender: "김준영", content: "저녁 7시 괜찮을까요?", timestamp: "14:37" },
];

export const mockAgentMessages: ChatMessage[] = [
  { id: "1", role: "system", sender: "AI", content: "현재 일정이 모두 확인되셨습니다!", timestamp: "14:30" },
  { id: "2", role: "assistant", sender: "AI", content: "가능 시간 나오신 분들을 확인합니다.\n참여 대상을 위확해야 일정 조율 추진이 가능합니다.", timestamp: "14:31" },
  { id: "3", role: "user", sender: "나", content: "네, 다음주에서 가능한 시간 알려주세요", timestamp: "14:32" },
  { id: "4", role: "assistant", sender: "AI", content: "네, 다음주에서 가능한요일?\n시간대를 조사하겠습니다.", timestamp: "14:33" },
];
```

- [ ] **Step 7: 커밋**

```bash
git add src/mocks/
git commit -m "feat: mock 데이터 파일 생성 (friends, meetings, places, calendar, chat)"
```

---

## Task 3: UI 공통 컴포넌트

**Files:**
- Create: `src/components/ui/Avatar.tsx`
- Create: `src/components/ui/Badge.tsx`
- Create: `src/components/ui/Button.tsx`
- Create: `src/components/ui/Card.tsx`

- [ ] **Step 1: Avatar.tsx**

```tsx
interface AvatarProps {
  name: string;
  color: string;
  size?: "sm" | "md" | "lg";
}

const sizeMap = { sm: "w-8 h-8 text-xs", md: "w-10 h-10 text-sm", lg: "w-12 h-12 text-base" };

export default function Avatar({ name, color, size = "md" }: AvatarProps) {
  return (
    <div
      className={`${sizeMap[size]} rounded-full flex items-center justify-center text-white font-semibold shrink-0`}
      style={{ backgroundColor: color }}
    >
      {name.charAt(0)}
    </div>
  );
}
```

- [ ] **Step 2: Badge.tsx**

```tsx
interface BadgeProps {
  children: React.ReactNode;
  variant?: "primary" | "accent" | "neutral";
}

const variantMap = {
  primary: "bg-primary-100 text-primary-600",
  accent: "bg-accent-100 text-accent-400",
  neutral: "bg-slate-100 text-slate-500",
};

export default function Badge({ children, variant = "primary" }: BadgeProps) {
  return (
    <span className={`${variantMap[variant]} px-2 py-0.5 rounded-full text-xs font-medium`}>
      {children}
    </span>
  );
}
```

- [ ] **Step 3: Button.tsx**

```tsx
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}

const variantMap = {
  primary: "bg-primary-600 text-white hover:bg-primary-500",
  secondary: "bg-white text-primary-600 border border-primary-600 hover:bg-primary-50",
  ghost: "bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100",
};

const sizeMap = { sm: "px-3 py-1.5 text-sm", md: "px-5 py-2.5 text-base", lg: "px-6 py-3 text-lg" };

export default function Button({ variant = "primary", size = "md", className = "", children, ...props }: ButtonProps) {
  return (
    <button
      className={`${variantMap[variant]} ${sizeMap[size]} rounded-xl font-semibold transition-colors ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 4: Card.tsx**

```tsx
interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export default function Card({ children, className = "" }: CardProps) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 shadow-md ${className}`}>
      {children}
    </div>
  );
}
```

- [ ] **Step 5: 커밋**

```bash
git add src/components/ui/
git commit -m "feat: UI 공통 컴포넌트 (Avatar, Badge, Button, Card)"
```

---

## Task 4: 레이아웃 컴포넌트 (Header, StepIndicator)

**Files:**
- Create: `src/components/layout/Header.tsx`
- Create: `src/components/layout/StepIndicator.tsx`

- [ ] **Step 1: StepIndicator.tsx**

```tsx
import { ChevronRight } from "lucide-react";

export type Step = "schedule" | "place" | "done";

interface StepIndicatorProps {
  currentStep: Step;
}

const steps: { key: Step; label: string }[] = [
  { key: "schedule", label: "일정" },
  { key: "place", label: "장소" },
  { key: "done", label: "생성 완료" },
];

export default function StepIndicator({ currentStep }: StepIndicatorProps) {
  const currentIndex = steps.findIndex((s) => s.key === currentStep);

  return (
    <div className="flex items-center gap-2">
      {steps.map((step, i) => {
        const isActive = i <= currentIndex;
        const isCurrent = step.key === currentStep;
        return (
          <div key={step.key} className="flex items-center gap-2">
            {i > 0 && <ChevronRight className="w-4 h-4 text-accent-300" />}
            <div
              className={`w-[42px] h-[37px] rounded-full flex items-center justify-center text-sm font-semibold border-2 ${
                isActive
                  ? "bg-gradient-to-r from-[#2286ff] to-[#00b5dd] border-[#00d1ff] text-white"
                  : "bg-accent-100 border-accent-100 text-accent-300"
              }`}
            >
              {i + 1}
            </div>
            <span
              className={`text-xl tracking-wide ${
                isCurrent ? "font-semibold text-white" : "text-accent-300"
              }`}
            >
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Header.tsx**

```tsx
import { Bell, User, Menu } from "lucide-react";
import StepIndicator, { Step } from "./StepIndicator";

interface HeaderProps {
  showSteps?: boolean;
  currentStep?: Step;
}

export default function Header({ showSteps = false, currentStep = "schedule" }: HeaderProps) {
  return (
    <header>
      <div className="h-[79px] bg-primary-600 flex items-center justify-between px-7">
        <span className="text-white text-[30px] font-semibold tracking-wide">
          매듭 : AI 모임 플래너
        </span>
        {showSteps && (
          <div className="absolute left-1/2 -translate-x-1/2">
            <StepIndicator currentStep={currentStep} />
          </div>
        )}
        <div className="flex items-center gap-3">
          <Bell className="w-10 h-10 text-white/70 cursor-pointer hover:text-white" />
          <User className="w-10 h-10 text-white/70 cursor-pointer hover:text-white" />
          <Menu className="w-[38px] h-[38px] text-white/70 cursor-pointer hover:text-white" />
        </div>
      </div>
      <div className="h-[5px] bg-accent-50" />
    </header>
  );
}
```

- [ ] **Step 3: 커밋**

```bash
git add src/components/layout/
git commit -m "feat: Header + StepIndicator 레이아웃 컴포넌트"
```

---

## Task 5: 1.0 로그인 페이지

**Files:**
- Modify: `src/components/auth/LoginPage.tsx` (전면 교체)
- Modify: `src/app/page.tsx`

- [ ] **Step 1: LoginPage.tsx 전면 교체**

```tsx
"use client";

import { Calendar, Bot, Users } from "lucide-react";

export default function LoginPage() {
  const handleGoogleLogin = () => {
    window.location.href = "http://localhost:8000/auth/google";
  };

  return (
    <div className="flex h-screen">
      {/* 좌측 패널 - 보라색 그라데이션 */}
      <div className="flex-1 bg-gradient-to-br from-[#4f46e5] via-[#6366f1] to-[#818cf8] flex flex-col items-center justify-center px-16 relative overflow-hidden">
        <h1 className="text-white text-5xl font-bold mb-6">매듭</h1>
        <p className="text-white text-xl text-center mb-10">
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
              <span className="text-white text-[15px]">{text}</span>
            </div>
          ))}
        </div>

        {/* 하단 장식 프레임 */}
        <div className="mt-12 w-[600px] h-[200px] bg-white/10 rounded-[20px] relative overflow-hidden">
          <div className="absolute top-[30px] left-[40px] w-[120px] h-[90px] bg-white/8 rounded-xl" />
          <div className="absolute top-[10px] left-[55px] w-[90px] h-[20px] bg-white/10 rounded-md" />
          <div className="absolute top-[50px] left-[220px] w-[160px] h-[50px] bg-white/10 rounded-2xl" />
          <div className="absolute top-[115px] left-[250px] w-[140px] h-[45px] bg-white/8 rounded-2xl" />
          <div className="absolute top-[40px] left-[440px] w-[80px] h-[80px] bg-white/6 rounded-full" />
          <div className="absolute top-[100px] left-[490px] w-[50px] h-[50px] bg-white/5 rounded-full" />
        </div>
      </div>

      {/* 우측 패널 - 흰색 로그인 폼 */}
      <div className="flex-1 bg-white flex flex-col items-center justify-center">
        <h2 className="text-slate-800 text-[28px] font-bold mb-8">매듭</h2>
        <div className="flex flex-col items-center gap-2 mb-10">
          <h3 className="text-slate-900 text-[32px] font-bold">로그인</h3>
          <p className="text-slate-500 text-[15px]">구글 계정으로 간편하게 시작하세요</p>
        </div>

        <button
          onClick={handleGoogleLogin}
          className="w-[320px] h-[52px] bg-white border-[1.5px] border-slate-200 rounded-xl flex items-center justify-center gap-3 hover:bg-slate-50 transition-colors"
        >
          <svg width="20" height="20" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
          </svg>
          <span className="text-slate-700 text-base font-semibold">Google로 계속하기</span>
        </button>

        <div className="flex items-center gap-4 w-[320px] my-6">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="text-slate-400 text-[13px]">또는</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>

        <button className="w-[320px] h-12 bg-slate-50 border border-slate-200 rounded-xl text-slate-500 text-[15px] font-medium hover:bg-slate-100 transition-colors">
          회원가입 하기
        </button>

        <p className="text-slate-400 text-xs text-center mt-8 leading-relaxed w-[320px]">
          계속 진행하면 서비스 이용약관 및 개인정보 처리방침에
          <br />
          동의하는 것으로 간주됩니다.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: page.tsx 수정 — 인증 분기**

```tsx
"use client";

import { useAuth } from "@/hooks/useAuth";
import LoginPage from "@/components/auth/LoginPage";
import ExplorePage from "@/components/home/ExplorePage";

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-slate-400">로딩 중...</p>
      </div>
    );
  }

  if (!user) return <LoginPage />;
  return <ExplorePage />;
}
```

참고: ExplorePage는 Task 6에서 생성. 빌드 에러 방지를 위해 placeholder를 먼저 생성:

```tsx
// src/components/home/ExplorePage.tsx (placeholder)
export default function ExplorePage() {
  return <div className="p-8">모임 탐색 (구현 예정)</div>;
}
```

- [ ] **Step 3: dev 서버에서 로그인 페이지 확인**

```bash
npm run dev
```

`localhost:3000` 접속 → 좌우 분할 로그인 화면 확인.

- [ ] **Step 4: 커밋**

```bash
git add src/components/auth/LoginPage.tsx src/app/page.tsx src/components/home/ExplorePage.tsx
git commit -m "feat: 1.0 로그인 페이지 리디자인 (좌우 분할 레이아웃)"
```

---

## Task 6: 2.1 모임 탐색 페이지

**Files:**
- Create: `src/components/home/AiRecommendCard.tsx`
- Create: `src/components/home/FriendList.tsx`
- Create: `src/components/home/MeetingList.tsx`
- Create: `src/components/home/MiniCalendar.tsx`
- Modify: `src/components/home/ExplorePage.tsx`

- [ ] **Step 1: AiRecommendCard.tsx**

```tsx
import { Recommendation } from "@/mocks/recommendations";

interface AiRecommendCardProps {
  item: Recommendation;
}

export default function AiRecommendCard({ item }: AiRecommendCardProps) {
  return (
    <div className="min-w-[280px] bg-gradient-to-br from-primary-600 to-primary-400 rounded-2xl p-5 text-white flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium opacity-80">{item.type === "schedule" ? "일정" : "장소"}</span>
        <span className="text-xs opacity-60">{item.memberCount}명</span>
      </div>
      <h3 className="text-lg font-bold">{item.title}</h3>
      <p className="text-sm opacity-80">{item.description}</p>
      {item.time && (
        <div className="mt-auto bg-white/20 rounded-xl px-4 py-2 text-center">
          <span className="text-2xl font-bold tracking-wider">{item.time}</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: FriendList.tsx**

```tsx
import Avatar from "@/components/ui/Avatar";
import { mockFriends } from "@/mocks/friends";

export default function FriendList() {
  const onlineCount = mockFriends.filter((f) => f.online).length;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-slate-900">친구</h3>
        <span className="text-sm text-slate-400">{onlineCount}명 온라인</span>
      </div>
      <div className="flex flex-col gap-3">
        {mockFriends.map((friend) => (
          <div key={friend.id} className="flex items-center gap-3">
            <div className="relative">
              <Avatar name={friend.name} color={friend.color} size="sm" />
              {friend.online && (
                <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-400 rounded-full border-2 border-white" />
              )}
            </div>
            <span className="text-sm text-slate-700">{friend.name}</span>
          </div>
        ))}
      </div>
      <button className="w-full mt-4 py-2 text-sm text-primary-600 border border-primary-600 rounded-xl hover:bg-primary-50 transition-colors">
        추가하기
      </button>
    </div>
  );
}
```

- [ ] **Step 3: MeetingList.tsx**

```tsx
import { mockMeetings } from "@/mocks/meetings";

export default function MeetingList() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-slate-900">참여중인 모임</h3>
        <span className="text-sm text-slate-400">{mockMeetings.length}개</span>
      </div>
      <div className="flex flex-col gap-3">
        {mockMeetings.map((meeting) => (
          <div key={meeting.id} className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 cursor-pointer transition-colors">
            <span className="text-2xl">{meeting.emoji}</span>
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-800">{meeting.name}</p>
              <p className="text-xs text-slate-400">{meeting.memberCount}명 참여</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: MiniCalendar.tsx**

```tsx
import { mockCalendarEvents } from "@/mocks/calendar";

export default function MiniCalendar() {
  const year = 2026;
  const month = 3;
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDay = new Date(year, month - 1, 1).getDay();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const blanks = Array.from({ length: firstDay }, (_, i) => i);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-slate-900">나의 일정 캘린더</h3>
        <span className="text-sm text-slate-500">{year}년 {month}월</span>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs mb-2">
        {["일", "월", "화", "수", "목", "금", "토"].map((d) => (
          <span key={d} className="text-slate-400 py-1">{d}</span>
        ))}
        {blanks.map((b) => (
          <span key={`b-${b}`} />
        ))}
        {days.map((day) => {
          const today = new Date().getDate();
          const isToday = day === today && month === new Date().getMonth() + 1;
          return (
            <span
              key={day}
              className={`py-1 rounded-lg cursor-pointer hover:bg-primary-50 ${
                isToday ? "bg-primary-600 text-white font-bold" : "text-slate-700"
              }`}
            >
              {day}
            </span>
          );
        })}
      </div>
      <div className="mt-4 flex flex-col gap-2">
        {mockCalendarEvents.map((event) => (
          <div key={event.id} className="flex items-center gap-2 text-xs">
            <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: event.color }} />
            <span className="text-slate-600 truncate">{event.title}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: ExplorePage.tsx 완성**

```tsx
"use client";

import Header from "@/components/layout/Header";
import AiRecommendCard from "./AiRecommendCard";
import FriendList from "./FriendList";
import MeetingList from "./MeetingList";
import MiniCalendar from "./MiniCalendar";
import Button from "@/components/ui/Button";
import { mockRecommendations } from "@/mocks/recommendations";
import { useRouter } from "next/navigation";

export default function ExplorePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />

      <main className="max-w-7xl mx-auto p-6 flex flex-col gap-6">
        {/* AI 추천 섹션 */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-xl font-bold text-slate-900">AI 추천</h2>
              <p className="text-sm text-slate-500">지금 진행에 좋은 모임을 시작해보세요</p>
            </div>
            <button className="text-sm text-primary-600 bg-primary-50 px-4 py-2 rounded-full font-medium hover:bg-primary-100 transition-colors">
              가장 빠르게 가능한 모임 확인하기!
            </button>
          </div>
          <div className="flex gap-4 overflow-x-auto pb-2">
            {mockRecommendations.map((rec) => (
              <AiRecommendCard key={rec.id} item={rec} />
            ))}
          </div>
        </section>

        {/* 3열 그리드 */}
        <div className="grid grid-cols-3 gap-6">
          <FriendList />
          <MeetingList />
          <MiniCalendar />
        </div>

        {/* 하단 버튼 */}
        <div className="flex justify-end gap-4">
          <Button variant="secondary" size="lg">모임 초대</Button>
          <Button variant="primary" size="lg" onClick={() => router.push("/meeting/new/schedule")}>
            모임 생성
          </Button>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 6: dev 서버 확인**

```bash
npm run dev
```

로그인 후 모임 탐색 페이지 확인. AI 추천 카드, 친구 목록, 모임 목록, 캘린더가 보이면 성공.

- [ ] **Step 7: 커밋**

```bash
git add src/components/home/
git commit -m "feat: 2.1 모임 탐색 페이지 (AI 추천, 친구, 모임, 캘린더)"
```

---

## Task 7: 채팅 컴포넌트 리디자인

**Files:**
- Create: `src/components/chat/ChatBubble.tsx`
- Create: `src/components/chat/ChatInput.tsx`
- Delete: `src/components/chat/ChatMessageBubble.tsx`
- Delete: `src/components/chat/ChatInputBar.tsx`

- [ ] **Step 1: ChatBubble.tsx**

```tsx
import Avatar from "@/components/ui/Avatar";

interface ChatBubbleProps {
  role: "user" | "assistant" | "system";
  sender: string;
  content: string;
  timestamp?: string;
  isMe?: boolean;
  avatarColor?: string;
}

export default function ChatBubble({ role, sender, content, timestamp, isMe = false, avatarColor = "#818cf8" }: ChatBubbleProps) {
  if (role === "system") {
    return (
      <div className="flex justify-center my-3">
        <div className="bg-primary-50 border border-primary-100 rounded-xl px-4 py-2 text-sm text-primary-600">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-2 ${isMe ? "flex-row-reverse" : "flex-row"}`}>
      {!isMe && <Avatar name={sender} color={avatarColor} size="sm" />}
      <div className={`max-w-[75%] flex flex-col ${isMe ? "items-end" : "items-start"}`}>
        {!isMe && <span className="text-xs text-slate-400 mb-1">{sender}</span>}
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
            isMe
              ? "bg-primary-600 text-white rounded-br-md"
              : role === "assistant"
              ? "bg-primary-50 text-slate-800 rounded-bl-md"
              : "bg-slate-100 text-slate-800 rounded-bl-md"
          }`}
        >
          {content}
        </div>
        {timestamp && <span className="text-[10px] text-slate-300 mt-1">{timestamp}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: ChatInput.tsx**

```tsx
"use client";

import { useState } from "react";
import { Send } from "lucide-react";

interface ChatInputProps {
  placeholder?: string;
  onSend: (message: string) => void;
  accentColor?: string;
}

export default function ChatInput({ placeholder = "메세지를 입력하세요", onSend, accentColor = "#4f46e5" }: ChatInputProps) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input.trim());
    setInput("");
  };

  return (
    <div className="flex items-center gap-2 p-3 border-t border-slate-200">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
        placeholder={placeholder}
        className="flex-1 px-4 py-2.5 bg-slate-50 rounded-xl text-sm text-slate-800 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-primary-400"
      />
      <button
        onClick={handleSend}
        className="w-10 h-10 rounded-full flex items-center justify-center text-white shrink-0 transition-colors hover:opacity-90"
        style={{ backgroundColor: accentColor }}
      >
        <Send className="w-4 h-4" />
      </button>
    </div>
  );
}
```

- [ ] **Step 3: 이전 채팅 컴포넌트 삭제**

```bash
rm src/components/chat/ChatMessageBubble.tsx src/components/chat/ChatInputBar.tsx
```

- [ ] **Step 4: 커밋**

```bash
git add src/components/chat/
git commit -m "feat: 채팅 컴포넌트 리디자인 (ChatBubble, ChatInput)"
```

---

## Task 8: 3.1 일정 조율 페이지

**Files:**
- Create: `src/components/meeting/ChatPane.tsx`
- Create: `src/components/meeting/AiAssistantPane.tsx`
- Create: `src/components/meeting/CalendarPane.tsx`
- Create: `src/app/meeting/[id]/schedule/page.tsx`

- [ ] **Step 1: ChatPane.tsx**

```tsx
"use client";

import { User } from "lucide-react";
import ChatBubble from "@/components/chat/ChatBubble";
import ChatInput from "@/components/chat/ChatInput";
import { mockSocialMessages } from "@/mocks/chatMessages";

export default function ChatPane() {
  const handleSend = (message: string) => {
    console.log("social:", message);
  };

  return (
    <div className="w-[414px] h-[733px] bg-white rounded-[20px] border border-slate-200 shadow-md flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
        <h3 className="text-lg font-bold text-slate-900">채팅방</h3>
        <User className="w-5 h-5 text-slate-400" />
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
        {mockSocialMessages.map((msg) => (
          <ChatBubble
            key={msg.id}
            role={msg.role}
            sender={msg.sender}
            content={msg.content}
            timestamp={msg.timestamp}
            isMe={msg.sender === "김준영"}
            avatarColor="#818cf8"
          />
        ))}
      </div>
      <ChatInput placeholder="메세지를 입력하세요" onSend={handleSend} />
    </div>
  );
}
```

- [ ] **Step 2: AiAssistantPane.tsx**

```tsx
"use client";

import { Sparkles } from "lucide-react";
import ChatBubble from "@/components/chat/ChatBubble";
import ChatInput from "@/components/chat/ChatInput";
import { mockAgentMessages } from "@/mocks/chatMessages";

export default function AiAssistantPane() {
  const handleSend = (message: string) => {
    console.log("agent:", message);
  };

  return (
    <div className="w-[414px] h-[733px] bg-white rounded-[20px] border border-slate-200 shadow-md flex flex-col overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-slate-200">
        <Sparkles className="w-5 h-5 text-primary-500" />
        <h3 className="text-lg font-bold text-slate-900">AI 어시스턴트</h3>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
        {mockAgentMessages.map((msg) => (
          <ChatBubble
            key={msg.id}
            role={msg.role}
            sender={msg.sender}
            content={msg.content}
            timestamp={msg.timestamp}
            isMe={msg.role === "user"}
            avatarColor="#6366f1"
          />
        ))}
      </div>
      <ChatInput placeholder="AI에게 질문하세요" onSend={handleSend} accentColor="#6366f1" />
    </div>
  );
}
```

- [ ] **Step 3: CalendarPane.tsx**

```tsx
"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { mockCalendarEvents } from "@/mocks/calendar";

export default function CalendarPane() {
  const year = 2026;
  const month = 3;
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDay = new Date(year, month - 1, 1).getDay();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const blanks = Array.from({ length: firstDay }, (_, i) => i);

  return (
    <div className="w-[414px] h-[733px] bg-white rounded-[20px] border border-slate-200 shadow-md flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
        <h3 className="text-lg font-bold text-slate-900">매듭 {year}년 {month}월</h3>
        <div className="flex gap-1">
          <ChevronLeft className="w-5 h-5 text-slate-400 cursor-pointer hover:text-slate-600" />
          <ChevronRight className="w-5 h-5 text-slate-400 cursor-pointer hover:text-slate-600" />
        </div>
      </div>

      <div className="px-5 py-3">
        <div className="grid grid-cols-7 gap-1 text-center text-xs">
          {["일", "월", "화", "수", "목", "금", "토"].map((d) => (
            <span key={d} className="text-slate-400 py-2 font-medium">{d}</span>
          ))}
          {blanks.map((b) => <span key={`b-${b}`} />)}
          {days.map((day) => {
            const isToday = day === 24;
            return (
              <span
                key={day}
                className={`py-2 rounded-lg cursor-pointer text-sm hover:bg-primary-50 ${
                  isToday ? "bg-primary-600 text-white font-bold" : "text-slate-700"
                }`}
              >
                {day}
              </span>
            );
          })}
        </div>
      </div>

      <div className="px-5 py-3 border-t border-slate-100">
        <h4 className="text-sm font-bold text-slate-900 mb-3">오늘의 가능한 시간대</h4>
        <div className="flex flex-col gap-2">
          {mockCalendarEvents.map((event) => (
            <div key={event.id} className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-50">
              <div className="w-1 h-8 rounded-full shrink-0" style={{ backgroundColor: event.color }} />
              <div>
                <p className="text-sm text-slate-800">{event.title}</p>
                <p className="text-xs text-slate-400">{event.startTime} ~ {event.endTime}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-auto p-5">
        <button className="w-full py-3 bg-primary-600 text-white rounded-xl font-semibold hover:bg-primary-500 transition-colors">
          추가 제출
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: schedule/page.tsx 라우트**

```tsx
"use client";

import Header from "@/components/layout/Header";
import ChatPane from "@/components/meeting/ChatPane";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import CalendarPane from "@/components/meeting/CalendarPane";

export default function SchedulePage() {
  return (
    <div className="min-h-screen bg-white">
      <Header showSteps currentStep="schedule" />
      <main className="flex justify-center items-start gap-[53px] pt-10 px-12">
        <ChatPane />
        <AiAssistantPane />
        <CalendarPane />
      </main>
    </div>
  );
}
```

- [ ] **Step 5: dev 서버에서 `/meeting/test/schedule` 확인**

```bash
npm run dev
```

`localhost:3000/meeting/test/schedule` 접속 → 3패널 레이아웃 확인.

- [ ] **Step 6: 커밋**

```bash
git add src/components/meeting/ChatPane.tsx src/components/meeting/AiAssistantPane.tsx src/components/meeting/CalendarPane.tsx src/app/meeting/
git commit -m "feat: 3.1 일정 조율 페이지 (채팅 + AI + 캘린더 3패널)"
```

---

## Task 9: 3.2 장소 조율 페이지

**Files:**
- Create: `src/components/meeting/PlaceDetailPane.tsx`
- Create: `src/app/meeting/[id]/place/page.tsx`

- [ ] **Step 1: PlaceDetailPane.tsx**

```tsx
"use client";

import { MapPin, Phone, Star } from "lucide-react";
import Button from "@/components/ui/Button";
import { mockPlaces } from "@/mocks/places";

export default function PlaceDetailPane() {
  const place = mockPlaces[0];

  return (
    <div className="w-[414px] h-[733px] bg-white rounded-[20px] border border-slate-200 shadow-md flex flex-col overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200">
        <h3 className="text-lg font-bold text-slate-900">세부 사항</h3>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-5">
        {/* 장소명 + 카테고리 */}
        <div>
          <h4 className="text-xl font-bold text-slate-900">{place.name}</h4>
          <span className="text-sm text-slate-500">{place.category}</span>
          <div className="flex items-center gap-1 mt-1">
            <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
            <span className="text-sm font-medium text-slate-700">{place.rating}</span>
          </div>
        </div>

        {/* 주소 + 전화 */}
        <div className="flex flex-col gap-2">
          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
            <span className="text-sm text-slate-600">{place.address}</span>
          </div>
          <div className="flex items-center gap-2">
            <Phone className="w-4 h-4 text-slate-400 shrink-0" />
            <span className="text-sm text-slate-600">{place.phone}</span>
          </div>
        </div>

        {/* 대표 메뉴 */}
        <div>
          <h5 className="text-sm font-bold text-slate-900 mb-3">대표 메뉴</h5>
          <div className="flex flex-col gap-2">
            {place.menu.map((item) => (
              <div key={item.name} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                <span className="text-sm text-slate-700">{item.name}</span>
                <span className="text-sm font-medium text-slate-900">{item.price.toLocaleString()}원</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="p-5 flex gap-3">
        <Button variant="primary" className="flex-1">이 장소로 선택</Button>
        <Button variant="secondary" className="flex-1">공유하기</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: place/page.tsx 라우트**

```tsx
"use client";

import Header from "@/components/layout/Header";
import ChatPane from "@/components/meeting/ChatPane";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import PlaceDetailPane from "@/components/meeting/PlaceDetailPane";

export default function PlacePage() {
  return (
    <div className="min-h-screen bg-white">
      <Header showSteps currentStep="place" />
      <main className="flex justify-center items-start gap-[53px] pt-10 px-12">
        <ChatPane />
        <AiAssistantPane />
        <PlaceDetailPane />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: dev 서버에서 `/meeting/test/place` 확인**

- [ ] **Step 4: 커밋**

```bash
git add src/components/meeting/PlaceDetailPane.tsx src/app/meeting/
git commit -m "feat: 3.2 장소 조율 페이지 (장소 세부사항 패널)"
```

---

## Task 10: 3.3 생성 완료 페이지

**Files:**
- Create: `src/components/meeting/CompletionPage.tsx`
- Create: `src/app/meeting/[id]/done/page.tsx`

- [ ] **Step 1: CompletionPage.tsx**

```tsx
"use client";

import { Check, Share2, List, Calendar, MapPin, Users } from "lucide-react";
import Button from "@/components/ui/Button";
import Avatar from "@/components/ui/Avatar";
import { useRouter } from "next/navigation";

export default function CompletionPage() {
  const router = useRouter();

  const meetingInfo = {
    title: "클라인 프로젝트 회의",
    date: "2026년 3월 22일 (일) 오후 3:00",
    location: "강남역 스타벅스 3층",
    members: [
      { name: "김준영", color: "#818cf8" },
      { name: "정은빈", color: "#f472b6" },
      { name: "한도이", color: "#34d399" },
      { name: "가인영", color: "#fbbf24" },
    ],
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-8 py-12 relative">
      {/* Confetti 장식 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute w-2 h-2 rounded-full bg-primary-600/10 top-[200px] left-[200px]" />
        <div className="absolute w-3 h-3 rounded-full bg-primary-400/15 top-[250px] right-[200px]" />
        <div className="absolute w-4 h-1.5 rounded bg-primary-100/25 top-[300px] left-[350px]" />
        <div className="absolute w-3.5 h-1 rounded bg-primary-100/20 top-[350px] right-[300px]" />
        <div className="absolute w-1.5 h-1.5 rounded-full bg-primary-600/10 bottom-[200px] left-[500px]" />
        <div className="absolute w-2.5 h-2.5 rounded-full bg-primary-400/10 bottom-[220px] right-[400px]" />
      </div>

      {/* 성공 아이콘 */}
      <div className="w-24 h-24 rounded-full bg-gradient-to-br from-primary-600 to-primary-400 flex items-center justify-center">
        <Check className="w-12 h-12 text-white" strokeWidth={3} />
      </div>

      <div className="text-center">
        <h2 className="text-[28px] font-bold text-slate-900">모임이 성공적으로 생성되었어요!</h2>
        <p className="text-base text-slate-500 mt-2">참여자들에게 초대 알림이 전송되었습니다</p>
      </div>

      {/* 요약 카드 */}
      <div className="w-[480px] bg-primary-50 rounded-2xl border border-slate-200 p-7">
        <h3 className="text-base font-bold text-slate-900 mb-5">모임 정보</h3>
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-slate-400 shrink-0" />
            <div>
              <p className="text-xs text-slate-400">모임명</p>
              <p className="text-sm text-slate-800 font-medium">{meetingInfo.title}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-slate-400 shrink-0" />
            <div>
              <p className="text-xs text-slate-400">날짜</p>
              <p className="text-sm text-slate-800 font-medium">{meetingInfo.date}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <MapPin className="w-5 h-5 text-slate-400 shrink-0" />
            <div>
              <p className="text-xs text-slate-400">장소</p>
              <p className="text-sm text-slate-800 font-medium">{meetingInfo.location}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Users className="w-5 h-5 text-slate-400 shrink-0" />
            <div>
              <p className="text-xs text-slate-400 mb-1">참여자</p>
              <div className="flex -space-x-2">
                {meetingInfo.members.map((m) => (
                  <Avatar key={m.name} name={m.name} color={m.color} size="sm" />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 버튼 행 */}
      <div className="flex gap-4">
        <Button variant="primary" size="lg">
          <Share2 className="w-4 h-4 mr-2 inline" />
          모임 공유하기
        </Button>
        <Button variant="secondary" size="lg" onClick={() => router.push("/")}>
          <List className="w-4 h-4 mr-2 inline" />
          모임 목록으로
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: done/page.tsx 라우트**

```tsx
"use client";

import Header from "@/components/layout/Header";
import CompletionPage from "@/components/meeting/CompletionPage";

export default function DonePage() {
  return (
    <div className="min-h-screen bg-white flex flex-col">
      <Header showSteps currentStep="done" />
      <CompletionPage />
    </div>
  );
}
```

- [ ] **Step 3: dev 서버에서 `/meeting/test/done` 확인**

- [ ] **Step 4: 커밋**

```bash
git add src/components/meeting/CompletionPage.tsx src/app/meeting/
git commit -m "feat: 3.3 생성 완료 페이지 (성공 아이콘 + 요약 카드)"
```

---

## Task 11: 정리 및 삭제

**Files:**
- Delete: `src/components/agent/AgentPane.tsx`
- Delete: `src/components/meeting/DataPane.tsx`
- Delete: `src/components/social/SocialPane.tsx`

- [ ] **Step 1: 사용하지 않는 기존 컴포넌트 삭제**

```bash
rm src/components/agent/AgentPane.tsx
rm src/components/meeting/DataPane.tsx
rm src/components/social/SocialPane.tsx
```

- [ ] **Step 2: 빌드 확인**

```bash
npm run build
```

에러 없으면 성공. import 참조가 남아있으면 수정.

- [ ] **Step 3: 커밋**

```bash
git add -A
git commit -m "chore: 기존 다크 테마 컴포넌트 삭제 (AgentPane, DataPane, SocialPane)"
```

---

## Task 12: 최종 QA

- [ ] **Step 1: 전체 빌드 확인**

```bash
npm run build
```

- [ ] **Step 2: 각 페이지 시각적 확인**

| 경로 | 확인 사항 |
|------|----------|
| `localhost:3000` (미인증) | 좌우 분할 로그인 |
| `localhost:3000` (인증 후) | 모임 탐색 (AI 추천, 친구, 모임, 캘린더) |
| `localhost:3000/meeting/test/schedule` | 3패널 (채팅+AI+캘린더) |
| `localhost:3000/meeting/test/place` | 3패널 (채팅+AI+장소) |
| `localhost:3000/meeting/test/done` | 성공 페이지 |

- [ ] **Step 3: CHANGELOG.md 업데이트**

- [ ] **Step 4: 최종 커밋**

```bash
git add -A
git commit -m "feat: 프론트엔드 전면 리디자인 완료 (Tailwind CSS, 5개 화면)"
```

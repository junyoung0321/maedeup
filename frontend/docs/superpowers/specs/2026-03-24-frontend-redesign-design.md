# 매듭 프론트엔드 전면 리디자인 스펙

## 개요

pencil.pen 디자인 5개 화면을 Next.js 14 + Tailwind CSS로 구현한다.
기존 다크 테마를 전면 교체하고, 목 데이터로 UI를 먼저 완성한다.

## 기술 스택

- **프레임워크**: Next.js 14 App Router
- **스타일링**: Tailwind CSS (기존 인라인 스타일 + CSS 변수 전면 교체)
- **폰트**: Pretendard (로컬), Noto Sans KR (fallback)
- **아이콘**: Lucide React
- **타입**: TypeScript strict
- **데이터**: 목(mock) 데이터 → 추후 API 연결

## 디자인 토큰

pencil.pen에서 추출한 컬러 시스템:

```
# Primary (Indigo 계열)
--primary-600: #4f46e5  (헤더 배경, 주요 버튼)
--primary-500: #6366f1  (그라데이션 중간)
--primary-400: #818cf8  (그라데이션 끝, 서브 액센트)
--primary-100: #c7d2fe  (뱃지 배경, 장식)
--primary-50:  #f8faff  (카드 배경)

# Accent (Cyan 계열 - 스텝 인디케이터)
--accent-400:  #22d3ee  (활성 스텝)
--accent-300:  #5ed3e8  (비활성 스텝 텍스트)
--accent-100:  #a2f4fd  (비활성 스텝 원)
--accent-50:   #cff9fe  (프로그레스 바)

# Neutral (Slate 계열)
--slate-900:   #0f172a  (제목 텍스트)
--slate-800:   #1e293b  (본문 텍스트)
--slate-500:   #64748b  (서브 텍스트)
--slate-400:   #94a3b8  (힌트 텍스트)
--slate-200:   #e2e8f0  (보더, 구분선)
--slate-100:   #f1f5f9  (연한 배경)
--slate-50:    #f8fafc  (페이지 배경)

# 기능 컬러
--white:       #ffffff
--success:     #10b981  (카카오톡 스터디 등 그린 배지)
--warning:     #f59e0b  (타이머)
--error:       #ef4444
```

## 라우팅 구조

```
src/app/
├── page.tsx                    → 인증 분기: 미인증 → 로그인, 인증 → 모임 탐색
├── auth/callback/page.tsx      → OAuth 콜백 (기존 유지)
├── meeting/[id]/
│   ├── schedule/page.tsx       → 3.1 일정 조율
│   ├── place/page.tsx          → 3.2 장소 조율
│   └── done/page.tsx           → 3.3 생성 완료
└── layout.tsx                  → 루트 레이아웃 (Tailwind, 폰트)
```

## 화면별 상세 스펙

---

### 1.0 로그인 (`/` 미인증 시)

**레이아웃**: 좌우 50:50 분할, 전체 높이

**좌측 패널 (보라색 그라데이션)**:
- 배경: linear-gradient(135deg, #4f46e5, #6366f1, #818cf8)
- 중앙 정렬 콘텐츠:
  - 로고 텍스트 "매듭" (Pretendard 700, 48px, 흰색)
  - 태그라인 "AI와 함께하는 똑똑한 모임 일정 조율" (20px, 흰색)
  - 기능 목록 3개 (아이콘 + 텍스트, 흰색):
    - calendar_month "스마트 일정 조율"
    - smart_toy "AI 개인 비서"
    - group "실시간 그룹 채팅"
  - 하단 장식 프레임 (둥근 모서리 20px, 반투명 흰색 배경, 내부에 채팅/캘린더 모양 장식)

**우측 패널 (흰색)**:
- 중앙 정렬 콘텐츠:
  - 로고 아이콘 + "매듭" (28px, #1e293b)
  - "로그인" (32px, 700, #0f172a)
  - "구글 계정으로 간편하게 시작하세요" (15px, #64748b)
  - Google 로그인 버튼 (320px 너비, 52px 높이, 둥근 12px, 흰색 배경, #e2e8f0 보더)
  - 구분선 "또는" (#94a3b8)
  - "회원가입 하기" 버튼 (320px, 48px, #f8fafc 배경)
  - 이용약관 텍스트 (12px, #94a3b8, 중앙 정렬)

---

### 2.1 모임 탐색 (`/` 인증 후)

**레이아웃**: 상단 헤더 바 + 본문 그리드

**헤더**: "매듭 : AI 모임 플래너" (보라색 #4f46e5 배경, 흰색 텍스트)

**본문 구성** (그리드 레이아웃):

1. **AI 추천 섹션** (상단 배너):
   - "AI 추천" 타이틀 + 설명
   - 카드 3개 가로 스크롤:
     - 각 카드: 추천 장소/활동명, 설명, 카운트다운 타이머
   - "가장 빠르게 가능한 모임 확인" 바로가기 버튼

2. **친구 섹션** (좌측):
   - "친구" 타이틀 + 온라인 인원 수
   - 친구 목록 (아바타 + 이름, 컬러 뱃지)
   - "추가하기" 버튼

3. **참여중인 모임 섹션** (중앙):
   - "참여중인 모임" 타이틀
   - 모임 리스트 (아이콘 + 모임명 + 인원)

4. **나의 일정/캘린더 섹션** (우측):
   - 월별 캘린더 뷰
   - 일정 목록 (시간 + 제목, 컬러 코드)

5. **내 캘린더 연동** (좌하단):
   - Google Calendar 연동 상태
   - 동기화된 캘린더 목록

6. **모임 생성 영역** (우하단):
   - "모임 초대" / "모임 생성" 버튼 2개 (보라색)

---

### 3.1 일정 조율 (`/meeting/[id]/schedule`)

**레이아웃**: 헤더 + 3패널 (균등 분할, gap 53px)

**헤더** (79px 높이, #4f46e5):
- 좌: "매듭 : AI 모임 플래너" (30px, 600)
- 중앙: 스텝 인디케이터 (일정 > 장소 > 생성 완료)
  - 활성 스텝: 그라데이션 원(#2286ff→#00b5dd), 흰색 텍스트, 600
  - 비활성 스텝: #a2f4fd 원, #5ed3e8 텍스트, normal
  - 화살표 구분자
- 우: 알림/사용자/메뉴 아이콘

**프로그레스 바**: 5px 높이, #cff9fe

**좌측 패널 - 채팅방** (414px, 733px, 둥근 20px, 그림자):
- 헤더: "채팅방" + 사용자 아이콘
- 메시지 영역:
  - 상대방 메시지: 좌측, 회색 배경 (#f1f5f9), 아바타
  - 내 메시지: 우측, 보라색 배경 (#4f46e5), 흰색 텍스트
- 하단 입력: "메세지를 입력하세요" + 전송 버튼

**중앙 패널 - AI 어시스턴트** (414px, 733px, 둥근 20px, 그림자):
- 헤더: "✨ AI 어시스턴트"
- AI 메시지: 연보라 배경, 시스템 메시지 스타일
- 일정 조율 시작 알림 카드 (아이콘 + 텍스트)
- 하단 입력: "AI에게 질문하세요" + 전송 버튼

**우측 패널 - 캘린더** (414px, 733px, 둥근 20px, 그림자):
- 헤더: "매듭 2026년 3월" + 네비게이션
- 월간 캘린더 그리드 (일~토, 날짜 셀)
- "오늘의 가능한 시간대" 섹션
- 일정 목록 (시간대 + 제목, 컬러 태그)
- "추가 제출" 버튼

---

### 3.2 장소 조율 (`/meeting/[id]/place`)

**레이아웃**: 3.1과 동일한 헤더 + 3패널 구조 (스텝 "장소" 활성화)

**좌측 패널 - 채팅방**: 3.1과 동일

**중앙 패널 - AI 어시스턴트**:
- AI 장소 추천 메시지
- 추천 장소 카드 (평점, 거리, 가격대 포함)
- 지도/이미지 영역

**우측 패널 - 세부 사항**:
- "세부 사항" 타이틀
- 선택된 장소 상세:
  - 장소명 (예: "을지로 풀무식당")
  - 카테고리 (예: "한식")
  - 주소, 전화번호
- "대표 메뉴" 섹션 (메뉴명 + 가격)
- "이 장소로 선택" / "공유하기" 버튼

---

### 3.3 생성 완료 (`/meeting/[id]/done`)

**레이아웃**: 헤더 + 중앙 정렬 콘텐츠

**헤더**: 3.1과 동일 (모든 스텝 완료 상태, #4f46e5 원, 흰색 텍스트)

**프로그레스 바**: 5px, #4f46e5 (100%)

**중앙 콘텐츠** (수직 정렬, gap 32px):
- 성공 아이콘: 96x96 원, 보라색 그라데이션, 체크마크
- "모임이 성공적으로 생성되었어요!" (28px, 700, #0f172a)
- "참여자들에게 초대 알림이 전송되었습니다" (16px, #64748b)
- 요약 카드 (480px, 둥근 16px, #f8faff 배경, #e2e8f0 보더):
  - "모임 정보" 타이틀
  - 아이콘 + 정보 행:
    - 모임명, 날짜/시간, 장소, 참여자 (아바타 그룹)
- 버튼 행:
  - "모임 공유하기" (보라색 배경, 흰색 텍스트)
  - "모임 목록으로" (흰색 배경, 보라색 텍스트, 보더)
- 장식: 작은 confetti 도트 (반투명 보라색, 랜덤 배치)

---

## 컴포넌트 구조

```
src/components/
├── layout/
│   ├── Header.tsx              → 공통 헤더 (로고 + 스텝 인디케이터 + 아이콘)
│   └── StepIndicator.tsx       → 일정 > 장소 > 생성 완료 스텝
├── auth/
│   └── LoginPage.tsx           → 1.0 로그인 (전면 교체)
├── home/
│   ├── ExplorePage.tsx         → 2.1 모임 탐색 메인
│   ├── AiRecommendCard.tsx     → AI 추천 카드
│   ├── FriendList.tsx          → 친구 목록
│   ├── MeetingList.tsx         → 참여 모임 목록
│   └── MiniCalendar.tsx        → 미니 캘린더
├── meeting/
│   ├── ChatPane.tsx            → 채팅방 패널 (3.1, 3.2 공통)
│   ├── AiAssistantPane.tsx     → AI 어시스턴트 패널 (3.1, 3.2 공통)
│   ├── CalendarPane.tsx        → 캘린더 패널 (3.1 우측)
│   ├── PlaceDetailPane.tsx     → 장소 세부사항 패널 (3.2 우측)
│   └── CompletionPage.tsx      → 3.3 생성 완료
├── chat/
│   ├── ChatBubble.tsx          → 메시지 버블 (리디자인)
│   └── ChatInput.tsx           → 채팅 입력 (리디자인)
└── ui/
    ├── Avatar.tsx              → 사용자 아바타
    ├── Badge.tsx               → 컬러 뱃지
    ├── Button.tsx              → 공통 버튼
    └── Card.tsx                → 공통 카드
```

## 목(Mock) 데이터

```
src/mocks/
├── friends.ts          → 친구 목록 (이름, 아바타 컬러)
├── meetings.ts         → 참여 모임 목록 (모임명, 인원, 카테고리)
├── recommendations.ts  → AI 추천 데이터 (장소, 활동, 타이머)
├── calendar.ts         → 캘린더 일정 데이터
├── places.ts           → 추천 장소 상세 (메뉴, 가격, 주소)
└── chatMessages.ts     → 샘플 채팅 메시지
```

## 기존 코드 처리

### 유지
- `src/hooks/useAuth.ts` — JWT 인증 로직 그대로
- `src/hooks/useAgentWebSocket.ts` — WebSocket 훅 (나중에 연결)
- `src/hooks/useSocialWebSocket.ts` — WebSocket 훅 (나중에 연결)
- `src/app/auth/callback/page.tsx` — OAuth 콜백

### 전면 교체
- `src/app/globals.css` → Tailwind 설정으로 대체
- `src/app/page.tsx` → 인증 분기 + 모임 탐색
- `src/app/layout.tsx` → Tailwind + 폰트 설정
- `src/components/auth/LoginPage.tsx` → 좌우 분할 리디자인
- `src/components/chat/*` → Tailwind 기반 리디자인

### 삭제
- `src/components/agent/AgentPane.tsx` → AiAssistantPane으로 대체
- `src/components/meeting/DataPane.tsx` → CalendarPane + PlaceDetailPane으로 분리
- `src/components/social/SocialPane.tsx` → ChatPane으로 대체

## Tailwind 설정

`tailwind.config.ts`에 추가할 커스텀 설정:

```typescript
{
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f8faff',
          100: '#c7d2fe',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
        },
        accent: {
          50: '#cff9fe',
          100: '#a2f4fd',
          300: '#5ed3e8',
          400: '#22d3ee',
        },
      },
      fontFamily: {
        pretendard: ['Pretendard', 'Noto Sans KR', 'sans-serif'],
      },
    },
  },
}
```

## 구현 순서

1. Tailwind CSS 설치 + 설정 + 폰트 세팅
2. 공통 컴포넌트 (Header, StepIndicator, Button, Card, Avatar, Badge)
3. 1.0 로그인 페이지
4. 2.1 모임 탐색 페이지
5. 3.1 일정 조율 페이지
6. 3.2 장소 조율 페이지
7. 3.3 생성 완료 페이지
8. 반응형 + 마무리 QA

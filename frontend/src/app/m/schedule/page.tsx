"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

// 구 캘린더(finalization 2지선다 투표)는 통합 meeting 화면의 '캘린더' 탭(InfoPane:
// 캘린더 그리드 + 멤버 가용성 + TimeBar 시간대 조율)으로 대체됨. 리다이렉트.
function ScheduleRedirect() {
  const router = useRouter();
  const roomId = useSearchParams().get("roomId");
  useEffect(() => {
    if (roomId) router.replace(`/m/chat/ai?tab=calendar&roomId=${roomId}`);
    else router.replace("/m/calendar");
  }, [roomId, router]);
  return null;
}

export default function ScheduleRedirectPage() {
  return (
    <Suspense fallback={null}>
      <ScheduleRedirect />
    </Suspense>
  );
}

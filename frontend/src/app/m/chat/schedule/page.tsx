"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

// 채팅방은 통합 meeting 화면(/m/chat/ai)의 '채팅방' 탭(데스크탑 ChatPane)으로 통합됨.
// ChatPane이 social WS 브릿지(시간선택·합의·미가용·finalization)를 세팅하므로,
// 통합 페이지에서 TimeBar 합의·호스트 확정이 데스크탑처럼 작동한다. 리다이렉트.
function ChatRedirect() {
  const router = useRouter();
  const roomId = useSearchParams().get("roomId");
  useEffect(() => {
    if (roomId) router.replace(`/m/chat/ai?tab=chat&roomId=${roomId}`);
    else router.replace("/m/chat");
  }, [roomId, router]);
  return null;
}

export default function ScheduleChatRedirectPage() {
  return (
    <Suspense fallback={null}>
      <ChatRedirect />
    </Suspense>
  );
}

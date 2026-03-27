export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  sender: string;
  content: string;
  timestamp: string;
}

export const mockSocialMessages: ChatMessage[] = [
  { id: "1", role: "user", sender: "정은빈", content: "저희 회식 언제 할까요?", timestamp: "14:30" },
  { id: "2", role: "user", sender: "한도이", content: "저는 다음주엔 전부 가능해요.", timestamp: "14:31" },
  { id: "3", role: "user", sender: "김준영", content: "저도 다음주엔 다 가능합니다!", timestamp: "14:32" },
  { id: "4", role: "user", sender: "김준영", content: "강남이나 논현 어때요?", timestamp: "14:33" },
  { id: "5", role: "user", sender: "정은빈", content: "그럼 강남에서 볼까요?", timestamp: "14:34" },
  { id: "6", role: "user", sender: "김준영", content: "네 좋습니다!", timestamp: "14:35" },
  { id: "7", role: "user", sender: "한도이", content: "시간은 언제가 좋으세요?", timestamp: "14:36" },
  { id: "8", role: "user", sender: "김준영", content: "저녁 7시 괜찮을까요?", timestamp: "14:37" },
];

export const mockAgentMessages: ChatMessage[] = [
  { id: "1", role: "system", sender: "AI", content: "채팅방에서 회식 일정 대화가 감지되었습니다", timestamp: "" },
  { id: "2", role: "assistant", sender: "AI", content: "저희 회식 언제 할까요?", timestamp: "" },
  { id: "3", role: "assistant", sender: "AI", content: "저는 다음주엔 전부 가능해요.", timestamp: "" },
  { id: "4", role: "user", sender: "나", content: "저도 다음주엔 다 가능합니다!", timestamp: "" },
  { id: "5", role: "assistant", sender: "AI", content: "시간은 언제가 좋으세요?", timestamp: "" },
  { id: "6", role: "user", sender: "나", content: "저녁 7시 괜찮을까요?", timestamp: "" },
];

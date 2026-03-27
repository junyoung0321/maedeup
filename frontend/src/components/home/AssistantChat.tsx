"use client";

import { useState } from "react";
import { Bot, Send } from "lucide-react";

const initialMessages = [
  {
    id: "1",
    role: "user" as const,
    text: "내 이번주 일정 확인해줘",
  },
  {
    id: "2",
    role: "ai" as const,
    text: "이번 주 일정입니다:\n\ud83d\udcc5 3/20(목) 20:00 기획 스터디\n\ud83d\udcc5 3/25(화) 14:00 등산 모임\n\ud83d\udcc5 3/27(목) 19:00 독서 모임",
  },
  {
    id: "3",
    role: "user" as const,
    text: "등산 모임 날 못 먹는 음식 알려줘",
  },
  {
    id: "4",
    role: "ai" as const,
    text: "등록된 음식 제한 정보:\n\ud83d\udeab 땅콩 알레르기\n\ud83d\udeab 갑각류",
  },
];

export default function AssistantChat() {
  const [messages] = useState(initialMessages);
  const [input, setInput] = useState("");

  return (
    <div
      className="bg-white rounded-[20px] flex flex-col h-full overflow-hidden border border-[#e2e8f0] shadow-[0_4px_10.5px_rgba(0,0,0,0.08)]"
      style={{ width: 414, minHeight: 490 }}
    >
      {/* Purple gradient header */}
      <div
        className="px-4 py-3 flex items-center gap-2"
        style={{
          background: "linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)",
        }}
      >
        <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <span className="text-[16px] font-semibold text-white">
          비서 어시스턴트
        </span>
        <div className="flex items-center gap-1 ml-1">
          <div className="w-2 h-2 rounded-full bg-[#4ade80]" />
          <span className="text-[11px] text-white">active</span>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 bg-[#f8fafc] p-4 flex flex-col gap-3 overflow-y-auto min-h-[200px]">
        {messages.map((msg) =>
          msg.role === "ai" ? (
            <div key={msg.id} className="flex gap-2 items-start">
              <div className="w-6 h-6 rounded-full bg-[#ede9fe] flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-3 h-3 text-[#7c3aed]" />
              </div>
              <div className="bg-[#e3e3e3] rounded-[14px] rounded-tl-[4px] px-3.5 py-2.5 text-[17px] text-black max-w-[80%] whitespace-pre-line">
                {msg.text}
              </div>
            </div>
          ) : (
            <div key={msg.id} className="flex justify-end">
              <div className="bg-[#4f46e5] rounded-[14px] rounded-tr-[4px] px-3.5 py-2.5 text-[17px] text-white max-w-[80%]">
                {msg.text}
              </div>
            </div>
          )
        )}
      </div>

      {/* Input bar */}
      <div className="px-3 py-2.5 border-t border-[#e2e8f0] flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="개인 요청을 입력하세요..."
          className="flex-1 text-[14px] text-[#334155] placeholder-[#94a3b8] outline-none bg-transparent"
        />
        <button className="w-8 h-8 rounded-full bg-[#4f46e5] flex items-center justify-center hover:bg-[#4338ca] transition-colors shrink-0">
          <Send className="w-3.5 h-3.5 text-white" />
        </button>
      </div>
    </div>
  );
}

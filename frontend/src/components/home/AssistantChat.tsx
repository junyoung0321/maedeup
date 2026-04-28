"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Send, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface AssistantMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface HistoryResponse {
  messages: AssistantMessage[];
}

interface ChatResponse {
  user_message: AssistantMessage;
  assistant_message: AssistantMessage;
}

export default function AssistantChat() {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // 히스토리 로딩
  const loadHistory = useCallback(async () => {
    try {
      setError(null);
      const data = await apiFetch<HistoryResponse>("/api/v1/assistant/history");
      setMessages(data.messages);
    } catch (e) {
      setError(e instanceof Error ? e.message : "히스토리를 불러오지 못했습니다.");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  // 새 메시지 추가 시 자동 스크롤
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    setInput("");
    setSending(true);
    setError(null);

    // optimistic — 사용자 메시지 즉시 표시
    const optimisticUserMsg: AssistantMessage = {
      id: -Date.now(),
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);

    try {
      const data = await apiFetch<ChatResponse>("/api/v1/assistant/chat", {
        method: "POST",
        body: JSON.stringify({ message: trimmed }),
      });
      // optimistic을 서버 데이터로 교체 (id 정확화) + assistant 메시지 append
      setMessages((prev) => {
        const without = prev.filter((m) => m.id !== optimisticUserMsg.id);
        return [...without, data.user_message, data.assistant_message];
      });
    } catch (e) {
      // 실패 시 optimistic 제거 + 에러 표시
      setMessages((prev) => prev.filter((m) => m.id !== optimisticUserMsg.id));
      setInput(trimmed); // 입력 복원
      setError(e instanceof Error ? e.message : "전송 실패 — 잠시 후 다시 시도");
    } finally {
      setSending(false);
    }
  };

  const handleClearHistory = async () => {
    if (!confirm("대화 기록을 모두 삭제할까요?")) return;
    try {
      await apiFetch("/api/v1/assistant/history", { method: "DELETE" });
      setMessages([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제 실패");
    }
  };

  return (
    <div
      className="bg-white rounded-[20px] flex flex-col h-full overflow-hidden border border-[#e2e8f0] shadow-[0_4px_10.5px_rgba(0,0,0,0.08)] w-full max-w-full lg:max-w-[414px]"
      style={{ minHeight: 490 }}
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
          <div
            className={`w-2 h-2 rounded-full ${
              sending ? "bg-[#fbbf24] animate-pulse" : "bg-[#4ade80]"
            }`}
          />
          <span className="text-[11px] text-white">
            {sending ? "thinking…" : "active"}
          </span>
        </div>
        {messages.length > 0 && (
          <button
            onClick={handleClearHistory}
            aria-label="대화 기록 삭제"
            className="ml-auto w-7 h-7 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center"
            title="대화 기록 삭제"
          >
            <Trash2 className="w-3.5 h-3.5 text-white" />
          </button>
        )}
      </div>

      {/* Chat area */}
      <div
        ref={scrollRef}
        className="flex-1 bg-[#f8fafc] p-4 flex flex-col gap-3 overflow-y-auto min-h-[200px]"
      >
        {historyLoading && (
          <div className="text-[12px] text-[#94a3b8] text-center my-auto">
            대화 기록 불러오는 중…
          </div>
        )}

        {!historyLoading && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center my-auto gap-3 px-6 text-center">
            <div className="w-12 h-12 rounded-full bg-[#ede9fe] flex items-center justify-center">
              <Bot className="w-6 h-6 text-[#7c3aed]" />
            </div>
            <p className="text-[13px] font-semibold text-[#1e293b]">
              안녕하세요! 비서 어시스턴트입니다.
            </p>
            <p className="text-[11px] text-[#64748b] leading-relaxed">
              내 일정, 음식 제한, 친구, AI가 학습한 정보 등을 물어볼 수 있어요.
              <br />
              예: <span className="italic">&quot;내 다음 모임 언제야?&quot;</span>
              {" · "}
              <span className="italic">&quot;내가 못 먹는 거 뭐였지?&quot;</span>
            </p>
          </div>
        )}

        {!historyLoading &&
          messages.map((msg) =>
            msg.role === "assistant" ? (
              <div key={msg.id} className="flex gap-2 items-start">
                <div className="w-6 h-6 rounded-full bg-[#ede9fe] flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-3 h-3 text-[#7c3aed]" />
                </div>
                <div className="bg-[#e3e3e3] rounded-[14px] rounded-tl-[4px] px-3.5 py-2.5 text-[14px] text-black max-w-[80%] whitespace-pre-line leading-relaxed">
                  {msg.content}
                </div>
              </div>
            ) : (
              <div key={msg.id} className="flex justify-end">
                <div className="bg-[#4f46e5] rounded-[14px] rounded-tr-[4px] px-3.5 py-2.5 text-[14px] text-white max-w-[80%] whitespace-pre-line leading-relaxed">
                  {msg.content}
                </div>
              </div>
            ),
          )}

        {/* thinking indicator */}
        {sending && (
          <div className="flex gap-2 items-start">
            <div className="w-6 h-6 rounded-full bg-[#ede9fe] flex items-center justify-center shrink-0 mt-0.5">
              <Bot className="w-3 h-3 text-[#7c3aed]" />
            </div>
            <div className="bg-[#e3e3e3] rounded-[14px] rounded-tl-[4px] px-3.5 py-2.5 text-[14px] text-[#64748b] max-w-[80%] flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#7c3aed] animate-bounce" />
              <span
                className="w-1.5 h-1.5 rounded-full bg-[#7c3aed] animate-bounce"
                style={{ animationDelay: "0.15s" }}
              />
              <span
                className="w-1.5 h-1.5 rounded-full bg-[#7c3aed] animate-bounce"
                style={{ animationDelay: "0.3s" }}
              />
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="px-4 py-1.5 bg-[#fef2f2] border-t border-[#fecaca]">
          <p className="text-[11px] text-[#dc2626]">{error}</p>
        </div>
      )}

      {/* Input bar */}
      <div className="px-3 py-2.5 border-t border-[#e2e8f0] flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
          disabled={sending}
          placeholder="개인 요청을 입력하세요..."
          className="flex-1 text-[14px] text-[#334155] placeholder-[#94a3b8] outline-none bg-transparent disabled:opacity-50"
        />
        <button
          onClick={() => void handleSend()}
          disabled={sending || !input.trim()}
          className="w-8 h-8 rounded-full bg-[#4f46e5] flex items-center justify-center hover:bg-[#4338ca] transition-colors shrink-0 disabled:bg-[#c7d2fe] disabled:cursor-not-allowed"
          aria-label="전송"
        >
          <Send className="w-3.5 h-3.5 text-white" />
        </button>
      </div>
    </div>
  );
}

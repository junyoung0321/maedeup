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

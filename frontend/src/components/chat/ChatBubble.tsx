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

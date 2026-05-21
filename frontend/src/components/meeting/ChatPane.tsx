"use client";

import { useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { User, Send, X, Calendar, MapPin } from "lucide-react";
import { useSocialWebSocket } from "@/hooks/useSocialWebSocket";
import { MeetingContext } from "@/contexts/MeetingContext";
import { fs } from "@/lib/responsive";

function getNameFromToken(): string {
  try {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      return "익명";
    }

    const payload = token.split(".")[1];
    if (!payload) {
      return "익명";
    }

    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");

    let decodedPayload = "";
    try {
      decodedPayload = atob(padded);
    } catch {
      return "익명";
    }

    let decoded: unknown;
    try {
      decoded = JSON.parse(decodedPayload);
    } catch {
      return "익명";
    }

    if (
      decoded &&
      typeof decoded === "object" &&
      "name" in decoded &&
      typeof decoded.name === "string" &&
      decoded.name.trim()
    ) {
      return decoded.name;
    }

    return "익명";
  } catch {
    return "익명";
  }
}

const INTENT_BANNER: Record<
  string,
  { icon: ReactNode; message: string; color: string }
> = {
  meeting_schedule: {
    icon: <Calendar style={{ width: 14, height: 14 }} />,
    message: "채팅방에서 모임 일정 대화가 감지되었습니다",
    color: "#4f46e5",
  },
  place_suggestion: {
    icon: <MapPin style={{ width: 14, height: 14 }} />,
    message: "채팅방에서 장소 관련 대화가 감지되었습니다",
    color: "#0891b2",
  },
};

export default function ChatPane() {
  const [input, setInput] = useState("");
  const [currentUserName, setCurrentUserName] = useState<string>("익명");
  const scrollRef = useRef<HTMLDivElement>(null);
  const meetingContext = useContext(MeetingContext);

  useEffect(() => {
    setCurrentUserName(getNameFromToken());
  }, []);

  const roomId = useMemo(() => {
    const candidate = meetingContext?.roomId?.trim();
    return candidate && candidate.length > 0 ? candidate : "1";
  }, [meetingContext?.roomId]);
  const setAiTriggerIntent = meetingContext?.setAiTriggerIntent;

  const {
    messages,
    sendMessage,
    sendDateSelection,
    sendTimeSelection,
    status,
    peerSelections,
    peerTimeSelections,
    unavailabilityByUser,
    sendUnavailableToggle,
    myTimeSelection,
    myDateSelection,
    finalizationProposal,
    finalizationPending,
    lastConfirmedMeeting,
    scheduleConsensus,
    lastMemberJoined,
  } = useSocialWebSocket(roomId, currentUserName);

  // Bridge: socket의 peerSelections/sendDateSelection을 MeetingContext로 노출
  const setPeerDateSelections = meetingContext?.setPeerDateSelections;
  const setSendDateSelection = meetingContext?.setSendDateSelection;
  const setPeerTimeSelections = meetingContext?.setPeerTimeSelections;
  const setSendTimeSelection = meetingContext?.setSendTimeSelection;
  const setUnavailabilityByUser = meetingContext?.setUnavailabilityByUser;
  const setSendUnavailableToggle = meetingContext?.setSendUnavailableToggle;
  const setMyTimeSelection = meetingContext?.setMyTimeSelection;
  const setMyDateSelection = meetingContext?.setMyDateSelection;
  const setFinalizationProposal = meetingContext?.setFinalizationProposal;
  const setFinalizationPending = meetingContext?.setFinalizationPending;
  const setLastConfirmedMeeting = meetingContext?.setLastConfirmedMeeting;
  const setScheduleConsensus = meetingContext?.setScheduleConsensus;
  const refreshCalendar = meetingContext?.refreshCalendar;
  useEffect(() => {
    setPeerDateSelections?.(peerSelections);
  }, [peerSelections, setPeerDateSelections]);
  useEffect(() => {
    setSendDateSelection?.(sendDateSelection);
    return () => setSendDateSelection?.(null);
  }, [sendDateSelection, setSendDateSelection]);
  useEffect(() => {
    setPeerTimeSelections?.(peerTimeSelections);
  }, [peerTimeSelections, setPeerTimeSelections]);
  useEffect(() => {
    setSendTimeSelection?.(sendTimeSelection);
    return () => setSendTimeSelection?.(null);
  }, [sendTimeSelection, setSendTimeSelection]);
  useEffect(() => {
    setUnavailabilityByUser?.(unavailabilityByUser);
  }, [unavailabilityByUser, setUnavailabilityByUser]);
  useEffect(() => {
    setSendUnavailableToggle?.(sendUnavailableToggle);
    return () => setSendUnavailableToggle?.(null);
  }, [sendUnavailableToggle, setSendUnavailableToggle]);
  useEffect(() => {
    setMyTimeSelection?.(myTimeSelection);
  }, [myTimeSelection, setMyTimeSelection]);
  useEffect(() => {
    setMyDateSelection?.(myDateSelection);
  }, [myDateSelection, setMyDateSelection]);
  useEffect(() => {
    setFinalizationProposal?.(finalizationProposal);
  }, [finalizationProposal, setFinalizationProposal]);
  useEffect(() => {
    setFinalizationPending?.(finalizationPending);
  }, [finalizationPending, setFinalizationPending]);
  useEffect(() => {
    setLastConfirmedMeeting?.(lastConfirmedMeeting);
  }, [lastConfirmedMeeting, setLastConfirmedMeeting]);
  useEffect(() => {
    setScheduleConsensus?.(scheduleConsensus);
  }, [scheduleConsensus, setScheduleConsensus]);
  // G-1: 새 멤버 join → 다른 멤버 화면 캘린더 X/N 자동 갱신
  useEffect(() => {
    if (lastMemberJoined) refreshCalendar?.();
  }, [lastMemberJoined, refreshCalendar]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const nextInput = input.trim();
    if (!nextInput || status !== "open") {
      return;
    }

    sendMessage(nextInput);
    setInput("");
  };

  // 감지 배너 비활성화 — AI가 조용히 관찰하다 필요할 때만 개입
  const banner = null;

  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        borderRadius: 20,
        border: "1px solid #e2e8f0",
        boxShadow: "0 4px 3.5px rgba(0,0,0,0.25)",
        background: "#fff",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "clamp(10px, 1vw, 16px) clamp(12px, 1.2vw, 20px)",
          background: "#f2f4f7",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <span
          style={{
            fontSize: fs(26, 17),
            fontWeight: 400,
            color: "#000000",
            letterSpacing: 0.75,
          }}
        >
          채팅방
        </span>
        <User style={{ width: 20, height: 20, color: "#94a3b8" }} />
      </div>

      {/* 감지 배너 제거됨 — AI가 조용히 관찰 후 필요시에만 개입 */}

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.map((msg) => {
          const isMe = msg.sender === currentUserName;
          return (
            <div
              key={msg.id}
              style={{
                display: "flex",
                flexDirection: isMe ? "row-reverse" : "row",
                gap: 8,
                alignItems: "flex-end",
              }}
            >
              {!isMe && (
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: "#818cf8",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontSize: 18,
                    fontWeight: 300,
                    flexShrink: 0,
                  }}
                >
                  {(msg.sender ?? "?").charAt(0)}
                </div>
              )}
              <div
                style={{
                  maxWidth: "75%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: isMe ? "flex-end" : "flex-start",
                }}
              >
                {!isMe && (
                  <span style={{ fontSize: fs(11, 10), color: "#94a3b8", marginBottom: 4 }}>
                    {msg.sender}
                  </span>
                )}
                <div
                  style={{
                    padding: "10px 16px",
                    borderRadius: 16,
                    ...(isMe
                      ? {
                          borderBottomRightRadius: 6,
                          background: "#4f46e5",
                          color: "#ffffff",
                        }
                      : {
                          borderBottomLeftRadius: 6,
                          background: "#f1f5f9",
                          color: "#000000",
                        }),
                    fontSize: fs(17, 13),
                    fontWeight: 300,
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap" as const,
                  }}
                >
                  {msg.content}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: 12,
          background: "#fcfdfe",
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <input
          type="text"
          value={input}
          maxLength={2000}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && !event.shiftKey && handleSend()}
          placeholder={status === "open" ? "메세지를 입력하세요" : "연결 중입니다"}
          disabled={status !== "open"}
          style={{
            flex: 1,
            padding: "10px 16px",
            background: "#ffffff",
            borderRadius: 60,
            border: "1px solid #e2e8f0",
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            outline: "none",
            fontSize: fs(15, 12),
            color: "#1e293b",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
          }}
        />
        <button
          onClick={handleSend}
          disabled={status !== "open"}
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: status === "open" ? "#4f46e5" : "#cbd5e1",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: status === "open" ? "pointer" : "not-allowed",
            flexShrink: 0,
          }}
        >
          <Send style={{ width: 16, height: 16, color: "#fff" }} />
        </button>
      </div>
    </div>
  );
}

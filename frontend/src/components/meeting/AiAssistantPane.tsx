"use client";

import { useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Sparkles, Send, Square, MessageCircle, CalendarDays, MapPin, Users, CheckCircle2, ClipboardList, Share2, Check, AlertCircle } from "lucide-react";
import { useAgentWebSocket } from "@/hooks/useAgentWebSocket";
import { useAuth } from "@/hooks/useAuth";
import { MeetingContext } from "@/contexts/MeetingContext";
import { fs } from "@/lib/responsive";
import { apiFetch } from "@/lib/api";
import type { ContextMode } from "@/types";

interface ShareMessageResponse {
  id: number;
  shared_from_id: number;
  created_at: string;
  already_shared: boolean;
}

const PANE_TYPE_MAP: Record<string, ContextMode> = {
  schedule: "schedule",
  place: "place",
  done: "done",
  agent: "agent",
};

export default function AiAssistantPane() {
  const [input, setInput] = useState("");
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [aiTimeoutMessage, setAiTimeoutMessage] = useState<string | null>(null);
  const aiLoadingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const aiWarningTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const meetingContext = useContext(MeetingContext);

  const roomId = meetingContext?.roomId?.trim() || "1";
  const setContextMode = meetingContext?.setContextMode;
  const aiTriggerIntent = meetingContext?.aiTriggerIntent ?? null;
  const setAiTriggerIntent = meetingContext?.setAiTriggerIntent;
  const setVoteCardCtx = meetingContext?.setVoteCard;
  const setVoteUpdateCtx = meetingContext?.setVoteUpdate;
  const setPlaceRecommendationCtx = meetingContext?.setPlaceRecommendation;
  const setSendMessageToAi = meetingContext?.setSendMessageToAi;

  const handlePaneSwitch = useCallback(
    (paneType: string) => {
      const mode = PANE_TYPE_MAP[paneType];
      if (mode && setContextMode) {
        setContextMode(mode);
      }
    },
    [setContextMode],
  );

  const websocketOptions = useMemo(
    () => ({ onPaneSwitch: handlePaneSwitch }),
    [handlePaneSwitch],
  );

  const {
    messages,
    sendMessage,
    status,
    voteCard,
    voteUpdate,
    placeRecommendation,
    maedeupCard,
    autoTrigger,
    dismissAutoTrigger,
    meetingSummary,
  } = useAgentWebSocket(roomId, user?.name ?? "나", websocketOptions);

  const [autoTriggerBanner, setAutoTriggerBanner] = useState<string | null>(null);

  // docs/ai-separation.md §6.1 — share button state
  const [sharedSourceIds, setSharedSourceIds] = useState<Set<number>>(new Set());
  const [sharingId, setSharingId] = useState<number | null>(null);
  const [shareError, setShareError] = useState<{ id: number; message: string } | null>(null);
  const currentUserId = user?.sub ? Number(user.sub) : null;

  const handleShareMessage = useCallback(
    async (messageId: number) => {
      if (sharingId !== null || sharedSourceIds.has(messageId)) return;
      setSharingId(messageId);
      setShareError(null);
      try {
        const res = await apiFetch<ShareMessageResponse>(
          `/api/v1/chat/messages/${messageId}/share`,
          { method: "POST", body: JSON.stringify({}) },
        );
        setSharedSourceIds((prev) => {
          const next = new Set(prev);
          next.add(res.shared_from_id);
          return next;
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "공유 실패";
        setShareError({ id: messageId, message });
      } finally {
        setSharingId(null);
      }
    },
    [sharingId, sharedSourceIds],
  );

  // Sync WS data to MeetingContext for VoteCardSection in InfoPane
  useEffect(() => {
    setVoteCardCtx?.(voteCard ?? null);
  }, [voteCard, setVoteCardCtx]);

  useEffect(() => {
    setVoteUpdateCtx?.(voteUpdate ?? null);
  }, [voteUpdate, setVoteUpdateCtx]);

  useEffect(() => {
    setPlaceRecommendationCtx?.(placeRecommendation ?? null);
  }, [placeRecommendation, setPlaceRecommendationCtx]);

  // Register sendMessage callback so CalendarPane can send messages to AI
  useEffect(() => {
    setSendMessageToAi?.(sendMessage);
    return () => setSendMessageToAi?.(null);
  }, [sendMessage, setSendMessageToAi]);

  // (vote state and place state now managed by VoteCardSection in InfoPane)

  // aiTriggerIntent는 더 이상 자동 메시지를 보내지 않음
  // 채팅방 자체가 일정 조율 목적이므로 AI가 알아서 관찰하다 개입
  useEffect(() => {
    if (aiTriggerIntent) {
      setAiTriggerIntent?.(null);
    }
  }, [aiTriggerIntent, setAiTriggerIntent]);

  // 소셜 채팅에서 AI 자동 트리거가 감지되면 배너 표시
  useEffect(() => {
    if (!autoTrigger) {
      return;
    }
    // 자동 트리거는 배너 없이 조용히 처리 (AI가 필요할 때만 응답)
    dismissAutoTrigger();
  }, [autoTrigger, dismissAutoTrigger]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, voteCard, placeRecommendation, maedeupCard, meetingSummary, isAiLoading, aiTimeoutMessage]);

  // Clear loading state helper
  const clearAiLoading = useCallback(() => {
    setIsAiLoading(false);
    setAiTimeoutMessage(null);
    if (aiLoadingTimeoutRef.current) {
      clearTimeout(aiLoadingTimeoutRef.current);
      aiLoadingTimeoutRef.current = null;
    }
    if (aiWarningTimeoutRef.current) {
      clearTimeout(aiWarningTimeoutRef.current);
      aiWarningTimeoutRef.current = null;
    }
  }, []);

  // Set isAiLoading to false when an assistant message arrives
  useEffect(() => {
    if (messages.length > 0 && messages[messages.length - 1]?.role === "assistant") {
      clearAiLoading();
    }
  }, [messages, clearAiLoading]);

  // Also clear loading when any card payload arrives
  useEffect(() => {
    if (voteCard || placeRecommendation || maedeupCard) {
      clearAiLoading();
    }
  }, [voteCard, placeRecommendation, maedeupCard, clearAiLoading]);

  // Reset loading when WS reconnects (don't treat connecting as loading)
  useEffect(() => {
    if (status === "open") {
      // WS 연결 완료 시, 메시지가 없으면 로딩 해제
      if (messages.length === 0) {
        setIsAiLoading(false);
      }
    }
  }, [status, messages.length]);

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (aiLoadingTimeoutRef.current) clearTimeout(aiLoadingTimeoutRef.current);
      if (aiWarningTimeoutRef.current) clearTimeout(aiWarningTimeoutRef.current);
    };
  }, []);

  // Error auto-dismiss moved to VoteCardSection

  const handleStopAi = () => {
    setIsAiLoading(false);
    setAiTimeoutMessage(null);
    if (aiLoadingTimeoutRef.current) {
      clearTimeout(aiLoadingTimeoutRef.current);
      aiLoadingTimeoutRef.current = null;
    }
    if (aiWarningTimeoutRef.current) {
      clearTimeout(aiWarningTimeoutRef.current);
      aiWarningTimeoutRef.current = null;
    }
  };

  const handleSend = () => {
    const nextInput = input.trim();
    if (!nextInput || status !== "open") {
      return;
    }

    sendMessage(nextInput);
    setInput("");
    setIsAiLoading(true);
    setAiTimeoutMessage(null);

    // Warning after 20 seconds
    if (aiWarningTimeoutRef.current) {
      clearTimeout(aiWarningTimeoutRef.current);
    }
    aiWarningTimeoutRef.current = setTimeout(() => {
      setAiTimeoutMessage("응답이 지연되고 있어요. 잠시만 기다려주세요...");
      aiWarningTimeoutRef.current = null;
    }, 20_000);

    // Auto-cancel after 90 seconds
    if (aiLoadingTimeoutRef.current) {
      clearTimeout(aiLoadingTimeoutRef.current);
    }
    aiLoadingTimeoutRef.current = setTimeout(() => {
      setIsAiLoading(false);
      setAiTimeoutMessage("응답 시간이 초과되었어요. 다시 시도해주세요.");
      aiLoadingTimeoutRef.current = null;
    }, 90_000);
  };

  // Vote handlers moved to VoteCardSection in InfoPane

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
          gap: 8,
          padding: "clamp(10px, 1vw, 16px) clamp(12px, 1.2vw, 20px)",
          background: "linear-gradient(135deg, #837cff, #6eb3ff)",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <Sparkles style={{ width: 20, height: 20, color: "#ffffff" }} />
        <span
          style={{
            fontSize: fs(26, 17),
            fontWeight: 400,
            color: "#ffffff",
            letterSpacing: 0.75,
          }}
        >
          AI 어시스턴트
        </span>
      </div>

      {status !== "open" && messages.length > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 16px",
            background: status === "connecting" ? "#fef3c7" : "#fee2e2",
            color: status === "connecting" ? "#92400e" : "#991b1b",
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: status === "connecting" ? "#f59e0b" : "#ef4444",
              flexShrink: 0,
            }}
          />
          <span>{status === "connecting" ? "재연결 중..." : "연결이 끊어졌습니다. 자동으로 재연결합니다."}</span>
        </div>
      )}

      {autoTriggerBanner && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 16px",
            background: "linear-gradient(135deg, #4f46e5, #0891b2)",
            color: "#fff",
            fontSize: 13,
            fontWeight: 500,
            animation: "fadeIn 0.3s ease-in",
          }}
        >
          <Sparkles style={{ width: 14, height: 14 }} />
          <span style={{ flex: 1 }}>{autoTriggerBanner}</span>
          <button
            onClick={() => setAutoTriggerBanner(null)}
            style={{
              background: "none",
              border: "none",
              color: "#fff",
              cursor: "pointer",
              padding: 0,
              fontSize: 14,
              lineHeight: 1,
            }}
          >
            &times;
          </button>
        </div>
      )}

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "14px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {meetingSummary && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              padding: 16,
              borderRadius: 16,
              background: "linear-gradient(135deg, #7c3aed 0%, #a855f7 50%, #c084fc 100%)",
              color: "#ffffff",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              boxShadow: "0 4px 14px rgba(124, 58, 237, 0.18)",
              animation: "fadeIn 0.4s ease-out",
            }}
          >
            <style>{`
              @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-8px); }
                to { opacity: 1; transform: translateY(0); }
              }
              @keyframes summaryPulse {
                0%, 100% { box-shadow: 0 4px 14px rgba(124, 58, 237, 0.18); }
                50% { box-shadow: 0 6px 20px rgba(124, 58, 237, 0.3); }
              }
            `}</style>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <ClipboardList style={{ width: 18, height: 18, color: "#ffffff" }} />
              <span style={{ fontSize: fs(13, 11), fontWeight: 700, color: "rgba(255,255,255,0.9)" }}>
                현재 대화 정리
              </span>
            </div>
            <div
              style={{
                display: "grid",
                gap: 8,
                padding: 14,
                borderRadius: 12,
                background: "rgba(255,255,255,0.15)",
                border: "1px solid rgba(255,255,255,0.2)",
              }}
            >
              {meetingSummary.date && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <CalendarDays style={{ width: 14, height: 14, color: "#e9d5ff", flexShrink: 0 }} />
                  <span style={{ fontSize: fs(14, 12), fontWeight: 500 }}>
                    날짜: {meetingSummary.date}
                  </span>
                </div>
              )}
              {meetingSummary.place && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <MapPin style={{ width: 14, height: 14, color: "#e9d5ff", flexShrink: 0 }} />
                  <span style={{ fontSize: fs(14, 12), fontWeight: 500 }}>
                    장소: {meetingSummary.place}
                  </span>
                </div>
              )}
              {meetingSummary.headcount && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Users style={{ width: 14, height: 14, color: "#e9d5ff", flexShrink: 0 }} />
                  <span style={{ fontSize: fs(14, 12), fontWeight: 500 }}>
                    인원: {meetingSummary.headcount}
                  </span>
                </div>
              )}
              {meetingSummary.meeting_type && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Sparkles style={{ width: 14, height: 14, color: "#e9d5ff", flexShrink: 0 }} />
                  <span style={{ fontSize: fs(14, 12), fontWeight: 500 }}>
                    유형: {meetingSummary.meeting_type}
                  </span>
                </div>
              )}
              {meetingSummary.notes && meetingSummary.notes.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 2 }}>
                  {meetingSummary.notes.map((note, i) => (
                    <span key={i} style={{ fontSize: fs(13, 11), fontWeight: 400, color: "rgba(255,255,255,0.85)" }}>
                      · {note}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {messages.length === 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 14px",
              background: "#eef2ff",
              borderRadius: 18,
            }}
          >
            <MessageCircle style={{ width: 16, height: 16, color: "#4f46e5" }} />
            <span style={{ fontSize: fs(15, 12), fontWeight: 400, color: "#4f46e5", fontFamily: "Inter, sans-serif" }}>
              AI 어시스턴트에게 모임 일정이나 장소를 물어보세요
            </span>
          </div>
        )}

        {/* Vote card stub - actual cards now rendered in InfoPane's VoteCardSection */}
        {(voteCard || placeRecommendation) && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 16px",
              borderRadius: 14,
              background: "#eef2ff",
              border: "1px solid #c7d2fe",
            }}
          >
            <CalendarDays style={{ width: 18, height: 18, color: "#4f46e5" }} />
            <span style={{ fontSize: fs(14, 12), fontWeight: 500, color: "#4f46e5", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
              {voteCard ? "투표가 진행 중입니다" : "장소 추천이 도착했습니다"} — 오른쪽 캘린더 탭에서 확인하세요
            </span>
          </div>
        )}

        {maedeupCard && (() => {
          const displayTime = maedeupCard.selected_time;
          const displayPlace = maedeupCard.selected_place;
          const title = maedeupCard.title ?? `${maedeupCard.meeting_type ?? "모임"} 매듭 카드`;

          return (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 16,
                padding: 20,
                borderRadius: 20,
                background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)",
                color: "#ffffff",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                boxShadow: "0 10px 24px rgba(79, 70, 229, 0.22)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <CheckCircle2 style={{ width: 24, height: 24, color: "#ffffff" }} />
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: fs(12, 10.5), fontWeight: 700, color: "rgba(255,255,255,0.82)" }}>
                    최종 확정
                  </span>
                  <span style={{ fontSize: fs(21, 15), fontWeight: 700, color: "#ffffff" }}>
                    {title}
                  </span>
                </div>
              </div>
              <div
                style={{
                  display: "grid",
                  gap: 10,
                  padding: 16,
                  borderRadius: 16,
                  background: "rgba(255,255,255,0.14)",
                  border: "1px solid rgba(255,255,255,0.18)",
                }}
              >
                {maedeupCard && (
                  <>
                    <span style={{ fontSize: fs(15, 12), lineHeight: 1.5 }}>
                      {maedeupCard.meeting_type} · {maedeupCard.date_hint}
                    </span>
                    <span style={{ fontSize: fs(15, 12), lineHeight: 1.5 }}>
                      참석 인원 {maedeupCard.headcount}명
                    </span>
                  </>
                )}
                {displayTime && (
                  <span style={{ fontSize: 15, lineHeight: 1.5 }}>
                    시간 {displayTime.label}
                  </span>
                )}
                {displayPlace && (
                  <>
                    <span style={{ fontSize: fs(15, 12), lineHeight: 1.5 }}>
                      장소 {displayPlace.name}
                    </span>
                    <span style={{ fontSize: fs(14, 12), lineHeight: 1.5, color: "rgba(255,255,255,0.84)" }}>
                      {displayPlace.address}
                    </span>
                  </>
                )}
              </div>
            </div>
          );
        })()}

        {messages.map((msg, index) => {
          const isMe = msg.role === "user";
          const rawSender = isMe ? (msg.sender ?? user?.name ?? "나") : (msg.sender ?? "AI 어시스턴트");
          const senderLabel = rawSender === "LangGraph" ? "매듭 AI" : rawSender;

          // docs/ai-separation.md §2.2 — visibility-based rendering
          const visibility = msg.visibility ?? "shared";
          const isPrivate = visibility === "private";
          const isSharedByUser = visibility === "shared" && msg.shared_by_user_id != null;
          const isSharedByMe = isSharedByUser && msg.shared_by_user_id === currentUserId;
          // Share button visibility: only on MY private AI responses
          const canShare =
            !isMe &&
            isPrivate &&
            msg.user_id != null &&
            msg.user_id === currentUserId &&
            typeof msg.id === "number";
          const alreadyShared = typeof msg.id === "number" && sharedSourceIds.has(msg.id);
          const isSharing = sharingId === msg.id;
          const hasShareError = shareError?.id === msg.id;

          // Accent rail color — different hues so "내가 공유" vs "OO님 공유" is distinguishable at a glance
          const accentColor = isSharedByMe ? "#10b981" : isSharedByUser ? "#f59e0b" : null;

          return (
            <div
              key={msg.id ?? index}
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
                    fontSize: 12,
                    fontWeight: 300,
                    flexShrink: 0,
                  }}
                >
                  {senderLabel.charAt(0)}
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
                    {senderLabel}
                  </span>
                )}
                {isSharedByUser && (
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "2px 8px",
                      marginBottom: 4,
                      background: isSharedByMe ? "#d1fae5" : "#fef3c7",
                      borderRadius: 10,
                      fontSize: fs(10, 9),
                      fontWeight: 500,
                      color: isSharedByMe ? "#065f46" : "#92400e",
                    }}
                  >
                    <Share2 size={10} />
                    {isSharedByMe ? "내가 공유" : `${senderLabel}님이 공유`}
                  </div>
                )}
                <div
                  style={{
                    padding: "10px 16px",
                    borderRadius: 16,
                    // Triple-code for shared-by-user: accent rail via left border (docs §2.3)
                    ...(accentColor
                      ? { borderLeft: `3px solid ${accentColor}` }
                      : {}),
                    ...(isMe
                      ? {
                          borderBottomRightRadius: 6,
                          background: "#4f46e5",
                          color: "#ffffff",
                        }
                      : {
                          borderBottomLeftRadius: 6,
                          background: isSharedByMe
                            ? "#ecfdf5"
                            : isSharedByUser
                              ? "#fffbeb"
                              : "#f1f5f9",
                          color: "#000000",
                        }),
                    fontSize: fs(17, 13),
                    fontWeight: 300,
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap" as const,
                    overflowWrap: "anywhere" as const,
                  }}
                >
                  {msg.content}
                </div>
                {canShare && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      marginTop: 4,
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => handleShareMessage(msg.id)}
                      disabled={alreadyShared || isSharing}
                      title={alreadyShared ? "이미 공유됨" : "모두에게 공유"}
                      aria-label={alreadyShared ? "이미 공유됨" : "모두에게 공유"}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "4px 10px",
                        minHeight: 28,
                        background: alreadyShared ? "#f1f5f9" : "transparent",
                        border: "1px solid",
                        borderColor: alreadyShared ? "#cbd5e1" : "#a5b4fc",
                        borderRadius: 12,
                        fontSize: fs(11, 10),
                        fontWeight: 500,
                        color: alreadyShared ? "#64748b" : "#4f46e5",
                        cursor: alreadyShared || isSharing ? "not-allowed" : "pointer",
                        opacity: isSharing ? 0.6 : 1,
                        transition: "all 0.15s ease",
                      }}
                    >
                      {alreadyShared ? (
                        <>
                          <Check size={12} />
                          공유됨
                        </>
                      ) : isSharing ? (
                        <>
                          <Share2 size={12} style={{ animation: "pulse 1s infinite" }} />
                          공유 중...
                        </>
                      ) : (
                        <>
                          <Share2 size={12} />
                          모두에게 공유
                        </>
                      )}
                    </button>
                    {hasShareError && (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 2,
                          fontSize: fs(10, 9),
                          color: "#dc2626",
                        }}
                      >
                        <AlertCircle size={10} /> {shareError.message}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {aiTimeoutMessage && !isAiLoading && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 14px",
              background: "#fef3c7",
              borderRadius: 12,
              fontSize: 13,
              color: "#92400e",
              fontWeight: 500,
            }}
          >
            {aiTimeoutMessage}
          </div>
        )}

        {isAiLoading && messages.length > 0 && (
          <div
            style={{
              display: "flex",
              flexDirection: "row",
              gap: 8,
              alignItems: "flex-end",
            }}
          >
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
                fontSize: 12,
                fontWeight: 300,
                flexShrink: 0,
              }}
            >
              AI
            </div>
            <div
              style={{
                padding: "12px 18px",
                borderRadius: 16,
                borderBottomLeftRadius: 6,
                background: "#f1f5f9",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <style>{`
                @keyframes aiTypingDot {
                  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
                  40% { opacity: 1; transform: scale(1); }
                }
              `}</style>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#4f46e5",
                  display: "inline-block",
                  animation: "aiTypingDot 1.4s infinite ease-in-out",
                  animationDelay: "0s",
                }}
              />
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#4f46e5",
                  display: "inline-block",
                  animation: "aiTypingDot 1.4s infinite ease-in-out",
                  animationDelay: "0.2s",
                }}
              />
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#4f46e5",
                  display: "inline-block",
                  animation: "aiTypingDot 1.4s infinite ease-in-out",
                  animationDelay: "0.4s",
                }}
              />
            </div>
            {aiTimeoutMessage && (
              <span style={{ fontSize: 12, color: "#92400e", marginLeft: 40 }}>
                {aiTimeoutMessage}
              </span>
            )}
          </div>
        )}

        {messages.length === 0 && (
          <div
            style={{
              background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
              borderRadius: 16,
              padding: 20,
              display: "flex",
              flexDirection: "column",
              gap: 12,
              marginTop: 4,
              boxShadow: "0 4px 14px rgba(79, 70, 229, 0.13)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Sparkles style={{ width: 20, height: 20, color: "#ffffff" }} />
              <span style={{ fontSize: fs(12, 10.5), fontWeight: 600, color: "#ffffff", fontFamily: "Inter, sans-serif" }}>
                AI 어시스턴트
              </span>
            </div>
            <span style={{ fontSize: fs(18, 14), fontWeight: 600, color: "#ffffff", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
              {isAiLoading ? "분석 중..." : "일정 조율을 시작하겠습니다"}
            </span>
            <span
              style={{
                fontSize: fs(13, 11),
                fontWeight: 300,
                color: "#ffffff",
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              }}
            >
              {isAiLoading
                ? "채팅 내용을 분석하여 모임원들의\n가능한 시간대를 정리하고 있어요."
                : "메시지를 보내 일정 조율을 시작해보세요."}
            </span>
            <div style={{ width: "100%", height: 1, background: "rgba(255,255,255,0.19)" }} />
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: isAiLoading ? "#fbbf24" : "#34d399",
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: fs(12, 10.5), fontWeight: 300, color: "#ffffff", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
                {status === "connecting"
                  ? "연결 중..."
                  : isAiLoading
                    ? "AI가 응답 중..."
                    : "연결됨 · 메시지를 기다리는 중"}
              </span>
            </div>
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: 12,
          background: "linear-gradient(135deg, #837cff, #6eb3ff)",
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <input
          type="text"
          value={input}
          maxLength={2000}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && !event.shiftKey && !isAiLoading && handleSend()}
          disabled={isAiLoading || status !== "open"}
          placeholder={
            status !== "open"
              ? status === "connecting" ? "연결 중..." : "연결이 끊어졌습니다"
              : isAiLoading ? "AI가 응답 중..." : "AI에게 질문하세요"
          }
          style={{
            flex: 1,
            padding: "10px 16px",
            background: isAiLoading || status !== "open" ? "#f1f5f9" : "#ffffff",
            borderRadius: 60,
            border: "1.5px solid #a2f4fd",
            outline: "none",
            fontSize: fs(15, 12),
            color: "#1e293b",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            boxShadow: "0 2px 3.5px rgba(0,0,0,0.15)",
            opacity: isAiLoading || status !== "open" ? 0.7 : 1,
            cursor: isAiLoading || status !== "open" ? "not-allowed" : "text",
          }}
        />
        <button
          onClick={isAiLoading ? handleStopAi : handleSend}
          title={isAiLoading ? "응답 정지" : "메시지 보내기"}
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: isAiLoading ? "#ef4444" : "#ffffff",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            flexShrink: 0,
            boxShadow: "0 2px 3.5px rgba(0,0,0,0.15)",
            transition: "background 0.2s ease",
          }}
        >
          {isAiLoading ? (
            <Square style={{ width: 14, height: 14, color: "#ffffff", fill: "#ffffff" }} />
          ) : (
            <Send style={{ width: 16, height: 16, color: "#837cff" }} />
          )}
        </button>
      </div>
    </div>
  );
}

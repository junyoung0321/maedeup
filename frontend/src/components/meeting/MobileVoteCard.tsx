"use client";

import { useState } from "react";
import { CalendarCheck, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type {
  VoteCardPayload,
  VoteUpdatePayload,
} from "@/hooks/useAgentWebSocket";

// 모바일 AI 비서(/m/chat/ai)에 AI의 일정 추천(vote_card)을 표시한다.
// 백엔드 파이프라인이 만든 추천 날짜 옵션(전원 가능/다수결)을 보여주고,
// 슬롯을 탭하면 가볍게 투표(POST /meetings/{id}/vote)한다.
// 데스크탑 ScheduleRecommendationCard의 풀 흐름(TimeBar 합의·호스트 확정·finalization)은
// 아직 모바일 미구현 — 여기서는 '추천 표시 + 기본 투표'까지만 담당한다.
export default function MobileVoteCard({
  card,
  voteUpdate,
}: {
  card: VoteCardPayload;
  voteUpdate: VoteUpdatePayload | null;
}) {
  const meetingId = card.meeting_id ?? null;
  const [selected, setSelected] = useState<number | null>(
    card.current_user_vote ?? null,
  );
  const [voting, setVoting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 집계 카운트: 이 모임에 대한 voteUpdate가 있으면 optionIndex→count 맵 사용.
  const counts: Record<string, number> =
    voteUpdate && voteUpdate.meeting_id === meetingId ? voteUpdate.votes : {};

  async function vote(idx: number) {
    if (meetingId == null || voting) return;
    const prev = selected;
    setVoting(true);
    setError(null);
    setSelected(idx);
    try {
      await apiFetch(`/api/v1/meetings/${meetingId}/vote`, {
        method: "POST",
        body: JSON.stringify({ option_index: idx }),
      });
    } catch {
      setSelected(prev);
      setError("투표 전송에 실패했어요. 다시 시도해주세요.");
    } finally {
      setVoting(false);
    }
  }

  const options = card.time_options ?? [];

  return (
    <div style={{ display: "flex", gap: 8 }}>
      {/* AI 아바타 */}
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 16,
          background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <CalendarCheck size={16} color="#ffffff" />
      </div>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
        <span style={{ fontSize: 12, color: "#94a3b8" }}>AI 비서</span>

        <div
          style={{
            borderRadius: "0 16px 16px 16px",
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: 14,
            display: "flex",
            flexDirection: "column",
            gap: 12,
            boxShadow: "0 2px 10px rgba(79,70,229,0.06)",
          }}
        >
          <span style={{ fontSize: 14, fontWeight: 700, color: "#1e293b" }}>
            {card.title || "모임 날짜 추천 📅"}
          </span>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {options.map((opt, idx) => {
              const isSel = selected === idx;
              const all =
                opt.available_count != null &&
                opt.total_count != null &&
                opt.available_count === opt.total_count;
              const badge =
                opt.available_count != null && opt.total_count != null
                  ? all
                    ? "전원 가능"
                    : `${opt.available_count}명 가능`
                  : null;
              const voteCount = counts[String(idx)] ?? 0;

              return (
                <div
                  key={opt.slot_id ?? idx}
                  onClick={() => vote(idx)}
                  style={{
                    borderRadius: 12,
                    background: isSel ? "#eef2ff" : "#f8fafc",
                    border: isSel
                      ? "1.5px solid #4f46e5"
                      : "1px solid #e2e8f0",
                    padding: "12px 14px",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    cursor: voting ? "wait" : "pointer",
                  }}
                >
                  <div
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: 10,
                      flexShrink: 0,
                      border: isSel ? "none" : "1.5px solid #cbd5e1",
                      background: isSel ? "#4f46e5" : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {isSel && <Check size={13} color="#ffffff" />}
                  </div>

                  <div
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      gap: 3,
                    }}
                  >
                    <span
                      style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}
                    >
                      {opt.label}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {badge && (
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 600,
                            color: all ? "#4f46e5" : "#64748b",
                            background: all ? "#eef2ff" : "#f1f5f9",
                            borderRadius: 999,
                            padding: "2px 8px",
                          }}
                        >
                          {badge}
                        </span>
                      )}
                      {voteCount > 0 && (
                        <span style={{ fontSize: 11, color: "#94a3b8" }}>
                          투표 {voteCount}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {error ? (
            <span style={{ fontSize: 11, color: "#ef4444" }}>{error}</span>
          ) : (
            <span style={{ fontSize: 11, color: "#94a3b8" }}>
              {selected != null
                ? "투표했어요. 다른 시간을 탭하면 변경됩니다."
                : "원하는 시간을 탭해 투표하세요."}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

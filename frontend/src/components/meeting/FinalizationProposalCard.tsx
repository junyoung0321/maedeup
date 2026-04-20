"use client";

import { useEffect, useState } from "react";
import { Sparkles, Check, Clock, User as UserIcon } from "lucide-react";
import type {
  FinalizationState,
  VoteChoice,
} from "@/hooks/useSocialWebSocket";
import { apiFetch } from "@/lib/api";
import { fs } from "@/lib/responsive";

// Brand indigo — matches the TimeBar COLOR_MY_PICK constant, kept in sync
// with design system variables.
const INDIGO = "#4f46e5";
const GREEN = "#22c55e";
const ORANGE = "#fb923c";
const GRAY = "#94a3b8";
const BG = "#ffffff";

interface Props {
  proposal: FinalizationState | null;
  pending: boolean;
  currentUserId: number | null;
  roomId: string;
  onConfirm: (proposalId: string, slot: { start_at: string; end_at: string; label: string }) => Promise<void>;
  onConfirmed?: () => void;
}

function _fmtTime(deadlineAt: number, now: number): string {
  const diff = Math.max(0, Math.floor(deadlineAt - now));
  if (diff > 24 * 3600) {
    return `D-${Math.floor(diff / (24 * 3600))}`;
  }
  const hrs = Math.floor(diff / 3600);
  const mins = Math.floor((diff % 3600) / 60);
  if (hrs > 0) return `${hrs}시간 ${mins}분`;
  return `${mins}분`;
}

export default function FinalizationProposalCard({
  proposal,
  pending,
  currentUserId,
  roomId,
  onConfirm,
  onConfirmed,
}: Props) {
  const [confirming, setConfirming] = useState(false);
  const [voting, setVoting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(Date.now());

  // Tick for the deadline counter (no need for a full scheduler).
  useEffect(() => {
    if (!proposal) return;
    const id = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, [proposal?.proposal_id]);

  // Shimmer / pending state — shown while AI is composing the reason.
  if (pending && !proposal) {
    return (
      <div
        role="region"
        aria-label="매듭 AI 확정 제안 준비 중"
        style={cardShell(true)}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Sparkles size={18} color={INDIGO} />
          <span style={{ fontSize: fs(14, 12), fontWeight: 600, color: INDIGO }}>
            매듭 AI가 분석 중이에요…
          </span>
        </div>
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          <Shimmer width="60%" height={24} />
          <Shimmer width="90%" height={14} />
          <Shimmer width="40%" height={28} />
        </div>
      </div>
    );
  }

  if (!proposal) return null;

  const isHost = currentUserId === proposal.host_user_id;
  const majorityReached = proposal.status === "majority_reached";
  const isConfirmed = proposal.status === "confirmed";
  const likeCount = Object.values(proposal.votes).filter((v) => v === "like").length;
  const otherCount = Object.values(proposal.votes).filter((v) => v === "other").length;
  const notVoted = Math.max(0, proposal.total_eligible_voters - likeCount - otherCount);

  const handleVote = async (choice: VoteChoice) => {
    if (voting || isConfirmed) return;
    setVoting(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/finalization/${proposal.proposal_id}/vote`, {
        method: "POST",
        body: JSON.stringify({ choice, room_id: parseInt(roomId, 10) }),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "투표에 실패했어요");
    } finally {
      setVoting(false);
    }
  };

  const handleConfirm = async () => {
    if (!majorityReached || confirming) return;
    setConfirming(true);
    setError(null);
    try {
      await onConfirm(proposal.proposal_id, {
        start_at: proposal.proposed_slot.start_at,
        end_at: proposal.proposed_slot.end_at,
        label: proposal.proposed_slot.label,
      });
      onConfirmed?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "확정에 실패했어요. 다시 시도해주세요.");
    } finally {
      setConfirming(false);
    }
  };

  // ── Confirmed state: success banner ──
  if (isConfirmed) {
    return (
      <div role="region" aria-live="polite" style={{ ...cardShell(false), borderColor: GREEN, background: "#ecfdf5" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Check size={20} color={GREEN} />
          <span style={{ fontSize: fs(16, 13), fontWeight: 700, color: "#166534" }}>
            모임이 확정되었습니다!
          </span>
        </div>
        <div style={{ marginTop: 6, fontSize: fs(14, 12), color: "#166534" }}>
          {proposal.proposed_slot.label}
        </div>
      </div>
    );
  }

  return (
    <div role="region" aria-label="매듭 AI 확정 제안" style={cardShell(false)}>
      {/* Narrator line */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <Sparkles size={18} color={INDIGO} />
        <span style={{ fontSize: fs(13, 11), fontWeight: 600, color: INDIGO }}>매듭 AI</span>
      </div>

      {/* Hero — proposed slot */}
      <div
        style={{
          fontSize: fs(24, 18),
          fontWeight: 700,
          color: "#1e1b4b",
          letterSpacing: "-0.02em",
        }}
      >
        {proposal.proposed_slot.label}
      </div>

      {/* Alternate slot (tie case) */}
      {proposal.alternate_slot && (
        <div style={{ marginTop: 4, fontSize: fs(16, 13), color: "#475569" }}>
          또는 <strong>{proposal.alternate_slot.label}</strong>
        </div>
      )}

      {/* Reason line */}
      <div
        style={{
          marginTop: 8,
          fontSize: fs(14, 12),
          color: "#475569",
          lineHeight: 1.5,
        }}
      >
        {proposal.reason}
      </div>

      {/* Tally pills */}
      <div
        role="group"
        aria-live="polite"
        aria-label="현재 투표 현황"
        style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}
      >
        <Pill
          color={GREEN}
          icon={<Check size={14} />}
          label="좋아요"
          value={likeCount}
        />
        <Pill
          color={ORANGE}
          icon={<Clock size={14} />}
          label="다른 시간"
          value={otherCount}
        />
        <Pill
          color={GRAY}
          icon={<UserIcon size={14} />}
          label="미투표"
          value={notVoted}
        />
      </div>

      {/* My vote status */}
      {proposal.my_vote && (
        <div style={{ marginTop: 10, fontSize: fs(13, 11), color: GREEN }}>
          ✓ {proposal.my_vote === "like" ? "좋아요" : "다른 시간"}로 투표함
        </div>
      )}

      {/* Vote buttons (members who haven't voted yet, except the confirmed state) */}
      {!proposal.my_vote && !isConfirmed && (
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button
            onClick={() => handleVote("like")}
            disabled={voting}
            aria-label="이 시간에 동의"
            style={primaryButton()}
          >
            좋아요
          </button>
          <button
            onClick={() => handleVote("other")}
            disabled={voting}
            aria-label="다른 시간 요청"
            style={secondaryButton()}
          >
            다른 시간 제안
          </button>
        </div>
      )}

      {/* Host confirm / wait status */}
      <div style={{ marginTop: 14, paddingTop: 10, borderTop: "1px solid #e2e8f0" }}>
        {isHost ? (
          <button
            onClick={handleConfirm}
            disabled={!majorityReached || confirming}
            aria-label="이 시간으로 모임 확정"
            style={hostConfirmButton(majorityReached, confirming)}
          >
            {confirming
              ? "확정 중…"
              : majorityReached
              ? "이 시간으로 확정"
              : `과반 동의 대기 중 (${likeCount}/${proposal.total_eligible_voters})`}
          </button>
        ) : (
          <div style={{ fontSize: fs(13, 11), color: "#64748b", textAlign: "center" }}>
            {majorityReached ? "방장 확정 대기 중 ⏳" : "과반 동의 대기 중"}
          </div>
        )}
      </div>

      {/* Deadline footer */}
      {proposal.deadline_at > 0 && (
        <div style={{ marginTop: 8, fontSize: fs(11, 10), color: "#94a3b8", textAlign: "right" }}>
          마감 {_fmtTime(proposal.deadline_at, nowMs / 1000)} 후
        </div>
      )}

      {/* Error toast */}
      {error && (
        <div
          role="alert"
          style={{
            marginTop: 10,
            padding: "8px 10px",
            background: "#fee2e2",
            color: "#991b1b",
            borderRadius: 8,
            fontSize: fs(12, 11),
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}

// ── Styling helpers ────────────────────────────────────────────────────

function cardShell(isPending: boolean): React.CSSProperties {
  return {
    padding: "14px 16px",
    margin: "0 4px 8px",
    borderRadius: 14,
    background: BG,
    border: `2px solid ${isPending ? "#c7d2fe" : INDIGO}`,
    boxShadow: "0 6px 16px rgba(79,70,229,0.08)",
    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
  };
}

function Pill({
  color, icon, label, value,
}: { color: string; icon: React.ReactNode; label: string; value: number }) {
  return (
    <div
      aria-label={`${label} ${value}표`}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "6px 10px",
        borderRadius: 999,
        background: `${color}1a`,
        color,
        fontWeight: 600,
        fontSize: fs(12, 11),
        minHeight: 32,
      }}
    >
      {icon}
      <span>{label}</span>
      <strong style={{ fontSize: fs(14, 12) }}>{value}</strong>
    </div>
  );
}

function primaryButton(): React.CSSProperties {
  return {
    flex: 1,
    minHeight: 44,
    padding: "10px 14px",
    background: INDIGO,
    color: "white",
    border: "none",
    borderRadius: 10,
    fontWeight: 700,
    fontSize: fs(14, 12),
    cursor: "pointer",
    fontFamily: "inherit",
  };
}

function secondaryButton(): React.CSSProperties {
  return {
    flex: 1,
    minHeight: 44,
    padding: "10px 14px",
    background: "white",
    color: INDIGO,
    border: `1.5px solid ${INDIGO}`,
    borderRadius: 10,
    fontWeight: 600,
    fontSize: fs(14, 12),
    cursor: "pointer",
    fontFamily: "inherit",
  };
}

function hostConfirmButton(enabled: boolean, busy: boolean): React.CSSProperties {
  return {
    width: "100%",
    minHeight: 44,
    padding: "10px 14px",
    background: enabled ? GREEN : "#e2e8f0",
    color: enabled ? "white" : "#64748b",
    border: "none",
    borderRadius: 10,
    fontWeight: 700,
    fontSize: fs(14, 12),
    cursor: enabled && !busy ? "pointer" : "not-allowed",
    fontFamily: "inherit",
    transition: "all 0.15s",
  };
}

function Shimmer({ width, height }: { width: string; height: number }) {
  return (
    <div
      aria-hidden
      style={{
        width,
        height,
        background: "linear-gradient(90deg,#f1f5f9 0%,#e2e8f0 50%,#f1f5f9 100%)",
        backgroundSize: "200% 100%",
        borderRadius: 6,
        animation: "shimmer 1.2s infinite linear",
      }}
    />
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AiTriggerIntent, ChatMessagePayload } from "@/types";

export type { ChatMessagePayload };

export interface ReminderPayload {
  type: "reminder";
  message: string;
  meeting_id: number;
}

export interface VoteReminderPayload {
  type: "vote_reminder";
  message: string;
  meeting_id: number;
}

export interface PeerDateSelectionPayload {
  type: "peer_date_selection";
  user_id: number | null;
  sender: string | null;
  date: string | null; // "YYYY-MM-DD" or null (해제)
}

export interface PeerSelection {
  userId: number | null;
  name: string;
  date: string | null;
}

export interface PeerTimeSelectionPayload {
  type: "peer_time_selection";
  user_id: number | null;
  sender: string | null;
  date: string | null;
  start: number | null;
  end: number | null;
}

export interface PeerTimeSelection {
  userId: number | null;
  name: string;
  date: string;
  start: number;
  end: number;
}

// ── Unavailability (red-bordered calendar dates) ─────────────────────────
export interface PeerUnavailableUpdatePayload {
  type: "peer_unavailable_update";
  user_id: number | null;
  sender: string | null;
  dates: string[];
}

export interface UnavailableSnapshotPayload {
  type: "unavailable_snapshot";
  by_user: Record<string, string[]>;
}

export interface AvailabilitySnapshotPayload {
  type: "availability_snapshot";
  by_user: Record<string, { date: string; start: number; end: number }>;
}

export interface DateSelectionSnapshotPayload {
  type: "date_selection_snapshot";
  by_user: Record<string, string>;
}

// ── Finalization (AI proposal → host approval) payloads ──────────────────
export type FinalizationStatus =
  | "pending_ai"
  | "active"
  | "majority_reached"
  | "confirmed"
  | "superseded";

export type VoteChoice = "like" | "other";

export interface FinalizationSlot {
  date: string;
  start_idx: number;
  end_idx: number;
  start_at: string;
  end_at: string;
  label: string;
}

export interface FinalizationPendingPayload {
  type: "finalization_pending";
  room_id: number;
  snapshot_hash: string;
}

export interface FinalizationProposalPayload {
  type: "finalization_proposal";
  room_id: number;
  proposal_id: string;
  version: number;
  status: FinalizationStatus;
  proposed_slot: FinalizationSlot;
  alternate_slot: FinalizationSlot | null;
  reason: string;
  host_user_id: number;
  total_eligible_voters: number;
  votes: Record<string, VoteChoice>;
  deadline_at: number;
  created_at: number;
}

export interface FinalizationVoteUpdatePayload {
  type: "finalization_vote_update";
  room_id: number;
  proposal_id: string;
  version: number;
  status: FinalizationStatus;
  proposed_slot: FinalizationSlot;
  alternate_slot: FinalizationSlot | null;
  reason: string;
  host_user_id: number;
  total_eligible_voters: number;
  like_count: number;
  other_count: number;
  votes: Record<string, VoteChoice>;
  my_vote: VoteChoice | null;
}

export interface MeetingConfirmedPayload {
  type: "meeting_confirmed";
  room_id: number;
  meeting_id: number;
  proposal_id: string;
  scheduled_at: string;
  end_at: string;
  title: string;
}

// A3-2: TimeBar 전원 합의 완료 → 호스트가 "확정하기" 클릭해야 AI 파이프라인 발동.
// 백엔드가 이 노티 송출, 프론트는 host에게만 "일정 확정하기" 버튼 노출.
export interface ScheduleConsensusReadyPayload {
  type: "schedule_consensus_ready";
  room_id: number;
  snapshot_hash: string;
  host_user_id: number;
  member_count: number;
}

// 호스트가 "시간대 변경"을 누르면 전 멤버를 TimeBar 단계로 진입시키는 브로드캐스트.
export interface TimebarOpenPayload {
  type: "timebar_open";
  room_id: number;
  meeting_id: number;
  date: string; // YYYY-MM-DD
}

// G-1: 새 멤버 join 시 다른 멤버 화면 캘린더 X/N 자동 갱신 트리거.
export interface MemberJoinedPayload {
  type: "member_joined";
  room_id: number;
  user_id: number;
  user_name: string;
  member_count: number;
}

export interface FinalizationState {
  proposal_id: string;
  version: number;
  status: FinalizationStatus;
  proposed_slot: FinalizationSlot;
  alternate_slot: FinalizationSlot | null;
  reason: string;
  host_user_id: number;
  total_eligible_voters: number;
  votes: Record<string, VoteChoice>;
  my_vote: VoteChoice | null;
  deadline_at: number;
  created_at: number;
}

type WsStatus = "connecting" | "open" | "closed" | "error";

const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_RECONNECT_DELAY_MS = 30_000;

function isChatMessagePayload(data: unknown): data is ChatMessagePayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<ChatMessagePayload>;
  return (
    typeof candidate.id === "number" &&
    typeof candidate.pane_type === "string" &&
    typeof candidate.role === "string" &&
    typeof candidate.content === "string" &&
    typeof candidate.created_at === "string"
  );
}

function isFinalizationPendingPayload(data: unknown): data is FinalizationPendingPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<FinalizationPendingPayload>;
  return c.type === "finalization_pending" && typeof c.room_id === "number";
}

function isFinalizationProposalPayload(data: unknown): data is FinalizationProposalPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<FinalizationProposalPayload>;
  return (
    c.type === "finalization_proposal" &&
    typeof c.proposal_id === "string" &&
    typeof c.version === "number" &&
    typeof c.status === "string" &&
    !!c.proposed_slot
  );
}

function isFinalizationVoteUpdatePayload(
  data: unknown,
): data is FinalizationVoteUpdatePayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<FinalizationVoteUpdatePayload>;
  return (
    c.type === "finalization_vote_update" &&
    typeof c.proposal_id === "string" &&
    typeof c.version === "number"
  );
}

function isMeetingConfirmedPayload(data: unknown): data is MeetingConfirmedPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<MeetingConfirmedPayload>;
  return (
    c.type === "meeting_confirmed" &&
    typeof c.meeting_id === "number" &&
    typeof c.proposal_id === "string"
  );
}

function isScheduleConsensusReadyPayload(data: unknown): data is ScheduleConsensusReadyPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<ScheduleConsensusReadyPayload>;
  return (
    c.type === "schedule_consensus_ready" &&
    typeof c.room_id === "number" &&
    typeof c.snapshot_hash === "string" &&
    typeof c.host_user_id === "number"
  );
}

function isTimebarOpenPayload(data: unknown): data is TimebarOpenPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<TimebarOpenPayload>;
  return (
    c.type === "timebar_open" &&
    typeof c.room_id === "number" &&
    typeof c.meeting_id === "number" &&
    typeof c.date === "string"
  );
}

function isMemberJoinedPayload(data: unknown): data is MemberJoinedPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<MemberJoinedPayload>;
  return (
    c.type === "member_joined" &&
    typeof c.room_id === "number" &&
    typeof c.user_id === "number" &&
    typeof c.member_count === "number"
  );
}

function isReminderPayload(data: unknown): data is ReminderPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<ReminderPayload>;
  return (
    candidate.type === "reminder" &&
    typeof candidate.message === "string" &&
    typeof candidate.meeting_id === "number"
  );
}

function isPeerDateSelectionPayload(data: unknown): data is PeerDateSelectionPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<PeerDateSelectionPayload>;
  return (
    candidate.type === "peer_date_selection" &&
    (candidate.date === null || typeof candidate.date === "string")
  );
}

function isPeerTimeSelectionPayload(data: unknown): data is PeerTimeSelectionPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<PeerTimeSelectionPayload>;
  return (
    c.type === "peer_time_selection" &&
    (c.date === null || typeof c.date === "string") &&
    (c.start === null || typeof c.start === "number") &&
    (c.end === null || typeof c.end === "number")
  );
}

function isPeerUnavailableUpdatePayload(data: unknown): data is PeerUnavailableUpdatePayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<PeerUnavailableUpdatePayload>;
  return c.type === "peer_unavailable_update" && Array.isArray(c.dates);
}

function isUnavailableSnapshotPayload(data: unknown): data is UnavailableSnapshotPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<UnavailableSnapshotPayload>;
  return c.type === "unavailable_snapshot" && c.by_user != null && typeof c.by_user === "object";
}

function isAvailabilitySnapshotPayload(data: unknown): data is AvailabilitySnapshotPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<AvailabilitySnapshotPayload>;
  return c.type === "availability_snapshot" && c.by_user != null && typeof c.by_user === "object";
}

function isDateSelectionSnapshotPayload(data: unknown): data is DateSelectionSnapshotPayload {
  if (!data || typeof data !== "object") return false;
  const c = data as Partial<DateSelectionSnapshotPayload>;
  return c.type === "date_selection_snapshot" && c.by_user != null && typeof c.by_user === "object";
}

function isVoteReminderPayload(data: unknown): data is VoteReminderPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<VoteReminderPayload>;
  return (
    candidate.type === "vote_reminder" &&
    typeof candidate.message === "string" &&
    typeof candidate.meeting_id === "number"
  );
}

function getReconnectDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS);
}

export function useSocialWebSocket(roomId: string, sender: string) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [peerSelections, setPeerSelections] = useState<Record<string, PeerSelection>>({});
  const [peerTimeSelections, setPeerTimeSelections] = useState<Record<string, PeerTimeSelection>>({});
  // user_id → 해당 유저가 표시한 불가능 날짜 배열. 내 것과 남 것을 한 dict에 담음.
  const [unavailabilityByUser, setUnavailabilityByUser] = useState<Record<number, string[]>>({});
  // 본인의 TimeBar 선택 — 리프레시 시 Redis 스냅샷에서 복구되어 TimeBarSelector가 초기값으로 씀.
  const [myTimeSelection, setMyTimeSelection] = useState<
    { date: string; start: number; end: number } | null
  >(null);
  // 본인의 날짜 선택 — 리프레시 시 Redis 스냅샷에서 복구.
  const [myDateSelection, setMyDateSelection] = useState<string | null>(null);
  const [finalizationProposal, setFinalizationProposal] = useState<FinalizationState | null>(null);
  const [finalizationPending, setFinalizationPending] = useState<boolean>(false);
  const [lastConfirmedMeeting, setLastConfirmedMeeting] = useState<MeetingConfirmedPayload | null>(null);
  // A3-2: TimeBar 합의 완료 시 host에게만 "확정하기" 버튼 노출용
  const [scheduleConsensus, setScheduleConsensus] = useState<ScheduleConsensusReadyPayload | null>(null);
  // G-1: 새 멤버 join 시 캘린더 X/N 자동 갱신 트리거
  const [lastMemberJoined, setLastMemberJoined] = useState<MemberJoinedPayload | null>(null);
  const [lastTimebarOpen, setLastTimebarOpen] = useState<TimebarOpenPayload | null>(null);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      window.location.href = "/";
      return;
    }

    // JWT sub에서 내 user_id 추출 (echo 필터용)
    let myUserId: number | null = null;
    try {
      const payloadPart = token.split(".")[1];
      if (payloadPart) {
        const normalized = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
        const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
        const decoded = JSON.parse(atob(padded));
        if (decoded?.sub) {
          const asNum = Number(decoded.sub);
          if (Number.isFinite(asNum)) myUserId = asNum;
        }
      }
    } catch {
      /* token 파싱 실패는 무시 — echo 필터만 못함 */
    }

    let isActive = true;

    setMessages([]);

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    const roomPk = /^\d+$/.test(roomId) ? roomId : null;

    if (roomPk) {
      fetch(`${apiBase}/api/v1/chat/messages?pane_type=social&room_id=${roomPk}&limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Failed to load social messages: ${response.status}`);
          }
          return response.json();
        })
        .then((data: unknown) => {
          if (!isActive || !Array.isArray(data)) {
            return;
          }
          const nextMessages = data.filter(isChatMessagePayload);
          setMessages(nextMessages);
        })
        .catch(() => {
          if (!isActive) {
            return;
          }
          setMessages([]);
        });

      // Restore any active finalization proposal so page reloads / late joiners
      // see the card even if the original WS broadcast already fired.
      fetch(`${apiBase}/api/v1/finalization/room/${roomPk}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(async (response) => {
          if (!response.ok) return null;
          return response.json();
        })
        .then((data: unknown) => {
          if (!isActive || data == null || typeof data !== "object") return;
          const p = data as Partial<{
            proposal_id: string;
            version: number;
            status: FinalizationStatus;
            proposed_slot: FinalizationSlot;
            alternate_slot: FinalizationSlot | null;
            reason: string;
            host_user_id: number;
            total_eligible_voters: number;
            votes: Record<string, VoteChoice>;
            my_vote: VoteChoice | null;
            deadline_at: number;
            created_at: number;
          }>;
          if (!p.proposal_id || !p.proposed_slot) return;
          setFinalizationProposal({
            proposal_id: p.proposal_id,
            version: p.version ?? 0,
            status: (p.status ?? "active") as FinalizationStatus,
            proposed_slot: p.proposed_slot,
            alternate_slot: p.alternate_slot ?? null,
            reason: p.reason ?? "",
            host_user_id: p.host_user_id ?? 0,
            total_eligible_voters: p.total_eligible_voters ?? 0,
            votes: p.votes ?? {},
            my_vote: p.my_vote ?? null,
            deadline_at: p.deadline_at ?? 0,
            created_at: p.created_at ?? 0,
          });
        })
        .catch(() => {
          /* non-fatal — WS will eventually deliver */
        });
    }

    const clearReconnectTimeout = () => {
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    const cleanupSocket = (socket: WebSocket) => {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
    };

    const scheduleReconnect = (socket: WebSocket, code?: number) => {
      if (!isActive || !shouldReconnectRef.current || wsRef.current !== socket) {
        return;
      }
      if (code === 4001 || code === 1008) {
        return;
      }
      if (reconnectTimeoutRef.current !== null) {
        return;
      }
      if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        return;
      }

      const delay = getReconnectDelay(reconnectAttemptsRef.current);
      reconnectAttemptsRef.current += 1;
      reconnectTimeoutRef.current = window.setTimeout(() => {
        reconnectTimeoutRef.current = null;
        connect();
      }, delay);
    };

    const connect = () => {
      if (!isActive) {
        return;
      }

      clearReconnectTimeout();
      setStatus("connecting");

      const socket = new WebSocket(`${wsBase}/ws/social/${roomId}?token=${encodeURIComponent(token)}`);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!isActive || wsRef.current !== socket) {
          socket.close();
          return;
        }

        clearReconnectTimeout();
        reconnectAttemptsRef.current = 0;
        setStatus("open");
      };

      socket.onmessage = (event) => {
        if (!isActive || wsRef.current !== socket) {
          return;
        }

        let data: unknown;
        try {
          data = JSON.parse(event.data as string);
        } catch {
          return;
        }

        if (isFinalizationPendingPayload(data)) {
          setFinalizationPending(true);
          return;
        }

        if (isFinalizationProposalPayload(data)) {
          setFinalizationPending(false);
          setFinalizationProposal((prev) => {
            // Drop out-of-order frames (older version than currently-held one)
            if (prev && prev.proposal_id === data.proposal_id && prev.version > data.version) {
              return prev;
            }
            const myKey = myUserId != null ? String(myUserId) : null;
            return {
              proposal_id: data.proposal_id,
              version: data.version,
              status: data.status,
              proposed_slot: data.proposed_slot,
              alternate_slot: data.alternate_slot ?? null,
              reason: data.reason,
              host_user_id: data.host_user_id,
              total_eligible_voters: data.total_eligible_voters,
              votes: data.votes ?? {},
              my_vote: myKey ? ((data.votes ?? {})[myKey] ?? null) : null,
              deadline_at: data.deadline_at,
              created_at: data.created_at,
            };
          });
          return;
        }

        if (isFinalizationVoteUpdatePayload(data)) {
          setFinalizationProposal((prev) => {
            if (prev && prev.proposal_id === data.proposal_id && prev.version > data.version) {
              return prev;
            }
            const myKey = myUserId != null ? String(myUserId) : null;
            return {
              proposal_id: data.proposal_id,
              version: data.version,
              status: data.status,
              proposed_slot: data.proposed_slot,
              alternate_slot: data.alternate_slot ?? null,
              reason: data.reason,
              host_user_id: data.host_user_id,
              total_eligible_voters: data.total_eligible_voters,
              votes: data.votes ?? {},
              my_vote: myKey ? ((data.votes ?? {})[myKey] ?? null) : null,
              deadline_at: prev?.deadline_at ?? 0,
              created_at: prev?.created_at ?? 0,
            };
          });
          return;
        }

        if (isScheduleConsensusReadyPayload(data)) {
          setScheduleConsensus(data);
          return;
        }

        if (isTimebarOpenPayload(data)) {
          // 호스트가 "시간대 변경" → 전 멤버를 TimeBar 단계로 진입. 매번 새 객체로
          // 세팅돼야 동일 meeting 재요청도 effect를 다시 트리거함.
          setLastTimebarOpen({ ...data });
          return;
        }

        if (isMemberJoinedPayload(data)) {
          setLastMemberJoined(data);
          return;
        }

        if (isMeetingConfirmedPayload(data)) {
          setLastConfirmedMeeting(data);
          // A3-2: 확정되면 schedule_consensus 상태 해제
          setScheduleConsensus(null);
          setFinalizationProposal((prev) => {
            if (prev && prev.proposal_id === data.proposal_id) {
              return { ...prev, status: "confirmed" };
            }
            return prev;
          });
          return;
        }

        if (isPeerTimeSelectionPayload(data)) {
          // self-echo 무시
          if (myUserId !== null && data.user_id === myUserId) return;
          if (data.user_id == null && data.sender && data.sender === sender) return;
          const peerKey = data.user_id != null ? `u${data.user_id}` : `n:${data.sender ?? ""}`;
          setPeerTimeSelections((prev) => {
            const next = { ...prev };
            // 범위가 null이거나 date null이면 해제
            if (data.date === null || data.start === null || data.end === null) {
              delete next[peerKey];
            } else {
              next[peerKey] = {
                userId: data.user_id,
                name: data.sender ?? "익명",
                date: data.date,
                start: data.start,
                end: data.end,
              };
            }
            return next;
          });
          return;
        }

        if (isAvailabilitySnapshotPayload(data)) {
          // 접속 시 서버가 1회 푸시. self 것은 myTimeSelection, others는 peerTimeSelections.
          const nextPeers: Record<string, PeerTimeSelection> = {};
          let mine: { date: string; start: number; end: number } | null = null;
          for (const [uidStr, sel] of Object.entries(data.by_user)) {
            const uid = Number(uidStr);
            if (!Number.isFinite(uid) || !sel || typeof sel !== "object") continue;
            const date = typeof sel.date === "string" ? sel.date : null;
            const start = typeof sel.start === "number" ? sel.start : null;
            const end = typeof sel.end === "number" ? sel.end : null;
            if (!date || start === null || end === null) continue;
            if (myUserId !== null && uid === myUserId) {
              mine = { date, start, end };
            } else {
              nextPeers[`u${uid}`] = {
                userId: uid, name: "익명", date, start, end,
              };
            }
          }
          setPeerTimeSelections((prev) => ({ ...nextPeers, ...prev }));
          if (mine) setMyTimeSelection(mine);
          return;
        }

        if (isDateSelectionSnapshotPayload(data)) {
          // 접속 시 서버가 1회 푸시. self는 myDateSelection, others는 peerSelections.
          const nextPeers: Record<string, PeerSelection> = {};
          let mine: string | null = null;
          for (const [uidStr, date] of Object.entries(data.by_user)) {
            const uid = Number(uidStr);
            if (!Number.isFinite(uid) || typeof date !== "string") continue;
            if (myUserId !== null && uid === myUserId) {
              mine = date;
            } else {
              nextPeers[`u${uid}`] = { userId: uid, name: "익명", date };
            }
          }
          setPeerSelections((prev) => ({ ...nextPeers, ...prev }));
          setMyDateSelection(mine);
          return;
        }

        if (isUnavailableSnapshotPayload(data)) {
          // 접속 직후 서버가 직접 푸시하는 현재 상태. 덮어쓰기.
          const next: Record<number, string[]> = {};
          for (const [uidStr, dates] of Object.entries(data.by_user)) {
            const uid = Number(uidStr);
            if (!Number.isFinite(uid) || !Array.isArray(dates)) continue;
            next[uid] = dates.filter((d) => typeof d === "string");
          }
          setUnavailabilityByUser(next);
          return;
        }

        if (isPeerUnavailableUpdatePayload(data)) {
          if (data.user_id == null) return;
          const uid = data.user_id;
          setUnavailabilityByUser((prev) => {
            const next = { ...prev };
            if (data.dates.length === 0) {
              delete next[uid];
            } else {
              next[uid] = data.dates;
            }
            return next;
          });
          return;
        }

        if (isPeerDateSelectionPayload(data)) {
          // 자기 자신 이벤트는 무시 (user_id 기준 — 동명이인에 안전).
          // user_id가 누락된 이벤트(예: 구버전 서버)는 sender 이름으로 fallback.
          if (myUserId !== null && data.user_id === myUserId) return;
          if (data.user_id == null && data.sender && data.sender === sender) return;
          const peerKey = data.user_id != null ? `u${data.user_id}` : `n:${data.sender ?? ""}`;
          setPeerSelections((prev) => {
            const next = { ...prev };
            if (data.date === null) {
              delete next[peerKey];
            } else {
              next[peerKey] = {
                userId: data.user_id,
                name: data.sender ?? "익명",
                date: data.date,
              };
            }
            return next;
          });
          return;
        }

        if (isReminderPayload(data) || isVoteReminderPayload(data)) {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now(),
              pane_type: "social",
              role: "system",
              content: data.message,
              sender: "매듭이",
              created_at: new Date().toISOString(),
            },
          ]);
          return;
        }

        if (!isChatMessagePayload(data)) {
          return;
        }

        setMessages((prev) => {
          if (prev.some((message) => message.id === data.id)) {
            return prev;
          }
          return [...prev, data];
        });
      };

      socket.onerror = () => {
        if (!isActive || wsRef.current !== socket) {
          return;
        }

        setStatus("error");
      };

      socket.onclose = (event) => {
        if (wsRef.current === socket) {
          wsRef.current = null;
        }

        cleanupSocket(socket);

        if (!isActive) {
          return;
        }

        setStatus("closed");
        if (event.code === 1008) {
          shouldReconnectRef.current = false;
          localStorage.removeItem("auth_token");
          window.location.href = "/";
          return;
        }

        scheduleReconnect(socket, event.code);
      };
    };

    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;
    clearReconnectTimeout();
    connect();

    return () => {
      isActive = false;
      shouldReconnectRef.current = false;
      clearReconnectTimeout();

      const socket = wsRef.current;
      if (socket) {
        wsRef.current = null;
        cleanupSocket(socket);
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close();
        }
      }
    };
  }, [roomId]);

  const sendMessage = useCallback(
    (content: string) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ role: "user", content, sender }));
      }
    },
    [sender],
  );

  const sendDateSelection = useCallback(
    (date: string | null) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "date_selection", date, sender }));
      }
    },
    [sender],
  );

  const sendTimeSelection = useCallback(
    (date: string | null, start: number | null, end: number | null) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "time_selection", date, start, end, sender }));
      }
    },
    [sender],
  );

  const sendUnavailableToggle = useCallback(
    (date: string, unavailable: boolean) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "unavailable_toggle", date, unavailable }));
      }
    },
    [],
  );

  const clearFinalizationProposal = useCallback(() => {
    setFinalizationProposal(null);
    setFinalizationPending(false);
  }, []);

  return {
    messages,
    sendMessage,
    sendDateSelection,
    sendTimeSelection,
    sendUnavailableToggle,
    unavailabilityByUser,
    myTimeSelection,
    myDateSelection,
    status,
    peerSelections,
    peerTimeSelections,
    finalizationProposal,
    finalizationPending,
    lastConfirmedMeeting,
    clearFinalizationProposal,
    scheduleConsensus,
    clearScheduleConsensus: () => setScheduleConsensus(null),
    lastMemberJoined,
    lastTimebarOpen,
  };
}

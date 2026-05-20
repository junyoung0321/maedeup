"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { AiTriggerIntent, ContextMode, PlaceResult } from "@/types";
import type { VoteCardPayload, VoteUpdatePayload, PlaceRecommendationPayload, VoteCardTimeOption } from "@/hooks/useAgentWebSocket";
import type {
  FinalizationState,
  MeetingConfirmedPayload,
  PeerSelection,
  PeerTimeSelection,
  ScheduleConsensusReadyPayload,
} from "@/hooks/useSocialWebSocket";

// ┌─────────────────┐    setVoteCard/etc     ┌──────────────┐
// │ AiAssistantPane │ ─────────────────────→ │ MeetingContext│
// │ (WS receiver)   │    setSendMessageToAi  │              │
// │                 │ ─────────────────────→ │ coordination │
// └─────────────────┘                        │    state     │
//                                            └──────┬───────┘
//                          ┌─────────────────────────┤
//                          ↓                         ↓
//                   ┌──────────────┐        ┌────────────────┐
//                   │ CalendarPane │        │ InfoPane       │
//                   │ (highlight)  │        │ (phase-based)  │
//                   │ (DateCard)   │        │ TimeBar/Place  │
//                   └──────────────┘        └────────────────┘

export type InfoPanePhase =
  | "idle"
  | "dateSelected"
  | "dateConfirmed"
  | "timeConfirmed"
  | "placeConfirmed"
  | "done";

interface MeetingState {
  roomId: string;
  roomName: string;
  contextMode: ContextMode;
  selectedPlace: PlaceResult | null;
  aiTriggerIntent: AiTriggerIntent | null;
  calendarRefreshTrigger: number;
  // F-2: 선호도 팝업 제출 시 InfoPane room preferences re-fetch 신호.
  preferenceRefreshTrigger: number;
  // Coordination state for calendar-AI bidirectional sync
  voteCard: VoteCardPayload | null;
  voteUpdate: VoteUpdatePayload | null;
  placeRecommendation: PlaceRecommendationPayload | null;
  voteAwaitingTimeMeetingId: number | null;
  candidateSlots: VoteCardTimeOption[];
  highlightedDates: string[]; // "YYYY-MM-DD"
  // InfoPane phase state machine
  infoPanePhase: InfoPanePhase;
  confirmedDate: string | null; // "YYYY-MM-DD"
  confirmedTimeRange: { startAt: string; endAt: string } | null;
  confirmedMeetingId: number | null;
  // 실시간으로 다른 참여자들이 캘린더에서 선택한 날짜 공유용
  peerDateSelections: Record<string, PeerSelection>;
  // 실시간으로 다른 참여자들이 TimeBar에서 선택한 시간 범위 공유용
  peerTimeSelections: Record<string, PeerTimeSelection>;
  // 유저별 불가능 날짜 배열 (내 것 + 남 것. user_id를 키로 사용)
  unavailabilityByUser: Record<number, string[]>;
  // 본인 TimeBar 선택 — 리프레시 복구용. 서버 스냅샷에서 초기화됨.
  myTimeSelection: { date: string; start: number; end: number } | null;
  // 본인 날짜 선택 — 리프레시 복구용 (peer에겐 peerDateSelections로 따로 전송됨).
  myDateSelection: string | null;
  // AI 제안 카드 상태 (과반 도달 시 백엔드가 푸시)
  finalizationProposal: FinalizationState | null;
  // AI reason 생성 대기 중이면 shimmer 카드 렌더
  finalizationPending: boolean;
  // 최근 meeting_confirmed 이벤트 (성공 배너용)
  lastConfirmedMeeting: MeetingConfirmedPayload | null;
  // 직전 confirm/place/cancel 후 본인 구글 캘린더에 이벤트가 들어가 있는지.
  // null = 아직 확정 액션이 일어나지 않음. true/false = 마지막 응답 기준.
  calendarEventForSelf: boolean | null;
  // 직전 액션 후 캘린더 이벤트를 가진 멤버 수.
  calendarMemberCount: number;
  // A3-2: TimeBar 합의 완료 노티 (호스트만 "확정하기" 버튼 노출용)
  scheduleConsensus: ScheduleConsensusReadyPayload | null;
  // F-9: 장소 확정 시 PlaceDetailPane "이 장소로 확정" 버튼 비활성화용.
  confirmedPlaceId: string | null;
  // F-7: TimeBarSelector가 계산한 AI 추천 범위 — MiniTimeBar 등 다른 위치 SoT 단일화.
  aiRecommendedTimeRange: { date: string; start: number; end: number } | null;
}

interface MeetingContextValue extends MeetingState {
  setContextMode: (mode: ContextMode) => void;
  setSelectedPlace: (place: PlaceResult | null) => void;
  setRoom: (id: string, name: string) => void;
  setAiTriggerIntent: (intent: AiTriggerIntent | null) => void;
  refreshCalendar: () => void;
  refreshPreferences: () => void;
  // Coordination actions
  setVoteCard: (card: VoteCardPayload | null) => void;
  setVoteUpdate: (update: VoteUpdatePayload | null) => void;
  setPlaceRecommendation: (rec: PlaceRecommendationPayload | null, meetingId?: number | null) => void;
  requestTimeChange: (slot: VoteCardTimeOption, meetingId: number) => void;
  resetCoordination: () => void;
  // InfoPane phase actions
  setInfoPanePhase: (phase: InfoPanePhase) => void;
  confirmDate: (date: string) => void;
  confirmTime: (startAt: string, endAt: string, meetingId: number) => void;
  confirmPlace: () => void;
  // sendMessage bridge: AiAssistantPane registers, CalendarPane uses
  sendMessageToAi: ((msg: string) => void) | null;
  setSendMessageToAi: (fn: ((msg: string) => void) | null) => void;
  // 날짜 선택 공유 bridge: ChatPane의 social WS와 CalendarPane을 연결
  setPeerDateSelections: (selections: Record<string, PeerSelection>) => void;
  sendDateSelection: ((date: string | null) => void) | null;
  setSendDateSelection: (fn: ((date: string | null) => void) | null) => void;
  // 시간 선택 공유 bridge: ChatPane WS와 TimeBarSelector를 연결
  setPeerTimeSelections: (selections: Record<string, PeerTimeSelection>) => void;
  sendTimeSelection: ((date: string | null, start: number | null, end: number | null, confirmed?: boolean) => void) | null;
  setSendTimeSelection: (fn: ((date: string | null, start: number | null, end: number | null, confirmed?: boolean) => void) | null) => void;
  // 불가능 날짜 공유 bridge: ChatPane WS ↔ CalendarPane
  setUnavailabilityByUser: (by: Record<number, string[]>) => void;
  sendUnavailableToggle: ((date: string, unavailable: boolean) => void) | null;
  setSendUnavailableToggle: (fn: ((date: string, unavailable: boolean) => void) | null) => void;
  // 본인 TimeBar 선택 복구 bridge
  setMyTimeSelection: (sel: { date: string; start: number; end: number } | null) => void;
  // 본인 날짜 선택 복구 bridge
  setMyDateSelection: (date: string | null) => void;
  // Finalization bridge — ChatPane(social WS)이 여기로 push, InfoPane/Card가 소비
  setFinalizationProposal: (proposal: FinalizationState | null) => void;
  setFinalizationPending: (pending: boolean) => void;
  setLastConfirmedMeeting: (payload: MeetingConfirmedPayload | null) => void;
  setCalendarSyncStatus: (forSelf: boolean | null, memberCount: number) => void;
  setScheduleConsensus: (payload: ScheduleConsensusReadyPayload | null) => void;
  setConfirmedPlaceId: (id: string | null) => void;
  setAiRecommendedTimeRange: (range: { date: string; start: number; end: number } | null) => void;
}

export const MeetingContext = createContext<MeetingContextValue | null>(null);

export function MeetingProvider({
  children,
  initialRoomId = "",
  initialRoomName = "",
}: {
  children: ReactNode;
  initialRoomId?: string;
  initialRoomName?: string;
}) {
  const [state, setState] = useState<MeetingState>({
    roomId: initialRoomId,
    roomName: initialRoomName,
    contextMode: "schedule",
    selectedPlace: null,
    aiTriggerIntent: null,
    calendarRefreshTrigger: 0,
    preferenceRefreshTrigger: 0,
    voteCard: null,
    voteUpdate: null,
    placeRecommendation: null,
    voteAwaitingTimeMeetingId: null,
    candidateSlots: [],
    highlightedDates: [],
    infoPanePhase: "idle",
    confirmedDate: null,
    confirmedTimeRange: null,
    confirmedMeetingId: null,
    peerDateSelections: {},
    peerTimeSelections: {},
    unavailabilityByUser: {},
    myTimeSelection: null,
    myDateSelection: null,
    finalizationProposal: null,
    finalizationPending: false,
    lastConfirmedMeeting: null,
    calendarEventForSelf: null,
    calendarMemberCount: 0,
    scheduleConsensus: null,
    confirmedPlaceId: null,
    aiRecommendedTimeRange: null,
  });

  const [sendMessageToAi, setSendMessageToAiRaw] = useState<((msg: string) => void) | null>(null);
  const setSendMessageToAi = useCallback((fn: ((msg: string) => void) | null) => {
    setSendMessageToAiRaw(() => fn);
  }, []);

  const [sendDateSelection, setSendDateSelectionRaw] = useState<((date: string | null) => void) | null>(null);
  const setSendDateSelection = useCallback((fn: ((date: string | null) => void) | null) => {
    setSendDateSelectionRaw(() => fn);
  }, []);

  const setPeerDateSelections = useCallback((selections: Record<string, PeerSelection>) => {
    setState((prev) => ({ ...prev, peerDateSelections: selections }));
  }, []);

  const [sendTimeSelection, setSendTimeSelectionRaw] =
    useState<((date: string | null, start: number | null, end: number | null) => void) | null>(null);
  const setSendTimeSelection = useCallback(
    (fn: ((date: string | null, start: number | null, end: number | null) => void) | null) => {
      setSendTimeSelectionRaw(() => fn);
    },
    [],
  );

  const setPeerTimeSelections = useCallback((selections: Record<string, PeerTimeSelection>) => {
    setState((prev) => ({ ...prev, peerTimeSelections: selections }));
  }, []);

  const [sendUnavailableToggle, setSendUnavailableToggleRaw] =
    useState<((date: string, unavailable: boolean) => void) | null>(null);
  const setSendUnavailableToggle = useCallback(
    (fn: ((date: string, unavailable: boolean) => void) | null) => {
      setSendUnavailableToggleRaw(() => fn);
    },
    [],
  );

  const setUnavailabilityByUser = useCallback((by: Record<number, string[]>) => {
    setState((prev) => ({ ...prev, unavailabilityByUser: by }));
  }, []);

  const setMyTimeSelection = useCallback(
    (sel: { date: string; start: number; end: number } | null) => {
      setState((prev) => ({ ...prev, myTimeSelection: sel }));
    },
    [],
  );

  const setMyDateSelection = useCallback((date: string | null) => {
    setState((prev) => ({ ...prev, myDateSelection: date }));
  }, []);

  const setFinalizationProposal = useCallback((proposal: FinalizationState | null) => {
    setState((prev) => ({ ...prev, finalizationProposal: proposal }));
  }, []);

  const setFinalizationPending = useCallback((pending: boolean) => {
    setState((prev) => ({ ...prev, finalizationPending: pending }));
  }, []);

  const setLastConfirmedMeeting = useCallback(
    (payload: MeetingConfirmedPayload | null) => {
      setState((prev) => ({ ...prev, lastConfirmedMeeting: payload }));
    },
    [],
  );

  const setCalendarSyncStatus = useCallback(
    (forSelf: boolean | null, memberCount: number) => {
      setState((prev) => ({
        ...prev,
        calendarEventForSelf: forSelf,
        calendarMemberCount: memberCount,
      }));
    },
    [],
  );

  const setScheduleConsensus = useCallback(
    (payload: ScheduleConsensusReadyPayload | null) => {
      setState((prev) => ({ ...prev, scheduleConsensus: payload }));
    },
    [],
  );

  const setConfirmedPlaceId = useCallback((id: string | null) => {
    setState((prev) => ({ ...prev, confirmedPlaceId: id }));
  }, []);

  const setAiRecommendedTimeRange = useCallback(
    (range: { date: string; start: number; end: number } | null) => {
      setState((prev) => {
        // Skip if same value (avoid unnecessary re-render loops in publisher)
        const cur = prev.aiRecommendedTimeRange;
        if (
          (cur === null && range === null) ||
          (cur && range && cur.date === range.date && cur.start === range.start && cur.end === range.end)
        ) {
          return prev;
        }
        return { ...prev, aiRecommendedTimeRange: range };
      });
    },
    [],
  );

  const setContextMode = useCallback((mode: ContextMode) => {
    setState((prev) => (prev.contextMode === mode ? prev : { ...prev, contextMode: mode }));
  }, []);

  const setSelectedPlace = useCallback((place: PlaceResult | null) => {
    setState((prev) => (prev.selectedPlace === place ? prev : { ...prev, selectedPlace: place }));
  }, []);

  const setRoom = useCallback((id: string, name: string) => {
    setState((prev) => (
      prev.roomId === id && prev.roomName === name
        ? prev
        : { ...prev, roomId: id, roomName: name }
    ));
  }, []);

  const setAiTriggerIntent = useCallback((intent: AiTriggerIntent | null) => {
    setState((prev) => {
      const nextContextMode = intent ? "agent" : prev.contextMode;
      if (prev.aiTriggerIntent === intent && prev.contextMode === nextContextMode) {
        return prev;
      }

      return {
        ...prev,
        aiTriggerIntent: intent,
        contextMode: nextContextMode,
      };
    });
  }, []);

  const refreshCalendar = useCallback(() => {
    setState((prev) => ({
      ...prev,
      calendarRefreshTrigger: prev.calendarRefreshTrigger + 1,
    }));
  }, []);

  const refreshPreferences = useCallback(() => {
    setState((prev) => ({
      ...prev,
      preferenceRefreshTrigger: prev.preferenceRefreshTrigger + 1,
    }));
  }, []);

  const setVoteCard = useCallback((card: VoteCardPayload | null) => {
    setState((prev) => {
      if (!card) return { ...prev, voteCard: null, voteAwaitingTimeMeetingId: null };
      const slots = card.time_options;
      const dateSet = new Set(slots.map((s) => s.start_at.split("T")[0]));
      const dates = Array.from(dateSet);
      const shouldResetAwaiting =
        card.meeting_id !== prev.voteAwaitingTimeMeetingId;
      // Don't reset phase if already past time confirmation (prevents
      // pipeline re-triggering from resetting the flow)
      const phaseAlreadyAdvanced =
        prev.infoPanePhase === "timeConfirmed" ||
        prev.infoPanePhase === "placeConfirmed" ||
        prev.infoPanePhase === "done";
      return {
        ...prev,
        voteCard: card,
        voteAwaitingTimeMeetingId: shouldResetAwaiting ? null : prev.voteAwaitingTimeMeetingId,
        candidateSlots: slots,
        highlightedDates: dates,
        ...(phaseAlreadyAdvanced ? {} : {
          infoPanePhase: "idle" as InfoPanePhase,
          confirmedDate: null,
          confirmedTimeRange: null,
        }),
        confirmedMeetingId: card.meeting_id ?? prev.confirmedMeetingId ?? null,
        calendarRefreshTrigger: prev.calendarRefreshTrigger + 1,
      };
    });
  }, []);

  const setVoteUpdate = useCallback((update: VoteUpdatePayload | null) => {
    setState((prev) => ({ ...prev, voteUpdate: update }));
  }, []);

  const setPlaceRecommendation = useCallback((rec: PlaceRecommendationPayload | null, meetingId?: number | null) => {
    setState((prev) => {
      const meetingIdUpdate =
        meetingId != null && prev.confirmedMeetingId == null
          ? { confirmedMeetingId: meetingId }
          : {};
      return { ...prev, placeRecommendation: rec, ...meetingIdUpdate };
    });
  }, []);

  const requestTimeChange = useCallback((slot: VoteCardTimeOption, meetingId: number) => {
    const selectedDate = slot.start_at.split("T")[0] || null;
    setState((prev) => ({
      ...prev,
      myDateSelection: selectedDate,
      infoPanePhase: "dateConfirmed" as InfoPanePhase,
      confirmedDate: selectedDate,
      confirmedTimeRange: null,
      voteAwaitingTimeMeetingId: meetingId,
    }));
  }, []);

  // InfoPane phase actions
  const setInfoPanePhase = useCallback((phase: InfoPanePhase) => {
    setState((prev) => {
      if (prev.infoPanePhase === phase) return prev;
      const updates: Partial<MeetingState> = { infoPanePhase: phase };
      // Backward transitions clear dependent state
      if (phase === "idle") {
        updates.confirmedDate = null;
        updates.confirmedTimeRange = null;
        updates.voteAwaitingTimeMeetingId = null;
      } else if (phase === "dateSelected") {
        updates.confirmedDate = null;
        updates.confirmedTimeRange = null;
        updates.voteAwaitingTimeMeetingId = null;
      } else if (phase === "dateConfirmed") {
        updates.confirmedTimeRange = null;
      }
      return { ...prev, ...updates };
    });
  }, []);

  const confirmDate = useCallback((date: string) => {
    setState((prev) => ({
      ...prev,
      infoPanePhase: "dateConfirmed" as InfoPanePhase,
      confirmedDate: date,
      confirmedTimeRange: null,
    }));
  }, []);

  const confirmTime = useCallback((startAt: string, endAt: string, meetingId: number) => {
    setState((prev) => ({
      ...prev,
      infoPanePhase: "timeConfirmed" as InfoPanePhase,
      confirmedTimeRange: { startAt, endAt },
      confirmedMeetingId: meetingId,
      voteAwaitingTimeMeetingId: null,
    }));
  }, []);

  const confirmPlace = useCallback(() => {
    setState((prev) => ({
      ...prev,
      infoPanePhase: "placeConfirmed" as InfoPanePhase,
    }));
  }, []);

  const resetCoordination = useCallback(() => {
    setState((prev) => ({
      ...prev,
      voteCard: null,
      voteUpdate: null,
      placeRecommendation: null,
      candidateSlots: [],
      highlightedDates: [],
      infoPanePhase: "idle" as InfoPanePhase,
      confirmedDate: null,
      confirmedTimeRange: null,
      confirmedMeetingId: null,
      voteAwaitingTimeMeetingId: null,
    }));
  }, []);

  const value = useMemo(
    () => ({
      roomId: state.roomId,
      roomName: state.roomName,
      contextMode: state.contextMode,
      selectedPlace: state.selectedPlace,
      aiTriggerIntent: state.aiTriggerIntent,
      calendarRefreshTrigger: state.calendarRefreshTrigger,
      preferenceRefreshTrigger: state.preferenceRefreshTrigger,
      voteCard: state.voteCard,
      voteUpdate: state.voteUpdate,
      placeRecommendation: state.placeRecommendation,
      voteAwaitingTimeMeetingId: state.voteAwaitingTimeMeetingId,
      candidateSlots: state.candidateSlots,
      highlightedDates: state.highlightedDates,
      infoPanePhase: state.infoPanePhase,
      confirmedDate: state.confirmedDate,
      confirmedTimeRange: state.confirmedTimeRange,
      confirmedMeetingId: state.confirmedMeetingId,
      peerDateSelections: state.peerDateSelections,
      setPeerDateSelections,
      sendDateSelection,
      setSendDateSelection,
      peerTimeSelections: state.peerTimeSelections,
      setPeerTimeSelections,
      sendTimeSelection,
      setSendTimeSelection,
      unavailabilityByUser: state.unavailabilityByUser,
      setUnavailabilityByUser,
      sendUnavailableToggle,
      setSendUnavailableToggle,
      myTimeSelection: state.myTimeSelection,
      setMyTimeSelection,
      myDateSelection: state.myDateSelection,
      setMyDateSelection,
      finalizationProposal: state.finalizationProposal,
      finalizationPending: state.finalizationPending,
      lastConfirmedMeeting: state.lastConfirmedMeeting,
      calendarEventForSelf: state.calendarEventForSelf,
      calendarMemberCount: state.calendarMemberCount,
      scheduleConsensus: state.scheduleConsensus,
      confirmedPlaceId: state.confirmedPlaceId,
      aiRecommendedTimeRange: state.aiRecommendedTimeRange,
      setFinalizationProposal,
      setFinalizationPending,
      setLastConfirmedMeeting,
      setCalendarSyncStatus,
      setScheduleConsensus,
      setConfirmedPlaceId,
      setAiRecommendedTimeRange,
      setContextMode,
      setSelectedPlace,
      setRoom,
      setAiTriggerIntent,
      refreshCalendar,
      refreshPreferences,
      setVoteCard,
      setVoteUpdate,
      setPlaceRecommendation,
      requestTimeChange,
      resetCoordination,
      setInfoPanePhase,
      confirmDate,
      confirmTime,
      confirmPlace,
      sendMessageToAi,
      setSendMessageToAi,
    }),
    [
      state.aiTriggerIntent,
      state.calendarRefreshTrigger,
      state.preferenceRefreshTrigger,
      state.contextMode,
      state.roomId,
      state.roomName,
      state.selectedPlace,
      state.voteCard,
      state.voteUpdate,
      state.placeRecommendation,
      state.voteAwaitingTimeMeetingId,
      state.candidateSlots,
      state.highlightedDates,
      state.infoPanePhase,
      state.confirmedDate,
      state.confirmedTimeRange,
      state.confirmedMeetingId,
      state.peerDateSelections,
      setPeerDateSelections,
      sendDateSelection,
      setSendDateSelection,
      state.peerTimeSelections,
      setPeerTimeSelections,
      sendTimeSelection,
      setSendTimeSelection,
      state.unavailabilityByUser,
      setUnavailabilityByUser,
      sendUnavailableToggle,
      setSendUnavailableToggle,
      state.myTimeSelection,
      setMyTimeSelection,
      state.myDateSelection,
      setMyDateSelection,
      state.finalizationProposal,
      state.finalizationPending,
      state.lastConfirmedMeeting,
      state.calendarEventForSelf,
      state.calendarMemberCount,
      state.scheduleConsensus,
      state.confirmedPlaceId,
      state.aiRecommendedTimeRange,
      setFinalizationProposal,
      setFinalizationPending,
      setLastConfirmedMeeting,
      setCalendarSyncStatus,
      setScheduleConsensus,
      setConfirmedPlaceId,
      setAiRecommendedTimeRange,
      setAiTriggerIntent,
      setContextMode,
      refreshCalendar,
      refreshPreferences,
      setRoom,
      setSelectedPlace,
      setVoteCard,
      setVoteUpdate,
      setPlaceRecommendation,
      requestTimeChange,
      resetCoordination,
      setInfoPanePhase,
      confirmDate,
      confirmTime,
      confirmPlace,
      sendMessageToAi,
      setSendMessageToAi,
    ],
  );

  return (
    <MeetingContext.Provider value={value}>
      {children}
    </MeetingContext.Provider>
  );
}

export function useMeeting() {
  const ctx = useContext(MeetingContext);
  if (!ctx) {
    throw new Error("useMeeting must be used within MeetingProvider");
  }
  return ctx;
}

export function useMeetingOptional() {
  return useContext(MeetingContext);
}

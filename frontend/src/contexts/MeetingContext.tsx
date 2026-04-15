"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { AiTriggerIntent, ContextMode, PlaceResult } from "@/types";
import type { VoteCardPayload, VoteUpdatePayload, PlaceRecommendationPayload, VoteCardTimeOption } from "@/hooks/useAgentWebSocket";

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
  // Coordination state for calendar-AI bidirectional sync
  voteCard: VoteCardPayload | null;
  voteUpdate: VoteUpdatePayload | null;
  placeRecommendation: PlaceRecommendationPayload | null;
  candidateSlots: VoteCardTimeOption[];
  highlightedDates: string[]; // "YYYY-MM-DD"
  // InfoPane phase state machine
  infoPanePhase: InfoPanePhase;
  confirmedDate: string | null; // "YYYY-MM-DD"
  confirmedTimeRange: { startAt: string; endAt: string } | null;
  confirmedMeetingId: number | null;
}

interface MeetingContextValue extends MeetingState {
  setContextMode: (mode: ContextMode) => void;
  setSelectedPlace: (place: PlaceResult | null) => void;
  setRoom: (id: string, name: string) => void;
  setAiTriggerIntent: (intent: AiTriggerIntent | null) => void;
  refreshCalendar: () => void;
  // Coordination actions
  setVoteCard: (card: VoteCardPayload | null) => void;
  setVoteUpdate: (update: VoteUpdatePayload | null) => void;
  setPlaceRecommendation: (rec: PlaceRecommendationPayload | null) => void;
  resetCoordination: () => void;
  // InfoPane phase actions
  setInfoPanePhase: (phase: InfoPanePhase) => void;
  confirmDate: (date: string) => void;
  confirmTime: (startAt: string, endAt: string, meetingId: number) => void;
  confirmPlace: () => void;
  // sendMessage bridge: AiAssistantPane registers, CalendarPane uses
  sendMessageToAi: ((msg: string) => void) | null;
  setSendMessageToAi: (fn: ((msg: string) => void) | null) => void;
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
    voteCard: null,
    voteUpdate: null,
    placeRecommendation: null,
    candidateSlots: [],
    highlightedDates: [],
    infoPanePhase: "idle",
    confirmedDate: null,
    confirmedTimeRange: null,
    confirmedMeetingId: null,
  });

  const [sendMessageToAi, setSendMessageToAiRaw] = useState<((msg: string) => void) | null>(null);
  const setSendMessageToAi = useCallback((fn: ((msg: string) => void) | null) => {
    setSendMessageToAiRaw(() => fn);
  }, []);

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

  const setVoteCard = useCallback((card: VoteCardPayload | null) => {
    setState((prev) => {
      if (!card) return { ...prev, voteCard: null };
      const slots = card.time_options;
      const dateSet = new Set(slots.map((s) => s.start_at.split("T")[0]));
      const dates = Array.from(dateSet);
      // Don't reset phase if already past time confirmation (prevents
      // pipeline re-triggering from resetting the flow)
      const phaseAlreadyAdvanced =
        prev.infoPanePhase === "timeConfirmed" ||
        prev.infoPanePhase === "placeConfirmed" ||
        prev.infoPanePhase === "done";
      return {
        ...prev,
        voteCard: card,
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

  const setPlaceRecommendation = useCallback((rec: PlaceRecommendationPayload | null) => {
    setState((prev) => {
      // If in phased flow and waiting for place recommendation, auto-transition
      if (rec && prev.infoPanePhase === "timeConfirmed") {
        return { ...prev, placeRecommendation: rec };
      }
      return { ...prev, placeRecommendation: rec };
    });
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
      } else if (phase === "dateSelected") {
        updates.confirmedDate = null;
        updates.confirmedTimeRange = null;
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
      voteCard: state.voteCard,
      voteUpdate: state.voteUpdate,
      placeRecommendation: state.placeRecommendation,
      candidateSlots: state.candidateSlots,
      highlightedDates: state.highlightedDates,
      infoPanePhase: state.infoPanePhase,
      confirmedDate: state.confirmedDate,
      confirmedTimeRange: state.confirmedTimeRange,
      confirmedMeetingId: state.confirmedMeetingId,
      setContextMode,
      setSelectedPlace,
      setRoom,
      setAiTriggerIntent,
      refreshCalendar,
      setVoteCard,
      setVoteUpdate,
      setPlaceRecommendation,
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
      state.contextMode,
      state.roomId,
      state.roomName,
      state.selectedPlace,
      state.voteCard,
      state.voteUpdate,
      state.placeRecommendation,
      state.candidateSlots,
      state.highlightedDates,
      state.infoPanePhase,
      state.confirmedDate,
      state.confirmedTimeRange,
      state.confirmedMeetingId,
      setAiTriggerIntent,
      setContextMode,
      refreshCalendar,
      setRoom,
      setSelectedPlace,
      setVoteCard,
      setVoteUpdate,
      setPlaceRecommendation,
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

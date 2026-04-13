"use client";

import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from "react";
import type { ContextMode, PlaceResult } from "@/types";

interface MeetingState {
  roomId: string;
  roomName: string;
  contextMode: ContextMode;
  selectedPlace: PlaceResult | null;
  aiTriggerIntent: string | null;
}

interface MeetingContextValue extends MeetingState {
  setContextMode: (mode: ContextMode) => void;
  setSelectedPlace: (place: PlaceResult | null) => void;
  setRoom: (id: string, name: string) => void;
  /** 소셜 채팅에서 의도 감지 시 AI 파이프라인을 트리거하는 시그널 (intent 문자열, 없으면 null) */
  aiTriggerIntent: string | null;
  setAiTriggerIntent: (intent: string | null) => void;
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
  });

  const setContextMode = useCallback((mode: ContextMode) => {
    setState((prev) => ({ ...prev, contextMode: mode }));
  }, []);

  const setSelectedPlace = useCallback((place: PlaceResult | null) => {
    setState((prev) => ({ ...prev, selectedPlace: place }));
  }, []);

  const setRoom = useCallback((id: string, name: string) => {
    setState((prev) => ({ ...prev, roomId: id, roomName: name }));
  }, []);

  const setAiTriggerIntent = useCallback((intent: string | null) => {
    setState((prev) => ({ ...prev, aiTriggerIntent: intent, contextMode: intent ? "agent" : prev.contextMode }));
  }, []);

  const value = useMemo(
    () => ({ ...state, setContextMode, setSelectedPlace, setRoom, setAiTriggerIntent }),
    [state, setContextMode, setSelectedPlace, setRoom, setAiTriggerIntent],
  );

  return (
    <MeetingContext.Provider value={value}>
      {children}
    </MeetingContext.Provider>
  );
}

export function useMeeting() {
  const ctx = useContext(MeetingContext);
  if (!ctx) throw new Error("useMeeting must be used within MeetingProvider");
  return ctx;
}

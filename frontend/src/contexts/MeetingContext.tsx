"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { AiTriggerIntent, ContextMode, PlaceResult } from "@/types";

interface MeetingState {
  roomId: string;
  roomName: string;
  contextMode: ContextMode;
  selectedPlace: PlaceResult | null;
  aiTriggerIntent: AiTriggerIntent | null;
  calendarRefreshTrigger: number;
}

interface MeetingContextValue extends MeetingState {
  setContextMode: (mode: ContextMode) => void;
  setSelectedPlace: (place: PlaceResult | null) => void;
  setRoom: (id: string, name: string) => void;
  setAiTriggerIntent: (intent: AiTriggerIntent | null) => void;
  refreshCalendar: () => void;
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
  });

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

  const value = useMemo(
    () => ({
      roomId: state.roomId,
      roomName: state.roomName,
      contextMode: state.contextMode,
      selectedPlace: state.selectedPlace,
      aiTriggerIntent: state.aiTriggerIntent,
      calendarRefreshTrigger: state.calendarRefreshTrigger,
      setContextMode,
      setSelectedPlace,
      setRoom,
      setAiTriggerIntent,
      refreshCalendar,
    }),
    [
      state.aiTriggerIntent,
      state.calendarRefreshTrigger,
      state.contextMode,
      state.roomId,
      state.roomName,
      state.selectedPlace,
      setAiTriggerIntent,
      setContextMode,
      refreshCalendar,
      setRoom,
      setSelectedPlace,
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

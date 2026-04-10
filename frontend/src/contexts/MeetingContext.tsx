"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { ContextMode, PlaceResult } from "@/types";

interface MeetingState {
  roomId: string;
  roomName: string;
  contextMode: ContextMode;
  selectedPlace: PlaceResult | null;
}

interface MeetingContextValue extends MeetingState {
  setContextMode: (mode: ContextMode) => void;
  setSelectedPlace: (place: PlaceResult | null) => void;
  setRoom: (id: string, name: string) => void;
}

const MeetingContext = createContext<MeetingContextValue | null>(null);

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

  return (
    <MeetingContext.Provider
      value={{ ...state, setContextMode, setSelectedPlace, setRoom }}
    >
      {children}
    </MeetingContext.Provider>
  );
}

export function useMeeting() {
  const ctx = useContext(MeetingContext);
  if (!ctx) throw new Error("useMeeting must be used within MeetingProvider");
  return ctx;
}

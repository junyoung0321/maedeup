import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { MeetingProvider, useMeeting } from "@/contexts/MeetingContext";
import type { ReactNode } from "react";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <MeetingProvider initialRoomId="1" initialRoomName="test-room">
      {children}
    </MeetingProvider>
  );
}

const mockVoteCard = {
  type: "vote_card" as const,
  title: "테스트 모임",
  room_id: "1",
  meeting_id: 42,
  time_options: [
    {
      slot_id: "slot_0",
      label: "4월 17일 (목) 오후 2:00 ~ 4:00",
      start_at: "2026-04-17T14:00:00",
      end_at: "2026-04-17T16:00:00",
    },
    {
      slot_id: "slot_1",
      label: "4월 18일 (금) 오후 3:00 ~ 5:00",
      start_at: "2026-04-18T15:00:00",
      end_at: "2026-04-18T17:00:00",
    },
  ],
  headcount: 4,
};

describe("MeetingContext — InfoPanePhase", () => {
  it("starts with idle phase", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });
    expect(result.current.infoPanePhase).toBe("idle");
    expect(result.current.confirmedDate).toBeNull();
    expect(result.current.confirmedTimeRange).toBeNull();
  });

  it("setVoteCard resets phase to idle and extracts highlighted dates", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() => result.current.setVoteCard(mockVoteCard));

    expect(result.current.infoPanePhase).toBe("idle");
    expect(result.current.voteCard).toBe(mockVoteCard);
    expect(result.current.highlightedDates).toEqual(["2026-04-17", "2026-04-18"]);
    expect(result.current.candidateSlots).toHaveLength(2);
    expect(result.current.confirmedMeetingId).toBe(42);
  });

  it("confirmDate transitions to dateConfirmed", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() => result.current.setVoteCard(mockVoteCard));
    act(() => result.current.confirmDate("2026-04-17"));

    expect(result.current.infoPanePhase).toBe("dateConfirmed");
    expect(result.current.confirmedDate).toBe("2026-04-17");
    expect(result.current.confirmedTimeRange).toBeNull();
  });

  it("confirmTime transitions to timeConfirmed", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() => result.current.setVoteCard(mockVoteCard));
    act(() => result.current.confirmDate("2026-04-17"));
    act(() => result.current.confirmTime("2026-04-17T14:00:00", "2026-04-17T16:00:00", 42));

    expect(result.current.infoPanePhase).toBe("timeConfirmed");
    expect(result.current.confirmedTimeRange).toEqual({
      startAt: "2026-04-17T14:00:00",
      endAt: "2026-04-17T16:00:00",
    });
    expect(result.current.confirmedMeetingId).toBe(42);
  });

  it("timeConfirmed clears stale scheduleConsensus", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() =>
      result.current.setScheduleConsensus({
        type: "schedule_consensus_ready",
        room_id: 1,
        snapshot_hash: "snapshot",
        host_user_id: 1,
        member_count: 2,
      }),
    );
    act(() => result.current.setInfoPanePhase("timeConfirmed"));

    expect(result.current.scheduleConsensus).toBeNull();
    expect(result.current.infoPanePhase).toBe("timeConfirmed");
  });

  it("confirmPlace transitions to placeConfirmed", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() => result.current.setVoteCard(mockVoteCard));
    act(() => result.current.confirmDate("2026-04-17"));
    act(() => result.current.confirmTime("2026-04-17T14:00:00", "2026-04-17T16:00:00", 42));
    act(() => result.current.confirmPlace());

    expect(result.current.infoPanePhase).toBe("placeConfirmed");
  });

  it("backward transition: dateConfirmed → dateSelected clears time", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() => result.current.setVoteCard(mockVoteCard));
    act(() => result.current.confirmDate("2026-04-17"));
    act(() => result.current.setInfoPanePhase("dateSelected"));

    expect(result.current.infoPanePhase).toBe("dateSelected");
    expect(result.current.confirmedDate).toBeNull();
    expect(result.current.confirmedTimeRange).toBeNull();
  });

  it("backward transition: dateSelected → idle clears all", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() => result.current.setVoteCard(mockVoteCard));
    act(() => result.current.setInfoPanePhase("dateSelected"));
    act(() => result.current.setInfoPanePhase("idle"));

    expect(result.current.infoPanePhase).toBe("idle");
    expect(result.current.confirmedDate).toBeNull();
  });

  it("new vote_card preserves dateConfirmed phase mid-flow", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    // Progress to dateConfirmed
    act(() => result.current.setVoteCard(mockVoteCard));
    act(() => result.current.confirmDate("2026-04-17"));
    expect(result.current.infoPanePhase).toBe("dateConfirmed");

    // New vote card arrives
    const newCard = { ...mockVoteCard, title: "새 모임", meeting_id: 99 };
    act(() => result.current.setVoteCard(newCard));

    expect(result.current.infoPanePhase).toBe("dateConfirmed");
    expect(result.current.confirmedDate).toBe("2026-04-17");
    expect(result.current.confirmedMeetingId).toBe(99);
  });

  it("resetCoordination clears everything", () => {
    const { result } = renderHook(() => useMeeting(), { wrapper });

    act(() => result.current.setVoteCard(mockVoteCard));
    act(() => result.current.confirmDate("2026-04-17"));
    act(() => result.current.resetCoordination());

    expect(result.current.infoPanePhase).toBe("idle");
    expect(result.current.voteCard).toBeNull();
    expect(result.current.confirmedDate).toBeNull();
    expect(result.current.confirmedTimeRange).toBeNull();
    expect(result.current.confirmedMeetingId).toBeNull();
    expect(result.current.highlightedDates).toEqual([]);
  });
});

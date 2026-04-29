import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import FinalizationProposalCard from "@/components/meeting/FinalizationProposalCard";
import type { FinalizationState } from "@/hooks/useSocialWebSocket";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(() => Promise.resolve({})),
}));

function makeProposal(overrides: Partial<FinalizationState> = {}): FinalizationState {
  return {
    proposal_id: "p-1",
    version: 1,
    status: "active",
    proposed_slot: {
      date: "2026-05-02",
      start_idx: 12,
      end_idx: 14,
      start_at: "2026-05-02T15:00:00",
      end_at: "2026-05-02T16:30:00",
      label: "2026-05-02 15:00-16:30",
    },
    alternate_slot: null,
    reason: "세 분이 이 시간을 선택하셨네요.",
    host_user_id: 1,
    total_eligible_voters: 5,
    votes: {},
    my_vote: null,
    deadline_at: Date.now() / 1000 + 24 * 3600,
    created_at: Date.now() / 1000,
    ...overrides,
  };
}

describe("FinalizationProposalCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders proposed slot as the hero", () => {
    render(
      <FinalizationProposalCard
        proposal={makeProposal()}
        pending={false}
        currentUserId={1}
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    expect(screen.getByText("2026-05-02 15:00-16:30")).toBeDefined();
  });

  it("shows AI reason line", () => {
    render(
      <FinalizationProposalCard
        proposal={makeProposal({ reason: "세 분이 이 시간을 선택하셨네요." })}
        pending={false}
        currentUserId={2}
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    expect(screen.getByText("세 분이 이 시간을 선택하셨네요.")).toBeDefined();
  });

  it("disables host confirm when below majority", () => {
    render(
      <FinalizationProposalCard
        proposal={makeProposal({ status: "active", total_eligible_voters: 5, votes: { "1": "like" } })}
        pending={false}
        currentUserId={1}
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    const btn = screen.getByRole("button", { name: /이 시간으로 모임 확정/i });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it("activates host confirm when majority reached", () => {
    render(
      <FinalizationProposalCard
        proposal={makeProposal({
          status: "majority_reached",
          total_eligible_voters: 3,
          votes: { "1": "like", "2": "like" },
        })}
        pending={false}
        currentUserId={1}
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    const btn = screen.getByRole("button", { name: /이 시간으로 모임 확정/i });
    expect((btn as HTMLButtonElement).disabled).toBe(false);
  });

  it("non-host sees waiting state after majority, not a confirm button", () => {
    render(
      <FinalizationProposalCard
        proposal={makeProposal({
          status: "majority_reached",
          total_eligible_voters: 3,
          votes: { "1": "like", "2": "like" },
        })}
        pending={false}
        currentUserId={2}  /* not the host (host_user_id=1) */
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    expect(screen.queryByRole("button", { name: /이 시간으로 모임 확정/i })).toBeNull();
    expect(screen.getByText(/방장 확정 대기 중/)).toBeDefined();
  });

  it("shows my_vote banner after voting", () => {
    render(
      <FinalizationProposalCard
        proposal={makeProposal({ my_vote: "like", votes: { "2": "like" } })}
        pending={false}
        currentUserId={2}
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    expect(screen.getByText(/좋아요로 투표함/)).toBeDefined();
    expect(screen.queryByRole("button", { name: /다른 시간 제안/ })).toBeNull();
  });

  it("renders shimmer when pending with no proposal", () => {
    render(
      <FinalizationProposalCard
        proposal={null}
        pending={true}
        currentUserId={1}
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    expect(screen.getByText(/분석 중이에요/)).toBeDefined();
  });

  it("renders success banner on confirmed status", () => {
    render(
      <FinalizationProposalCard
        proposal={makeProposal({ status: "confirmed" })}
        pending={false}
        currentUserId={1}
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    expect(screen.getByText(/모임이 확정되었습니다/)).toBeDefined();
  });

  it("renders alternate slot on tie", () => {
    render(
      <FinalizationProposalCard
        proposal={makeProposal({
          alternate_slot: {
            date: "2026-05-03",
            start_idx: 10,
            end_idx: 12,
            start_at: "2026-05-03T14:00:00",
            end_at: "2026-05-03T15:00:00",
            label: "2026-05-03 14:00-15:00",
          },
        })}
        pending={false}
        currentUserId={1}
        roomId="10"
        onConfirm={vi.fn(() => Promise.resolve())}
      />,
    );
    expect(screen.getByText(/2026-05-03 14:00-15:00/)).toBeDefined();
  });

  it("calls onConfirm with proposal_id + slot when host clicks confirm", async () => {
    const onConfirm = vi.fn(() => Promise.resolve());
    render(
      <FinalizationProposalCard
        proposal={makeProposal({
          status: "majority_reached",
          total_eligible_voters: 3,
          votes: { "1": "like", "2": "like" },
        })}
        pending={false}
        currentUserId={1}
        roomId="10"
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /이 시간으로 모임 확정/i }));
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith("p-1", expect.objectContaining({
        start_at: "2026-05-02T15:00:00",
      }));
    });
  });
});

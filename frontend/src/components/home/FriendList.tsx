"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { UserPlus, Send, Check, X } from "lucide-react";
import AddFriendModal from "./AddFriendModal";
import { apiFetch } from "@/lib/api";
import type { FriendInfo } from "@/types";

const AVATAR_PALETTE = [
  "#c7d2fe", "#93c5fd", "#86efac", "#fca5a5",
  "#fde68a", "#fbcfe8", "#a5f3fc", "#d9f99d",
];

interface FriendRequestInfo {
  id: number;
  status: string;
  created_at: string;
  direction: "incoming" | "outgoing";
  user: FriendInfo;
}

export default function FriendList() {
  const router = useRouter();
  const [modalOpen, setModalOpen] = useState(false);
  const [friends, setFriends] = useState<FriendInfo[]>([]);
  const [requests, setRequests] = useState<FriendRequestInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set());

  const loadFriends = useCallback(async () => {
    const [friendsRes, requestsRes] = await Promise.allSettled([
      apiFetch<FriendInfo[]>("/api/v1/users/friends"),
      apiFetch<FriendRequestInfo[]>("/api/v1/users/friends/requests?direction=incoming"),
    ]);
    if (friendsRes.status === "fulfilled") {
      setFriends(friendsRes.value);
    } else {
      setError(true);
    }
    setRequests(requestsRes.status === "fulfilled" ? requestsRes.value : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadFriends();
  }, [loadFriends]);

  const respondToRequest = async (requestId: number, action: "accept" | "reject") => {
    setProcessingIds((prev) => new Set(prev).add(requestId));
    try {
      await apiFetch(`/api/v1/users/friends/requests/${requestId}`, {
        method: "PATCH",
        body: JSON.stringify({ action }),
      });
      // optimistic: remove from requests list, reload friends if accepted
      setRequests((prev) => prev.filter((r) => r.id !== requestId));
      if (action === "accept") {
        const fresh = await apiFetch<FriendInfo[]>("/api/v1/users/friends");
        setFriends(fresh);
      }
    } catch {
      // on error, reload everything to get true state
      await loadFriends();
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(requestId);
        return next;
      });
    }
  };

  const handleAddModalClose = () => {
    setModalOpen(false);
    // requests list might have changed if user sent outgoing; refresh for safety
    loadFriends();
  };

  return (
    <>
      <div className="bg-white rounded-[20px] p-5 flex flex-col border border-[#e2e8f0] shadow-[0_4px_2.7px_rgba(0,0,0,0.25)]" style={{ height: 620 }}>
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-[27px] font-semibold text-[#111827]">친구</h3>
            <p className="text-[18px] font-medium text-[#9f9f9f] mt-1">
              친구 목록을 확인하고 새 친구를 추가할 수 있어요
            </p>
          </div>
          {requests.length > 0 && (
            <span
              className="mt-1 px-2 py-1 rounded-full bg-[#ef4444] text-white text-[12px] font-semibold"
              title={`받은 친구 요청 ${requests.length}건`}
            >
              요청 {requests.length}
            </span>
          )}
        </div>

        {/* Incoming requests section */}
        {requests.length > 0 && (
          <div className="mt-4 mb-2 p-3 rounded-[12px] bg-[#fef2f2] border border-[#fecaca]">
            <p className="text-[13px] font-semibold text-[#991b1b] mb-2">
              받은 친구 요청
            </p>
            <div className="flex flex-col gap-2">
              {requests.map((req) => {
                const busy = processingIds.has(req.id);
                return (
                  <div key={req.id} className="flex items-center gap-2">
                    <div
                      className="w-[32px] h-[32px] rounded-full flex items-center justify-center text-[#334155] text-[12px] font-semibold shrink-0"
                      style={{ backgroundColor: AVATAR_PALETTE[req.user.id % AVATAR_PALETTE.length] }}
                    >
                      {req.user.name.charAt(0)}
                    </div>
                    <span className="flex-1 text-[14px] font-medium text-[#111827] truncate">
                      {req.user.name}
                    </span>
                    <button
                      onClick={() => respondToRequest(req.id, "accept")}
                      disabled={busy}
                      className="px-2 py-1 rounded-md bg-[#22c55e] text-white text-[12px] font-semibold flex items-center gap-1 disabled:opacity-50"
                    >
                      <Check className="w-3 h-3" /> 수락
                    </button>
                    <button
                      onClick={() => respondToRequest(req.id, "reject")}
                      disabled={busy}
                      className="px-2 py-1 rounded-md bg-white border border-[#e2e8f0] text-[#64748b] text-[12px] font-semibold flex items-center gap-1 disabled:opacity-50"
                    >
                      <X className="w-3 h-3" /> 거절
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="mb-3" />

        {/* Friend rows - scrollable */}
        <div className="flex flex-col flex-1 overflow-y-auto min-h-0">
          {loading ? (
            <div className="flex-1 flex items-center justify-center text-[#94a3b8] text-sm">
              불러오는 중...
            </div>
          ) : error ? (
            <div className="flex-1 flex items-center justify-center text-[#ef4444] text-sm">
              친구 목록을 불러올 수 없습니다
            </div>
          ) : friends.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-[#94a3b8] text-sm">
              아직 친구가 없어요
            </div>
          ) : (
            friends.map((friend, idx) => (
              <div key={friend.id}>
                <div className="flex items-center gap-3" style={{ height: 72 }}>
                  <div
                    className="w-[44px] h-[44px] rounded-full flex items-center justify-center text-[#334155] text-[14px] font-semibold shrink-0"
                    style={{ backgroundColor: AVATAR_PALETTE[friend.id % AVATAR_PALETTE.length] }}
                  >
                    {friend.name.charAt(0)}
                  </div>
                  <div className="flex-1">
                    <span className="text-[20px] font-medium text-[#111827]">
                      {friend.name}
                    </span>
                  </div>
                  <button
                    onClick={() => router.push(`/meeting/dm-${friend.id}`)}
                    className="w-[42px] h-[37px] rounded-full bg-[#4f46e5] flex items-center justify-center shrink-0 hover:bg-[#4338ca] transition-colors"
                  >
                    <Send className="w-[18px] h-[18px] text-white" />
                  </button>
                </div>
                {idx < friends.length - 1 && (
                  <div className="h-px bg-[#f0f0f2]" />
                )}
              </div>
            ))
          )}
        </div>

        {/* Add friend button */}
        <button
          onClick={() => setModalOpen(true)}
          className="mt-5 w-full py-3 rounded-[12px] bg-[#4f46e5] text-white text-[15px] font-semibold hover:bg-[#4338ca] transition-colors flex items-center justify-center gap-2 shrink-0"
        >
          <UserPlus className="w-4 h-4" />
          친구 추가
        </button>
      </div>

      <AddFriendModal open={modalOpen} onClose={handleAddModalClose} />
    </>
  );
}

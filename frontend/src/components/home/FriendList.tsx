"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { UserPlus, Send } from "lucide-react";
import AddFriendModal from "./AddFriendModal";
import { apiFetchWithFallback } from "@/lib/api";
import { mockFriends } from "@/mocks/friends";
import type { FriendInfo } from "@/types";
import EmptyState from "@/components/ui/EmptyState";

const AVATAR_PALETTE = [
  "#c7d2fe", "#93c5fd", "#86efac", "#fca5a5",
  "#fde68a", "#fbcfe8", "#a5f3fc", "#d9f99d",
];

export default function FriendList() {
  const router = useRouter();
  const [modalOpen, setModalOpen] = useState(false);
  const [friends, setFriends] = useState<FriendInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fallback: FriendInfo[] = mockFriends.map((f, i) => ({ id: i + 1, name: f.name, email: "", picture: null }));
    apiFetchWithFallback<FriendInfo[]>("/api/v1/users/friends", fallback)
      .then((data) => { setFriends(data); setLoading(false); });
  }, []);

  return (
    <>
      <div className="bg-white rounded-[20px] p-5 flex flex-col border border-[#e2e8f0] shadow-[0_4px_2.7px_rgba(0,0,0,0.25)]" style={{ height: 620 }}>
        {/* Header */}
        <h3 className="text-[27px] font-semibold text-[#111827]">친구</h3>
        <p className="text-[18px] font-medium text-[#9f9f9f] mt-1 mb-5">
          친구 목록을 확인하고 새 친구를 추가할 수 있어요
        </p>

        {/* Friend rows - scrollable */}
        <div className="flex flex-col flex-1 overflow-y-auto min-h-0">
          {loading ? (
            <div className="flex-1 flex items-center justify-center text-[#94a3b8] text-sm">
              불러오는 중...
            </div>
          ) : error ? (
            <EmptyState message="친구 목록을 불러올 수 없습니다" icon={UserPlus} />
          ) : friends.length === 0 ? (
            <EmptyState
              icon={UserPlus}
              message="아직 친구가 없어요"
              sub="친구 추가 버튼으로 새 친구를 초대해 보세요"
              action={{ label: "친구 추가", onClick: () => setModalOpen(true) }}
            />
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

      <AddFriendModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}

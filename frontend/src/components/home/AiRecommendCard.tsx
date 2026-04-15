"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { parseServerDate } from "@/lib/datetime";
import AiRecommendDetailModal from "./AiRecommendDetailModal";

type AvailabilityState = "free" | "busy_now" | "free_in" | "unknown";

interface AvailableFriend {
  user: { id: number; name: string; email: string; picture: string | null };
  state: AvailabilityState;
  available_at: string | null;
}

interface AvailableFriendsResponse {
  window_minutes: number;
  now: string;
  friends: AvailableFriend[];
}

interface RecommendedPlace {
  id: string;
  name: string;
  address: string;
  distance_label?: string | null;
  category: string;
  url: string;
  x: string;
  y: string;
}

interface NearbyPlacesResponse {
  home_base: string | null;
  category: string;
  places: RecommendedPlace[];
  reason?: string | null;
}

function stateLabel(state: AvailabilityState, availableAt: string | null): string {
  if (state === "free") return "가능";
  if (state === "free_in" && availableAt) {
    const minutes = Math.max(1, Math.round((parseServerDate(availableAt).getTime() - Date.now()) / 60000));
    return `${minutes}분 후`;
  }
  if (state === "busy_now") return "바쁨";
  return "미연동";
}

function stateColor(state: AvailabilityState): string {
  if (state === "free") return "#bbf7d0";       // green
  if (state === "free_in") return "#fde68a";    // yellow
  if (state === "busy_now") return "#fecaca";   // red-ish
  return "#cbd5e1";                              // gray
}

function shortCategory(raw: string): string | null {
  if (!raw) return null;
  // Kakao category 예: "음식점 > 카페" → 마지막 segment만
  const parts = raw.split(">").map((p) => p.trim()).filter(Boolean);
  return parts[parts.length - 1] ?? null;
}

export default function AiRecommendCard() {
  const router = useRouter();
  const [detailOpen, setDetailOpen] = useState(false);

  const [friends, setFriends] = useState<AvailableFriend[]>([]);
  const [friendsLoading, setFriendsLoading] = useState(true);

  const [places, setPlaces] = useState<RecommendedPlace[]>([]);
  const [placesReason, setPlacesReason] = useState<string | null>(null);
  const [placesLoading, setPlacesLoading] = useState(true);

  useEffect(() => {
    apiFetch<AvailableFriendsResponse>("/api/v1/recommendations/available-friends?window_minutes=120")
      .then((data) => {
        setFriends(data.friends);
      })
      .catch(() => setFriends([]))
      .finally(() => setFriendsLoading(false));

    apiFetch<NearbyPlacesResponse>("/api/v1/recommendations/nearby-places?category=카페&limit=3")
      .then((data) => {
        setPlaces(data.places);
        setPlacesReason(data.reason ?? null);
      })
      .catch(() => {
        setPlaces([]);
        setPlacesReason("추천을 불러올 수 없어요");
      })
      .finally(() => setPlacesLoading(false));
  }, []);

  const visibleFriends = friends.slice(0, 3);
  const availableCount = friends.filter((f) => f.state === "free").length;

  return (
    <>
      <div
        className="bg-white rounded-[24px] p-6 border border-[#e5e7eb] shadow-[0_4px_3px_rgba(0,0,0,0.25)]"
        style={{ width: 728, minHeight: 419 }}
      >
        <h2 className="text-[28px] font-semibold text-[#111827]">AI 추천</h2>
        <p className="text-[18px] text-[#6b7280] mt-1 mb-5">
          지금 상황에 맞는 모임을 바로 시작해보세요
        </p>

        <div className="flex gap-4">
          {/* Card A — friends */}
          <div
            className="flex-1 rounded-[18px] p-5 flex flex-col justify-between text-white min-h-[280px]"
            style={{
              background: "linear-gradient(160deg, #7c3aed 0%, #4f46e5 50%, #6366f1 100%)",
            }}
          >
            <div>
              <span className="text-[15px] font-medium text-[#e0e7ff]">
                지금 시간대 가능한 친구
              </span>
              <h3 className="text-[24px] font-bold mt-2 leading-snug text-white">
                {friendsLoading
                  ? "확인 중..."
                  : availableCount > 0
                  ? `${availableCount}명 지금 모임 가능`
                  : friends.length === 0
                  ? "친구를 추가해보세요"
                  : "지금은 모두 바빠요"}
              </h3>

              <div className="mt-4 flex flex-col gap-2">
                {friendsLoading ? (
                  <span className="text-[13px] text-[#e0e7ff]">불러오는 중...</span>
                ) : visibleFriends.length === 0 ? (
                  <span className="text-[13px] text-[#e0e7ff]">표시할 친구가 없어요</span>
                ) : (
                  visibleFriends.map((f) => (
                    <div key={f.user.id} className="flex items-center justify-between">
                      <span className="text-[14px] text-white truncate max-w-[60%]">
                        {f.user.name}
                      </span>
                      <span
                        className="text-[13px]"
                        style={{ color: stateColor(f.state) }}
                      >
                        {stateLabel(f.state, f.available_at)}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            <button
              onClick={() => router.push("/meeting/new")}
              disabled={friends.length === 0}
              className="mt-4 self-start px-5 py-2 rounded-full bg-white/20 text-[15px] font-medium text-white hover:bg-white/30 transition-colors disabled:opacity-50"
            >
              모임 만들기
            </button>
          </div>

          {/* Card B — places */}
          <div
            className="flex-1 rounded-[18px] p-5 flex flex-col justify-between text-white min-h-[280px]"
            style={{
              background: "linear-gradient(145deg, #0ea5e9 0%, #22c55e 100%)",
            }}
          >
            <div>
              <span className="text-[15px] font-medium text-[#dcfce7]">
                {placesLoading
                  ? "추천 준비 중"
                  : placesReason
                  ? "장소 추천"
                  : `근처 ${places[0]?.category ? shortCategory(places[0].category) ?? "카페" : "카페"}`}
              </span>
              <h3 className="text-[24px] font-bold mt-2 leading-snug text-white">
                이번 주 모임 추천 장소
              </h3>

              <div className="mt-4 flex flex-col gap-3">
                {placesLoading ? (
                  <span className="text-[13px] text-[#dcfce7]">불러오는 중...</span>
                ) : placesReason ? (
                  <div className="flex flex-col gap-2">
                    <span className="text-[13px] text-[#dcfce7]">{placesReason}</span>
                    {placesReason.includes("동네") && (
                      <button
                        onClick={() => router.push("/onboarding")}
                        className="self-start px-3 py-1 rounded-full bg-white/20 text-[12px] font-medium text-white"
                      >
                        동네 등록하러 가기
                      </button>
                    )}
                  </div>
                ) : places.length === 0 ? (
                  <span className="text-[13px] text-[#dcfce7]">결과가 없어요</span>
                ) : (
                  places.map((p, idx) => (
                    <div key={p.id}>
                      <p className="text-[14px] font-semibold text-white truncate">
                        {idx + 1}) {p.name}
                      </p>
                      <p className="text-[12px] text-[#dcfce7] truncate">
                        {shortCategory(p.category) ?? p.category} · {p.address || "주소 정보 없음"}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>

            <button
              onClick={() => setDetailOpen(true)}
              disabled={places.length === 0}
              className="mt-4 self-start px-5 py-2 rounded-full bg-white/20 text-[13px] font-semibold text-white hover:bg-white/30 transition-colors disabled:opacity-50"
            >
              자세히 보기
            </button>
          </div>
        </div>
      </div>

      <AiRecommendDetailModal open={detailOpen} onClose={() => setDetailOpen(false)} />
    </>
  );
}

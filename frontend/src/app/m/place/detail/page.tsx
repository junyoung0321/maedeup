"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Share2,
  MapPin,
  Phone,
  Clock,
  Wallet,
  ExternalLink,
  Sparkles,
  Star,
  Users,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { NearbyPlace, ProposalPayload } from "@/types";

const TAG_STYLES = [
  { color: "#4f46e5", backgroundColor: "#eef2ff" },
  { color: "#b45309", backgroundColor: "#fef3c7" },
  { color: "#059669", backgroundColor: "#ecfdf5" },
];

function buildTags(place: NearbyPlace): string[] {
  const tags: string[] = [place.category];
  if (place.distance_label) tags.push(place.distance_label);
  return tags.slice(0, 3);
}

function PlaceDetailPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [place, setPlace] = useState<NearbyPlace | null>(null);
  const [proposal, setProposal] = useState<ProposalPayload | null>(null);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("selectedPlace");
      if (raw) setPlace(JSON.parse(raw) as NearbyPlace);
    } catch {
      // sessionStorage unavailable or invalid JSON
    }
  }, []);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<ProposalPayload | null>(`/api/v1/finalization/room/${roomId}`)
      .then(setProposal)
      .catch(() => null);
  }, [authLoading, user, roomId]);

  function handleShare() {
    if (place?.url) {
      navigator.clipboard?.writeText(place.url);
    }
    alert("링크가 복사되었습니다!");
  }

  const likeCount = proposal?.like_count ?? 0;
  const total = proposal?.total_eligible_voters ?? 0;
  const likePercent = total > 0 ? (likeCount / total) * 100 : 0;

  return (
    <div
      className="relative flex flex-col bg-white"
      style={{ width: "100%", height: "100dvh", fontFamily: "Pretendard, sans-serif" }}
    >
      {/* Header */}
      <div
        className="flex items-center shrink-0"
        style={{ height: 56, padding: "0 16px", borderBottom: "1px solid #e2e8f0", backgroundColor: "#ffffff" }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push(`/m/place?roomId=${roomId}`)} />
        <div className="flex flex-col items-center flex-1 gap-[2px]">
          <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b" }}>
            장소 상세
          </span>
        </div>
        <Share2 size={22} color="#64748b" className="shrink-0 cursor-pointer" onClick={handleShare} />
      </div>

      {/* Hero Image */}
      <div
        className="shrink-0 w-full"
        style={{
          height: 220,
          background: "linear-gradient(135deg, #b8976a 0%, #8b7355 50%, #6b5842 100%)",
        }}
      />

      {/* Content */}
      <div
        className="flex flex-col flex-1 overflow-y-auto"
        style={{ backgroundColor: "#ffffff", padding: 20, gap: 16 }}
      >
        {!place ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", paddingTop: 40 }}>
            <span style={{ fontSize: 14, color: "#94a3b8" }}>
              장소 정보를 불러올 수 없습니다
            </span>
          </div>
        ) : (
          <>
            {/* Name row */}
            <div className="flex items-center justify-between">
              <span
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: "#1e293b",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  maxWidth: "70%",
                }}
              >
                {place.name}
              </span>
              {place.rating != null && (
                <div className="flex items-center" style={{ gap: 4 }}>
                  <Star size={14} color="#f59e0b" fill="#f59e0b" />
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
                    {place.rating.toFixed(1)}
                  </span>
                </div>
              )}
            </div>

            {/* Tag row */}
            <div className="flex items-center" style={{ gap: 8, flexWrap: "wrap" }}>
              {buildTags(place).map((tag, i) => (
                <span
                  key={tag}
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    color: TAG_STYLES[i % TAG_STYLES.length].color,
                    backgroundColor: TAG_STYLES[i % TAG_STYLES.length].backgroundColor,
                    borderRadius: 999,
                    padding: "4px 10px",
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>

            {/* Divider */}
            <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

            {/* Info section */}
            <div className="flex flex-col" style={{ gap: 12 }}>
              {/* Address */}
              <div className="flex items-start" style={{ gap: 10 }}>
                <MapPin size={16} color="#94a3b8" className="shrink-0" style={{ marginTop: 2 }} />
                <span style={{ fontSize: 14, fontWeight: 400, color: "#374151", lineHeight: 1.5 }}>
                  {place.address}
                </span>
              </div>

              {/* Phone */}
              {place.phone && (
                <div className="flex items-center" style={{ gap: 10 }}>
                  <Phone size={16} color="#94a3b8" className="shrink-0" />
                  <span style={{ fontSize: 14, fontWeight: 400, color: "#374151" }}>
                    {place.phone}
                  </span>
                </div>
              )}

              {/* Hours placeholder */}
              <div className="flex items-center" style={{ gap: 10 }}>
                <Clock size={16} color="#94a3b8" className="shrink-0" />
                <span style={{ fontSize: 14, fontWeight: 400, color: "#94a3b8" }}>
                  영업 시간 정보 없음
                </span>
              </div>

              {/* Price placeholder */}
              <div className="flex items-center" style={{ gap: 10 }}>
                <Wallet size={16} color="#94a3b8" className="shrink-0" />
                <span style={{ fontSize: 14, fontWeight: 400, color: "#94a3b8" }}>
                  가격 정보 없음
                </span>
              </div>

              {/* External link */}
              {place.url && (
                <a
                  href={place.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center"
                  style={{ gap: 10, textDecoration: "none" }}
                >
                  <ExternalLink size={16} color="#94a3b8" className="shrink-0" />
                  <span style={{ fontSize: 14, fontWeight: 400, color: "#4f46e5" }}>
                    카카오맵에서 보기
                  </span>
                </a>
              )}
            </div>

            {/* Divider */}
            <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

            {/* AI 추천 이유 card */}
            {place.ai_reason && (
              <>
                <div
                  className="flex flex-col"
                  style={{
                    borderRadius: 12,
                    backgroundColor: "#f5f3ff",
                    border: "1px solid #e0e7ff",
                    padding: 16,
                    gap: 8,
                  }}
                >
                  <div className="flex items-center" style={{ gap: 6 }}>
                    <Sparkles size={14} color="#7c3aed" />
                    <span style={{ fontSize: 12, fontWeight: 600, color: "#7c3aed" }}>
                      AI 추천 이유
                    </span>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 400, color: "#374151", lineHeight: 1.6 }}>
                    {place.ai_reason}
                  </span>
                </div>

                {/* Divider */}
                <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />
              </>
            )}

            {/* 참여자 투표 현황 */}
            {proposal && total > 0 && (
              <div className="flex flex-col" style={{ gap: 12 }}>
                <div className="flex items-center" style={{ gap: 6 }}>
                  <Users size={16} color="#1e293b" />
                  <span style={{ fontSize: 15, fontWeight: 700, color: "#1e293b" }}>
                    참여자 투표 현황
                  </span>
                </div>

                {/* Vote bar */}
                <div className="flex flex-col" style={{ gap: 6 }}>
                  <div className="flex items-center justify-between">
                    <span style={{ fontSize: 12, fontWeight: 500, color: "#64748b" }}>
                      참여 가능
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>
                      {likeCount}/{total}명
                    </span>
                  </div>
                  <div
                    style={{
                      height: 8,
                      borderRadius: 4,
                      backgroundColor: "#e2e8f0",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${likePercent}%`,
                        height: "100%",
                        borderRadius: 4,
                        backgroundColor: "#4f46e5",
                      }}
                    />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Button area */}
      <div
        className="shrink-0"
        style={{ backgroundColor: "#ffffff", padding: "12px 20px", borderTop: "1px solid #e2e8f0" }}
      >
        <button
          className="flex items-center justify-center w-full cursor-pointer"
          onClick={() => router.push(`/m/meeting/confirm?roomId=${roomId}`)}
          style={{ borderRadius: 12, backgroundColor: "#4f46e5", height: 48, gap: 8, border: "none" }}
        >
          <MapPin size={18} color="#ffffff" />
          <span style={{ fontSize: 15, fontWeight: 600, color: "#ffffff" }}>
            이 장소 선택하기
          </span>
        </button>
      </div>

      {/* Home bar */}
      <div className="flex items-center justify-center shrink-0" style={{ height: 20, backgroundColor: "#ffffff" }}>
        <div style={{ width: 134, height: 5, borderRadius: 999, backgroundColor: "#000000" }} />
      </div>
    </div>
  );
}

export default function PlaceDetailPage() {
  return (
    <Suspense fallback={null}>
      <PlaceDetailPageContent />
    </Suspense>
  );
}

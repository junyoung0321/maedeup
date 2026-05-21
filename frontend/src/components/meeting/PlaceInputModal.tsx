"use client";

import { useCallback, useState } from "react";
import { MapPin, X } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface PlaceInputModalProps {
  meetingId: number;
  onClose: () => void;
  onSuccess: () => void;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error && error.message
    ? error.message
    : "장소 저장에 실패했습니다.";
}

export default function PlaceInputModal({
  meetingId,
  onClose,
  onSuccess,
}: PlaceInputModalProps) {
  const [place, setPlace] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleConfirm = useCallback(async () => {
    const nextPlace = place.trim();
    if (!nextPlace) {
      setError("장소 이름을 입력해주세요.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/meetings/${meetingId}/place`, {
        method: "PATCH",
        body: JSON.stringify({ place: nextPlace }),
      });
      onSuccess();
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }, [meetingId, onClose, onSuccess, place]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="place-input-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        background: "rgba(15, 23, 42, 0.42)",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div
        style={{
          width: "min(100%, 420px)",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          padding: 20,
          borderRadius: 18,
          background: "#ffffff",
          boxShadow: "0 24px 60px rgba(15, 23, 42, 0.22)",
          border: "1px solid rgba(226, 232, 240, 0.9)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 14,
              background: "#eef2ff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <MapPin size={20} color="#4f46e5" />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1 }}>
            <span id="place-input-title" style={{ fontSize: 26, fontWeight: 800, color: "#1e293b" }}>
              장소 입력
            </span>
            <span style={{ fontSize: 20, fontWeight: 500, color: "#64748b" }}>
              확정된 모임 카드에 표시할 장소를 적어주세요.
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="닫기"
            style={{
              width: 32,
              height: 32,
              borderRadius: 10,
              border: "none",
              background: "#f8fafc",
              color: "#64748b",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: isSubmitting ? "not-allowed" : "pointer",
              opacity: isSubmitting ? 0.6 : 1,
            }}
          >
            <X size={17} />
          </button>
        </div>

        <input
          autoFocus
          type="text"
          value={place}
          maxLength={80}
          onChange={(event) => {
            setPlace(event.target.value);
            if (error) setError(null);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !isSubmitting) {
              handleConfirm();
            }
            if (event.key === "Escape" && !isSubmitting) {
              onClose();
            }
          }}
          placeholder="예: 강남역, 성수동 카페거리"
          style={{
            width: "100%",
            minHeight: 46,
            padding: "0 14px",
            borderRadius: 12,
            border: `1.5px solid ${error ? "#fca5a5" : "#cbd5e1"}`,
            outline: "none",
            fontSize: 23,
            fontWeight: 500,
            color: "#1e293b",
            background: "#ffffff",
            boxSizing: "border-box",
          }}
        />

        {error && (
          <span style={{ minHeight: 18, fontSize: 20, fontWeight: 600, color: "#dc2626" }}>
            {error}
          </span>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            style={{
              minHeight: 40,
              padding: "0 14px",
              borderRadius: 12,
              border: "1px solid #cbd5e1",
              background: "#ffffff",
              color: "#475569",
              fontSize: 21,
              fontWeight: 700,
              cursor: isSubmitting ? "not-allowed" : "pointer",
            }}
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isSubmitting}
            style={{
              minHeight: 40,
              padding: "0 16px",
              borderRadius: 12,
              border: "none",
              background: isSubmitting ? "#cbd5e1" : "#4f46e5",
              color: "#ffffff",
              fontSize: 21,
              fontWeight: 800,
              cursor: isSubmitting ? "not-allowed" : "pointer",
              transform: "translateZ(0)",
            }}
          >
            {isSubmitting ? "저장 중..." : "확인"}
          </button>
        </div>
      </div>
    </div>
  );
}

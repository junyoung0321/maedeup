import Link from "next/link";

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        background: "#f8fafc",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      <span style={{ fontSize: 56, lineHeight: 1 }}>🪢</span>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: "#111827", margin: 0 }}>
        페이지를 찾을 수 없어요
      </h1>
      <p style={{ fontSize: 14, color: "#94a3b8", margin: 0, textAlign: "center" }}>
        주소가 잘못됐거나 삭제된 페이지예요
      </p>
      <Link
        href="/"
        style={{
          marginTop: 8,
          padding: "10px 24px",
          borderRadius: 10,
          background: "#4f46e5",
          color: "#ffffff",
          fontSize: 14,
          fontWeight: 600,
          textDecoration: "none",
        }}
      >
        홈으로 돌아가기
      </Link>
    </div>
  );
}

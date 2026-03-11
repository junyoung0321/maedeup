"use client";

import { useAuth } from "./hooks/useAuth";
import LoginPage from "./components/LoginPage";
import SocialPane from "./components/SocialPane";
import AgentPane from "./components/AgentPane";
import DataPane from "./components/DataPane";

export default function HomePage() {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0d0d0d",
          color: "#444",
          fontSize: "13px",
        }}
      />
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <main
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* 상단 헤더 */}
      <div
        style={{
          height: "48px",
          borderBottom: "1px solid #1e1e1e",
          display: "flex",
          alignItems: "center",
          padding: "0 20px",
          gap: "8px",
          flexShrink: 0,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: "16px", color: "#e8e8e8" }}>
          매듭
        </span>
        <span style={{ color: "#444", fontSize: "12px" }}>Maedeup</span>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "12px" }}>
          {user.picture && (
            <img
              src={user.picture}
              alt={user.name}
              width={24}
              height={24}
              style={{ borderRadius: "50%" }}
            />
          )}
          <span style={{ color: "#aaa", fontSize: "13px" }}>{user.name}</span>
          <button
            onClick={logout}
            style={{
              background: "transparent",
              border: "1px solid #333",
              borderRadius: "6px",
              padding: "4px 10px",
              color: "#666",
              fontSize: "12px",
              cursor: "pointer",
            }}
          >
            로그아웃
          </button>
        </div>
      </div>

      {/* 3단 레이아웃 */}
      <div
        style={{
          flex: 1,
          display: "flex",
          overflow: "hidden",
        }}
      >
        <SocialPane sender={user.name} />
        <AgentPane sender={user.name} />
        <DataPane />
      </div>
    </main>
  );
}

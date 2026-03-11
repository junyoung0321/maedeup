import SocialPane from "./components/SocialPane";
import AgentPane from "./components/AgentPane";
import DataPane from "./components/DataPane";

export default function HomePage() {
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
      </div>

      {/* 3단 레이아웃 */}
      <div
        style={{
          flex: 1,
          display: "flex",
          overflow: "hidden",
        }}
      >
        <SocialPane />
        <AgentPane />
        <DataPane />
      </div>
    </main>
  );
}

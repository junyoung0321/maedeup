export default function AgentPane() {
  return (
    <section
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid #222",
        minWidth: 0,
      }}
    >
      <header
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #222",
          fontWeight: 600,
          fontSize: "13px",
          letterSpacing: "0.05em",
          color: "#aaa",
          textTransform: "uppercase",
        }}
      >
        Agent
      </header>
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#444",
            fontSize: "13px",
          }}
        >
          AI 에이전트 채팅 영역
        </div>

        {/* 입력창 자리 */}
        <div
          style={{
            border: "1px solid #2a2a2a",
            borderRadius: "8px",
            padding: "10px 14px",
            color: "#333",
            fontSize: "13px",
            background: "#161616",
          }}
        >
          메시지를 입력하세요...
        </div>
      </div>
    </section>
  );
}

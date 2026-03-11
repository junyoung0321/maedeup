export default function DataPane() {
  return (
    <section
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
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
        Data
      </header>
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#444",
          fontSize: "13px",
        }}
      >
        일정 · 장소 데이터 영역
      </div>
    </section>
  );
}

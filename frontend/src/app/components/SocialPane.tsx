export default function SocialPane() {
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
        Social
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
        소셜 피드 영역
      </div>
    </section>
  );
}

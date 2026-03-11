import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "매듭 (Maedeup)",
  description: "Social · Agent · Data — three panes, one workspace",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
        {children}
      </body>
    </html>
  );
}

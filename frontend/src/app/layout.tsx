import type { Metadata } from "next";
import Script from "next/script";
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
        <Script
          src={`//dapi.kakao.com/v2/maps/sdk.js?appkey=${process.env.NEXT_PUBLIC_KAKAO_MAP_KEY}&libraries=services&autoload=false`}
          strategy="beforeInteractive"
        />
      </body>
    </html>
  );
}

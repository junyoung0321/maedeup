import type { MetadataRoute } from "next";

// 매듭 PWA 매니페스트 — 설치형 앱(standalone) + TWA 래핑 대상.
// start_url은 모바일 앱뷰(/m). 색상은 브랜드 인디고(#4f46e5).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "매듭 — AI 모임 플래너",
    short_name: "매듭",
    description: "AI와 함께하는 똑똑한 모임 일정·장소 조율. 채팅만 하면 안 되는 날을 알아서 빼고 일정을 추천해줘요.",
    id: "/m",
    start_url: "/m",
    scope: "/",
    display: "standalone",
    display_override: ["standalone", "minimal-ui"],
    orientation: "portrait",
    background_color: "#ffffff",
    theme_color: "#4f46e5",
    lang: "ko",
    dir: "ltr",
    categories: ["productivity", "social", "lifestyle"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-192-maskable.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "새 모임 만들기", short_name: "새 모임", url: "/m/meeting/setup", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "내 모임", short_name: "모임", url: "/m/schedule", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  };
}

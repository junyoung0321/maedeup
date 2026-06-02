/** @type {import('next').NextConfig} */
const nextConfig = {
  trailingSlash: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "*.daumcdn.net" },
      { protocol: "https", hostname: "dapi.kakao.com" },
    ],
  },
  async headers() {
    // 카카오맵 SDK 스크립트 도메인 허용: dapi.kakao.com, *.daumcdn.net
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "script-src 'self' 'unsafe-eval' 'unsafe-inline' dapi.kakao.com *.daumcdn.net;",
          },
        ],
      },
      {
        // 서비스워커는 항상 최신 — 캐시 금지
        source: "/sw.js",
        headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }],
      },
    ];
  },
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

// PWA — @ducanh2912/next-pwa (App Router). dev에선 비활성(개발 캐시 방지),
// production 빌드에서만 SW 생성. 동적 데이터(API/WS)는 캐시하지 않음.
const withPWA = require("@ducanh2912/next-pwa").default({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
  reloadOnOnline: true,
  cacheOnFrontEndNav: true,
  aggressiveFrontEndNavCaching: true,
  fallbacks: {
    // 오프라인 시 보여줄 페이지
    document: "/offline",
  },
  workboxOptions: {
    disableDevLogs: true,
    navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
    runtimeCaching: [
      {
        // 정적 자산(폰트/이미지/아이콘)만 캐시 — 데이터는 fresh 유지
        urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp|ico|woff2?|ttf)$/i,
        handler: "StaleWhileRevalidate",
        options: { cacheName: "static-assets", expiration: { maxEntries: 120, maxAgeSeconds: 30 * 24 * 60 * 60 } },
      },
      {
        // Next.js 빌드 산출물(해시 파일)
        urlPattern: /\/_next\/static\/.*/i,
        handler: "CacheFirst",
        options: { cacheName: "next-static", expiration: { maxEntries: 200, maxAgeSeconds: 30 * 24 * 60 * 60 } },
      },
      {
        // 페이지 내비게이션: 네트워크 우선, 실패 시 캐시(오프라인 대비)
        urlPattern: ({ request, url }) =>
          request.mode === "navigate" && !url.pathname.startsWith("/api") && !url.pathname.startsWith("/ws"),
        handler: "NetworkFirst",
        options: { cacheName: "pages", networkTimeoutSeconds: 5, expiration: { maxEntries: 60, maxAgeSeconds: 24 * 60 * 60 } },
      },
      {
        // API/소켓은 절대 캐시 안 함 — 항상 네트워크 (실시간 데이터 stale 방지)
        urlPattern: /^\/(api|ws)\//i,
        handler: "NetworkOnly",
      },
    ],
  },
});

module.exports = withPWA(nextConfig);

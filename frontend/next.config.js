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
// 실시간 앱(WS/라이브 데이터) — SW는 '설치 가능 + 앱셸/오프라인'에만 쓰고
// 동적 데이터는 절대 건드리지 않는다(stale 방지). 공격적 페이지 캐싱은 끈다.
const withPWA = require("@ducanh2912/next-pwa").default({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
  reloadOnOnline: true,
  cacheOnFrontEndNav: false,
  aggressiveFrontEndNavCaching: false,
  workboxOptions: {
    disableDevLogs: true,
    // SW 업데이트 즉시 활성화 — 옛 SW가 남아 stale 서빙하는 것 방지
    skipWaiting: true,
    clientsClaim: true,
    navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
    runtimeCaching: [
      {
        // ★ API/소켓(상대·절대 URL 모두): 절대 캐시 안 함. pathname 기준이라
        //   http://<backend>/api/... 같은 절대 URL도 확실히 NetworkOnly.
        urlPattern: ({ url }) =>
          url.pathname.startsWith("/api/") ||
          url.pathname.startsWith("/ws/") ||
          /\/api\//.test(url.pathname),
        handler: "NetworkOnly",
      },
      {
        // 정적 자산(폰트/이미지/아이콘)만 캐시
        urlPattern: ({ request, url }) =>
          !url.pathname.startsWith("/api/") &&
          /\.(?:png|jpg|jpeg|svg|gif|webp|ico|woff2?|ttf)$/i.test(url.pathname),
        handler: "StaleWhileRevalidate",
        options: { cacheName: "static-assets", expiration: { maxEntries: 120, maxAgeSeconds: 30 * 24 * 60 * 60 } },
      },
      {
        // Next.js 빌드 산출물(해시 파일) — 불변
        urlPattern: /\/_next\/static\/.*/i,
        handler: "CacheFirst",
        options: { cacheName: "next-static", expiration: { maxEntries: 200, maxAgeSeconds: 30 * 24 * 60 * 60 } },
      },
      {
        // 페이지 내비게이션: 항상 네트워크 우선(온라인이면 fresh), 실패 시만 캐시
        urlPattern: ({ request, url }) =>
          request.mode === "navigate" && !url.pathname.startsWith("/api/") && !url.pathname.startsWith("/ws/"),
        handler: "NetworkFirst",
        options: { cacheName: "pages", networkTimeoutSeconds: 4, expiration: { maxEntries: 50, maxAgeSeconds: 12 * 60 * 60 } },
      },
    ],
  },
  fallbacks: { document: "/offline" },
});

module.exports = withPWA(nextConfig);

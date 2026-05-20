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

module.exports = nextConfig;

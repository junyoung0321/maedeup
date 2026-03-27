import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f8faff",
          100: "#c7d2fe",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
        },
        accent: {
          50: "#cff9fe",
          100: "#a2f4fd",
          300: "#5ed3e8",
          400: "#22d3ee",
        },
      },
      fontFamily: {
        pretendard: ["Pretendard Variable", "Pretendard", "Noto Sans KR", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;

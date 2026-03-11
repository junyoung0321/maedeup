# ── 1. deps: 의존성 설치 ──────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./
RUN \
  if [ -f package-lock.json ]; then npm ci; \
  elif [ -f yarn.lock ];       then yarn install --frozen-lockfile; \
  elif [ -f pnpm-lock.yaml ];  then corepack enable pnpm && pnpm install --frozen-lockfile; \
  else npm install; \
  fi

# ── 2. builder: Next.js 빌드 ─────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG BACKEND_URL=http://fastapi-app:8000
ENV BACKEND_URL=$BACKEND_URL

RUN npm run build

# ── 3. runner: 프로덕션 실행 ──────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

CMD ["npm", "run", "start"]

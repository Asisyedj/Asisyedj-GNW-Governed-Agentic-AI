# syntax=docker/dockerfile:1
FROM node:20-bookworm-slim AS build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json* ./
RUN npm ci
COPY tsconfig.json vite.config.ts vitest.config.ts ./
COPY src ./src
COPY tests ./tests
RUN npm run typecheck && npm run build

FROM node:20-bookworm-slim AS deps
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev && npm cache clean --force

FROM node:20-bookworm-slim AS runtime
ENV NODE_ENV=production PORT=8787 DATA_DIR=/data
ENV NODE_OPTIONS=--disable-proto=throw
WORKDIR /app
RUN useradd --system --uid 10001 --create-home gnw && mkdir -p /data && chown -R gnw:gnw /data
COPY --from=deps  --chown=gnw:gnw /app/node_modules ./node_modules
COPY --from=build --chown=gnw:gnw /app/dist ./dist
COPY --chown=gnw:gnw package.json ./
USER gnw
EXPOSE 8787
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8787)+'/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "dist/server/index.js"]

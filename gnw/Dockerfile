# syntax=docker/dockerfile:1
# Node.js 22.23.4 LTS on Alpine 3.23; immutable multi-arch manifest digest.
ARG NODE_IMAGE=node:22.23.4-alpine3.23@sha256:6abbcf5dd6b231da109bcde1181db1d92bf78015ae1a9514d9807c1f857869db
ARG ALPINE_IMAGE=alpine:3.23.7@sha256:ff7f0c727dd796aa36787bfcd9a64bf35a6ce72a73451b3359fde849b6703d63

FROM ${NODE_IMAGE} AS build
WORKDIR /app
RUN apk upgrade --no-cache && apk add --no-cache python3 make g++ \
 && musl_ver="$(apk list --installed musl | sed -n '1s/^musl-\([^ ]*\).*/\1/p')" \
 && test -n "$musl_ver" \
 && test "$(apk version -t "$musl_ver" "1.2.5-r24")" != "<"
COPY package.json package-lock.json* ./
RUN npm ci
COPY tsconfig.json vite.config.ts vitest.config.ts ./
COPY src ./src
COPY tests ./tests
RUN npm run typecheck && npm run build

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
RUN apk upgrade --no-cache && apk add --no-cache python3 make g++ \
 && musl_ver="$(apk list --installed musl | sed -n '1s/^musl-\([^ ]*\).*/\1/p')" \
 && test -n "$musl_ver" \
 && test "$(apk version -t "$musl_ver" "1.2.5-r24")" != "<"
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev && npm cache clean --force

FROM ${ALPINE_IMAGE} AS runtime
ENV NODE_ENV=production PORT=8787 DATA_DIR=/data
ENV NODE_OPTIONS=--disable-proto=throw
WORKDIR /app
RUN apk upgrade --no-cache && apk add --no-cache ca-certificates-bundle libstdc++ \
 && musl_ver="$(apk list --installed musl | sed -n '1s/^musl-\([^ ]*\).*/\1/p')" \
 && test -n "$musl_ver" \
 && test "$(apk version -t "$musl_ver" "1.2.5-r24")" != "<" \
 && addgroup -S -g 10001 gnw \
 && adduser -S -D -H -u 10001 -G gnw gnw \
 && mkdir -p /data && chown -R gnw:gnw /data
COPY --from=build /usr/local/bin/node /usr/local/bin/node
COPY --from=deps  --chown=gnw:gnw /app/node_modules ./node_modules
COPY --from=build --chown=gnw:gnw /app/dist ./dist
COPY --chown=gnw:gnw package.json ./
USER gnw
RUN node --version | grep -qx v22.23.4
EXPOSE 8787
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8787)+'/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "dist/server/index.js"]

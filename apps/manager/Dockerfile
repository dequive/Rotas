FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS dependencies

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/manager/package.json ./apps/manager/package.json
COPY apps/driver/package.json ./apps/driver/package.json
COPY packages/http-contract/package.json ./packages/http-contract/package.json
RUN --mount=type=cache,target=/root/.npm npm ci --include=optional \
    && test -f /workspace/node_modules/@next/swc-linux-x64-gnu/next-swc.linux-x64-gnu.node


FROM dependencies AS builder

ARG ROTAS_VERSION=dev
ARG ROTAS_REVISION=unknown
ENV ROTAS_VERSION="${ROTAS_VERSION}" \
    ROTAS_REVISION="${ROTAS_REVISION}"

COPY apps/manager ./apps/manager
COPY packages/http-contract ./packages/http-contract
RUN --network=none npm --workspace apps/manager run build


FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS runtime

ARG ROTAS_VERSION=dev
ARG ROTAS_REVISION=unknown

LABEL org.opencontainers.image.title="ROTAS Manager" \
      org.opencontainers.image.version="${ROTAS_VERSION}" \
      org.opencontainers.image.revision="${ROTAS_REVISION}" \
      org.opencontainers.image.source="ROTAS"

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app
COPY --from=builder --chown=node:node /workspace/apps/manager/.next/standalone ./
COPY --from=builder --chown=node:node /workspace/apps/manager/.next/static ./apps/manager/.next/static

USER node
EXPOSE 3000
CMD ["node", "apps/manager/server.js"]

FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS builder

ARG VITE_ROTAS_API_BASE_URL
ARG ROTAS_VERSION=dev
ARG ROTAS_REVISION=unknown

ENV VITE_ROTAS_API_BASE_URL="${VITE_ROTAS_API_BASE_URL}" \
    VITE_ROTAS_VERSION="${ROTAS_VERSION}" \
    VITE_ROTAS_REVISION="${ROTAS_REVISION}"

WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/manager/package.json ./apps/manager/package.json
COPY apps/driver/package.json ./apps/driver/package.json
COPY packages/http-contract/package.json ./packages/http-contract/package.json
RUN --mount=type=cache,target=/root/.npm npm ci
COPY apps/driver ./apps/driver
COPY packages/http-contract ./packages/http-contract
RUN test -n "${VITE_ROTAS_API_BASE_URL}" \
    && npm --workspace apps/driver run build


FROM caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d AS runtime

ARG ROTAS_VERSION=dev
ARG ROTAS_REVISION=unknown

LABEL org.opencontainers.image.title="ROTAS Driver PWA" \
      org.opencontainers.image.version="${ROTAS_VERSION}" \
      org.opencontainers.image.revision="${ROTAS_REVISION}" \
      org.opencontainers.image.source="ROTAS"

COPY infra/staging/Driver.Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /workspace/apps/driver/dist /srv

USER 1000:1000
EXPOSE 8080

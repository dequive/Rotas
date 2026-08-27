FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "${VIRTUAL_ENV}"
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /build
COPY backend/pyproject.toml backend/README.md backend/requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip==26.1.2 setuptools==83.0.0 wheel==0.47.0 \
    && pip install --require-hashes --requirement requirements.lock

COPY backend/app ./app
RUN pip install --no-deps --no-build-isolation . \
    && pip check


FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93 AS runtime

ARG ROTAS_VERSION=dev
ARG ROTAS_REVISION=unknown

LABEL org.opencontainers.image.title="ROTAS Backend" \
      org.opencontainers.image.version="${ROTAS_VERSION}" \
      org.opencontainers.image.revision="${ROTAS_REVISION}" \
      org.opencontainers.image.source="ROTAS"

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

RUN groupadd --gid 10001 rotas \
    && useradd --uid 10001 --gid rotas --create-home --shell /usr/sbin/nologin rotas

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=rotas:rotas backend/alembic.ini ./
COPY --chown=rotas:rotas backend/alembic ./alembic
COPY --chown=rotas:rotas backend/app ./app
COPY --chown=root:root infra/staging/load-backend-secrets.sh /usr/local/bin/rotas-entrypoint
RUN chmod 0555 /usr/local/bin/rotas-entrypoint

USER 10001:10001
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/rotas-entrypoint"]
CMD ["gunicorn", "--config", "python:app.gunicorn_conf", "--no-control-socket", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "--timeout", "30", "--bind", "0.0.0.0:8000", "app.main:app"]

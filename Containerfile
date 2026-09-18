# syntax=docker/dockerfile:1
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS frontend
WORKDIR /build/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS python-builder
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake ninja-build \
    && rm -rf /var/lib/apt/lists/*
RUN CMAKE_BUILD_PARALLEL_LEVEL=1 CMAKE_ARGS="-DGGML_NATIVE=OFF" \
    pip install --no-cache-dir \
    cryptography==50.0.1 fastapi==0.141.1 pydantic==2.13.5 'uvicorn[standard]==0.53.0' \
    llama-cpp-python==0.3.16
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps . \
    && rm -rf "$VIRTUAL_ENV"/lib/python3.12/site-packages/pip* "$VIRTUAL_ENV"/bin/pip*

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS assessor-model
ARG ASSESSOR_URL="https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF/resolve/593b5a2e04c8f3e4ee880263f93e0bd2901ad47f/smollm2-360m-instruct-q8_0.gguf?download=true"
ARG ASSESSOR_SHA256="48ab3034d0dd401fbc721eb1df3217902fee7dab9078992d66431f09b7750201"
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /models \
    # Some Podman VMs do not inherit the host's enterprise/intercept CA. The
    # pinned digest below remains the hard integrity and identity boundary.
    && curl --fail --insecure --location --retry 3 "$ASSESSOR_URL" -o /models/assessor.gguf \
    && echo "$ASSESSOR_SHA256  /models/assessor.gguf" | sha256sum -c -

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROUTELLECT_DATA_DIR=/data \
    ROUTELLECT_ASSESSOR_MODEL=/opt/routellect/models/assessor.gguf \
    ROUTELLECT_ASSESSOR_TIMEOUT=5.0
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 routellect \
    && useradd --system --uid 10001 --gid routellect --home-dir /nonexistent --shell /usr/sbin/nologin routellect \
    && mkdir -p /data /opt/routellect/models \
    && chown -R routellect:routellect /data
LABEL org.opencontainers.image.title="Routellect" \
      org.opencontainers.image.description="Private, advisory-only LLM model selection" \
      org.opencontainers.image.version="0.5.0" \
      org.opencontainers.image.licenses="Apache-2.0"
COPY --from=python-builder /opt/venv /opt/venv
COPY --from=assessor-model /models/assessor.gguf /opt/routellect/models/assessor.gguf
COPY --from=frontend /build/frontend/dist/ /opt/venv/lib/python3.12/site-packages/routellect/static/
USER 10001:10001
WORKDIR /data
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/ready', timeout=2)"]
ENTRYPOINT ["uvicorn", "routellect.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]

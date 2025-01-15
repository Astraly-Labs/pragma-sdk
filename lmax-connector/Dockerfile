FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

ENV PATH="/root/.local/bin:${PATH}"

FROM base AS builder

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    gcc \
    g++ \
    libssl-dev \
    swig \
    libgmp3-dev \
    pkg-config \
    pipx \
    stunnel4

RUN pipx install uv
COPY pragma-sdk/ /opt/pragma-sdk/
COPY lmax-connector/ /opt/lmax-connector/
WORKDIR /opt/lmax-connector
RUN uv sync

FROM base AS final
RUN apt-get update && \
    apt-get install --no-install-recommends -y stunnel4 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt /opt
VOLUME /opt/lmax-connector/config/

WORKDIR /opt/lmax-connector

# Create startup script
RUN echo '#!/bin/bash\n\
exec /usr/bin/stunnel stunnel.conf &\n\
sleep 2\n\
exec /opt/lmax-connector/.venv/bin/python3.12 -m lmax_connector' > /start.sh && \
chmod +x /start.sh

ENTRYPOINT ["/start.sh"]

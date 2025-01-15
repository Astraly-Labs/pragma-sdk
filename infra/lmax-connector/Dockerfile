FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

ENV PATH="/root/.local/bin:${PATH}"

FROM base as builder

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

RUN apt-get update && apt-get install -y bash curl && curl -1sLf \
'https://dl.cloudsmith.io/public/infisical/infisical-cli/setup.deb.sh' | bash \
&& apt-get update && apt-get install -y infisical

RUN pipx install uv
COPY pragma-sdk/ /opt/pragma-sdk/
COPY lmax-connector/ /opt/lmax-connector/
WORKDIR /opt/lmax-connector
RUN uv sync

FROM base as final

COPY --from=builder /usr/bin/infisical /usr/bin/infisical
COPY --from=builder /usr/bin/stunnel /usr/bin/stunnel
COPY --from=builder /usr/lib /usr/lib
COPY --from=builder /opt /opt
COPY infra/lmax-connector/entrypoint.sh /opt/lmax-connector/
WORKDIR /opt/lmax-connector
ENTRYPOINT ["bash","/opt/lmax-connector/entrypoint.sh"]

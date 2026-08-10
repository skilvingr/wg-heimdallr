# syntax=docker/dockerfile:1

ARG ALPINE_VERSION=3.24
FROM alpine:${ALPINE_VERSION}

ARG BUILD_DATE
ARG VERSION

LABEL org.opencontainers.image.title="wg-heimdallr"
LABEL org.opencontainers.image.description="A companion container that adds password + TOTP authentication (2FA / MFA) to any WireGuard setup"
LABEL org.opencontainers.image.url="https://github.com/skilvingr/wg-heimdallr"
LABEL org.opencontainers.image.source="https://github.com/skilvingr/wg-heimdallr"
LABEL org.opencontainers.image.licenses="GPL-3.0"
LABEL org.opencontainers.image.authors="skilfingr"
LABEL org.opencontainers.image.vendor="skilfingr"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"


RUN apk add --no-cache \
    bash \
    curl \
    libqrencode-tools \
    nftables \
    openssl \
    python3 \
    py3-pip \
    tini \
    wireguard-tools && \
  pip3 install --break-system-packages pyotp argon2-cffi && \
  apk del py3-pip && \
  rm -rf /usr/lib/python3.*/site-packages/pip* /root/.cache/pip && \
  find / -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null; true

COPY /root /

RUN chmod +x /app/heimdallr/init.sh /app/heimdallr/entrypoint.sh

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/app/heimdallr/entrypoint.sh"]

# syntax=docker/dockerfile:1

FROM ghcr.io/linuxserver/baseimage-alpine:3.24

# set version label
ARG BUILD_DATE
ARG VERSION
ARG WIREGUARD_RELEASE

LABEL org.opencontainers.image.title="wg-heimdallr"
LABEL org.opencontainers.image.description="A companion container that adds password + TOTP authentication (2FA / MFA) to any WireGuard setup"
LABEL org.opencontainers.image.url="https://github.com/skilfingr/wg-heimdallr"
LABEL org.opencontainers.image.source="https://github.com/skilfingr/wg-heimdallr"
LABEL org.opencontainers.image.licenses="GPL-3.0"
LABEL org.opencontainers.image.authors="skilfingr"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"


RUN \
  if [ -z "${WIREGUARD_RELEASE+x}" ]; then \
  WIREGUARD_RELEASE=$(curl -sL "http://dl-cdn.alpinelinux.org/alpine/v3.24/main/x86_64/APKINDEX.tar.gz" | tar -xz -C /tmp \
    && awk '/^P:wireguard-tools$/,/V:/' /tmp/APKINDEX | sed -n 2p | sed 's/^V://'); \
  fi && \
  echo "Using WireGuard release ${WIREGUARD_RELEASE}" && \
  echo "**** install dependencies ****" && \
  apk add --no-cache \
    libqrencode-tools \
    nftables \
    openssl \
    python3 \
    py3-pip \
    wireguard-tools==${WIREGUARD_RELEASE} && \
  printf "${VERSION}\nBuild-date: ${BUILD_DATE}" > /build_version && \
  echo "**** clean up ****" && \
  rm -rf \
    /tmp/*    

RUN pip3 install --break-system-packages pyotp qrcode Pillow argon2-cffi

# add local files
COPY /root /

RUN chmod +x /app/heimdallr/auth_server.py /app/heimdallr/cleanup.py /app/heimdallr/seed_admin.py

FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/tmp

RUN apt-get update && apt-get install -y --no-install-recommends \
    # LibreOffice — only the three components we use (skip Base, Draw, Math)
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    libreoffice-core \
    libreoffice-common \
    # Fonts for document rendering
    fonts-liberation \
    fonts-dejavu-core \
    fonts-noto-core \
    # CJK fonts — Simplified Chinese, Traditional Chinese, Japanese, Korean
    fonts-noto-cjk \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    fonts-arphic-ukai \
    fonts-arphic-uming \
    # Java runtime — required by LibreOffice for XLSX/XLS processing
    default-jre-headless \
    libreoffice-java-common \
    # clamav-daemon provides the clamdscan client binary; daemon runs in the sidecar
    clamav-daemon \
    clamdscan \
    # bsdtar (libarchive-tools) — used by the rarfile Python package for RAR extraction
    libarchive-tools \
    # weasyprint runtime deps (Pango, Cairo, GDK-PixBuf for HTML/CSS → PDF rendering)
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libharfbuzz-icu0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# fontconfig substitution: map Windows CJK font names to installed equivalents
COPY docker/99-cjk-subst.conf /etc/fonts/conf.d/99-cjk-subst.conf
RUN fc-cache -f

# Minimal client config so clamdscan knows where to find the clamd socket
RUN printf 'LocalSocket /run/clamav/clamd.sock\n' > /etc/clamav/clamd.conf

# Create non-root user
RUN groupadd --gid 1000 scrub && \
    useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/false scrub

# Install Python package
WORKDIR /app
COPY pyproject.toml ./
COPY scrub/ ./scrub/
RUN pip install --no-cache-dir .

USER scrub

ENTRYPOINT ["scrub"]

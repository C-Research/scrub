FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

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
    # clamav-daemon provides the clamdscan client binary; daemon runs in the sidecar
    clamav-daemon \
    clamdscan \
    && rm -rf /var/lib/apt/lists/*

# Minimal client config so clamdscan knows where to find the clamd socket
RUN printf 'LocalSocket /run/clamav/clamd.sock\n' > /etc/clamav/clamd.conf

# Disable LibreOffice Java integration system-wide
RUN mkdir -p /etc/libreoffice && \
    printf '[Bootstrap]\nJavaenabled=0\n' >> /etc/libreoffice/sofficerc

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

# Dockerfile for Horse Racing Tool Backend
# Optimized for Raspberry Pi 5 (ARM64)

FROM python:3.13-slim-bookworm

ARG TARGETARCH

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/New_York

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    wget \
    ca-certificates \
    libicu-dev \
    && rm -rf /var/lib/apt/lists/* \
    && case "${TARGETARCH:-arm64}" in \
        arm64) PS_ARCH=arm64 ;; \
        amd64) PS_ARCH=x64 ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" && exit 1 ;; \
      esac \
    && mkdir -p /opt/microsoft/powershell/7 \
    && wget -q "https://github.com/PowerShell/PowerShell/releases/download/v7.4.1/powershell-7.4.1-linux-${PS_ARCH}.tar.gz" \
    && tar -zxf "powershell-7.4.1-linux-${PS_ARCH}.tar.gz" -C /opt/microsoft/powershell/7 \
    && chmod +x /opt/microsoft/powershell/7/pwsh \
    && ln -s /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh \
    && ln -s /opt/microsoft/powershell/7/pwsh /usr/bin/powershell \
    && rm "powershell-7.4.1-linux-${PS_ARCH}.tar.gz"

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Expose Flask port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://127.0.0.1:5001/api/health/live', timeout=5)" || exit 1

# Run Flask backend
CMD ["python3", "backend/backend.py"]

FROM python:3.12-slim

# Install system dependencies + Node.js 18 + Vercel CLI in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl wget git vim nano ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g vercel \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Keep container alive
CMD ["tail", "-f", "/dev/null"]

FROM python:3.12-slim

WORKDIR /app

# Install system deps for yt-dlp, curl, etc
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Optional: playwright + chromium for JS-rendered pages
# RUN pip install playwright && playwright install chromium

COPY . .

ENTRYPOINT ["fusion"]

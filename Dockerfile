# Monster in the Closet: one container runs the API and serves the built app.
# Data (every closet's database, cutouts and renders, plus the shared model cache) lives in
# /data, which must be a persistent volume (see fly.toml) so a redeploy keeps it.

FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.14-slim
# OpenCV's runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY closet/ closet/
COPY server/ server/
COPY fixtures/ fixtures/
COPY --from=web /web/dist web/dist

# Safe defaults: demo mode, one closet per browser. fly.toml (or your host) switches on live
# mode with a daily spend cap. API keys come from the host's secrets, never the image.
ENV MONSTER_MODE=fixture \
    MONSTER_CLOSETS=device \
    MONSTER_VAR_DIR=/data \
    PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]

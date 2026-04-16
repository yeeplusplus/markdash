# ---- Stage 1: build Next.js static bundle ----
FROM node:20-alpine AS frontend-builder

WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/tsconfig.json frontend/next.config.js frontend/postcss.config.js \
     frontend/tailwind.config.ts frontend/next-env.d.ts ./
COPY frontend/app ./app

RUN npm run build

# ---- Stage 2: FastAPI runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api/app ./app

# static bundle from frontend-builder
COPY --from=frontend-builder /fe/out /app/static

EXPOSE 80

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]

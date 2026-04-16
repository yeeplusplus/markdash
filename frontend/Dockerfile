FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY tsconfig.json next.config.js postcss.config.js tailwind.config.ts next-env.d.ts ./
COPY app ./app

RUN npm run build

FROM scratch AS export
COPY --from=builder /app/out /out

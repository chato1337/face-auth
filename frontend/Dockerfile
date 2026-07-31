# syntax=docker/dockerfile:1
FROM oven/bun:1.3-alpine

WORKDIR /app

COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

COPY . .

ENV FRONTEND_PORT=5173
EXPOSE 5173

CMD ["sh", "-c", "bun run dev -- --host 0.0.0.0 --port ${FRONTEND_PORT:-5173}"]

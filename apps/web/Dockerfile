# syntax=docker/dockerfile:1
# CloudNova PaymentOps - web (Next.js) image.
# Standalone output keeps the runtime minimal. Non-root, no secrets embedded.
# Build context MUST be apps/web:
#   docker build -f apps/web/Dockerfile -t paymentops-web:dev .
FROM node:22-alpine AS builder

WORKDIR /app

# Use corepack-managed pnpm for reproducible installs.
RUN corepack enable

COPY package.json pnpm-lock.yaml ./
COPY pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
# Next 15 requires a build cache; disable telemetry.
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

WORKDIR /app

# Non-root runtime user.
RUN addgroup --system nodejs && adduser --system --ingroup nodejs nextjs

# Standalone server + static assets + public dir.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER nextjs

EXPOSE 3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]

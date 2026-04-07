# syntax=docker/dockerfile:1
# ========================================
# EllinCRM - Frontend
# Production Dockerfile (Multi-stage Build)
# ========================================
# Author: Kypraios Chariton
# ========================================

# ------------------------------
# Stage 1: Dependencies
# ------------------------------
FROM node:22-alpine AS deps
WORKDIR /app

# Install dependencies only when needed
COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps

# ------------------------------
# Stage 2: Builder
# ------------------------------
FROM node:22-alpine AS builder
WORKDIR /app

# Build arguments for Next.js public env vars (must be set at build time)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/notifications
ENV NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Set environment for build
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Build the application
RUN npm run build

# ------------------------------
# Stage 3: Production
# ------------------------------
FROM node:22-alpine AS production

LABEL maintainer="Kypraios Chariton"
LABEL project="EllinCRM - Frontend"
LABEL version="1.0.0"

WORKDIR /app

# Set environment variables
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built assets from builder
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000 || exit 1

# Start the application
CMD ["node", "server.js"]

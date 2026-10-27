# Multi-stage build for Next.js frontend

# Stage 1: Dependencies
FROM registry.access.redhat.com/ubi9/nodejs-18:latest AS deps
USER 0
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

# Stage 2: Builder
FROM registry.access.redhat.com/ubi9/nodejs-18:latest AS builder
USER 0
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public && npm run build

# Stage 3: Runner (OpenShift compatible)
FROM registry.access.redhat.com/ubi9/nodejs-18-minimal:latest AS runner
WORKDIR /app

# UBI images already have proper user setup for OpenShift
# Prepare directories with proper permissions
USER 0
RUN mkdir -p /app/.next && \
    chown -R 1001:0 /app && \
    chmod -R g+rwX /app

# Copy built application
COPY --from=builder --chown=1001:0 /app/public ./public
COPY --from=builder --chown=1001:0 /app/.next/standalone ./
COPY --from=builder --chown=1001:0 /app/.next/static ./.next/static

# Switch to non-root user (default UBI user)
USER 1001

# Expose port
EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Run the application
CMD ["node", "server.js"]
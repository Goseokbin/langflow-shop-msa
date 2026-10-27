#!/bin/bash

# Script to add OpenTelemetry packages to all Python services
# This script adds OTEL dependencies to requirements.txt files

OTEL_PACKAGES="
# OpenTelemetry for Instana monitoring
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-instrumentation-fastapi==0.42b0
opentelemetry-instrumentation-sqlalchemy==0.42b0
opentelemetry-instrumentation-requests==0.42b0
opentelemetry-exporter-otlp==1.21.0"

SERVICES=("product-service" "order-service" "cart-service" "api-gateway")

for service in "${SERVICES[@]}"; do
    echo "Adding OTEL packages to $service..."
    echo "$OTEL_PACKAGES" >> "services/$service/requirements.txt"
    echo "✅ Updated services/$service/requirements.txt"
done

echo ""
echo "🎉 All services updated with OpenTelemetry packages!"
echo "Next steps:"
echo "1. Update main.py files to initialize OTEL"
echo "2. Update deployment YAML files with OTEL env vars"
echo "3. Rebuild and push images"

# Made with Bob

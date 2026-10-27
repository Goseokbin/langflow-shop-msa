#!/bin/bash

# Podman 이미지 빌드 및 푸시 스크립트
# OpenShift 배포를 위한 이미지 생성 (linux/amd64 플랫폼)

set -e

# 스크립트가 실행되는 위치와 관계없이 프로젝트 루트로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

REGISTRY="quay.io/seokbin/langflow-shop"
VERSION="${1:-latest}"
PLATFORM="linux/amd64"

echo "🚀 Building and pushing images to ${REGISTRY} using Podman"
echo "📦 Version: ${VERSION}"
echo "🖥️  Platform: ${PLATFORM}"
echo ""

# User Service
if [ -f "${PROJECT_ROOT}/services/user-service/Dockerfile" ]; then
  echo "📦 Building user-service..."
  cd "${PROJECT_ROOT}/services/user-service"
  podman build --platform ${PLATFORM} -t ${REGISTRY}:user-${VERSION} .
  echo "⬆️  Pushing user-service..."
  podman push ${REGISTRY}:user-${VERSION}
  echo "✅ user-service complete"
  echo ""
else
  echo "⚠️  Skipping user-service (no Dockerfile found)"
  echo ""
fi

# Product Service
if [ -f "${PROJECT_ROOT}/services/product-service/Dockerfile" ]; then
  echo "📦 Building product-service..."
  cd "${PROJECT_ROOT}/services/product-service"
  podman build --platform ${PLATFORM} -t ${REGISTRY}:product-${VERSION} .
  echo "⬆️  Pushing product-service..."
  podman push ${REGISTRY}:product-${VERSION}
  echo "✅ product-service complete"
  echo ""
else
  echo "⚠️  Skipping product-service (no Dockerfile found)"
  echo ""
fi

# Cart Service
if [ -f "${PROJECT_ROOT}/services/cart-service/Dockerfile" ]; then
  echo "📦 Building cart-service..."
  cd "${PROJECT_ROOT}/services/cart-service"
  podman build --platform ${PLATFORM} -t ${REGISTRY}:cart-${VERSION} .
  echo "⬆️  Pushing cart-service..."
  podman push ${REGISTRY}:cart-${VERSION}
  echo "✅ cart-service complete"
  echo ""
else
  echo "⚠️  Skipping cart-service (no Dockerfile found)"
  echo ""
fi

# Order Service
if [ -f "${PROJECT_ROOT}/services/order-service/Dockerfile" ]; then
  echo "📦 Building order-service..."
  cd "${PROJECT_ROOT}/services/order-service"
  podman build --platform ${PLATFORM} -t ${REGISTRY}:order-${VERSION} .
  echo "⬆️  Pushing order-service..."
  podman push ${REGISTRY}:order-${VERSION}
  echo "✅ order-service complete"
  echo ""
else
  echo "⚠️  Skipping order-service (no Dockerfile found)"
  echo ""
fi

# Langflow AI Service
if [ -f "${PROJECT_ROOT}/services/langflow-ai-service/Dockerfile" ]; then
  echo "📦 Building langflow-ai-service..."
  cd "${PROJECT_ROOT}/services/langflow-ai-service"
  podman build --platform ${PLATFORM} -t ${REGISTRY}:langflow-ai-${VERSION} .
  echo "⬆️  Pushing langflow-ai-service..."
  podman push ${REGISTRY}:langflow-ai-${VERSION}
  echo "✅ langflow-ai-service complete"
  echo ""
else
  echo "⚠️  Skipping langflow-ai-service (no Dockerfile found)"
  echo ""
fi

# API Gateway
if [ -f "${PROJECT_ROOT}/services/api-gateway/Dockerfile" ]; then
  echo "📦 Building api-gateway..."
  cd "${PROJECT_ROOT}/services/api-gateway"
  podman build --platform ${PLATFORM} -t ${REGISTRY}:api-gateway-${VERSION} .
  echo "⬆️  Pushing api-gateway..."
  podman push ${REGISTRY}:api-gateway-${VERSION}
  echo "✅ api-gateway complete"
  echo ""
else
  echo "⚠️  Skipping api-gateway (no Dockerfile found)"
  echo ""
fi

# Frontend
if [ -f "${PROJECT_ROOT}/services/frontend/Dockerfile" ]; then
  echo "📦 Building frontend..."
  cd "${PROJECT_ROOT}/services/frontend"
  podman build --platform ${PLATFORM} -t ${REGISTRY}:frontend-${VERSION} .
  echo "⬆️  Pushing frontend..."
  podman push ${REGISTRY}:frontend-${VERSION}
  echo "✅ frontend complete"
  echo ""
else
  echo "⚠️  Skipping frontend (no Dockerfile found)"
  echo ""
fi

echo "🎉 All images built and pushed successfully!"
echo ""
echo "📋 Image List:"
echo "  - ${REGISTRY}:user-${VERSION}"
echo "  - ${REGISTRY}:product-${VERSION}"
echo "  - ${REGISTRY}:cart-${VERSION}"
echo "  - ${REGISTRY}:order-${VERSION}"
echo "  - ${REGISTRY}:langflow-ai-${VERSION}"
echo "  - ${REGISTRY}:api-gateway-${VERSION}"
echo "  - ${REGISTRY}:frontend-${VERSION}"
echo ""
echo "💡 Usage:"
echo "  ./scripts/build-and-push-images.sh          # Build with 'latest' tag"
echo "  ./scripts/build-and-push-images.sh v1.0.0   # Build with specific version"

# Made with Bob

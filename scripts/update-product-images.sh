#!/bin/bash

# Update product images script
set -e

API_URL="https://api-gateway-shopping-mall.apps.itz-895szy.infra01-lb.syd05.techzone.ibm.com"

# Login to get token
echo "🔐 Logging in..."
TOKEN=$(curl -s -X POST "${API_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin"}' | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "❌ Login failed"
  exit 1
fi

echo "✅ Login successful"
echo ""

# Get all products
echo "📦 Fetching products..."
PRODUCTS=$(curl -s "${API_URL}/api/products" -H "Authorization: Bearer $TOKEN")

# Function to get image URL for product name
get_image_url() {
  case "$1" in
    "Laptop"|"Laptop Pro 15")
      echo "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400"
      ;;
    "Smartphone")
      echo "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400"
      ;;
    "Headphones")
      echo "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400"
      ;;
    "Tablet")
      echo "https://images.unsplash.com/photo-1561154464-82e9adf32764?w=400"
      ;;
    "Smartwatch")
      echo "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400"
      ;;
    "USB-C Hub")
      echo "https://images.unsplash.com/photo-1625948515291-69613efd103f?w=400"
      ;;
    "Wireless Mouse")
      echo "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400"
      ;;
    "Keyboard"|"Mechanical Keyboard")
      echo "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400"
      ;;
    "Monitor"|"4K Monitor")
      echo "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400"
      ;;
    "Webcam")
      echo "https://images.unsplash.com/photo-1587825140708-dfaf72ae4b04?w=400"
      ;;
    *)
      # Default tech product image
      echo "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=400"
      ;;
  esac
}

# Update each product
echo "$PRODUCTS" | jq -c '.[]' | while read -r product; do
  PRODUCT_ID=$(echo "$product" | jq -r '.id')
  PRODUCT_NAME=$(echo "$product" | jq -r '.name')
  CURRENT_IMAGE=$(echo "$product" | jq -r '.image_url')
  
  # Skip if already has image
  if [ "$CURRENT_IMAGE" != "null" ] && [ -n "$CURRENT_IMAGE" ]; then
    echo "⏭️  Skipping $PRODUCT_NAME (already has image)"
    continue
  fi
  
  # Get image URL for this product
  IMAGE_URL=$(get_image_url "$PRODUCT_NAME")
  
  if [ -z "$IMAGE_URL" ]; then
    echo "⚠️  No image URL found for $PRODUCT_NAME"
    continue
  fi
  
  echo "🖼️  Updating $PRODUCT_NAME..."
  
  # Update product with image URL
  curl -s -X PUT "${API_URL}/api/products/${PRODUCT_ID}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"image_url\": \"$IMAGE_URL\"}" > /dev/null
  
  echo "✅ Updated $PRODUCT_NAME"
done

echo ""
echo "🎉 All products updated!"

# Made with Bob
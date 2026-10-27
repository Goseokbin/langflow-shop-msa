#!/bin/bash

# Seed more products script
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

# Array of products to add
declare -a products=(
  '{"name":"iPhone 14 Pro","description":"Latest Apple smartphone with A16 Bionic chip","price":"999.99","category":"Electronics","inventory":50,"image_url":"https://images.unsplash.com/photo-1678685888221-cda773a3dcdb?w=400"}'
  '{"name":"Samsung Galaxy S23","description":"Flagship Android phone with amazing camera","price":"899.99","category":"Electronics","inventory":45,"image_url":"https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=400"}'
  '{"name":"iPad Air","description":"Powerful tablet for work and play","price":"599.99","category":"Electronics","inventory":35,"image_url":"https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=400"}'
  '{"name":"MacBook Air M2","description":"Thin and light laptop with M2 chip","price":"1199.99","category":"Electronics","inventory":25,"image_url":"https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=400"}'
  '{"name":"AirPods Pro","description":"Active noise cancellation wireless earbuds","price":"249.99","category":"Accessories","inventory":100,"image_url":"https://images.unsplash.com/photo-1606841837239-c5a1a4a07af7?w=400"}'
  '{"name":"Sony WH-1000XM5","description":"Industry-leading noise canceling headphones","price":"399.99","category":"Accessories","inventory":60,"image_url":"https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=400"}'
  '{"name":"Apple Watch Series 8","description":"Advanced health and fitness tracking","price":"399.99","category":"Wearables","inventory":40,"image_url":"https://images.unsplash.com/photo-1434494878577-86c23bcb06b9?w=400"}'
  '{"name":"Nintendo Switch OLED","description":"Hybrid gaming console with vibrant display","price":"349.99","category":"Gaming","inventory":30,"image_url":"https://images.unsplash.com/photo-1578303512597-81e6cc155b3e?w=400"}'
  '{"name":"PlayStation 5","description":"Next-gen gaming console","price":"499.99","category":"Gaming","inventory":20,"image_url":"https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=400"}'
  '{"name":"Xbox Series X","description":"Powerful 4K gaming console","price":"499.99","category":"Gaming","inventory":20,"image_url":"https://images.unsplash.com/photo-1621259182978-fbf93132d53d?w=400"}'
  '{"name":"Canon EOS R6","description":"Professional mirrorless camera","price":"2499.99","category":"Cameras","inventory":15,"image_url":"https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=400"}'
  '{"name":"DJI Mini 3 Pro","description":"Compact and powerful drone","price":"759.99","category":"Drones","inventory":25,"image_url":"https://images.unsplash.com/photo-1473968512647-3e447244af8f?w=400"}'
  '{"name":"Logitech MX Master 3","description":"Advanced wireless mouse for productivity","price":"99.99","category":"Accessories","inventory":80,"image_url":"https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400"}'
  '{"name":"Keychron K8","description":"Wireless mechanical keyboard","price":"89.99","category":"Accessories","inventory":70,"image_url":"https://images.unsplash.com/photo-1595225476474-87563907a212?w=400"}'
  '{"name":"LG UltraWide Monitor","description":"34-inch curved ultrawide display","price":"599.99","category":"Monitors","inventory":30,"image_url":"https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400"}'
)

echo "📦 Adding products..."
echo ""

for product in "${products[@]}"; do
  PRODUCT_NAME=$(echo "$product" | jq -r '.name')
  
  # Check if product already exists
  EXISTING=$(curl -s "${API_URL}/api/products" -H "Authorization: Bearer $TOKEN" | jq -r ".[] | select(.name==\"$PRODUCT_NAME\") | .id")
  
  if [ -n "$EXISTING" ]; then
    echo "⏭️  Skipping $PRODUCT_NAME (already exists)"
    continue
  fi
  
  echo "➕ Adding $PRODUCT_NAME..."
  
  curl -s -X POST "${API_URL}/api/products" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$product" > /dev/null
  
  echo "✅ Added $PRODUCT_NAME"
done

echo ""
echo "🎉 All products added!"

# Made with Bob
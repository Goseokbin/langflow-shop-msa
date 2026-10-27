#!/bin/bash

# Seed products into the database
API_URL="https://api-gateway-shopping-mall.apps.itz-895szy.infra01-lb.syd05.techzone.ibm.com"

echo "🌱 Seeding products..."

# Product 1
curl -X POST "${API_URL}/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Laptop Pro 15",
    "description": "High-performance laptop with 16GB RAM and 512GB SSD",
    "price": 1299.99,
    "inventory": 50,
    "category": "Electronics"
  }' -k

echo ""

# Product 2
curl -X POST "${API_URL}/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Wireless Mouse",
    "description": "Ergonomic wireless mouse with precision tracking",
    "price": 29.99,
    "inventory": 200,
    "category": "Accessories"
  }' -k

echo ""

# Product 3
curl -X POST "${API_URL}/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "USB-C Hub",
    "description": "7-in-1 USB-C hub with HDMI, USB 3.0, and SD card reader",
    "price": 49.99,
    "inventory": 150,
    "category": "Accessories"
  }' -k

echo ""

# Product 4
curl -X POST "${API_URL}/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mechanical Keyboard",
    "description": "RGB mechanical keyboard with blue switches",
    "price": 89.99,
    "inventory": 75,
    "category": "Accessories"
  }' -k

echo ""

# Product 5
curl -X POST "${API_URL}/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "4K Monitor",
    "description": "27-inch 4K UHD monitor with HDR support",
    "price": 399.99,
    "inventory": 30,
    "category": "Electronics"
  }' -k

echo ""
echo "✅ Products seeded successfully!"

# Made with Bob

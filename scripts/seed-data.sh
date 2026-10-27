#!/bin/bash

# 더미 데이터 삽입 스크립트
# PostgreSQL에 샘플 상품 데이터 추가

set -e

NAMESPACE="shopping-mall"
POSTGRES_POD=$(oc get pod -n ${NAMESPACE} -l name=postgresql -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POSTGRES_POD" ]; then
  POSTGRES_POD=$(oc get pod -n ${NAMESPACE} -l deploymentconfig=postgresql -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
fi

if [ -z "$POSTGRES_POD" ]; then
  echo "❌ PostgreSQL pod not found"
  exit 1
fi

echo "🗄️  Found PostgreSQL pod: $POSTGRES_POD"
echo "📝 Inserting sample data..."

# Product 데이터 삽입
oc exec -n ${NAMESPACE} $POSTGRES_POD -- psql -U postgres -d product_db << 'EOF'
-- 기존 데이터 삭제 (있다면)
TRUNCATE TABLE products CASCADE;

-- 샘플 상품 데이터 삽입
INSERT INTO products (id, name, description, price, category, inventory, image_url, created_at, updated_at) VALUES
('prod-001', 'MacBook Pro 16"', 'Apple M3 Max chip, 36GB RAM, 1TB SSD. Perfect for developers and creators.', 2999.99, 'Electronics', 15, 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=400', NOW(), NOW()),
('prod-002', 'iPhone 15 Pro', 'A17 Pro chip, Titanium design, 256GB storage. The most powerful iPhone ever.', 1199.99, 'Electronics', 50, 'https://images.unsplash.com/photo-1592286927505-c0d0e0c5d7c0?w=400', NOW(), NOW()),
('prod-003', 'AirPods Pro', 'Active Noise Cancellation, Adaptive Audio, USB-C charging case.', 249.99, 'Electronics', 100, 'https://images.unsplash.com/photo-1606841837239-c5a1a4a07af7?w=400', NOW(), NOW()),
('prod-004', 'Sony WH-1000XM5', 'Industry-leading noise canceling headphones with premium sound quality.', 399.99, 'Electronics', 30, 'https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=400', NOW(), NOW()),
('prod-005', 'iPad Air', 'M2 chip, 11-inch Liquid Retina display, 128GB. Powerful and portable.', 599.99, 'Electronics', 40, 'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=400', NOW(), NOW()),
('prod-006', 'Samsung Galaxy S24 Ultra', 'Snapdragon 8 Gen 3, 12GB RAM, 512GB storage, S Pen included.', 1299.99, 'Electronics', 25, 'https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=400', NOW(), NOW()),
('prod-007', 'Dell XPS 15', 'Intel Core i7, 32GB RAM, 1TB SSD, 15.6" 4K OLED display.', 2199.99, 'Electronics', 20, 'https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=400', NOW(), NOW()),
('prod-008', 'Logitech MX Master 3S', 'Wireless mouse with ultra-fast scrolling and ergonomic design.', 99.99, 'Accessories', 75, 'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400', NOW(), NOW()),
('prod-009', 'Mechanical Keyboard RGB', 'Cherry MX switches, RGB backlight, aluminum frame. Perfect for gaming.', 149.99, 'Accessories', 60, 'https://images.unsplash.com/photo-1595225476474-87563907a212?w=400', NOW(), NOW()),
('prod-010', 'LG 27" 4K Monitor', 'IPS panel, HDR10, USB-C connectivity, height adjustable stand.', 449.99, 'Electronics', 35, 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400', NOW(), NOW()),
('prod-011', 'Bose SoundLink Flex', 'Portable Bluetooth speaker, waterproof, 12-hour battery life.', 149.99, 'Electronics', 45, 'https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=400', NOW(), NOW()),
('prod-012', 'Apple Watch Series 9', 'Always-On Retina display, health tracking, GPS, 41mm.', 399.99, 'Electronics', 55, 'https://images.unsplash.com/photo-1434494878577-86c23bcb06b9?w=400', NOW(), NOW()),
('prod-013', 'Nintendo Switch OLED', '7-inch OLED screen, enhanced audio, 64GB storage.', 349.99, 'Gaming', 40, 'https://images.unsplash.com/photo-1578303512597-81e6cc155b3e?w=400', NOW(), NOW()),
('prod-014', 'PlayStation 5', 'Ultra-high speed SSD, ray tracing, 4K gaming, 825GB storage.', 499.99, 'Gaming', 15, 'https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=400', NOW(), NOW()),
('prod-015', 'Xbox Series X', '12 teraflops GPU, 1TB SSD, 4K gaming at 120fps.', 499.99, 'Gaming', 18, 'https://images.unsplash.com/photo-1621259182978-fbf93132d53d?w=400', NOW(), NOW()),
('prod-016', 'Kindle Paperwhite', '6.8" display, adjustable warm light, waterproof, 16GB.', 139.99, 'Electronics', 80, 'https://images.unsplash.com/photo-1592496431122-2349e0fbc666?w=400', NOW(), NOW()),
('prod-017', 'GoPro HERO12', '5.3K video, HyperSmooth 6.0, waterproof to 33ft.', 399.99, 'Electronics', 30, 'https://images.unsplash.com/photo-1519638399535-1b036603ac77?w=400', NOW(), NOW()),
('prod-018', 'DJI Mini 3 Pro', 'Lightweight drone, 4K HDR video, 34-min flight time.', 759.99, 'Electronics', 12, 'https://images.unsplash.com/photo-1473968512647-3e447244af8f?w=400', NOW(), NOW()),
('prod-019', 'Anker PowerCore 20K', '20,000mAh portable charger, USB-C PD, charges 3 devices.', 59.99, 'Accessories', 120, 'https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=400', NOW(), NOW()),
('prod-020', 'USB-C Hub 7-in-1', 'HDMI, USB 3.0, SD/TF card reader, 100W PD charging.', 39.99, 'Accessories', 150, 'https://images.unsplash.com/photo-1625948515291-69613efd103f?w=400', NOW(), NOW());

SELECT COUNT(*) as total_products FROM products;
EOF

echo "✅ Sample products inserted successfully!"
echo ""
echo "📊 Summary:"
echo "  - 20 products added"
echo "  - Categories: Electronics, Accessories, Gaming"
echo "  - Total inventory: 1,000+ items"
echo ""
echo "🌐 You can now browse products on the frontend!"

# Made with Bob

#!/bin/bash

# Fix missing 'import os' in main.py files

SERVICES=("product-service" "order-service" "cart-service" "api-gateway")

for service in "${SERVICES[@]}"; do
    file="services/$service/app/main.py"
    echo "Fixing $file..."
    
    # Add 'import os' after 'import logging' if not already present
    if ! grep -q "^import os" "$file"; then
        sed -i '' '/^import logging$/a\
import os
' "$file"
        echo "  ✅ Added 'import os' to $file"
    else
        echo "  ⏭️  'import os' already exists in $file"
    fi
done

echo ""
echo "🎉 All files fixed!"

# Made with Bob

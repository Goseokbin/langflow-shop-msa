#!/bin/bash

# Fix missing 'engine' import in main.py files

SERVICES=("product-service" "order-service" "cart-service")

for service in "${SERVICES[@]}"; do
    file="services/$service/app/main.py"
    echo "Fixing $file..."
    
    # Change 'from .database import init_db' to 'from .database import init_db, engine'
    if grep -q "from .database import init_db$" "$file"; then
        sed -i '' 's/from \.database import init_db$/from .database import init_db, engine/' "$file"
        echo "  ✅ Added 'engine' import to $file"
    elif grep -q "from .database import init_db, engine" "$file"; then
        echo "  ⏭️  'engine' import already exists in $file"
    else
        echo "  ❌ Could not find database import in $file"
    fi
done

# api-gateway doesn't have database, so remove SQLAlchemy instrumentation
file="services/api-gateway/app/main.py"
echo "Fixing $file (removing SQLAlchemy instrumentation)..."
sed -i '' '/from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor/d' "$file"
sed -i '' '/SQLAlchemyInstrumentor().instrument(engine=engine)/d' "$file"
echo "  ✅ Removed SQLAlchemy instrumentation from $file"

echo ""
echo "🎉 All files fixed!"

# Made with Bob

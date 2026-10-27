#!/bin/bash

# Admin 사용자 생성 스크립트
# PostgreSQL에 직접 admin/admin 계정 생성

set -e

echo "🔐 Creating admin user in database..."

# PostgreSQL pod 이름 가져오기
POSTGRES_POD=$(oc get pods -n langflow-shop -l app=postgresql -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POSTGRES_POD" ]; then
  echo "❌ PostgreSQL pod not found. Make sure the database is deployed."
  exit 1
fi

echo "📦 Found PostgreSQL pod: $POSTGRES_POD"

# Python 스크립트로 비밀번호 해시 생성
HASHED_PASSWORD=$(python3 -c "
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
print(pwd_context.hash('admin'))
")

echo "🔑 Generated password hash"

# SQL 명령어 실행
echo "💾 Inserting admin user into database..."

oc exec -n langflow-shop $POSTGRES_POD -- psql -U postgres -d user_db -c "
INSERT INTO users (email, username, hashed_password, is_active, created_at, updated_at)
VALUES (
  'admin@example.com',
  'admin',
  '$HASHED_PASSWORD',
  true,
  NOW(),
  NOW()
)
ON CONFLICT (email) DO UPDATE SET
  username = EXCLUDED.username,
  hashed_password = EXCLUDED.hashed_password,
  updated_at = NOW();
"

echo "✅ Admin user created successfully!"
echo ""
echo "📋 Login credentials:"
echo "  Email: admin@example.com"
echo "  Password: admin"
echo ""
echo "💡 You can now login with these credentials"

# Made with Bob

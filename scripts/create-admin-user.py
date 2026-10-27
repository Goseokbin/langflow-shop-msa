#!/usr/bin/env python3
"""
Admin 사용자 생성 스크립트
로컬 또는 OpenShift 환경에서 admin/admin 계정 생성
"""

import sys
import uuid
from passlib.context import CryptContext

# 비밀번호 해싱 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_hash(password: str) -> str:
    """비밀번호 해시 생성"""
    return pwd_context.hash(password)

def generate_sql(email: str, name: str, password: str, phone: str | None = None) -> str:
    """SQL INSERT 문 생성"""
    hashed_password = generate_hash(password)
    user_id = str(uuid.uuid4())
    
    phone_value = f"'{phone}'" if phone else "NULL"
    
    sql = f"""
-- Admin 사용자 생성 SQL
INSERT INTO users (id, email, password_hash, name, phone, created_at, updated_at)
VALUES (
  '{user_id}',
  '{email}',
  '{hashed_password}',
  '{name}',
  {phone_value},
  NOW(),
  NOW()
)
ON CONFLICT (email) DO UPDATE SET
  name = EXCLUDED.name,
  password_hash = EXCLUDED.password_hash,
  phone = EXCLUDED.phone,
  updated_at = NOW();
"""
    return sql

if __name__ == "__main__":
    print("🔐 Admin User Creation Script")
    print("=" * 50)
    
    # 기본값
    email = "admin@example.com"
    name = "admin"
    password = "admin"
    phone = None
    
    # 커맨드 라인 인자로 변경 가능
    if len(sys.argv) > 1:
        email = sys.argv[1]
    if len(sys.argv) > 2:
        name = sys.argv[2]
    if len(sys.argv) > 3:
        password = sys.argv[3]
    if len(sys.argv) > 4:
        phone = sys.argv[4]
    
    print(f"\n📋 Creating user:")
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    print(f"  Password: {password}")
    if phone:
        print(f"  Phone: {phone}")
    print()
    
    # SQL 생성
    sql = generate_sql(email, name, password, phone)
    
    print("📝 Generated SQL:")
    print("-" * 50)
    print(sql)
    print("-" * 50)
    print()
    
    # SQL 파일로 저장
    output_file = "create-admin-user.sql"
    with open(output_file, "w") as f:
        f.write(sql)
    
    print(f"✅ SQL saved to: {output_file}")
    print()
    print("💡 Usage:")
    print()
    print("1. OpenShift에서 실행:")
    print("   # PostgreSQL Pod 이름 확인")
    print("   oc get pods -n shopping-mall | grep postgresql")
    print("   # SQL 파일 복사")
    print(f"   oc cp {output_file} shopping-mall/postgresql-1-xxxxx:/tmp/{output_file}")
    print("   # SQL 실행")
    print(f"   oc exec -n shopping-mall postgresql-1-xxxxx -- psql -U postgres -d user_db -f /tmp/{output_file}")
    print()
    print("2. 로컬 PostgreSQL에서 실행:")
    print(f"   psql -U postgres -d user_db -f {output_file}")
    print()
    print("3. 또는 SQL 내용을 복사하여 직접 실행")
    print()
    print(f"🔑 Login credentials:")
    print(f"  Email: {email}")
    print(f"  Password: {password}")

# Made with Bob

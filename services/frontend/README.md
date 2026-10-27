# Shopping Mall Frontend

Next.js 기반의 쇼핑몰 프론트엔드 애플리케이션입니다.

## 기능

- 🛍️ 상품 목록 및 상세 보기
- 🛒 장바구니 관리
- 📦 주문 내역 조회
- 💬 AI 챗봇 (ChatGPT-3.5-turbo)
- 👤 사용자 인증 (로그인/회원가입)

## 기술 스택

- **Framework**: Next.js 14
- **Language**: TypeScript
- **Styling**: Tailwind CSS (inline styles)
- **State Management**: React Hooks
- **API Client**: Fetch API

## 로컬 개발

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev

# 프로덕션 빌드
npm run build

# 프로덕션 서버 실행
npm start
```

## 환경 변수

```env
API_GATEWAY_URL=http://api-gateway:8000
NODE_ENV=production
```

## Docker 빌드

```bash
# Podman으로 빌드 (linux/amd64)
podman build --platform linux/amd64 -t seokbin9023/my-repository:frontend-latest .

# 이미지 푸시
podman push seokbin9023/my-repository:frontend-latest
```

## OpenShift 배포

```bash
# Deployment 생성
oc apply -f ../openshift/deployments/frontend-deployment.yaml

# Service 노출
oc expose deployment frontend --port=3000 -n shopping-mall

# Route 생성 (외부 접근)
oc expose service frontend -n shopping-mall

# Route URL 확인
oc get route frontend -n shopping-mall
```

## 주요 컴포넌트

### Header
- 네비게이션 메뉴
- 로고 및 링크

### ProductList
- 상품 그리드 레이아웃
- 장바구니 추가 기능
- 재고 상태 표시

### ChatBot
- 플로팅 챗봇 버튼
- 실시간 AI 대화
- ChatGPT-3.5-turbo 통합
- 상품 추천 및 주문 조회

## API 엔드포인트

프론트엔드는 API Gateway를 통해 백엔드 서비스와 통신합니다:

- `GET /api/products` - 상품 목록
- `GET /api/products/{id}` - 상품 상세
- `POST /api/users/register` - 회원가입
- `POST /api/users/login` - 로그인
- `POST /api/cart/{user_id}/items` - 장바구니 추가
- `POST /api/orders` - 주문 생성
- `POST /api/chat` - AI 챗봇

## 프로젝트 구조

```
frontend/
├── src/
│   ├── components/
│   │   ├── Header.tsx
│   │   ├── ProductList.tsx
│   │   └── ChatBot.tsx
│   ├── pages/
│   │   └── index.tsx
│   ├── services/
│   └── styles/
├── public/
├── Dockerfile
├── next.config.js
├── package.json
└── tsconfig.json
```

## 특징

### OpenShift 호환
- Non-root 사용자 (UID 1001)
- 그룹 권한 설정
- Security Context 적용

### 반응형 디자인
- 모바일, 태블릿, 데스크톱 지원
- Tailwind CSS 유틸리티 클래스

### AI 챗봇
- 실시간 대화
- 상품 검색 및 추천
- 주문 상태 조회
- 자연어 처리

## 라이센스

MIT
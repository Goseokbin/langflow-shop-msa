# 상품 이미지 등록과 확인

배포 검증에서 빈 카탈로그를 만들 때 `image_url`을 생략하면 사진 대신 상자 아이콘이 표시됩니다.
`scripts/smoke-test.py`는 이제 데모 상품을 만들 때 이미지 URL을 함께 넣고, 기존 데모 상품의 빈 이미지도 보완합니다.
직접 등록한 이미지는 유지하며, 과거 허브·키보드의 잘못된 기본 매핑만 교정합니다.

기존 환경을 보완할 때는 해당 Frontend Route를 지정합니다. 기본 실행은 조회만 합니다.

```bash
scripts/update-product-images.sh --base-url https://<frontend-route> --apply --check-images
```

인증이 필요한 환경에서는 기존 토큰을 `SHOP_API_TOKEN` 환경변수로 전달합니다. 스크립트에는 계정·비밀번호나 클러스터 주소가 들어 있지 않습니다.

파이프라인의 검증 및 운영 기능 검사에서는 이미지의 HTTPS 응답, 이미지 MIME, 파일 시그니처와 크기까지 확인합니다.
상품 이미지 검사 실패는 기능 검사 실패로 처리합니다. 이미지 5개 검사 결과는 하나의 기능 검사 항목으로 기록합니다.

데모 대표 사진은 Unsplash와 T'nB의 공개 이미지 URL을 사용합니다. 허브 사진의 원문은 https://www.t-nb.com/products/hub-usb-c-8-en-1-iclick 입니다.
정확한 매핑은 `scripts/catalog_images.py`의 `DEMO_PRODUCT_IMAGES`에서 확인할 수 있습니다.

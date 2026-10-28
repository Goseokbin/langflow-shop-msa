# 내부 API 경로를 Concert에 연결하기

서비스 주소는 액세스 지점이고, 그 주소 아래의 API 경로는 엔드포인트입니다. 예를 들어 `http://product-service.shopping-mall.svc:8002` 아래에 `/api/products`, `/api/products/{product_id}`가 연결됩니다.

## 최초 권한 설정

클러스터 관리자가 예제 namespace에 한 번 적용합니다.

```sh
oc apply -f openshift/internal-openapi-rbac.json
```

이 Role은 shopping-mall의 지정된 API 서비스 7개에 한해 Kubernetes Service proxy GET 접근을 허용합니다. CI 계정과 예제 Tekton 계정에 바인딩합니다. pod exec나 새로운 외부 Route는 사용하지 않습니다. proxy GET 권한은 경로 단위로 제한할 수 없으므로 해당 서비스의 다른 GET 경로에도 적용됩니다. 애플리케이션 인증은 계속 적용됩니다.

## 파이프라인에서 확인

기존 GitHub Actions 파이프라인의 **09 · 저장소·이미지·배포 연결 검증** 단계에서 자동 수집합니다.

1. 배포된 Kubernetes Service 이름·포트를 확인합니다.
2. OpenShift API를 통해 각 내부 서비스의 `/openapi.json`을 조회합니다.
3. HTTP operation이 선언된 경로만 추출합니다. GET/POST가 같은 경로를 공유하면 경로는 하나, operation은 둘로 계산합니다.
4. 기존 서비스의 참조와 base-url을 유지하면서 application/deployment SBOM의 endpoints를 실제 경로로 교체합니다.
5. Concert 수집 완료 후 다시 내보낸 두 SBOM의 경로 집합과 액세스 주소를 대조합니다.

OpenAPI 조회나 파싱, 반영 검증이 실패하면 해당 단계가 실패합니다. 주소 하나로 조용히 대체하지 않습니다. 원본 스키마와 해시는 보호된 파이프라인 작업 파일에 보관하며, 공개 데모 보고서에는 서비스별 경로·operation 수와 검증 결과를 표시합니다.

## 수집 범위

OpenAPI 대상은 api-gateway, user-service, product-service, cart-service, order-service, langflow-ai-service, langflow입니다. 배포된 스키마가 바뀌면 다음 실행에서 목록을 다시 만듭니다. HTTP 서비스 추가·포트 변경 시 `scripts/concert_internal_endpoints.py`의 허용 목록과 RBAC 파일을 함께 갱신합니다.

- frontend: OpenAPI를 제공하지 않아 웹 루트 `/`로 구분합니다.
- PostgreSQL: HTTP API가 아니므로 TCP 주소·포트로 구분합니다.
- Langflow: OpenAPI에 선언된 관리 API도 포함합니다. 이 경로 수가 외부 공개 경로 수나 익명 호출 가능한 API 수를 뜻하지는 않습니다.
- OpenAPI 경로는 서비스가 선언한 API 목록입니다. 모든 경로를 호출하거나 정상 응답·인증·실제 트래픽을 검증한 결과는 아닙니다.

## 빌드 없이 기존 배포 정보만 갱신

oc 로그인, 위 권한, Concert 설정 환경변수 `CONCERT_HOST`, `CONCERT_APP_API`, `CONCERT_ENVIRONMENT_ID`, `CONCERT_DEPLOYMENT_ID`가 필요합니다. 인증 헤더는 권한이 제한된 파일로 준비합니다.

```sh
python3 scripts/sync-concert-internal-endpoints.py \
  --authorization-file /secure/path/concert-authorization \
  --apply
```

기존 애플리케이션과 배포 정의를 내보내 백업하고 내부 경로만 갱신합니다. workload나 이미지를 변경하지 않습니다. `--apply`를 빼면 업로드 없이 변경 파일을 준비합니다.

## Concert 화면에서 보기

애플리케이션 → 해당 버전 → 토폴로지를 새로고침합니다. 개인용 액세스 지점 수는 서비스 주소 수이고, 개인용 엔드포인트 수는 수집한 경로 수이므로 서로 같을 필요가 없습니다. 실제 서비스의 경로 목록도 펼쳐 확인합니다. 기존 저장소·이미지·배포·외부 경로가 유지되는지 함께 확인합니다.

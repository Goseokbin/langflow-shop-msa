# 검증 후 승인하여 같은 이미지를 운영에 배포하기

기존 OpenShift는 검증(staging), 별도 OpenShift는 운영 데모(production)로 사용합니다. **한 번 빌드한 이미지의 digest를 두 환경에서 그대로 사용**합니다. DB와 인증정보, PVC, 외부 주소는 환경별로 분리합니다.

## 파이프라인에서 볼 곳

| 단계 | 확인할 내용 |
| --- | --- |
| 01–07 | 같은 소스 commit의 Trivy·CodeQL 결과, 서비스 이미지 7개 빌드와 전체 이미지 9개 검사, Concert 수집 |
| 08 | 검증 OpenShift에 스캔한 digest 배포 |
| 09 | 저장소·패키지·CVE·이미지·배포 관계, 내부 OpenAPI 경로 대조 |
| 10 | 쇼핑몰 기능 8개 통과 후 승인용 릴리스 생성 |
| 11 | GitHub production 승인 후 같은 digest 9개 운영 배포, 기능 검사와 운영 배포 SBOM 수집 |

10의 `demo-smoke`에 이미지별 digest와 릴리스 SHA-256이 표시됩니다. `verified-release`는 다음 job이 사용하는 암호화된 릴리스 파일입니다. Secret 값은 넣지 않습니다. 11은 같은 실행의 파일과 SHA-256·인증값·commit·run ID를 확인하고, digest가 바뀌면 실패합니다.

현재 CVE 검사는 **감사 모드**입니다. 검사·수집 성공이 CVE 0개를 뜻하지 않으며, 운영 승인은 결과와 잔여 위험을 검토한 뒤 합니다.

## 최초 준비: 관리자

1. 두 API에 각각 로그인한 kubeconfig 파일을 준비합니다. 이후 명령에는 파일을 명시해 다른 클러스터를 변경하지 않도록 합니다.
2. 운영 저장소를 준비합니다. 관리형 StorageClass가 없는 이 데모는 정적 로컬 PV를 사용합니다.

```bash
python3 scripts/prepare-production-demo.py \
  --source-kubeconfig <검증_kubeconfig> \
  --target-kubeconfig <운영_kubeconfig> \
  --storage-node <운영_저장소_노드> \
  --output <로컬_준비결과_JSON>

oc --kubeconfig=<운영_kubeconfig> get deploy,pvc -n shopping-mall-prod
```

준비 스크립트는 전용 디렉터리의 PV 2개와 PVC, 독립 Secret·Service·Route·CI 권한 및 replica **0**인 Deployment 9개를 만듭니다. 기존 이름의 관련 없는 리소스가 있으면 덮어쓰지 않습니다. 노드 디렉터리를 준비하는 임시 privileged Pod와 해당 권한은 완료 후 제거합니다.

| 저장소 | 용량 | 보존 정책 |
| --- | --- | --- |
| postgres-data | 10Gi | Retain |
| langflow-data | 10Gi | Retain |

로컬 PV는 선택한 노드에 고정됩니다. 노드 장애 시 자동 전환·복제를 제공하지 않습니다. 실제 운영은 지원되는 CSI 저장소, 백업·복구와 DB 운영 정책을 별도로 준비합니다.

3. 검증 이미지 레지스트리에 읽기 전용 ServiceAccount를 만들고 `system:image-puller` 권한을 부여합니다. 해당 레지스트리 주소와 토큰을 운영 namespace의 `release-registry` Docker 인증 Secret으로 등록합니다. `shop-runtime`이 이를 참조합니다. 두 클러스터에서 접근 가능한 TLS 레지스트리가 필요합니다.
4. Concert에서 운영 환경을 추가하고 환경 ID를 준비합니다. 기존 검증 환경·앱·버전은 유지합니다. 운영용 Deploy SBOM은 실제 운영 배포 검증이 끝난 후 수집합니다.
5. 운영 namespace에 다음 ConfigMap을 만듭니다. `CONCERT_APP_API`는 검증과 **같은 앱·버전**, 환경 ID는 **운영 전용**입니다.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: langflow-shop-pipeline-config
  namespace: shopping-mall-prod
data:
  SHOP_NAMESPACE: shopping-mall-prod
  APPLICATION_NAME: langflow-shop
  APPLICATION_VERSION: "1.0.0"
  CONCERT_HOST: "<Concert_호스트>"
  CONCERT_APP_API: "/concert/core/api/v2/applications/<앱_ID>/versions/<버전_ID>"
  CONCERT_ENVIRONMENT_ID: "<운영_환경_ID>"
  CONCERT_ENVIRONMENT_NAME: "<운영_환경_이름>"
  CONCERT_DEPLOYMENT_ID: ""
  PRODUCTION_SERVER: "https://<운영_API>:6443"
  PRODUCTION_CLUSTER_ID: "<운영_clusterID>"
  PRODUCTION_CLUSTER_NAME: "<운영_클러스터_이름>"
```

배포 ID는 처음에 비워 두고 최초 운영 수집이 성공하면 파이프라인이 기록합니다.

## GitHub 승인과 인증 준비

1. **Settings → Environments → New environment → production**을 만듭니다.
2. **Required reviewers**에 승인자를 지정합니다. 관리자 우회를 끄고 배포 branch를 `main`으로 제한합니다.
3. 이 1인 데모는 본인이 실행하고 승인할 수 있도록 self-review를 허용합니다. 실무는 승인자를 분리하고 self-review를 막습니다.
4. 기존 검증용 repository Secrets는 유지하고 `PROMOTION_STATE_KEY`를 추가합니다. 긴 임의 키이며 승인용 릴리스를 보호합니다.
5. 아래 네 개는 repository Secret이 아니라 **production Environment secrets**로 추가합니다.

| 이름 | 값 |
| --- | --- |
| PROD_OPENSHIFT_SERVER | 운영 API URL |
| PROD_OPENSHIFT_TOKEN | 운영 shopping-mall-prod의 CI ServiceAccount 토큰 |
| PROD_OPENSHIFT_CA | 운영 API 인증서의 신뢰 CA PEM |
| PROD_CONCERT_AUTH_HEADER | Concert API 인증 헤더 전체 |

운영 CI 권한은 준비 스크립트가 만듭니다. 배포 변경, OpenAPI 조회, DB 초기화 Job 및 Langflow 연결 설정이 대상 namespace에서 실행됩니다. 토큰은 만료 시 갱신해야 하며, 이번 데모는 168시간 토큰을 요청했습니다. 레지스트리 pull 토큰도 갱신 대상입니다. API에 사용자 지정 인증서가 있으면 그 인증서를 실제로 서명한 신뢰 CA를 사용합니다.

## 실행·승인하기

1. main 변경을 push하거나 Actions에서 **Run workflow**를 실행합니다.
2. 01–10 성공을 확인합니다. `demo-source-scan`, `demo-image-scan`, `demo-link-verify`, `demo-smoke`와 Concert의 CVE·SAST 결과를 검토합니다.
3. 실행 Summary의 **Review deployments**에서 `production`을 선택하고 **Approve and deploy**를 누릅니다. 거절하면 운영 job은 진행되지 않습니다.
4. 11이 성공하면 Summary의 운영 쇼핑몰 링크와 `demo-production`에서 digest 일치, 기능 검사 결과와 Concert 운영 환경·배포 ID를 확인합니다.

운영 job은 DB → Langflow → 쇼핑몰 순으로 시작합니다. DB는 새 Secret과 PVC로 초기화하므로 검증 DB를 공유하거나 복사하지 않습니다. Langflow Flow와 앱 API 키도 운영에서 새로 설정합니다. 모델 응답에는 별도 운영 모델 Secret과 사용 가능한 API 크레딧이 필요합니다. 기능 검사 8개에 실제 모델 추론 성공은 포함되지 않습니다.

## Concert에서 설명하기

**같은 앱 버전이 서로 다른 환경에 배포**된 예입니다. 토폴로지는 환경과 배포의 관계를 표현하며, 단순한 HTTP 호출 순서를 그린 그림은 아닙니다.

- 앱/버전: 같은 릴리스의 코드·패키지·보안 결과를 모읍니다.
- 이미지 아티팩트: digest로 식별한 실제 빌드 결과입니다. 운영에서 새로 만들지 않습니다.
- 환경/배포: 검증과 운영의 클러스터·namespace·실행 이미지를 구분합니다.
- 서비스/액세스 지점/엔드포인트: 환경별 내부 주소와 외부 Route, 실제 OpenAPI 경로를 보여줍니다.

운영은 외부 레지스트리 주소로 pull하지만 Concert에는 스캔에 사용한 원래 이미지 식별값을 기록합니다. 실제 pull 주소는 별도 속성에 남겨 패키지·CVE가 레지스트리 별칭에 따라 다른 아티팩트로 갈라지지 않도록 합니다.

**확인할 곳:** 앱 버전의 배포 목록과 환경 상세 → 검증/운영 각각 선택 → 클러스터 API, namespace, 이미지 digest, Route 확인. 승인 전에는 운영 환경만 준비돼 있고 실행된 운영 배포는 아직 없습니다.

## 문제가 생기면

| 증상 | 확인 |
| --- | --- |
| 11이 대기 | 정상 승인 대기인지 확인하고 Review deployments 사용 |
| API 인증 오류 | 운영 Environment secret의 토큰·CA·URL 확인 |
| ImagePullBackOff | 운영 release-registry, 원본 레지스트리 TLS와 접근 권한 확인 |
| PVC/Pod Pending | 로컬 PV가 고정된 노드의 상태와 claim 확인 |
| 릴리스 검증 실패 | 같은 실행의 artifact/출력인지 확인, 파일 수정·재빌드 금지 |
| Concert에 운영 배포 없음 | 11의 기능 검사 및 Deploy SBOM 수집 완료 확인 |

실패하면 성공으로 표시하지 않습니다. 일부 워크로드가 시작된 상태로 실패할 수 있으므로 해당 job 로그와 운영 Deployment를 확인합니다. 이 데모에는 자동 DB 롤백이나 무중단·고가용성 구성이 포함돼 있지 않습니다.

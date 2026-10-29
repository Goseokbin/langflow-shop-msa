# Langflow Shop MSA

Langflow 기반 AI 쇼핑몰과 OpenShift DevSecOps 실습 프로젝트입니다.

## 구성

Frontend → API Gateway → User / Product / Cart / Order / Langflow AI Service로 연결합니다. AI Service는 Langflow를 호출하고, 주문·상품·장바구니·사용자 데이터는 PostgreSQL에 저장합니다. 자체 빌드 서비스는 7개이며 Langflow와 PostgreSQL은 외부 이미지를 사용합니다.

## 자동 파이프라인

main의 파이프라인 관련 파일 push 또는 Actions의 Run workflow에서 GitHub Actions가 다음 단계를 직접 실행합니다. 각 단계는 Actions 그래프의 별도 job으로 표시됩니다.

```text
준비 → 소스 Trivy → CodeQL SAST → Concert SAST 수집 → 이미지 빌드·Push
→ 이미지 9개 Trivy → Concert CVE 수집 → 검증 배포 → 연결 검증 → 기능 검사
→ production 승인 대기 → 같은 이미지 운영 배포·검증
```

- GitHub Actions가 소스를 checkout하고 namespace 전용 CI 계정으로 빌드 결과를 배포합니다.
- 실행 시 소스 tar의 SHA-256과 Git commit을 기록하고, 이후 job에서도 같은 실행·커밋인지 검사합니다.
- Trivy가 소스 의존성과 실제 이미지 digest를 스캔합니다.
- 소스 SBOM·CVE는 repository 대상으로, 이미지 결과는 image 대상으로 Concert에 수집합니다.
- 수집 완료 후 이미지를 배포하고 저장소·이미지·서비스·외부 Route 관계를 연결합니다.
- 저장소의 패키지와 CVE, 실행 이미지별 패키지와 CVE가 실제 API에 나타나야 완료됩니다.
- PostgreSQL의 미지원 OS는 별도 패키지 inventory로 처리하며 CVE 0건을 안전 판정하지 않습니다.

## GitHub Actions 설정

Repository Secrets에 `OPENSHIFT_SERVER`, `OPENSHIFT_TOKEN`, `OPENSHIFT_CA`, `CONCERT_AUTH_HEADER`, `PIPELINE_STATE_KEY`, `PROMOTION_STATE_KEY`가 필요합니다. OpenShift 토큰은 검증 namespace의 기존 CI 계정용입니다. GitHub hosted runner에서 클러스터 API·Concert·이미지 레지스트리에 접근할 수 있어야 합니다.

`production` Environment에는 `PROD_OPENSHIFT_SERVER`, `PROD_OPENSHIFT_TOKEN`, `PROD_OPENSHIFT_CA`, `PROD_CONCERT_AUTH_HEADER`를 준비하고 Required reviewers와 배포 브랜치 조건을 설정합니다. 운영 job은 사람이 승인한 뒤 검증된 릴리스를 받아 같은 이미지 digest를 배포합니다.

인스턴스 주소와 application/deployment 식별자는 각 namespace의 ConfigMap `langflow-shop-pipeline-config`에 보관합니다. 인증 값은 Git·일반 설정 파일·공개 보고서에 넣지 않습니다. `scripts/run-devsecops-pipeline.py`는 이전 Tekton 실습용이며 현재 GitHub Actions 실행에는 사용하지 않습니다.

## 애플리케이션 최초 배포

```sh
python3 scripts/deploy-current-cluster.py
python3 scripts/configure-langflow.py
python3 scripts/smoke-test.py
```

`oc` 로그인과 해당 테스트 namespace의 리소스 생성 권한이 필요합니다. 모델 API 키는 OpenShift Secret에 직접 준비합니다. 배포 스크립트의 namespace와 스토리지 클래스는 대상 클러스터에 맞춰 검토합니다.

## 검증과 정책

[상품 이미지 등록과 확인](docs/PRODUCT_IMAGES.md)은 빈 이미지 보완과 실제 이미지 응답 검증 방법을 설명합니다. 기능 검사는 초기 카탈로그에도 이미지 URL을 함께 등록합니다.

이번 파이프라인은 감사 모드입니다. 스캔·수집 실패는 배포를 중단하지만 발견된 CVE 수만으로 배포를 차단하지는 않습니다. 소스의 Python 명시 의존성과 npm production lock 데이터를 분석하며, OS 및 Python 전이 의존성은 이미지 스캔으로 보완합니다. AI 모델의 인증·크레딧 문제는 별도로 확인합니다.

원본 시스템의 인증정보, Git 이력, 내부 감사 리포트, 화면 캡처와 로컬 실행 결과는 이 저장소에 포함하지 않습니다. 새 릴리스에서는 application version 정책과 CVE 차단 기준, 계정·토큰 회전 정책을 팀 운영 기준에 맞게 확장합니다.

## CVE 조치 관리 데모

[기본 담당자·SLA·배포 후 검증 가이드](docs/NATIVE_GOVERNANCE.md)는 Automation rules로 티켓·담당자를, Goals로 SLA를 설정하고 Workflows는 두 환경의 패치 결과 조회에 사용하는 방법을 설명합니다. [이전 사용자 정의 데모](docs/CVE_CASE_MANAGEMENT.md)는 변경 이력으로 보존합니다.

[조직 저장소 이전 가이드](docs/REPOSITORY_TRANSFER.md)는 공개 상태·이력을 유지하며 저장소를 이전하고 Actions·운영 승인·Concert의 새 주소 연결을 확인하는 방법을 설명합니다.

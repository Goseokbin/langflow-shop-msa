# Langflow Shop MSA

Langflow 기반 AI 쇼핑몰과 OpenShift DevSecOps 실습 프로젝트입니다.

## 구성

Frontend → API Gateway → User / Product / Cart / Order / Langflow AI Service로 연결합니다. AI Service는 Langflow를 호출하고, 주문·상품·장바구니·사용자 데이터는 PostgreSQL에 저장합니다. 자체 빌드 서비스는 7개이며 Langflow와 PostgreSQL은 외부 이미지를 사용합니다.

## 자동 파이프라인

main push 또는 Actions의 Run workflow에서 다음 Tekton 단계가 실행됩니다.

```text
prepare → source-scan → build → image-scan → concert-ingest → deploy → link-verify
```

- GitHub Actions는 소스를 checkout하고 namespace 전용 CI 계정으로 PipelineRun을 시작합니다.
- 실행 시 소스 tar의 SHA-256과 Git commit을 기록합니다. 미커밋 작업은 별도 snapshot으로 표시합니다.
- Trivy가 소스 의존성과 실제 이미지 digest를 스캔합니다.
- 소스 SBOM·CVE는 repository 대상으로, 이미지 결과는 image 대상으로 Concert에 수집합니다.
- 수집 완료 후 이미지를 배포하고 저장소·이미지·서비스·외부 Route 관계를 연결합니다.
- 저장소의 패키지와 CVE, 실행 이미지별 패키지와 CVE가 실제 API에 나타나야 완료됩니다.
- PostgreSQL의 미지원 OS는 별도 패키지 inventory로 처리하며 CVE 0건을 안전 판정하지 않습니다.

## GitHub Actions 설정

Repository Secrets에 `OPENSHIFT_SERVER`, `OPENSHIFT_TOKEN`, `OPENSHIFT_CA`가 필요합니다. 토큰은 테스트 namespace에서 PipelineRun을 시작하는 CI 계정용이며 클러스터 관리자 토큰을 사용하지 않습니다. GitHub hosted runner에서 클러스터 API에 접근할 수 있어야 합니다.

Concert 인증은 클러스터 Secret `concert-pipeline-auth`의 `authorization` 키로 보관합니다. GitHub runner에 Concert 키를 복사하지 않습니다. 인스턴스 주소와 application/deployment 식별자는 namespace ConfigMap `langflow-shop-pipeline-config`에 보관합니다.

파이프라인의 최초 설치는 권한 있는 작업자가 수행합니다. `scripts/run-devsecops-pipeline.py --authorization-file ...`가 Task·Pipeline·SA·RBAC·PVC를 생성합니다. 이후 CI는 설치 권한 없이 다음 명령으로 실행합니다.

```sh
python3 scripts/run-devsecops-pipeline.py --start-only --wait-for-idle --wait
```

## 애플리케이션 최초 배포

```sh
python3 scripts/deploy-current-cluster.py
python3 scripts/configure-langflow.py
python3 scripts/smoke-test.py
```

`oc` 로그인과 해당 테스트 namespace의 리소스 생성 권한이 필요합니다. 모델 API 키는 OpenShift Secret에 직접 준비합니다. 배포 스크립트의 namespace와 스토리지 클래스는 대상 클러스터에 맞춰 검토합니다.

## 검증과 정책

이번 파이프라인은 감사 모드입니다. 스캔·수집 실패는 배포를 중단하지만 발견된 CVE 수만으로 배포를 차단하지는 않습니다. 소스의 Python 명시 의존성과 npm production lock 데이터를 분석하며, OS 및 Python 전이 의존성은 이미지 스캔으로 보완합니다. AI 모델의 인증·크레딧 문제는 별도로 확인합니다.

원본 시스템의 인증정보, Git 이력, 내부 감사 리포트, 화면 캡처와 로컬 실행 결과는 이 저장소에 포함하지 않습니다. 새 릴리스에서는 application version 정책과 CVE 차단 기준, 계정·토큰 회전 정책을 팀 운영 기준에 맞게 확장합니다.

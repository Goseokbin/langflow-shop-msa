# GitHub Actions DevSecOps

main push 또는 workflow_dispatch에서 GitHub hosted runner가 소스 스캔 → Docker 빌드 → 이미지 스캔 → Concert 수집 → OpenShift 배포 → 관계 및 쇼핑몰 smoke 검증을 직접 실행한다. Tekton 호출은 없다. 스캔·수집 실패 시 배포하지 않으며 CVE 발견 수 자체로 차단하는 정책은 아직 없는 감사 모드다.

## 설정

Repository Secrets는 OPENSHIFT_SERVER, OPENSHIFT_TOKEN, OPENSHIFT_CA, CONCERT_AUTH_HEADER다. namespace 전용 CI ServiceAccount로 인증하며 관리자 토큰을 사용하지 않는다. namespace의 Deployment 변경, Pod·Service·Route 조회, 설정 ConfigMap 조회 및 system:image-builder 권한을 부여한다.

ConfigMap langflow-shop-pipeline-config에는 CONCERT_HOST, CONCERT_APP_API, CONCERT_ENVIRONMENT_ID, CONCERT_DEPLOYMENT_ID, CONCERT_PREVIOUS_REPO_URL, DOCKER_REGISTRY_HOST를 설정한다. 레지스트리 값은 https:// 없이 외부에서 접근 가능한 인증된 호스트다. 테스트 클러스터는 내부 image-registry Service에 reencrypt TLS Route를 추가했다. API와 레지스트리 TLS 검증을 유지한다.

Concert 키와 CI 토큰은 GitHub Secrets로 전달하고 로그·artifact에 저장하지 않는다. 임시 Concert 인증 파일은 실행 종료 시 삭제한다. 실제 키는 발급 계정 권한을 가지므로 운영에서는 전용 계정과 회전·폐기 정책이 필요하다.

## 검증 방식

scripts/github-devsecops.py는 GITHUB_SHA와 clean checkout을 확인하고 tracked 파일만 아카이브해 SHA-256을 계산한다. 자체 서비스 7개를 Docker로 빌드하며 OCI label의 저장소·커밋·아카이브 해시를 확인한다. 레지스트리 push에서 얻은 digest로 스캔하고 그대로 배포한다. 외부 Langflow·PostgreSQL은 현재 실행 digest를 스캔한다.

레지스트리 외부 Route는 전송 경로다. Concert 식별자는 내부 저장소 경로+digest로 통일하며 CycloneDX root name·bom-ref·OCI repository_url을 함께 정규화한다. 소스 package_sbom과 code_scan은 repo URL·branch·repository 타입을 동일하게 사용한다. 이미지 결과를 소스 결과로 재분류하지 않는다.

현재 Concert 설치의 소스 SCA는 branch 범위로 연결된다. native source_repo commit_sha 필드는 수집 metadata의 SHA를 반영하지 않았다. 소스 화면은 branch 최신 스캔이며, 실행 커밋은 OCI label·이미지 속성·Deployment 주석·검증 보고서로 확인한다.

최종 작업은 저장소 패키지·CVE가 스캔 결과 이상인지 API로 조회하고 9개 이미지 inventory/CVE, 배포 digest, 외부 Route·내부 Service 관계를 확인한다. smoke-test.py는 상품·인증·장바구니·주문·취소를 테스트한다. 성공 시 Actions summary와 devsecops-verification artifact에 커밋·집계를 보관한다. 원본 스캔·내부 URL·키는 공개 artifact로 업로드하지 않는다.

소스는 Python requirements 직접 의존성과 npm production lock을 검사한다. Python 전이 의존성·OS 패키지는 이미지 스캔으로 보완한다. PostgreSQL CentOS Stream OS CVE 매칭은 미지원이라 별도 inventory만 수집하며 CVE 0건을 안전 판정으로 취급하지 않는다. OpenAI 크레딧 부족에 따른 AI 생성 검증 제한도 유지한다.

## 이전 Tekton 실험

사내 GitHub에서 Actions를 사용할 수 없어 처음에는 Tekton으로 검증했다. 개인 GitHub 이전 후 Actions 직접 실행으로 전환했다. run-devsecops-pipeline.py 및 기존 PipelineRun/PVC는 이전 방식과 감사 이력이며 현재 workflow의 의존성이 아니다.

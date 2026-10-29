# 조직 저장소 이전 후 연결 확인하기

앱 저장소는 `https://github.com/goseokbin-concert/langflow-shop-msa`입니다. 개인 저장소를 GitHub의 Transfer 기능으로 옮겨 공개 상태와 기존 커밋·PR·이슈 이력을 유지했습니다.

## 1. 저장소와 승인 설정 확인

이전 전후에 저장소 ID, main 커밋, PR·이슈 ID를 대조합니다. Actions와 production 환경의 승인자·배포 브랜치 조건, 저장소·환경 Secrets 이름이 보존됐는지 확인합니다. Secret 값은 출력하거나 보고서에 넣지 않습니다.

이번 이전에서는 저장소 ID `1435328955`, 기존 PR 3개와 일반 이슈 #4가 유지됐고, production의 Goseokbin 승인자 조건도 그대로였습니다. 기존 실행 이력은 새 저장소의 Actions에서 확인합니다.

```bash
git remote set-url origin https://github.com/goseokbin-concert/langflow-shop-msa.git
```

## 2. 파이프라인의 출처 확인 조건 변경

이 예제는 운영 승격 시 릴리스가 지정된 앱 저장소에서 만들어졌는지도 검사합니다. `scripts/promotion_bundle.py`의 허용 저장소를 새 조직 주소로 변경했습니다. 이전 개인 주소나 조치 티켓 전용 저장소의 릴리스는 새 실행의 승인 대상이 되지 않습니다.

일반 PR·소스 검사·이미지 빌드는 GitHub의 현재 `GITHUB_REPOSITORY`를 사용합니다. Commit과 이미지 digest를 확인하는 기존 조건은 유지합니다.

## 3. Concert 연결 변경

- 두 환경의 파이프라인 ConfigMap에서 `CONCERT_PREVIOUS_REPO_URL`을 이전 개인 저장소 URL로 지정합니다.
- 새 릴리스의 코드 참조는 조직 URL로 바뀝니다. 과거 릴리스와 기존 이미지에 기록된 출처는 덮어쓰지 않습니다.
- Automation rules의 대상 앱 버전을 새 릴리스로, 티켓 생성 대상을 `goseokbin-concert/langflow-shop-msa`로 설정합니다. Assignees는 Goseokbin을 유지합니다.
- 기본 GitHub 수집 작업의 organization·repository도 같은 주소로 설정합니다.
- 조회 전용 Workflows의 `repository`를 `goseokbin-concert/langflow-shop-msa`로 바꿔 다시 Import합니다. 기존 hourly Job은 같은 워크플로우의 최신 버전을 사용합니다.

SLA는 기존 Goals의 Critical 2일·High 7일을 유지합니다. 이전 별도 조치 저장소의 이슈는 과거 실습 기록으로 보존합니다. 새 앱 저장소 안의 PR에서는 새 이슈를 `Refs #번호`로 연결할 수 있습니다.

## 4. 실제 실행으로 확인

[이전 후 전체 실행](https://github.com/goseokbin-concert/langflow-shop-msa/actions/runs/40809360772)은 `13b75a03c3734bc303d49d4de71cb68f92470f43` 커밋에서 시작했습니다. Concert 릴리스는 `1.0.1-13b75a03c373`입니다.

Actions의 01–10 단계가 성공하면 검증 환경에서 새 저장소의 소스·이미지·배포 관계와 쇼핑몰 기능을 확인합니다. **Review deployments → production → Approve and deploy**는 운영 승인자가 수행합니다. 승인 후에는 같은 검증 이미지 digest 9개를 운영에 배포하며 재빌드하지 않습니다.

Concert의 새 버전에는 조직 저장소가 한 개만 보여야 합니다. 저장소의 패키지·CVE·SAST, 이미지별 패키지·CVE와 두 환경의 배포 연결을 확인합니다. Workflows의 검증 결과에는 새 조직 저장소의 Actions URL이 나와야 합니다.

자동 티켓 생성과 담당자 배정, 티켓 수집 job 성공, CVE 행의 티켓 배지는 각각 확인합니다. 한 항목의 성공으로 나머지도 성공했다고 가정하지 않습니다.

## 이전 과정에서 발견한 설정 문제

검증 클러스터의 `CONCERT_DEPLOYMENT_ID`가 서비스 정의가 없는 초기 배포 문서를 가리켜 09 연결 검증이 중단됐습니다. 내부 서비스 9개의 정의가 보존된 실제 이전 배포 문서로 설정을 바꾼 뒤 같은 실행의 실패 단계부터 재실행했습니다. 이미지 빌드·스캔 결과와 커밋은 그대로 재사용합니다. 이전 후에는 현재 배포 ID와 앱 버전도 최신 검증 결과로 맞춥니다.

새 저장소에서 Python 21개·npm 55개를 합친 패키지 76개, Concert CVE 102건, CodeQL 정적 노출 규칙 4개를 확인했습니다. 기본 Automation rule은 앱 저장소의 이슈 #5를 자동 생성해 Goseokbin에게 배정했습니다. 기본 GitHub 티켓 수집은 새 주소에서도 앱 컨텍스트를 명시하라는 409로 실패해 새 주소 설정과 이력을 보존한 채 비활성화했습니다. 이는 자동 티켓 생성·배정이나 스캔 수집의 실패를 뜻하지 않으며, 개별 CVE 행의 티켓 배지 자동 동기화는 미완료입니다.

검증 환경의 01–10 단계와 쇼핑몰 기능 검사 8개는 모두 통과했습니다. 저장소 1개·아티팩트 9개·공개 서비스 3개·내부 서비스 9개·내부 엔드포인트 201개를 대조했습니다. 검증된 암호화 릴리스 파일의 SHA-256은 `84b4faa45a6347328d792efee80e7a502d8f432b6e37ad9651b12ed0679cd351`입니다. 운영 배포는 동일 실행의 production 보호 규칙을 따릅니다.

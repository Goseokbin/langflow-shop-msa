# Concert Workflows 패치 데모 따라하기

이 데모는 **수정 버전이 확인된 Python 패키지 하나**를 변경한다. Concert가 임의의 CVE 패치를 추측하거나 실행 중인 컨테이너에서 `pip install`을 수행하지 않는다.

```
Concert CVE·패키지 확인 → Workflows 정책 확인 → 수정 PR 생성
→ PR 검사 → 담당자 검토·병합 → 기존 빌드·스캔·수집·배포 → Workflows 재확인
```

## 1. 사전 준비

먼저 `DEVSECOPS_PIPELINE.md`의 main 배포 파이프라인과 Concert 저장소 연결을 구성한다. `.github/workflows/patch-review.yml`을 기본 브랜치에 포함한다. PR 검증에는 OpenShift·Concert Secret이 필요 없다.

이번 정책은 `scripts/patch-policy.json`에 있다.

| 대상 | 값 |
|---|---|
| 파일 | `services/langflow-ai-service/requirements.txt` |
| 변경 | `requests==2.31.0` → `requests==2.33.0` |
| 대상 CVE | CVE-2024-35195, CVE-2024-47081, CVE-2026-25645 |
| 브랜치 | `concert-patch/requests-2.33.0` |

다른 패키지에 적용할 때는 공급자 권고, Python 버전, 의존성 호환성, 테스트를 검토해 **정책·가드·회귀검사를 함께 변경**한다. 현재 템플릿은 requests만 허용하며 범용 패치 엔진이 아니다.

## 2. Workflows 인증 작성

Workflows → 인증에서 다음 두 항목을 작성한다. 실제 값은 인증 저장소에만 입력한다.

| 서비스 | 설정 | 필요한 권한 |
|---|---|---|
| Bearer Token | GitHub 토큰 | 대상 저장소 Contents·Pull requests 쓰기, Actions 읽기 |
| API Key | Header Name=`Authorization`, 값=Concert 인증 헤더 전체 | 대상 앱 패키지·CVE 읽기 |

실무에는 해당 저장소만 허용하는 전용 자격증명을 사용한다. Workflow JSON과 Notion에는 토큰을 넣지 않는다. Workflows에서 GitHub·Concert로 HTTPS 연결이 가능해야 한다.

## 3. Workflow 작성

설정 예제를 로컬 파일에 복사해 환경 값 6개를 채운다. `source_repo_id`는 앱에 연결된 **저장소 브랜치 항목의 ID**다. 인증 이름은 `사용자/인증이름` 형식이다.

```sh
cp openshift/remediation/workflow-config.example.json /tmp/patch-config.json
# 파일의 repository, concert_host, application_api, source_repo_id,
# github_auth, concert_auth를 본인 환경에 맞게 편집
python3 scripts/build-patch-workflow.py \
  --config /tmp/patch-config.json --output /tmp/patch-workflow.json
```

Workflows에서 빈 워크플로우를 만든 후 편집기의 **JSON 편집**에 생성한 내용을 입력하고 저장한다. 이름은 `Langflow Package Patch Demo`다. UI 가져오기를 사용할 경우 해당 버전의 export/import 포맷을 확인한다. 생성 파일은 workflow 본문 JSON이다.

## 4. 먼저 plan, 그다음 create-pr

편집기의 실행 입력에서 `operation`을 지정한다.

| 입력 | 동작 |
|---|---|
| `plan` | Concert CVE, 수정 버전, GitHub 파일을 확인하고 제안만 반환 |
| `create-pr` | 허용된 한 줄만 바꾸는 PR 생성. 기존 PR이 있으면 재사용 |
| `verify` | 배포 파이프라인과 Concert 수집 결과를 다시 확인 |
| `auto` | 수정 전이면 PR 생성·재사용, 수정 후이면 재확인 |

기존 파일이나 수정 버전 권고가 정책과 다르면 중단한다. 고정 브랜치에 다른 내용이 있으면 덮어쓰지 않는다.

## 5. PR 검사와 병합

PR의 **Checks → Patch PR verification**에서 세 구간을 확인한다.

1. 패치 변경 범위: 승인된 파일·버전 한 줄인지 검증.
2. 패키지·이미지: 소스 스캔, 이미지 빌드, `pip check`, GET/POST·HTTP 오류 처리, 서비스 health, 이미지 스캔.
3. CodeQL: Python과 JavaScript/TypeScript 정적 분석. 성공은 분석 실행 성공을 뜻하며 기존 SAST 발견 사항이 없다는 뜻은 아니다.

Artifacts의 `patch-verification`에서 원본 소스·이미지 Trivy 결과와 `source-gate.json`, `image-gate.json`을 확인한다. **대상 패키지가 실제 인벤토리에 존재하고 버전이 2.33.0이며 대상 CVE가 없어야** 게이트를 통과한다. 빈 스캔은 성공으로 인정하지 않는다.

담당자가 PR을 검토·병합하면 기존 main 파이프라인이 새 이미지를 빌드·수집·배포한다. Workflow는 자동 병합하지 않는다. 운영 적용 시 GitHub 브랜치 보호와 필수 검사·승인 규칙도 설정한다.

## 6. 재확인과 정기 실행

배포 후 `verify`를 실행한다. 현재 requirements의 Git blob이 검사·배포 파이프라인에 사용된 blob과 같아야 하고, 그 파이프라인의 전체 실행이 성공해야 한다. 패치된 릴리스의 이미지 단계에서도 소스·AI 서비스 이미지의 대상 CVE 게이트를 다시 수행한다.

| 결과 | 의미 |
|---|---|
| `verification_pending` | 배포 또는 Concert 인벤토리 반영을 더 확인해야 함 |
| `deployment_verified_concert_findings_pending` | 배포 검증은 끝났지만 Concert에 대상 finding이 남아 있음. 완료 처리 금지 |
| `verified`, `closure=verified` | 파이프라인 성공, 수집된 수정 버전, 남은 대상 finding 0건 확인 |

여기서 `closure`는 **이 커스텀 Workflow의 검증 결과**다. Concert의 Action center 조치 상태를 강제로 변경하거나 전체 앱의 보안 문제 해결을 선언하지 않는다. 남은 finding을 숨기려고 `False positive`로 바꾸지 않는다.

Workflows → 작업 → 작업 작성에서 해당 워크플로우, 최신 버전, `operation=auto`, 시간별 반복을 선택하고 **작업 사용**을 켠다. 테스트 배포 완료 후에도 같은 정책을 정기 확인한다. 중지하려면 이 작업의 Enabled를 끈다. 정책 외의 새 CVE는 자동 변경하지 않는다. 시간별 작업은 수집된 Concert·GitHub 증거를 재확인하며, 새 CVE 탐지와 배포 드리프트 확인에는 최신 스캔·클러스터 수집도 필요하다.

## 문제를 구분하는 방법

- PR이 없음: Workflows 로그의 인증·네트워크·정책 오류를 확인한다.
- 같은 PR이 반환됨: 중복 방지 동작이다.
- 검사가 실패함: 해당 PR의 단계 로그와 원본 Trivy·SARIF 결과를 확인하고 병합을 보류한다.
- 배포 전인데 코드만 수정됨: `verification_pending`이 정상이다.
- Concert에 옛 finding이 남음: 현재 이미지 digest, 패키지 버전, scan 시각을 확인하고 과거 finding과 구분한다.
- 데모를 다시 보여주고 싶음: 테스트 버전을 새 앱/환경으로 복제한다. 현재 배포를 취약 버전으로 자동 되돌리지는 않는다.

## 실제 실행 증거

- Workflows가 만든 [PR #1](https://github.com/goseokbin-concert/langflow-shop-msa/pull/1): requirements 한 줄 변경, 재실행 시 기존 PR 재사용.
- [PR 검사](https://github.com/goseokbin-concert/langflow-shop-msa/actions/runs/40484138957): 3단계 통과.
- [병합 후 배포](https://github.com/goseokbin-concert/langflow-shop-msa/actions/runs/40484399389): 10단계 및 쇼핑몰 기능 8개 통과.
- 실행 중인 AI 서비스에서 requests 2.33.0과 해당 빌드 digest를 확인했다. Concert 저장소와 새 AI 서비스 이미지의 대상 CVE finding은 0건이며, Workflows는 `verified / closure=verified`를 반환했다.
- 이전 2.31.0 패키지 기록은 Concert 목록에 남는다. 실제 배포 이미지와 최신 스캔을 함께 확인한다. 다른 CVE와 SAST 발견 사항은 이번 패치 범위에 포함하지 않았다.
- 이미 수정된 main에서 `plan`을 실행하면 `source_already_patched`가 정상이다. 기존 PR과 실행 기록으로 시연하고, 새 실습에는 별도의 테스트 앱·환경을 사용한다.

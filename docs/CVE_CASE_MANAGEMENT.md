# CVE 발견부터 담당자·기한·배포 후 검증까지

> **이전 사용자 정의 데모 기록입니다.** 현재 구성은 [기본 Automation rules·Goals와 배포 후 검증](NATIVE_GOVERNANCE.md)을 사용합니다. 기존 담당자·기한 예약 작업은 비활성화했고, 설치된 `Langflow CVE Case Management`는 외부 작업을 하지 않는 종료 안내로 전환했습니다. 아래 파일·명령으로 예전 워크플로우를 다시 Import하면 이전 기능이 재활성화될 수 있으므로, 현재 구성에는 사용하지 않습니다.

이 데모에서는 Concert가 조치할 일을 추적하고, 개발자는 평소처럼 PR로 패치합니다. `policy_id`나 패치할 파일·버전을 CVE마다 등록할 필요가 없습니다.

흐름은 **현재 배포의 CVE 확인 → 담당자에게 이슈 배정 → 기한 추적 → 일반 패치 PR → 검증 환경 테스트 → 운영 승인 → 같은 이미지 승격 → 두 환경 재확인**입니다.

## 처음 한 번 준비하기

기존 두 환경 배포 파이프라인과 Concert 수집이 정상이어야 합니다. 다음 연결은 역할이 다릅니다.

| 설정 | 역할 |
| --- | --- |
| Concert의 GitHub connection | 원본 CVE에 연결된 GitHub 이슈 생성 |
| Workflows의 GitHub authentication | 이슈·담당자·PR·파이프라인 상태 조회와 이슈 갱신 |
| Workflows의 Concert authentication | 배포·패키지·CVE 조회와 선택한 평가 상태 갱신 |

GitHub 토큰은 대상 저장소의 Issues 읽기·쓰기와 Actions/PR 읽기 권한이 필요합니다. 이슈 담당자로 지정할 수 있는 계정을 사용합니다. 토큰은 인증 저장소에만 등록하며 JSON이나 Git에 넣지 않습니다.

1. `openshift/remediation/case-workflow-config.example.json`을 로컬 설정 파일로 복사합니다.
2. 저장소, Concert 호스트·앱 ID, 두 환경 ID, 배포 이름 접두사, 인증 참조, GitHub connection ID를 채웁니다.
3. `owners`에 서비스별 GitHub 담당자를, `sla_hours`에 승인된 기준을 입력합니다. 예시는 High 168시간·Critical 48시간입니다.
4. 아래 명령으로 ZIP을 생성하고 Concert **Workflows → Import**에서 가져옵니다.

```bash
python3 scripts/build-cve-case-workflow.py \
  --config /path/to/local-case-config.json \
  --output /path/to/cve-case-workflow.zip
```

`application_api`의 버전은 앱 ID를 식별하기 위한 기존 버전이면 됩니다. 실제 비교 대상은 매 실행마다 두 환경의 최신 파이프라인 배포에서 찾습니다. 배포 접두사는 본인 파이프라인의 Concert 배포 이름과 맞춰야 합니다.

필요한 GitHub 라벨은 `concert-remediation`, `concert-assigned`, `concert-in-progress`, `concert-awaiting-production`, `concert-verified`, `concert-sla-on-track`, `concert-sla-due-soon`, `concert-sla-overdue`입니다. 먼저 저장소에 생성합니다.

## 1. CVE를 조치 건으로 등록하기

Concert에서 **Langflow CVE Case Management → Run**을 엽니다.

| 입력 | 실습 값 |
| --- | --- |
| operation | triage |
| service | cart-service |
| cve | CVE-2024-53981 |
| preview_days | 8 — 미리보기에서만 사용 |

워크플로우는 두 환경에 배포된 이미지 digest를 읽고 해당 이미지의 패키지와 CVE를 확인합니다. High/Critical 발견 결과가 있을 때 서비스 소유자에게 이슈를 배정합니다. 같은 앱·서비스·CVE로 다시 실행하면 기존 건을 갱신합니다.

이번 실습의 실제 건은 [이슈 #4](https://github.com/goseokbin-concert/langflow-shop-msa/issues/4)입니다. 담당자는 `Goseokbin`, 기한은 최초 발견일부터 7일인 **2026-11-04 17:21 KST**입니다. 재스캔이나 앱 버전 변경으로 기한을 초기화하지 않습니다.

Concert의 **CVE findings → Filters → CVE**로 대상 CVE를 필터링합니다. `cart-service` 행을 펼치면 티켓 `#4`와 평가 상세의 담당자·기한이 나옵니다. 상단 Find와 CVE 필터는 구분합니다.

## 2. 담당자와 기한 확인하기

GitHub 이슈에서 담당자, 기한, 두 환경의 패키지 버전과 CVE 건수를 확인합니다. Concert에서도 원본 CVE의 평가 상태·티켓 연결을 확인할 수 있습니다.

기한 상태는 `on-track` → 남은 시간 24시간 이하 `due-soon` → 기한 도달 `overdue`로 바뀝니다. 상태가 바뀔 때만 이슈 댓글을 추가합니다.

이 SLA 계산과 라벨은 **이번에 만든 사용자 정의 워크플로우 로직**입니다. CVSS 7.0 이상은 High, 9.0 이상은 Critical로 구분하며 Concert의 Priority와는 구분합니다. Concert 기본 전역 SLA 설정을 변경한 것은 아닙니다. 원본 CVE·티켓 연결과 평가 상태 갱신은 Concert API를 사용합니다.

## 3. 기한 초과를 미리 보여주기

동일 입력에서 `operation=preview-deadline`, `preview_days=8`로 실행합니다. 미래 날짜로 평가한 `deadline.state=overdue`를 볼 수 있습니다.

출력의 `simulation=true`, `writes_enabled=false`를 함께 확인합니다. 이 기능은 읽기 전용이며 실제 기한·평가·이슈·댓글을 변경하지 않습니다. 실제로 기한을 초과했다는 증거로 사용하지 않습니다.

## 4. 개발자가 평소처럼 패치하기

1. 브랜치를 만들고 `services/cart-service/requirements.txt`에서 의존성을 검토·수정합니다.
2. PR 본문에 `Refs #4`를 넣어 이슈와 연결합니다. 검증 전 이슈가 자동으로 닫히지 않도록 `Fixes #4` 대신 참조를 권장합니다.
3. PR 검사 후 리뷰·병합합니다.
4. 기존 Actions가 소스·이미지 스캔, Concert 수집, 검증 환경 배포와 기능 검사를 수행합니다.
5. GitHub의 production 승인을 사람이 수행하면 검증한 동일 이미지 digest가 운영으로 승격됩니다.

이번 CVE의 Concert 수정 권고는 python-multipart 0.0.18 이상입니다. 패키지 호환성과 현재 보안 권고를 확인해 수정 버전을 결정합니다. 이 워크플로우가 자동으로 버전을 선택하거나 코드·PR·운영 승인을 대신하지는 않습니다.

## 5. 배포 후 조치 결과 확인하기

`operation=reconcile`로 실행하거나 다음 예약 실행을 기다립니다. `status`는 쓰지 않고 조회만 합니다.

| 현재 증거 | 조치 상태 |
| --- | --- |
| CVE가 남고 연결된 PR 없음 | assigned |
| 관련 PR이 연결됨 | in-progress |
| 검증 환경은 0건, 운영에는 남음 | awaiting-production |
| 아래 완료 조건 모두 충족 | verified |

완료하려면 두 환경의 대상 패키지 목록이 존재하고 대상 CVE가 없어야 합니다. 영향받은 이미지가 교체됐고, 두 환경에 같은 릴리스·이미지 digest가 배포됐으며 해당 commit의 전체 배포 파이프라인이 성공해야 합니다. 증거가 없거나 서로 다르면 완료 처리하지 않습니다.

완료 시 이슈와 선택한 원본 평가만 닫습니다. 과거 이미지 기록·다른 서비스의 같은 CVE·다른 취약점을 일괄 종료하지 않습니다. 검증 전에 이슈만 수동으로 닫으면 다음 확인에서 다시 엽니다. 수동 예외·유예 판단이 적용된 평가는 자동으로 덮어쓰지 않고 검토를 요구합니다.

## 6. 주기적 확인 설정하기

Concert **Workflows → Jobs → Create job**에서 이 워크플로우를 선택하고 기본 입력 사용을 끈 뒤 `operation=reconcile`, 서비스와 CVE를 지정합니다. 시간대와 Hourly 주기를 선택하고 Enable job을 켭니다.

이번 실습에는 **Langflow CVE case — hourly**가 활성화됐습니다. 매시간 44분에 장바구니의 이 CVE만 확인하며, 첫 예약 실행 성공을 확인했습니다. 다른 CVE를 모두 자동 등록하는 전역 규칙은 켜지 않았습니다. 범위를 늘릴 때는 대상 서비스·심각도·담당자와 생성량을 먼저 검토합니다.

## 실제 확인한 범위

- Concert 연결 티켓 #4와 담당자 배정·기한 기록 성공.
- 수동 재실행과 예약 재확인 성공. 이슈 1개·댓글 2개 유지.
- 검증·운영 모두 python-multipart 0.0.6, 대상 CVE 1건씩이므로 `not_closed` 유지.
- 미래 기한 초과 미리보기 성공, 실제 이슈 변경 없음.
- 누락된 패키지 목록, 실패한 파이프라인, 미교체 이미지, 운영 미반영, 기한 보존 등 8개 자동 테스트 통과.

**현재 장바구니 패치는 직접 체험할 수 있도록 미적용 상태입니다.** 이번 조치 건의 PR→운영→자동 종료는 아직 실행하지 않았습니다. 완료 분기는 테스트 데이터로 검증했고, 실제 실행에서는 미조치 CVE를 닫지 않는 동작까지 확인했습니다.

## 문제가 생기면

| 증상 | 확인할 것 |
| --- | --- |
| 티켓 API 403 | 대상 원본 finding의 `findings_id`를 `object_id`에 전달하는지. 화면 행의 `id`·`assessment_id`와 구분 |
| 티켓은 생성됐지만 후속 처리 실패 | 원본 CVE의 티켓과 기존 이슈를 먼저 확인. 동일 자동 생성 제목·본문·담당자가 확인되면 그 이슈를 복구하여 사용 |
| 패치 후에도 완료 안 됨 | 두 환경의 최신 배포·패키지·CVE 수집, digest, 최신 전체 파이프라인 성공 여부 |
| 기한 초과인데 라벨이 그대로임 | Jobs 활성 상태와 Logs의 예약 실행 결과 |

GitHub 이슈 100개 또는 타임라인 100개 이상의 페이지 처리, 동시 최초 생성의 잠금 처리는 확장 대상입니다. 대규모 적용 전 영속 상태 저장소·동시 실행 제어·조직별 SLA 기준·장애 알림을 준비합니다. 이 데모는 Concert에 정상 수집된 최신 배포 증거를 기준으로 하므로 수집 작업 자체의 최신성도 관리해야 합니다.

관련 제품 기능: [Concert 티켓 생성](https://www.ibm.com/docs/en/concert/2.3.x?topic=vulnerability-opening-tickets-address-vulnerabilities), [Concert 자동화 규칙](https://www.ibm.com/docs/en/concert?topic=automation-rules).

## 기본 GitHub 티켓 수집의 현재 제한

기본 GitHub ingestion job은 이슈 조회에는 성공했지만 같은 저장소의 여러 앱 버전을 연결하는 단계에서 409 오류(앱 이름·버전을 명시해야 함)가 발생했습니다. 진단 작업 `Langflow Shop GitHub Ticket Sync`는 비활성화하고 기록을 보존했습니다. 현재 워크플로우는 GitHub API의 실제 이슈 상태와 Concert 원본 평가를 각각 읽어 확인합니다. Concert에 저장된 외부 티켓 상태 배지의 자동 동기화까지 성공한 것은 아닙니다. 이 수집 문제는 별도로 해결한 뒤 기본 작업을 활성화해야 합니다.

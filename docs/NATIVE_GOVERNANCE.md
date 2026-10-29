# 기본 Automation rules·Goals와 배포 후 검증

담당자와 SLA는 Concert 화면에서 설정합니다. Workflows의 JSON에는 담당자 표나 기한 계산식을 넣지 않습니다.

| 역할 | 설정 위치 | 확인할 결과 |
| --- | --- | --- |
| CVE 조건에 따라 티켓 생성·배정 | Administration → Integrations → Automation rules | 원본 CVE의 티켓 링크와 외부 이슈 담당자 |
| 심각도별 조치 기한 준수 추적 | Protect → Goals → Vulnerability SLA Adherence | Critical 2일·High 7일, Met/Unmet 평가 |
| 실제 패치 결과 확인 | Workflows → Langflow Post-patch Verification | 두 환경의 현재 이미지·패키지·대상 CVE·배포 파이프라인 |

## 1. 조치 기한 설정

Goals에서 **Vulnerability SLA Adherence → … → Edit**를 엽니다. Critical을 **2일**, High를 **7일**로 설정하고 Next → Activate합니다. Medium·Low 등 다른 기준은 조직 정책에 맞춰 유지합니다.

이 설정은 Concert의 SLA 준수 목표입니다. GitHub 이슈의 Due date나 본문을 자동 작성한다는 뜻은 아닙니다. `Notify the application owner`의 앱 소유자는 외부 이슈의 담당자와 다른 설정입니다. 알림 설정 저장과 실제 알림 전달 성공도 구분합니다.

## 2. 담당자 배정 규칙 설정

1. GitHub connection에 대상 이슈 저장소를 읽고 쓸 수 있는 인증을 등록합니다.
2. **Automation rules → Create automation rule**에서 `A CVE is detected`를 선택합니다.
3. Application 또는 Environment와 조건을 지정합니다. 앱 기준 양식에서는 버전도 선택하므로 새 버전으로 바뀔 때 적용 범위를 확인합니다.
4. `Open a GitHub issue`, Target organization, Target repository, Connection, Assignees를 지정합니다.
5. 필요하면 수정 가능한 CVE만 티켓을 만들도록 설정합니다. 조건과 예상 건수를 확인한 뒤 활성화합니다.

설치된 Concert는 GitHub Assignees를 **조직 구성원으로 검사**합니다. 개인 소유 저장소에서 배정 가능한 사용자여도 이 검사에서 거부될 수 있습니다. 이번 환경의 `Goseokbin` 개인 저장소에서 실제 재현했습니다. GitHub 사용자 조회와 저장소 assignee 검사는 성공했지만 조직 구성원 조회는 404였습니다. 애플리케이션 코드는 기존 저장소에 두고, 조직에 별도 조치 티켓 저장소를 만들어 연결할 수 있습니다.

이 동작을 모든 버전의 제약으로 일반화하지 않습니다. 설치 버전에서 실제 규칙 생성과 자동 티켓의 assignee를 확인합니다. 담당자를 생략한 규칙을 켜고 자동 배정에 성공했다고 설명하지 않습니다.

## 3. 패치 후 두 환경 검증

개발자는 일반 PR로 패치합니다. 기존 GitHub Actions가 스캔·Concert 수집·검증 환경 배포와 테스트를 수행하고, 사람이 production을 승인하면 동일 이미지 digest를 운영에 배포합니다.

**Langflow Post-patch Verification → Run**의 입력은 세 가지입니다.

| 입력 | 미조치 예 | 이미 패치된 예 |
| --- | --- | --- |
| service | cart-service | user-service |
| expected_package | python-multipart | python-multipart |
| cve | CVE-2024-53981 | CVE-2024-53981 |

이 흐름은 GET 요청만 수행합니다. 티켓 생성·담당자·기한·평가 상태·코드·배포를 변경하지 않습니다. `verified`는 이 검증 실행의 결과이며 원본 CVE 평가나 티켓을 자동 종료한 결과가 아닙니다.

확인 순서는 최신 파이프라인 배포 → 실제 이미지 digest → 그 이미지의 패키지 목록과 CVE → 두 환경의 릴리스·이미지 일치 → 해당 릴리스의 전체 배포 파이프라인 성공입니다. 목록이 없거나 페이지가 잘렸을 가능성이 있으면 완료로 판정하지 않습니다. 수집된 증거 기준이므로 수집 작업의 최신성도 관리합니다.

### 다른 환경에 Import하기

`openshift/remediation/verification-workflow-config.example.json`을 복사해 Concert·GitHub 인증 참조, 앱·환경 ID와 배포 접두사를 채웁니다. 인증 값 자체는 파일에 넣지 않습니다. 앱 저장소는 이슈 저장소와 달라도 됩니다. 이 파일의 `repository`는 **배포 파이프라인이 있는 앱 저장소**입니다.

```bash
python3 scripts/build-post-patch-verification-workflow.py \
  --config /path/to/local-verification-config.json \
  --output /path/to/verification-cutover.zip \
  --retire-legacy
```

Workflows → Import에서 ZIP을 가져옵니다. `--retire-legacy`는 이전 `Langflow CVE Case Management`의 같은 이름에 읽기 전용 종료 안내를 등록합니다. 실행 이력은 삭제하지 않습니다. 기존 담당자·기한 예약 작업도 Jobs에서 끕니다.

Jobs에서 새 검증 흐름, Hourly, Enable job을 선택하면 지정한 서비스·패키지·CVE의 조회만 예약됩니다. 전체 CVE를 자동으로 순회하는 작업은 아닙니다. 패치 후에는 Run으로 즉시 확인할 수도 있습니다.

## 이번 실제 확인

현재 배포 릴리스는 `1.0.1-c2b2099a6000`이며 이미지를 재빌드하거나 새 버전을 만들지 않고 검증했습니다.

기본 규칙 **Langflow shop critical CVE ownership**은 이 릴리스의 수정 가능한 CVSS 9.9 이상 결과에 적용했습니다. 소스 재스캔 수집 후 Concert가 [조직 저장소 이슈 #1](https://github.com/goseokbin-concert/concert-remediation/issues/1)을 자동 생성하고 Goseokbin에게 배정했습니다. axios 1.6.2의 CVE-2025-62718·CVE-2026-42043 두 건이 컴포넌트별 이슈 하나에 묶였습니다. 앱 저장소와 배포 파이프라인은 기존 위치를 유지했고, 조치 티켓 저장소는 비공개입니다. 다른 저장소의 PR에서 참조할 때는 `Refs goseokbin-concert/concert-remediation#1`처럼 전체 이름을 씁니다.

이 규칙은 모든 High·Critical 대상의 전역 규칙이 아닙니다. 범위를 확대하기 전에 생성량과 담당 팀을 확인합니다. 다음 앱 버전에도 자동 적용된다고 가정하지 말고 적용 버전을 확인합니다.

| 항목 | 결과 |
| --- | --- |
| native Goals | Critical 2일·High 7일 저장, 재평가 Unmet / observed value 45 |
| native Automation rule | 조직 저장소에 이슈 1개·CVE 2건·담당자 Goseokbin 자동 생성 |
| cart-service | python-multipart 0.0.6, 대상 CVE 검증 1건·운영 1건 → target_present |
| user-service | python-multipart 0.0.32, 대상 CVE 두 환경 0건 → verified |
| 두 실행의 변경 여부 | writes_enabled=false |
| 기존 담당자·기한 job | 비활성화, 기존 워크플로우는 종료 안내로 전환 |
| 새 검증 job | Langflow post-patch verification — hourly, 매시간 42분 |
| 실제 예약 실행 | Job scheduler 실행 성공, cart-service 대상 CVE가 남아 있어 target_present |

Goals의 observed value 45는 해당 목표 평가 값입니다. 이를 전부 langflow-shop의 위반 건수라고 해석하지 않습니다. 다른 CVE가 남아 있으므로 대상 한 건의 `verified`가 앱 전체 무결함을 뜻하지 않습니다.

기존 이슈 #4는 미조치 상태와 과거 기록을 보존합니다. 예전 워크플로우가 본문에 기록한 기한·라벨을 현재 native Goals의 이슈별 기한으로 해석하지 않습니다.

조직 이슈 저장소의 기본 GitHub 수집 작업 `Langflow Native GitHub Ticket Sync`도 Run now로 실행해 SUCCESS를 확인했습니다. 다만 현재 앱 버전의 개별 CVE 조회에는 `issues=[]`가 반환되어 원본 행의 티켓 배지 연결은 확인하지 못했습니다. 자동 생성·배정 성공 및 수집 job 성공을 양방향 상태 동기화 검증으로 설명하지 않습니다. 기존 개인 코드 저장소의 수집은 다중 앱 버전 처리에서 409가 발생했으므로 비활성 상태로 보존했습니다.

기본 기능 참고: [Automation rules](https://www.ibm.com/docs/en/concert?topic=automation-rules), [우선순위 CVE의 자동 티켓](https://www.ibm.com/docs/en/concert/3.0.x?topic=rules-automating-tickets-prioritized-cves).

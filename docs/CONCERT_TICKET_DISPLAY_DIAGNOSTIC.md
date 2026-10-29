# Concert CVE 티켓 표시 점검

## 현재 결론

`cart-service / python-multipart 0.0.6 / CVE-2024-53981`의 GitHub 티켓 #6은 Automation rule이 생성했고 Goseokbin이 배정돼 있습니다. **Concert 내부 평가 기록에도 #6이 연결돼 있지만, 앱의 CVE 목록과 빌드 아티팩트 CVE 목록에서는 링크가 누락됩니다.** 이 두 조회 결과의 불일치가 확인됐으며, 정확한 제품 내부 원인은 아직 확정하지 못했습니다.

따라서 이슈를 새로 만들거나 PR 본문에 티켓 번호를 다시 넣는 것만으로 이 칸을 해결할 수 없습니다. PR에는 추적용 `Refs #6`을 사용하되, 기존 티켓을 중복 생성하지 않습니다.

## 재현 정보

| 항목 | 값 |
| --- | --- |
| 애플리케이션 | langflow-shop 1.0.0 |
| 앱 ID | 1199cceb-e68f-4f6f-a96c-b9bffa0b7431 |
| 버전 ID | a6b8821f-b02b-4417-b91e-d3831aea377a |
| 이미지 인스턴스 ID | 62b7ef0c-7c76-45b9-9366-5a08d53a8cb0 |
| 이미지 | image-registry.openshift-image-registry.svc:5000/shopping-mall/cart-service |
| 이미지 digest | sha256:18db88a4c917301dd8e6fa8fe1f80837bf9a2a678610a7608c7520c54ed35811 |
| CVE | CVE-2024-53981 |
| 티켓 | https://github.com/goseokbin-concert/langflow-shop-msa/issues/6 |
| 확인일 | 2026-10-29 |

동일 인증·동일 대상에 대한 GET 비교:

1. `/concert/core/api/v2/cves/CVE-2024-53981/assessments?page_size=100`의 cart-service 행에는 `issues[0].issue_link.issue_id = "6"`, GitHub URL, 담당자 `Goseokbin`이 있습니다.
2. `/concert/ingestion/api/v1/vulnerability_assessments`를 앱 이름과 전체 이미지 이름으로 조회해도 같은 티켓 연결이 있습니다.
3. 앱 버전 하위 `/build_artifacts/62b7ef0c-7c76-45b9-9366-5a08d53a8cb0/cve_findings?search=CVE-2024-53981&page_size=100`는 같은 CVE에 `issues: []`를 반환합니다.
4. 실제 브라우저의 Ticket 칸에는 기존 #6 링크 대신 `+ Open ticket`이 표시됩니다.

인증값·쿠키·원본 API 전체 응답은 이 문서에 포함하지 않습니다.

## 수행한 보완과 남은 조치

- 현재 앱 버전은 1.0.0 하나임을 확인했습니다.
- 현재 앱에 연결되지 않은 리허설 소스 인스턴스 하나는 백업 후 정리했습니다. main 연결은 유지했습니다.
- GitHub 기본 티켓 수집을 실제 재실행했습니다. 13개 이슈 읽기는 성공했으나, 저장소 등록 단계가 `409 / CNCRTRCOSR10008E`로 실패했습니다. 앱·버전 문맥이 모호하다는 오류이며, 설치된 수집 코드의 저장소 요청에는 해당 문맥이 전달되지 않습니다. 이 실패가 반복되지 않도록 점검 후 수집 job을 비활성으로 되돌렸습니다.
- Concert 기본 파생 데이터 갱신 작업을 한 번 요청했습니다. 상위 작업이 하위 작업을 접수한 것은 확인했으나, 하위 갱신 완료는 확인하지 못했습니다. 후속 GET에서 빈 `issues`가 계속 재현됐으므로 갱신 성공이나 티켓 칸 복구를 주장하지 않습니다.
- 벤더 코드·DB·화면 응답을 임의로 바꾸지 않았습니다. 이슈·취약점을 삭제하거나 상태를 조작하지 않았습니다.

**제품 지원으로 전달할 두 항목:** (1) CVE 평가 조회와 앱/아티팩트 CVE 조회의 티켓 연결 불일치, (2) GitHub 기본 수집의 source repository 등록 요청에서 앱·버전 문맥을 지정하지 않아 발생하는 409. 지원되는 수정 또는 패치를 적용한 뒤 두 API의 #6 일치, 실제 화면 링크, GitHub 상태 재수집을 각각 재검증해야 합니다. 아직 지원 요청을 외부로 보내지는 않았습니다.

현재 데모에서는 [기존 GitHub #6](https://github.com/goseokbin-concert/langflow-shop-msa/issues/6)에서 담당·패치 PR을 확인합니다. 앱 CVE 표에 링크가 자동 표시되는 장면과 양방향 자동 종료는 아직 정상 동작 장면으로 설명할 수 없습니다.

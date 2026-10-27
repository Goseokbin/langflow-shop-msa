# Concert 인증서 관리 따라하기

HTTPS 인증서의 만료일, 발행자와 영향을 받는 접속 주소를 Concert에서 함께 확인합니다.

## 1. 별도 데모 주소 만들기

OpenShift에 로그인한 상태에서 실행합니다. OpenSSL 3와 Python 3가 필요합니다.

```sh
python3 scripts/create-certificate-demo.py --namespace shopping-mall --days 5
```

기존 frontend·api-gateway·langflow Route는 그대로 두고, frontend Service를 향하는 `certificate-demo` Route와 전용 TLS Secret만 생성합니다. 자체 서명 인증서이므로 브라우저 신뢰 경고가 예상됩니다. 기존 Route가 데모 라벨을 가지고 있으면 재실행 시 인증서를 교체하지 않습니다.

## 2. 수집 워크플로 만들기

`openshift/certificates/config.example.json`을 복사하여 실제 Concert 호스트, 환경 이름/ID, Workflows 인증 참조, 수집할 HTTPS 호스트를 채웁니다. 키나 비밀번호를 넣지 않습니다.

Workflows의 인증 관리에서 Concert와 함께 설치된 환경은 `IBM/HubSelf` 인증을 업로드용으로 만들고, 조회용은 `Authorization` 헤더를 사용하는 Concert API 키 인증을 만듭니다. API 키 값은 Workflows 암호화 인증 저장소에만 입력합니다.

```sh
python3 scripts/build-certificate-workflow.py --config /path/to/config.json --output /path/to/workflow.json
```

Workflows에서 생성된 JSON을 가져와 `Langflow Certificate Inventory`를 실행합니다. 예제 JSON을 바로 가져왔다면 config 변수의 예시 값을 먼저 바꿉니다.

흐름: 호스트별 TLS 조회 → 공개 인증서 DER 해석 → 지문 기준 중복 제거 → 환경·공용 액세스 지점 연결 → Concert 업로드 → 수집 완료 및 연결 검증.

실행 결과의 `stage=verified`, `target_count=4`, `unique_certificates=2`를 확인합니다. 수집 이벤트 접수만으로 성공 처리하지 않습니다. 인증서 개인 키는 수집하거나 업로드하지 않습니다.

## 3. 화면에서 확인하기

Concert **Protect → Operations(조작) → 인증서**에서 확인합니다.

- 실제 세 Route가 공유하는 인증서 1개와 데모 주소의 인증서 1개가 표시됩니다.
- 데모 인증서는 7일 만료 임계값 안에 있어 곧 만료 상태가 됩니다.
- 인증서 일련번호 → 토폴로지에서 환경과 공용 액세스 지점 연결을 확인합니다.
- 공유 인증서는 여러 주소에서 수집해도 한 항목이며, 재수집해도 같은 일련번호를 갱신합니다.

설정 → 인증서 정책에서 만료 임계값과 허용 알고리즘·키 길이를 확인합니다. 알려진 발행자는 인스턴스 전체 정책이므로 운영에서 사용하는 CA 목록을 먼저 정합니다. 데모 자체 서명 발행자를 신뢰 목록에 추가하지 않습니다.

실제 환경 검증에서 만료·발행자·해시 알고리즘 평가는 확인했습니다. RSA 2048비트를 수집했지만 설치된 Concert 3.1의 키 길이 정책 결과는 비준수로 남아 있습니다. 실제 키가 2048비트보다 짧다는 뜻으로 해석하지 말고 수집 필드 매핑/제품 평가 동작을 추가 확인해야 합니다. 이 문제를 감추려고 최소 키 길이 정책을 낮추지 않았습니다.

## 4. 매일 자동 수집

Workflows → Jobs에서 위 워크플로, 입력값 없음, 시간대 `Asia/Seoul`, 매일 `09:00`, Enabled를 설정합니다. 기존 패치 PR 작업과는 별개입니다.

## 5. 데모 범위와 정리

이번 구성은 외부 HTTPS 인증서 인벤토리와 만료·정책 확인입니다. 서버의 JKS/P12 키 저장소를 등록하지 않아 키 저장소 항목은 비어 있으며 자동 갱신은 설정하지 않았습니다. 갱신 자동화에는 CA 발급, Secret/Route 반영, 재조회 검증, 실패 시 복구를 별도 구성해야 합니다.

실습 후에는 먼저 인증서 수집 Job을 중지하고 config에서 데모 주소를 제거합니다. 데모 자원만 삭제합니다.

```sh
oc delete route certificate-demo -n shopping-mall
oc delete secret concert-certificate-demo-tls -n shopping-mall
```

Concert에 남은 데모 인증서/접속 주소는 연결 관계를 확인한 뒤 정리합니다. 실제 공유 ingress 인증서는 삭제하지 않습니다.

참고: [IBM 인증서 업로드 문서](https://www.ibm.com/docs/en/concert?topic=certificates-uploading-certificate-details)

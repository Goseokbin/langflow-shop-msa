# 같은 워크플로우로 다른 패키지 패치하기

Concert의 **Langflow Dependency Remediation** 하나를 재사용한다.
실행 때 `policy_id`와 `operation`만 바꾼다. CVE마다 흐름을 복사하지 않는다.

| 입력 | 예시 | 의미 |
| --- | --- | --- |
| policy_id | multipart / jose / requests | 저장소에서 검토한 패치 정책 ID |
| operation | plan | 현재 이미지의 CVE와 수정할 소스를 확인 |
| operation | create-pr | 허용된 버전 한 줄을 바꾸는 PR 생성 또는 재사용 |
| operation | verify | 현재 양쪽 배포·소스·파이프라인을 대조 |

## 달라지는 것은 작업 명세

`scripts/remediation-policies.json`에 서비스, 패키지, 현재/수정 버전,
파일, 대상 CVE, 수정 버전 근거, PR 브랜치, 호환성 검사와 포트를 기록한다.
Workflows는 매 실행 GitHub main의 이 파일을 인증된 API로 읽는다.
정책을 추가해도 워크플로우를 다시 만들거나 Import하지 않는다.
등록되지 않은 정책 ID는 PR 생성 전에 거부한다.

지원 범위는 Python 서비스의 requirements.txt 직접 의존성 버전 한 줄이다.
extras(`python-jose[cryptography]`)를 보존한다. npm, 간접 의존성, 여러 파일 변경,
애플리케이션 코드 수정은 이 실행기로 자동 처리하지 않는다.
새 패키지는 변경 정책과 필요한 호환성 검사를 검토한 뒤 저장소에 반영한다.
워크플로우가 임의 CVE의 호환성과 패치 방법을 자동 판단하는 것은 아니다.

## 공통 실행 절차

1. `policy_id=multipart`, `operation=verify`: 앞선 사례를 같은 흐름에서 재확인한다.
2. `policy_id=jose`, `operation=plan`: 다른 패키지/CVE의 현재 발견 근거를 읽는다.
3. `operation=create-pr`: Concert가 PR을 만든다.
4. GitHub의 01 변경 범위, 02 소스·이미지/호환성, 03 CodeQL 검사를 확인한다.
5. PR merge 후 main 파이프라인이 검증 배포와 기능 검사를 수행한다.
6. 운영 승인은 사람이 한다. 승인한 검증 이미지 digest를 그대로 승격한다.
7. 같은 워크플로우의 `operation=verify`로 두 환경을 다시 확인한다.

워크플로우는 환경 ID와 파이프라인 배포 이름 접두어를 사용해 최신 Concert
배포 문서를 매번 찾는다. 이 문서는 수집된 배포 근거이므로 별도 증거 수집기는
실제 Pod 버전과 현재 Kubernetes Deployment 이미지도 대조한다.

## 두 번째 사례

user-service의 python-jose **3.3.0 → 3.5.0**, **CVE-2024-33664**.
[공식 3.4.0 릴리스 공지](https://github.com/mpdavis/python-jose/releases/tag/3.4.0)의
수정 근거를 사용한다. JWT 발급/검증, 변조·만료·다른 키·subject 누락 거부,
제한된 정상 JWE 압축 왕복, 의존성 해석, DB health 및 실제 쇼핑몰 기능을 검사한다.
선택한 CVE가 없어져도 다른 python-jose CVE가 남을 수 있다.

## 설치와 증거 저장

초기 공통 워크플로우 설치 때만 다음 ZIP을 Import한다.
config는 기존 인증 참조, repository, concert_host, application_api,
source_repo_id, staging/production_environment_id 및 각 deployment_prefix를 담는다.
키 값은 넣지 않는다.

```bash
python3 scripts/build-two-env-patch-workflow.py --config config.json --output common-workflow.zip
python3 scripts/collect-environment-cve-evidence.py --policy jose --phase baseline \
  --staging-kubeconfig <검증 kubeconfig> --production-kubeconfig <운영 kubeconfig> \
  --output baseline.json
```

검증 배포 후 `--phase staging-tested`, 운영 승격 후 `--phase production-promoted`로
동일 패키지와 CVE를 대조한다. 과거 이미지 기록이나 다른 서비스의 발견은 닫지 않는다.

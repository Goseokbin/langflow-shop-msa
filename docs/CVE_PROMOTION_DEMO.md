# Concert에서 CVE 패치 PR → 검증 → 승인 → 운영 승격

예제는 user-service의 python-multipart 0.0.6을 0.0.32로 올려 CVE-2024-53981을 제거합니다. 보안 공지는 0.0.18 이상을 수정 버전으로 제시합니다. 현재 PyPI의 안정 버전 0.0.32를 사용하고 실제 FastAPI 폼·업로드·오류 처리 호환성을 먼저 검사합니다. 다른 취약점이나 과거 이미지의 발견 항목까지 해결됐다고 처리하지 않습니다.

## 준비

- 두 클러스터의 별도 kubeconfig와 `shopping-mall` / `shopping-mall-prod` 배포
- 앞의 동일 이미지 승격 파이프라인 및 GitHub production 승인 규칙
- Concert Workflows의 GitHub·Concert 인증 참조: 기존 인증을 재사용하며 키를 코드나 ZIP에 넣지 않습니다.
- config JSON에 repository, concert_host, application_api, source_repo_id, github_auth, concert_auth 및 staging/production_environment_id·deployment_id를 지정합니다.

```bash
python3 scripts/build-two-env-patch-workflow.py --config <config.json> --output <multipart-workflow.zip>
```

Workflows → Import에서 ZIP을 선택합니다. JSON 원본은 편집용이며 목록의 Import는 ZIP을 사용합니다. 기존 requests 패치 워크플로우와 인증서 워크플로우는 유지합니다.

## 데모 순서

1. `Langflow Multipart CVE Promotion Demo`를 `operation=plan`으로 실행합니다. Concert의 실제 패키지·CVE, 저장소 원문, 검증·운영 배포의 현재 이미지와 발견 항목을 조회합니다.
2. `operation=create-pr`로 실행합니다. 허용된 user-service/requirements.txt의 버전 한 줄만 변경하고 PR을 생성합니다. 기존 PR이 있으면 재사용합니다. 자동 merge·운영 승인은 하지 않습니다.
3. GitHub PR에서 변경 범위, 소스·이미지 Trivy, 의존성 해석, FastAPI parser 회귀, PostgreSQL을 사용하는 실제 서비스 health, CodeQL 결과를 확인합니다.
4. PR을 검토·merge하여 전체 DevSecOps 파이프라인을 실행합니다. 검증 배포·기능 검사가 완료되면 production 승인에서 멈춥니다.
5. 이 시점의 두 환경을 비교합니다. 검증의 새 user-service 이미지에는 수정 패키지가 있고 대상 CVE가 없어야 합니다. 운영은 여전히 이전 이미지·버전·CVE를 유지해야 합니다.
6. 결과를 검토하고 GitHub에서 production을 승인합니다. 검증한 정확한 이미지 digest를 운영에 적용하고 재검사합니다.
7. Workflows를 `operation=verify`로 실행합니다. 원본 배포 파이프라인 성공과 두 환경의 동일 이미지·수정 버전·대상 CVE 부재를 함께 확인해야 `closure=verified`가 됩니다.

관측 결과는 다음 명령으로도 저장할 수 있습니다. kubeconfig는 명시적으로 지정합니다.

```bash
python3 scripts/collect-environment-cve-evidence.py \
  --phase baseline \
  --staging-kubeconfig <검증 kubeconfig> \
  --production-kubeconfig <운영 kubeconfig> \
  --output <baseline.json>
```

phase를 staging-tested, production-promoted로 바꿔 세 시점의 JSON을 보관합니다. 이 명령은 실제 Pod의 설치 버전, Deployment digest, Concert 배포 SBOM, 해당 이미지 아티팩트의 패키지·CVE를 대조합니다. 인증정보는 보고서에 포함하지 않습니다.

| 시점 | 검증 | 운영 |
| --- | --- | --- |
| 패치 전 | 0.0.6, 대상 CVE 있음 | 0.0.6, 대상 CVE 있음 |
| 검증 성공·승인 대기 | 0.0.32, 대상 CVE 없음 | 이전 digest·0.0.6·CVE 유지 |
| 운영 승인·승격 후 | 수정 digest, CVE 없음 | 검증과 같은 digest, CVE 없음 |

위 표는 기대 결과입니다. 실제 실행 증거를 대조해 결과를 기록하며, 실패 시 성공으로 표시하지 않습니다. 과거 취약 이미지가 Concert에 보존돼 있으면 전역 CVE 건수는 남을 수 있습니다. 현재 배포 이미지에 범위를 맞춰 설명합니다. 모델 추론과 다른 CVE는 기존 감사 모드의 별도 범위입니다.

## 판정 범위

이 정책은 user-service의 현재 배포 이미지에 대한 조치만 검증한다. 다른 서비스가 같은 CVE를 보유해도 임의로 닫지 않는다. `global_cve_closed=false`는 의도된 결과이고, `closure=selected_service_verified`는 선택한 서비스의 두 환경 검증 완료를 뜻한다. Concert 릴리스는 소스 커밋별로 분리해 이전 운영 릴리스의 스캔 관계를 보존한다.

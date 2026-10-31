# Plan: 기본 GitHub Actions CI

- 입력: [spec.md](spec.md).
- 상태: 구현·로컬 검사 완료, CodeRabbit 검토 완료, 실제 CI 확인 대기.

1. 공식 GitHub Python CI와 Astral setup-uv 문서·Action release SHA를 확인한다.
2. .github/workflows/ci.yml을 추가한다. PR·main push, 읽기 권한, 취소 그룹, 여섯 OS/Python 조합, 제한 시간과 개별 검사 단계를 구성한다.
3. scripts/smoke_cli.py를 추가한다. 합성 PNG로 설치된 CLI의 도움말·변환·메타데이터 읽기를 실제 subprocess로 실행한다. 사용자 데이터를 덮어쓰지 않는다.
4. README·docs/project.md·workflow.md·verification.md에 CI 범위·로컬 명령·기존 GPU 검사의 경계를 반영한다. 검증 전 성공을 선언하지 않는다.
5. 별도 임시 가상환경에서 워크플로 명령을 로컬 실행하고 actionlint·문서 링크·공백 검사와 잠금 불일치 실패를 확인한다. 앱의 기존 가상환경과 잠금 파일은 보존한다.
6. PR 전 로컬 CodeRabbit 리뷰를 실제 실행하고 타당한 지적을 수정한다.
7. codex/005-github-actions-ci를 push해 PR #2 브랜치 대상의 별도 PR을 생성한다. GitHub-hosted 여섯 작업이 끝날 때까지 결과를 확인하고 실패가 있으면 원인을 수정한다. 인라인 리뷰에도 답글·해결 여부를 확인한다.
8. 실제 실행 URL과 결과·남은 한계를 evidence에 기록한다.

## 위험·되돌리기

새 CI의 최초 실제 러너 실행은 PR 생성 후에 확인할 수 있다. 그 전에는 설정·로컬 검사까지만 검증했다고 기록한다. 플랫폼 차이의 기존 버그를 발견하면 먼저 재현하고 이 범위에 필요한 수정만 한다. 워크플로 삭제로 CI를 되돌릴 수 있으며 모델·생성 원본·프로젝트 데이터는 건드리지 않는다. 배포·브랜치 보호·병합 권한은 변경하지 않는다.

## 확인한 공식 자료

- https://docs.github.com/en/actions/tutorials/build-and-test-code/python
- https://docs.astral.sh/uv/guides/integration/github/
- https://github.com/actions/checkout/releases/tag/v7.0.1
- https://github.com/astral-sh/setup-uv/releases/tag/v10.3.3

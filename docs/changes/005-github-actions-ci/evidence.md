# Evidence: Windows·Linux CI

- 변경 ID: 005-github-actions-ci.
- 날짜: 2026년 10월 31일.
- 상태: 워크플로·스모크 구현과 로컬 검사 완료. PR 전 CodeRabbit 검토 완료, 지적 0건. 실제 GitHub-hosted 실행은 PR 생성 후 확인한다.
- 기준 브랜치: codex/004-pixel-model-comparison, 17813c4.

## 수락과 구성

사용자가 GitHub Actions로 잠금 설치·전체 검사·wheel·CLI를 Windows·Linux에서 실행하는 구성을 요청했다. 별도 codex/005-github-actions-ci 브랜치에서 PR #2 뒤에 이어지는 작업으로 구성했다. 실제 GPU 생성과 그림 품질 평가는 기존 별도 통합 검사로 유지한다.

- 이벤트: 모든 pull_request, main push.
- 조합: ubuntu-latest·windows-latest × Python 3.11·3.12·3.13, fail-fast=false.
- uv 0.9.3 고정, uv.lock·pyproject.toml을 기준으로 캐시. --locked 설치 후 run --no-sync로 검사.
- contents:read, 체크아웃 토큰 보존 금지, 15분 제한, PR별 오래된 실행 취소.
- Action 공식 release의 실제 tag commit 확인: checkout v7.0.1 = 3d3c42e5aac5ba805825da76410c181273ba90b1, setup-uv v10.3.3 = 68559e99cc807c1eb7e9238fd43a15bba460eec2.

## 로컬 실제 명령과 결과

Windows의 별도 UV_PROJECT_ENVIRONMENT=tmp/ci-validation에서 실행했다. 이 환경은 새로 생성됐고 Python 3.12.10을 선택했다. 기존 개발 .venv와 ComfyUI 환경은 변경하지 않았다. uv 실행은 기존 설치의 절대 경로를 사용했다.

- uv sync --locked --no-editable: 33개 패키지 설치, 종료 코드 0. 앱도 소스 editable 대신 패키지로 설치했다.
- uv run --no-sync python -m unittest discover -s tests -v: 기존 44개 전체 통과, 종료 코드 0.
- uv run --no-sync python -m compileall -q src tests examples scripts: 종료 코드 0.
- uv build --wheel: dist/pixelart_maker-0.1.0-py3-none-any.whl 생성, 종료 코드 0.
- uv run --no-sync python scripts/smoke_cli.py: 실제 설치된 CLI의 도움말·합성 PNG convert·inspect, 한글·공백 경로와 결과 파일 확인 통과, 종료 코드 0. ComfyUI 연결이나 모델·GPU를 사용하지 않았다.
- 잠금 거절 검사: 임시 복사본의 프로젝트 버전만 0.1.1로 바꾸고 uv sync --locked --no-editable --offline --project <copy> 실행. 잠금 갱신이 필요하다는 오류와 종료 코드 1을 확인했다. 복사본·원본 uv.lock은 모두 변경되지 않았다.
- 원본 uv.lock SHA-256 유지: 53991f1a1d72d52b9d6ddb14cd2ed06de03b17bfe6d32eedf0b276d6ff6f0012.
- actionlint 1.7.12 .github/workflows/ci.yml: 문법·표현식 검사 통과, 종료 코드 0. 공식 release의 Windows ZIP SHA-256 6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9를 확인한 뒤 tmp 아래에서만 실행했다.

추가 앱 단위 테스트를 만들거나 기존 테스트를 약화하지 않았다. CI는 기존 전체 검사와 실제 진입점 스모크를 실행한다. 이번 변경은 새 자동화 구성으로 기존 버그 수정에 해당하지 않는다.

## PR 전 CodeRabbit 검토

기존 설치·인증의 CodeRabbit CLI 0.9.2로 coderabbit review --agent --base codex/004-pixel-model-comparison --include-untracked를 실행했다. reviewType=all, review_completed, outcome=completed, findings=0, 종료 코드 0. 워크플로·스모크·문서의 새 변경 10개 파일을 실제 검토했으며 추가 수정 지적은 없었다. 원본 로그는 Git에서 제외한 tmp에 보관한다.

로컬 Markdown 링크 56개·UTF-8·미입력 항목과 변경/신규 파일 10개의 공백 검사도 통과했다. 저장소의 Actions는 enabled=true, allowed_actions=all이며 기존 인증에 workflow 범위가 있어 실행 구성을 바꾸거나 인증을 갱신하지 않았다.

## 실제 GitHub Actions와 미검증 범위

아직 PR을 생성하지 않아 GitHub-hosted 여섯 조합의 실행 결과는 없다. 로컬 Windows 3.12.10 결과를 Linux나 다른 Python 버전 통과로 간주하지 않는다. PR 생성 후 각 job·run URL과 실제 결과를 확인한다.

런타임 의존성은 잠금 설치하지만 격리 빌드 백엔드는 기존 hatchling 범위를 사용하므로 백엔드까지 완전히 잠긴 빌드를 주장하지 않는다. 브랜치 보호·필수 검사 지정·자동 병합·배포·PyPI 게시·GPU·실제 클라우드 생성은 이번 범위가 아니다.

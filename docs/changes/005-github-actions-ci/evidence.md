# Evidence: Windows·Linux CI

- 변경 ID: 005-github-actions-ci.
- 날짜: 2026년 10월 31일.
- 상태: 구현·로컬 검사·실제 GitHub-hosted 여섯 조합 성공. CodeRabbit PR 추가 지적 1건의 실행 증거 보완.
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

[PR #3](https://github.com/AtraFelis/pixelart-maker/pull/3)을 선행 PR #2 브랜치 대상으로 생성했다. 첫 실제 [CI 실행 #1](https://github.com/AtraFelis/pixelart-maker/actions/runs/41195098200)은 commit 0e4b0c0c707148fa80ab258eabbe0d426cb80547, run_attempt=1, status=completed, conclusion=success다.

GitHub API의 각 job·step 상태와 여섯 job의 실제 로그를 읽어 모두 확인했다.

- [ubuntu-latest / Python 3.11.14](https://github.com/AtraFelis/pixelart-maker/actions/runs/41195098200/job/124519566232): success.
- [ubuntu-latest / Python 3.12.12](https://github.com/AtraFelis/pixelart-maker/actions/runs/41195098200/job/124519566151): success.
- [ubuntu-latest / Python 3.13.9](https://github.com/AtraFelis/pixelart-maker/actions/runs/41195098200/job/124519566212): success.
- [windows-latest / Python 3.11.14](https://github.com/AtraFelis/pixelart-maker/actions/runs/41195098200/job/124519566153): success.
- [windows-latest / Python 3.12.12](https://github.com/AtraFelis/pixelart-maker/actions/runs/41195098200/job/124519566185): success.
- [windows-latest / Python 3.13.9](https://github.com/AtraFelis/pixelart-maker/actions/runs/41195098200/job/124519565959): success.
- 각 조합에서 44개 전체 테스트 통과, compileall 성공, wheel 생성, Packaged CLI smoke passed를 실제 로그로 확인했다. 동일한 44개 테스트를 여섯 환경에서 실행한 것이며 서로 다른 264개 테스트로 계산하지 않는다.
- 실제 CI에는 ComfyUI 서버·GPU·모델·생성 API 인증을 구성하거나 사용하지 않았다.

첫 실행 이후 이 증거 문서만 갱신하며 프로그램·테스트·워크플로는 동일하게 유지한다. 후속 문서 커밋에서도 PR 이벤트로 CI가 다시 실행되므로 최신 head의 결과까지 확인한다.

GitHub CodeRabbit은 기본 브랜치 이외의 자동 리뷰를 건너뛰어 이 PR에 한해 @coderabbitai review를 요청했다. 전역/저장소 리뷰 설정은 바꾸지 않았다. 추가 리뷰는 최초 커밋에 대해 COMMENTED로 완료됐고 actionable minor 1건은 “실제 CI 결과·각 작업 URL을 evidence에 기록하고 intent·spec·plan 상태를 갱신”하는 요청이었다. 워크플로·스모크 코드의 신규 수정 지적은 없었다.

이 지적을 수용해 위 여섯 job 로그·결과·URL과 문서 상태를 보완했다. 최초 확인 시점에는 [해당 스레드](https://github.com/AtraFelis/pixelart-maker/pull/3#discussion_r4431499241) 1건이 미해결이었다. 수정 커밋 후 답글·해결 결과와 최신 CI 상태는 PR에서 확인하며, 첫 실행의 성공을 아직 실행하지 않은 후속 커밋의 성공이나 최종 승인으로 확대하지 않는다.

런타임 의존성은 잠금 설치하지만 격리 빌드 백엔드는 기존 hatchling 범위를 사용하므로 백엔드까지 완전히 잠긴 빌드를 주장하지 않는다. 브랜치 보호·필수 검사 지정·자동 병합·배포·PyPI 게시·GPU·실제 클라우드 생성은 이번 범위가 아니다.

## PR #2 리뷰 수정 반영과 설치본 갱신 확인

비교 조건과 재개의 두 버그 수정 729d0a2를 f1d2f6c에 병합했다. [CI #3](https://github.com/AtraFelis/pixelart-maker/actions/runs/41205099506)은 성공했다. 실제 GitHub의 새 체크아웃과 별개로 기존 로컬 tmp/ci-validation의 단순 sync는 비편집 설치본을 갱신하지 않았다. 해당 설치본에서 새 회귀 검사를 실행해 필드 검증 상수가 없고, 8개 검사에서 실패 16건·오류 1건을 확인했다.

설치 명령에 --reinstall-package pixelart-maker를 추가해 프로젝트 패키지만 강제 갱신한다. 잠금 런타임 의존성과 uv.lock은 변경하지 않는다. 첫 CI 실행과 기존 44개 검사 기록은 해당 시점의 증거로 보존한다. 보완한 명령으로 기존 설치본을 새 소스로 재빌드·재설치했다. 이 비편집 설치 환경에서 전체 52개 검사·문법·wheel·CLI 스모크가 모두 종료 코드 0으로 통과했다. 워크플로 보완 후 최신 head의 실제 CI는 PR 체크와 설명의 실행 URL에서 확인한다.


## 시간별 추가 CodeRabbit 리뷰 확인

2026-10-31T13:10:55Z에 a0f8d89의 재리뷰를 요청했고, 13:20:13Z 갱신된 [bot 결과](https://github.com/AtraFelis/pixelart-maker/pull/3#issuecomment-6542534314)에서 “No actionable comments were generated”와 검토 범위 0e4b0c0..a0f8d89를 확인했다. 이 경우에는 새 본문 있는 Review 제출 대신 요약 댓글로 지적 없음이 보고됐다. 진행 표시가 사라지고 대상 커밋 범위가 일치하는지 함께 확인했다. 기존 인라인 스레드는 해결 상태이며 새 지적은 없었다. 그 뒤 반영한 비교 수정·패키지 재설치 보완의 최신 head는 별도 재리뷰 대상으로 시간 한도 이후 예약에서 처리한다.

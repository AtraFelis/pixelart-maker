# Spec: GitHub Actions의 잠금 설치·테스트·빌드

- 입력: [intent.md](intent.md).
- 상태: 구현·로컬 검사 완료, CodeRabbit 검토 완료, 실제 CI 확인 대기.

## 수용 기준

- AC-01: 모든 대상 브랜치의 PR과 main push에서 실행한다. PR별 오래된 실행은 취소하고 각 실행의 OS·Python 결과는 따로 확인한다.
- AC-02: ubuntu-latest·windows-latest와 Python 3.11·3.12·3.13의 여섯 조합을 검사한다. 프로젝트가 선언한 지원 범위를 사용하며 .python-version의 기본 3.12는 변경하지 않는다.
- AC-03: 현재 검증한 uv 0.9.3을 고정하고 uv sync --locked --no-editable로 설치한다. uv.lock과 pyproject.toml의 불일치는 실패해야 한다. run 단계는 --no-sync로 재해석·재설치하지 않는다.
- AC-04: 전체 unittest, compileall src tests examples scripts, uv build --wheel과 CLI 스모크 검사를 각각 실행한다. 실패를 무시하거나 테스트를 생략하지 않는다.
- AC-05: CLI 스모크는 실제 설치된 pixelart 진입점의 --help·convert·inspect를 실행한다. 합성 PNG와 한글·공백 경로를 임시 디렉터리에서 사용하며 완성 프로젝트·최종 파일을 확인한다.
- AC-06: ComfyUI 연결·모델 다운로드·실제 GPU 생성·인증 없이 완료한다. 코드는 읽기 전용 GitHub 토큰으로 체크아웃하며 토큰을 Git 설정에 보존하지 않는다.
- AC-07: Action을 확인한 전체 커밋 SHA로 고정하고 캐시 기준에 uv.lock·pyproject.toml을 포함한다. 캐시는 잠금 검사를 대신하지 않는다.
- AC-08: 로컬 검사와 실제 GitHub-hosted 실행을 구분해 기록한다. PR 전 CodeRabbit 리뷰, 실제 두 OS 실행과 후속 PR 리뷰 스레드 상태를 확인한다.

빌드 백엔드는 기존 pyproject.toml의 hatchling 범위를 격리 환경에서 설치한다. 런타임 의존성은 uv.lock으로 고정하지만 빌드 백엔드 전체까지 재현 가능한 빌드라고 주장하지 않는다. 이번 변경에서 앱 의존성이나 빌드 도구 범위는 변경하지 않는다.

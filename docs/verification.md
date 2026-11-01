# 검증 계약

현재 단계: Python CLI 시제품 구현. 단위·복구·모의 HTTP 검사와 로컬 MCP 생성은 실제 수행하며 결과는 001 evidence에 기록한다. 편집 UI와 실제 다른 PC·클라우드는 미검증이다.

## 초기 구성의 필수 확인

작업 위치는 저장소 루트다. PowerShell 7과 Git을 사용한다.

### 문서·링크·범위

- README에서 project, workflow, verification, 현재·다음 변경 문서로 이동할 수 있어야 한다.
- 문서의 로컬 Markdown 링크가 실제 파일을 가리켜야 한다.
- 전체 개발 계획은 요구 변경 시 관련 변경 기록과 함께 갱신한다. 사용자가 삭제한 선택적 참고 파일은 필수 파일·해시 검사의 대상으로 요구하지 않는다. 과거 evidence는 해당 실행 시점의 기록이다.
- TEMPLATE 밖의 작업 문서에는 채우지 않은 TBD가 없어야 한다.
- 변경 문서의 수락 기록과 실제 구현·검증 상태가 일치해야 한다.
- 실제 수행한 절차와 결과는 해당 변경의 evidence에 기록한다. 초기 구성은 000, 이식성 요구 반영은 002, 참고 파일 삭제 후 정리는 003이다.

### 새 파일까지 포함한 공백 검사

첫 커밋 전에는 일반 git diff --check가 미추적 파일을 검사하지 않으므로 다음 명령으로 현재 존재하는 관리 대상 파일을 검사한다. 삭제된 참고 파일을 위한 예외는 두지 않는다.

~~~powershell
$checkFiles = @(git -c core.quotepath=false ls-files --cached --others --exclude-standard | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
if ($LASTEXITCODE -ne 0) { throw 'Git 파일 목록 조회 실패' }
foreach ($checkFile in $checkFiles) {
  $checkMessages = @(git -c core.autocrlf=false -c core.safecrlf=false diff --no-index --check -- /dev/null $checkFile 2>&1)
  if ($LASTEXITCODE -gt 1 -or $checkMessages.Count -gt 0) { throw "공백 검사 실패: $checkFile $checkMessages" }
}
Write-Output 'Whitespace checks passed'
~~~

성공 기준: 공백 오류 출력 없이 Whitespace checks passed가 표시된다. --no-index는 새 파일의 차이가 있으면 정상 검사에서도 종료 코드 1을 반환하므로 이를 허용하고 공백 오류·그 외 실패는 거절한다. 이 명령은 커밋·스테이징을 하지 않는다.

### 제외 규칙

~~~powershell
git check-ignore --no-index .env .env.local data/example.png output/example.png models/example.safetensors .venv/example node_modules/example .env.example
~~~

성공 기준: 앞의 일곱 로컬 경로만 출력되며 .env.example은 출력되지 않는다. 검사용 실제 파일을 만들 필요는 없다.

### 작업 상태

~~~powershell
git status --short --branch
~~~

성공 기준: 현재 변경과 사용자가 삭제한 파일의 상태가 의도와 일치하고, 비밀정보·모델·생성 이미지가 실수로 포함되지 않는다. 선택적 참고 파일 삭제와 첫 커밋이 없는 상태는 실패가 아니다.

## CLI 시제품의 필수 검사

저장소 루트에서 실행한다. Python 3.12와 uv가 필요하며 로컬 생성에는 별도의 ComfyUI·comfy-mcp·comfy-cli가 필요하다.

- 설치: uv sync --locked. 잠금 파일과 일치하는 .venv 설치 성공.
- 단위·복구·이동·모의 HTTP: uv run --locked python -m unittest discover -s tests -v. 모든 검사 통과, 실패 시 종료 코드 비정상.
- 문법: uv run --locked python -m compileall -q src tests examples. 종료 코드 0.
- 패키지: uv build --wheel. dist에 wheel 생성.
- CLI: uv run --locked pixelart --help. 명령 설명과 종료 코드 0.
- 로컬 연결: uv run --locked pixelart doctor. 실제 대상과 체크포인트 확인. 이미지 생성은 하지 않음.
- 실제 생성·수집·변환: README의 generate·resume·convert. 성공 결과는 state=review이며 보고서의 규격 항목이 통과해야 함.
- 샘플 평가: uv run --locked python examples/run_samples.py. 6개 소재 원본·최종·확대본과 검사 보고서 수집. 실제 GPU를 사용하는 별도 통합 검사이므로 모든 문서 변경마다 재실행하지 않음.

종료 코드: 0=요청 완료 또는 submit-only 접수 확인, 1=오류, 3=대기 중이며 resume 필요.

## 표현과 미검증 범위

최종 크기·색상·알파·고정 팔레트·PNG 왕복은 자동 검사한다. 실루엣·특징·윤곽·명암·스타일은 실제 크기와 확대본을 보고 별도 기록한다. report의 quality는 사람이 검토하기 전 requires_visual_review다.

원격 HTTP 검사는 로컬 모의 서버로 수행하며 실제 원격 GPU·관리형 Comfy Cloud 인증·실제 두 번째 PC 검증을 대체하지 않는다. 프로젝트 경로 이동은 임시 디렉터리와 한글 경로로 자동 검사한다.

UI·참고 이미지 업로드·부분 재생성·취소·DB는 이 시제품 범위가 아니며 아직 검사하지 않는다. 관리형 클라우드 통합과 OS별 설치 검증은 해당 구현 변경에서 추가한다. 별도 린트·타입 검사 도구는 아직 도입하지 않았다.

## 선택적 LoRA·VAE와 모델 비교

004 변경의 단위 검사는 기존 unittest 명령에 포함된다. 기본 그래프 호환·모델/CLIP/VAE 연결·강도 경계·경로 입력·누락 파일/노드·로컬/HTTP 대상 조회·비교 재개·불일치 거절을 검사한다.

실제 비교: uv run --locked python examples/compare_models.py. 대상 서버에 세 체크포인트/LoRA/VAE 구성이 준비되어 있어야 하며 18개 GPU 작업을 순차 실행한다. 재실행 시 동일 정의의 완료 결과를 서버 없이 재사용하고 진행 중 작업은 확인된 ID로 재개한다. 비교 조건을 변경할 때는 새 --output 폴더를 사용한다. 결과의 격자 감지와 기술 검사는 시각 품질 평가를 대체하지 않는다.

사용자 요청에 따라 후속 PR 전 CodeRabbit 리뷰를 실제 확인하고 합당한 지적을 수정한다. 리뷰를 실행할 수 없으면 완료로 기록하지 않으며 차단 사유와 필요한 후속 조치를 알린다.

## GitHub Actions CI

005 변경의 .github/workflows/ci.yml은 모든 PR과 main push에서 ubuntu-latest·windows-latest × Python 3.11·3.12·3.13을 실행한다. uv 0.9.3과 Action의 검증한 전체 SHA를 고정한다. 읽기 전용 토큰, persist-credentials=false, 15분 제한, PR별 오래된 실행 취소, fail-fast=false를 사용한다.

각 조합에서 다음을 실행한다.

1. uv python install <matrix-version> 및 uv sync --locked --no-editable --reinstall-package pixelart-maker. uv.lock을 변경하지 않고 설치하며 프로젝트는 패키지로 설치한다.
2. uv run --no-sync python -m unittest discover -s tests -v.
3. uv run --no-sync python -m compileall -q src tests examples scripts.
4. uv build --wheel. 기존 격리 빌드 백엔드 범위를 사용하며 백엔드까지 완전 잠금된 빌드라고 주장하지 않는다.
5. uv run --no-sync python scripts/smoke_cli.py. 선택된 환경의 설치된 CLI로 --help·합성 PNG convert·inspect를 실제 실행하고 한글·공백 경로를 확인한다.

잠금 불일치·실패 테스트·빌드/CLI 오류는 0이 아닌 코드로 실패해야 한다. CI는 ComfyUI·GPU·모델·생성 API 인증을 요구하지 않는다. 실제 GPU 생성·시각 평가는 별도 통합 검사다. Linux CPU 검사 통과가 Linux에서 실제 ComfyUI 생성까지 검증했다는 뜻은 아니다.

워크플로 변경은 actionlint로 문법·표현식을 확인하고 등록된 문서·공백 검사도 수행한다. 로컬 재현과 실제 GitHub-hosted 결과를 구별해 005 evidence에 실행 URL과 함께 기록한다. 브랜치 보호·필수 상태 검사 지정은 이번 변경에 포함하지 않는다.

## 프롬프트 제어

007은 전체 unittest에서 공통 인물 억제 회귀, item v1 텍스트 동일성, character·양/음성 전체 대체·빈 네거티브·입력 오류, 저장 워크플로/메타데이터 일치, 오프라인 미리보기, 예전 프로젝트 무재제출과 비교 정의 호환성을 검사한다. scripts/smoke_cli.py는 설치된 CLI의 한글 프롬프트·빈 음성 인자도 실행한다.

- 오프라인 미리보기: uv run --locked pixelart prompts --prompt-preset character --prompt "blonde female knight, upright sword salute".
- 저장 텍스트 조회: uv run --locked pixelart prompts --project <생성 프로젝트>.
- 실제 통합: 기존 item v1 여섯 소재의 저장 그래프/출력 보존과 새 common·character 여성 기사 64픽셀 결과를 함께 확인한다. GPU 생성은 별도이며 원본·실제 크기·확대본의 특징·방향·경례 자세를 구분해 007 evidence에 기록한다.

새 필드가 모두 없는 요청과 비교 정의 v1은 item v1으로 정규화한다. 실제 예전 텍스트는 저장된 그래프에서 읽으며 새 기본값으로 다시 구성하지 않는다. 비교 재사용은 요청과 실효 텍스트가 확인된 경우에만 허용한다.

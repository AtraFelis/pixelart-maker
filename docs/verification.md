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

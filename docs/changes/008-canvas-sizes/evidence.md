# Evidence: 큰 캔버스 출력

- 변경 ID: 008-canvas-sizes. 시작 2026-11-02.
- 수락: 이 채팅의 “좋아. 그러면 다음 단계 진행해줘.”.
- 기준: PR #6 병합 main d017f0c. 작업 트리가 깨끗함을 확인하고 codex/008-canvas-sizes에서 시작했다.
- 현재 상태: CLI·저장·픽셀 처리·검증 구현, 로컬 패키지 검사 완료. 실제 평가·리뷰·PR 결과는 아래에서 관리한다.

## 로컬 구현과 필수 검사

- Request/CLI/workflow에 작업·생성 쌍, export_scale과 상한을 구현했다. Python 위치 인자는 유지하며 직사각형의 정사각형 별칭은 None으로 정규화해 저장한다. 32 미만은 계속 거절해 기존 잘못된 크기 검사도 유지했다.
- 직사각형 비율·padding, 큰 확대의 floor 좌표/알파를 보존한 벡터 다수결, 큰 미리보기 제한, export.png와 전체 RGBA 블록 검사를 추가했다. 후보의 색 수·알파·팔레트 검사는 그대로다.
- 새 검사 21개를 포함해 UV_PROJECT_ENVIRONMENT=tmp/ci-validation, uv sync --locked --no-editable --reinstall-package pixelart-maker, uv run --no-sync python -m unittest discover -s tests -q에서 전체 94개가 통과했다. Python 3.12.10의 실제 설치 패키지로 검사했다.
- 같은 환경의 compileall -q src tests examples scripts, uv build --wheel, uv run --no-sync python scripts/smoke_cli.py는 모두 종료 코드 0. 스모크는 설치 CLI의 정사각형·직사각형·정수 출력·한글/공백 경로·오프라인 재열기를 실행했다.
- ComfyUI MCP server_info에서 로컬 서버 실행, ComfyUI v0.43.2, RTX 5070을 확인했다. 실제 가로형 생성은 기존 SDXL base + Pixel Art XL + FP16 보정 VAE로 완료했다. 모델/노드 설치·업데이트나 유료 호출은 없다.

## 기존 결과와 경계 오류 검증

기존 output/model-comparison의 v1 정의를 새 기본값으로 정규화해 동등함을 확인했다. 세 모델 × 여섯 소재 18개를 check_existing으로 읽고 저장 원본을 메모리에서 새 convert로 다시 처리했다. 18개 모두 기존 final.png와 최종 RGBA가 완전히 같았다. 검사 전후 project.json·workflow.json·original/source.png·final.png SHA-256도 그대로였다. 기존 프로젝트에 다시 쓰거나 GPU 작업을 재제출하지 않았다.

추가 점검에서 저장 직사각형의 size=None/generation_size=None을 비교 설정이 실제 정사각형 혼용으로 잘못 거절함을 발견했다. test_comparison_accepts_null_square_aliases_for_saved_rectangles를 먼저 실행해 sample size cannot be combined 오류로 실패함을 확인했다. None은 미지정으로 해석하도록 비교의 두 혼용 조건을 수정했고 같은 검사가 통과했다. 실제 숫자 크기와 쌍의 혼용 거절은 유지한다. 새 검사 수는 22개이며 기존 테스트는 약화하지 않았다.

## 실제 크기·표현 확인

- 새 GPU 작업은 한 건이다. output/canvas-sizes/courtyard-wide, job 39eff657-967f-4818-b8bc-87565095c3b9. 공통 v1과 기존 SDXL/LoRA/VAE, seed 31417·28 steps·CFG 7, 생성 1024×576·작업 480×270·export_scale 4·32색·opaque·padding 0을 사용했다. 코어 노드 그래프의 실제 대상 검증·제출·수집을 통과해 state=review다. 보고서와 실제 PNG 크기는 source 1024×576, final 480×270, export 1920×1080, preview 960×540이며 모든 후보 규격·정수 블록 검사가 통과했다.
- 기존 knight-common 원본을 새 knight-128/256/1024 프로젝트에 16색으로 변환했다. GPU 생성은 없으며 기존 원본은 보존했다. 각 final/export는 해당 작업 크기이고 preview는 모두 1024×1024다. 규격 검사 모두 통과했다.
- 새 가로형 원본을 별도 courtyard-native-1920 프로젝트에 작업 1920×1080·배율 2로 변환했다. export 3840×2160, preview 1920×1080, 모든 후보/정수 검사가 통과했다. 이는 원본보다 큰 업스케일이며 새 세부 생성이 아니다.
- 작성 에이전트가 원본·실제 128/256/1024·가로형 480/1920 final과 1920 정수 export를 직접 열어 확인했다. 128/256 기사는 64보다 얼굴·갑옷 구분 공간이 늘었으나 발밑 그림자와 정확하지 않은 경례 자세는 그대로다. 1024는 작은 색 잡음·원본의 불규칙한 군집도 크게 보인다. 가로형 장면은 성곽·녹색 언덕·위로 든 검과 갑옷 인물의 실루엣이 읽히지만 얼굴 특징이 생략되고 방패가 추가됐으며, 전체 32색 양자화에서 금발 채도가 줄었다. 화면 해상도·정수 블록 정확성과 미적 완성을 구분한다. quality는 not_reviewed/requires_visual_review로 유지했다.

## 남은 확인과 범위

최종 비편집 잠금 설치 후 전체 95개 테스트·compileall·wheel·설치 CLI 검사가 다시 종료 코드 0으로 통과했다. 문서 60개·로컬 링크 75개·관리/신규 파일 100개 공백 검사도 통과했다. CodeRabbit CLI 0.9.2로 coderabbit review --agent --base origin/main --include-untracked를 실행해 완료까지 확인했다. 17개 파일, findings=0, outcome=completed, 종료 코드 0으로 완료됐다. 원본 로그는 Git에서 제외된 tmp/coderabbit-canvas-review.log에 보관한다. PR과 실제 GitHub CI/리뷰는 제출 후 별도로 확인한다. 실제 다른 PC·원격 GPU·타일 생성·UI·새 모델과 배경/팔레트 알고리즘 개선은 이번 작업의 구현/검증 범위 밖이다.

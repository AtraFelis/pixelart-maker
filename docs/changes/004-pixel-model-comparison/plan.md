# Plan: 픽셀 모델 비교 구현

- 입력: [spec.md](spec.md)
- 상태: 구현·18개 실제 비교 완료, CodeRabbit 검토와 타당한 지적 반영 완료

## 파일과 순서

1. presets/pixel-art-xl.json에 공식 모델·revision·해시와 파일명 등록.
2. MCP download_model로 checkpoint·LoRA·VAE 파일을 내려받고 완료 상태·SHA-256·실제 서버 인식을 확인.
3. request.py·cli.py에 선택적 LoRA 강도와 VAE 추가.
4. workflow.py에 선택적 LoraLoader·VAELoader 및 모델·CLIP·VAE 연결.
5. providers의 대상 모델·노드 사전 확인과 허용 코어 노드 범위를 갱신.
6. examples/compare_models.py와 비교 설정 추가. 샘플과 생성 설정을 고정하고 중단·설정 불일치 처리.
7. 동작별 자동 검사를 추가하고 기존 검사를 유지.
8. 실제 세 구성·여섯 소재의 결과·원본·규격과 표현을 평가하고 문서화.
9. 검증 후 codex/004-pixel-model-comparison을 push하고 PR #1 브랜치에 별도 PR 제출.

## 검증

LoRA 강도 경계·비정상 값, 그래프의 세 연결, 기본 그래프 호환, 누락 파일 제출 차단, 원격 대상 조회, 비교 재개·설정 불일치와 보고서를 검사한다.

등록된 unittest·compileall·wheel·문서 검사를 실행한다. 실제 GPU 비교는 자동 검사와 분리하며 원본·워크플로·시드·모델 출처를 보관한다.

## 위험과 대안

약 7.4GB의 새 가중치를 추가하되 기존 파일을 덮어쓰지 않는다. safetensors만 다운로드하며 커스텀 노드는 설치하지 않는다. 모델 교체 효과와 LoRA 효과를 혼동하지 않는다. 가중치·이미지·인증은 PR에서 제외한다.

기본 모델을 자동으로 교체하지 않는다. 결과와 사용자 평가를 보고 기본 프리셋 변경을 결정한다.

## 수락·되돌리기

2026년 10월 31일 사용자 진행·작업 단위 PR 요청. 기존 체크포인트·생성물은 보존한다. 코드 변경은 별도 PR이며 자동 병합·배포는 없다.

## 리뷰와 구현 중 보완

사용자의 후속 요청에 따라 PR 제출 전에 CodeRabbit CLI로 새 변경분을 리뷰하고 합당한 지적을 수정한다. 기존 PR #1의 CodeRabbit 지적은 먼저 해당 PR에 수정 반영했고 그 결과를 이 브랜치에도 반영했다. 검토 범위·판단은 evidence에 기록한다.

src/pixelart/comparison.py로 재개·정의 일치·보고서 수집을 분리하고 pipeline.generate에 호출자 소유 공급자 재사용을 추가했다. docs/project.md·README·verification과 평가 기록·소형 수치 results.json을 함께 갱신한다. 원본 이미지·가중치는 계속 Git에서 제외한다.

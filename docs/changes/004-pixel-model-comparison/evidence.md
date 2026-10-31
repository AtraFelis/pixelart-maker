# Evidence: 픽셀 전용 LoRA 비교

- 변경 ID: 004-pixel-model-comparison.
- 날짜: 2026년 10월 31일.
- 상태: 구현·기술 검사·18개 실제 생성·작성자 시각 평가·로컬 CodeRabbit 검토 완료. PR #2 제출, PR #1 스레드 후속 조치 완료. GitHub 자동 재리뷰는 별도 대기.
- 기준: PR #1의 시제품과 CodeRabbit 후속 수정 a8c24d7 위의 변경.

## 수락과 실행 환경

사용자가 픽셀 전용 모델 비교의 진행과 각 작업 단위 PR을 요청했다. 이어 PR 전에 CodeRabbit을 확인하고 합당한 수정만 반영하도록 요청했다. 기존 시제품은 PR #1이며 이번 모델 비교는 별도 codex/004-pixel-model-comparison 브랜치다. 자동 병합은 하지 않는다.

Windows 11, 앱 Python 3.12.14, Pillow 12.3.0, NumPy 2.5.4, MCP SDK 1.30.0. 로컬 MCP 대상 ComfyUI v0.43.2와 comfy-cli 1.22.0, RTX 5070 12GB. ComfyUI 자체 Python과 앱 가상환경은 별도다.

## 모델 다운로드·해시·대상 인식

공식 Hugging Face 저장소의 고정 revision에서 safetensors만 Comfy MCP download_model로 내려받았다. 새 체크포인트·LoRA·VAE 합계 약 7.4GB이며 커스텀 노드는 설치하지 않았다. 기존 모델과 생성물은 보존했다. 각 다운로드의 completed 상태를 확인했고 hashlib.file_digest(..., 'sha256')와 파일 크기를 실제 설치 파일에서 다시 검사했다. 모두 종료 코드 0이다.

- sd_xl_base_1.0.safetensors: SHA-256 31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b; 6938078334 bytes, 일치.
- pixel-art-xl.safetensors: SHA-256 4234637cb80c998f41e348e6a6cb6bc20d8d038b2b0f256b6129b3b5e353eef7; 170543052 bytes, 일치.
- sdxl_vae_fp16_fix.safetensors: SHA-256 235745af8d86bf4a4c1b5b4f529868b37019a10f7c0b2e79ad0abca3a22bc6e1; 334641162 bytes, 일치.

출처·revision·라이선스는 [presets/pixel-art-xl.json](../../../presets/pixel-art-xl.json)에 있다. 기존 Illustrious는 실제 서버 인식과 생성 실행을 확인했으나 로컬 가중치 경로·해시는 이번 신규 다운로드 검증에 포함하지 않았다.

실행: .venv/Scripts/pixelart.exe doctor --checkpoint sd_xl_base_1.0.safetensors --lora pixel-art-xl.safetensors --vae sdxl_vae_fp16_fix.safetensors. 종료 코드 0. 대상이 두 체크포인트와 지정한 LoRA·VAE를 인식했고 필요한 CheckpointLoaderSimple·CLIPTextEncode·EmptyLatentImage·KSampler·VAEDecode·SaveImage·LoraLoader·VAELoader를 조회했다. 실제 LoraLoader·VAELoader 스키마도 MCP nodes로 확인했다. 모델과 CLIP 두 출력 및 VAE의 연결은 그래프 테스트와 실제 제출에서 검증했다.

## 자동 검사와 재현

- 실행: .venv/Scripts/python.exe -m unittest discover -s tests -v. 모델 작업 단독 단계 37개 통과. PR #1의 리뷰 회귀 검사 7개를 반영한 최종 전체 44개 통과, 종료 코드 0.
- 최초 경로 입력 검사에서 역슬래시 루트·상위 경로 두 사례가 실패했다. Request의 구분자 정규화를 고친 뒤 동일 테스트를 유지해 통과했다.
- 기존 CodeRabbit 10건의 판단과 실패 재현·수정은 [001 review.md](../001-generation-spike/review.md)에 기록했다. 코드·안내 9건을 수정했고 과거 파일 수 1건은 입력 집합의 범위 설명을 보완하고 수치를 보존했다. 후속 확인에서 범위 설명 요청을 단순 수치 변경 제안으로 해석했던 기록도 정정했다.
- 실행: .venv/Scripts/python.exe -m compileall -q src tests examples. 종료 코드 0.
- 실행: uv build --wheel. dist/pixelart_maker-0.1.0-py3-none-any.whl 생성, 종료 코드 0.
- 실행: .venv/Scripts/pixelart.exe generate --help. --lora·--lora-strength·--vae 옵션 확인, 종료 코드 0.
- 로컬 Markdown 링크 51개·UTF-8·TEMPLATE 밖 미입력 항목 검사 통과. 관리 대상 76개 파일의 새 파일 포함 공백 검사 통과. output·models·가상환경·로컬 프로필·비밀정보 제외 규칙 확인.

## 실제 18개 생성과 재사용

실행: .venv/Scripts/python.exe examples/compare_models.py. 기존 모델·SDXL base/VAE·같은 base/VAE + LoRA의 세 구성에 여섯 고정 요청을 순차 실행했다. comparison.json에 서로 다른 확인된 job_id 18개, state=review 18개와 원본·최종·보고서가 수집됐다. 실행 프로세스의 마지막 종료 결과는 세션에서 회수하지 못했으므로 종료 코드를 추정하지 않았다. 최종 산출물 전체를 별도 검사했다.

- 규격: 18/18 통과. 32×32 또는 64×64, 최대 16색, 이진 알파, PNG 왕복.
- 격자 감지: 기존 모델 0/6, SDXL base 0/6, LoRA 구성 6/6. 올바른 원래 격자 복원이나 표현 품질의 보장은 아니다.
- 재사용 검사: comparison.connect와 pipeline.connect를 실패하도록 차단한 상태에서 같은 정의를 run_comparison으로 다시 열었다. 종료 코드 0, 18개 job_id와 이전 client_elapsed_seconds 모두 동일하며 서버 연결·새 제출 없이 완료했다.
- 원본·후처리 후보·워크플로·시드·확대본과 전체 comparison.json은 로컬 output/model-comparison에 보존한다. weights·원본 이미지·로컬 프로필·인증은 PR에서 제외한다.
- 공유 수치: [results.json](results.json). 작성자 시각 평가: [evaluation.md](evaluation.md). 별도 로컬 comparison-contact-sheet.png에서 각 원본 축소본과 최종의 정수 확대를 나란히 확인했다.

LoRA는 단일 별 동전과 닫힌 상자에서 뚜렷한 개선이 있었다. 사과 그림자·물약 라벨·칼과 열쇠 방향·32픽셀의 세부 손실은 남아 있다. 기본 모델 자동 교체는 하지 않았다.

## PR 전 CodeRabbit 검토

유효한 서명의 기존 CodeRabbit CLI 0.9.2와 기존 인증을 확인했다. 설치·인증 변경이나 유료 크레딧 사용 옵션은 실행하지 않았다.

실행: coderabbit review --agent --base-commit fd92fec4a7893dd6600d9bcade8478584a05d7da --include-untracked. 실제 실행은 설치된 CLI의 절대 경로를 사용했다. reviewType=all, outcome=completed, review_completed, 종료 코드 0. 기존 리뷰 수정과 새 모델 비교를 포함한 파일 32개를 검사했다.

지적 1건(minor): 이 evidence가 진행 중 상태이고 실제 다운로드·해시·테스트·18개 결과가 비어 있어 다른 문서의 완료 상태와 일치하지 않음. 타당하다고 판단해 이 문서에 실제 실행 증거·해시·세부 결과 링크·리뷰 결과를 추가했다. 소스 코드에 대한 신규 지적은 없었다. 문서 보완은 리뷰 완료 후 작성 에이전트가 수행했으며 이를 CodeRabbit이 다시 검토했다고 주장하지 않는다. 원본 CLI 로그는 인증·계정 관련 메시지가 섞일 수 있어 Git에서 제외한 tmp에만 둔다.

## 미검증과 다음 범위

실제 원격 GPU·관리형 Comfy Cloud·외부 인증 프록시·두 번째 PC는 미검증이다. 원격 선택적 모델 검사는 모의 HTTP 응답으로 확인했다. 사용자 시각 수락, 여러 시드·프롬프트의 통계적 품질, 인페인트·UI·수동 편집은 별도다. 이번 결과를 보편적인 모델 우열로 해석하지 않는다.

## GitHub 스레드 후속 확인

사용자가 스레드 답글 여부를 확인하고 “이어서 진행해줘”라고 요청하여, PR #1의 10개 인라인 리뷰에 수정 커밋·동작·재현 검사와 한계를 답글로 남기고 해결 처리했다. 코드 수정은 a8c24d7, 초기 검증 범위 설명 보완은 95f929e다. 해결 처리는 작성자의 조치 완료 표시이며 CodeRabbit이나 사용자의 승인으로 취급하지 않는다.

PR #2는 GitHub 자동 리뷰의 무료 한도 안내만 있었으며 신규 인라인 지적은 없었다. 앞선 CLI의 실제 completed 리뷰와 GitHub 자동 리뷰는 구별한다. 자동 리뷰가 완료됐다고 주장하지 않는다. 검토 상태와 32개/44개 테스트 결과를 각 PR 설명에도 반영한다. 이번 후속 변경은 문서와 리뷰 상태 정리이며 추가 GPU 생성·프로그램 동작 변경은 없다.

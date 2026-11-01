# Evidence: 프롬프트 제어

- 날짜: 2026-10-31. 브랜치 codex/007-prompt-controls, 문서 PR #5의 75510206373394c77b205688f6212aa38ed18d21 기반.
- 2026-11-01 PR #5의 문서 리뷰 보완 ff7d3aef5aa4695023e5e66c99bec9efd8a5299f를 fast-forward로 반영한 뒤 보존해 둔 기능 변경을 복원했다.
- 수락: 이 채팅의 “좋아. 진행해줘.”. 계획 순서대로 CLI 설정·저장·비교 호환성을 구현했다.

## 회귀와 로컬 검사

1. 수정 전 .venv/Scripts/python.exe -m unittest discover -s tests -p test_prompts.py -v: 예상한 2건 실패. 공통 네거티브에 human/person/body/face/scenery/room/architecture가 남았고 양성에 single isolated object가 붙었다. 같은 검사는 수정 후 통과했다.
2. 전체 unittest discover -s tests -q: 개발 Python 3.12.14에서 71개 통과. 추가 저장 테스트의 inspect가 running 상태에서 기존 계약대로 종료 코드 3을 반환함을 확인해 테스트 기대값을 맞췄다. 앱 종료 코드는 변경하지 않았다.
추가 호환성 검사에서 Request("coin", 64)의 기존 위치 인자가 새 프리셋 필드로 해석되어 실패함을 먼저 확인했다. 새 필드를 기존 필드 뒤로 옮겨 API 호환성을 보존했고 같은 회귀 검사를 유지했다.

3. UV_PROJECT_ENVIRONMENT=tmp/ci-validation에서 uv sync --locked --no-editable --reinstall-package pixelart-maker 후 uv run --no-sync python -m unittest discover -s tests -q: Python 3.12.10의 설치 패키지로 71개 통과.
4. 같은 설치 환경의 compileall -q src tests examples scripts, uv build --wheel, uv run --no-sync python scripts/smoke_cli.py: 모두 종료 코드 0. 설치 CLI의 help·prompts·convert·inspect와 한글/공백 경로·빈 네거티브를 실제 검사했다.
5. .venv/Scripts/python.exe -m pixelart doctor --checkpoint sd_xl_base_1.0.safetensors --lora pixel-art-xl.safetensors --vae sdxl_vae_fp16_fix.safetensors: 로컬 MCP·ComfyUI v0.43.2와 세 파일·코어 노드 호환 확인. 모델/노드 설치·업데이트 없음.

기존 비교 재개 테스트의 확인된 작업 fixture에는 실제 생성처럼 workflow 자산을 추가했다. 이전 샘플 불일치 검사 fixture는 item을 명시해 프롬프트·크기·시드 차이에 대한 원래 거절 검사를 유지한다. 단언을 삭제·완화하지 않았고 기존 동일 아이템 재사용의 양성 사례도 추가했다.

## 기존 결과 보존

output/model-comparison의 v1 정의를 새 예제의 명시적 item v1 정의와 정규화 비교했다. 3개 모델 × 6개 소재 18개 전체에서 요청·저장 워크플로 실효 텍스트가 동일하고 state=review임을 확인했다. 검사 전후 project.json·workflow.json·original/source.png·final.png의 SHA-256이 동일했다. 원본·작업 ID·장부·처리 시간을 변경하지 않는 읽기 검사였으며 18개 GPU 작업을 새로 생성하지 않았다.

## 실제 여성 기사 생성과 시각 확인

기존 SDXL base + Pixel Art XL LoRA 강도 1 + FP16 보정 VAE, 1024×1024·28 steps·CFG 7·seed 31417, 후처리 64×64·최대 16색·corner·majority로 같은 설명을 common/character v1에서 각각 새로 생성했다. 로컬 MCP의 사전 점검·그래프 검증·제출·수집을 실제 통과했고 두 작업 모두 state=review다.

- common: job 446caa93-369f-487c-b906-94f82f5af4f4, output/prompt-profiles/knight-common.
- character: job edda0eda-eeff-45cd-a805-47a7a8a3b2e7, output/prompt-profiles/knight-character.
- 두 결과의 nearest·majority·grid 후보 모두 크기·색 수·이진 알파·PNG 규격 통과. majority는 각각 16색이다. 격자 감지는 양쪽 8픽셀 간격이며 품질 판정으로 취급하지 않는다.
- 작성 에이전트가 1024 원본, 실제 64픽셀 final, 16배 preview를 직접 확인했다. 금발·은색 갑옷·한 인물의 전신과 위를 향한 검은 양쪽에 나타났다. common은 손잡이와 수직 검이 비교적 명확하지만 얼굴이 작은 크기에서 뭉친다. character는 머리카락·갑옷 실루엣이 더 크고 읽히나 손잡이 아래에도 긴 날이 생겨 검 구조가 잘못됐다.
- 두 그림 모두 팔을 앞으로 내민 자세에 가까워 가슴 앞의 엄숙한 검 경례를 정확히 충족하지 않는다. 정면 대신 약간의 측면 구도, 발밑 회색 그림자, 축소 후 손·얼굴 정보 손실도 남는다. 요청 충돌 수정의 완료와 아트 표현의 완성을 구분한다. 원본과 생성 프롬프트를 보존했고 자동 품질 상태는 requires_visual_review로 유지했다.
- 이전 세 모델/여섯 아이템 비교 시트도 다시 열어 확인했다. 동일 item v1의 물약 라벨·사과 그림자·칼/열쇠 방향 문제는 기존 평가와 같다. 이번에는 18개를 다시 생성하지 않았다.

## 리뷰와 PR

PR 전 CodeRabbit CLI 0.9.2로 coderabbit review --agent --base codex/006-prompt-profiles-docs --include-untracked를 두 번 실행해 완료까지 확인했다. 두 실행 모두 20개 파일·outcome=completed·종료 코드 0이다. 첫 검토는 0건, 위치 인자 보완 뒤 두 번째 검토는 Major 1건이었다. 로그는 Git에서 제외된 tmp/coderabbit-prompt-controls-review.log와 tmp/coderabbit-prompt-controls-final-review.log에 있다.

지적은 “샘플 러너가 예전 요청을 common으로 읽는데 상태만 단언하면 잘못된 재사용도 통과할 수 있다”는 내용이다. 지적이 인용한 7551020은 수정 전 base이며 실제 변경 코드에는 Request.from_dict와 명시적 item이 이미 있다. 따라서 현재 앱 결함이라는 부분은 수용하지 않았다. 다만 복원한 프리셋·실효 텍스트를 직접 확인하자는 제안은 타당해 수용했다. 예전 필드가 없는 fixture는 호환성 검사의 핵심이므로 삭제하지 않았다. 대신 예전/명시적 item 두 경우에서 실제 러너의 복원 호출, 복원된 item v1과 정확한 음성 텍스트, 전체 요청 동등성, 생성·재개가 호출되지 않는 것을 단언하도록 보강했다. 기존 비교·로더·거절 검사는 모두 유지했다.

UTF-8 문서 56개·로컬 링크 69개·관리/신규 파일 94개의 공백 검사 통과. 미입력 검사 첫 실행은 과거 evidence의 “TBD 없음”이라는 설명도 항목으로 잡아 멈췄다. 과거 기록은 수정하지 않고 미입력 단독 항목만 검사하도록 검사 패턴을 고쳐 통과했다.

테스트 보강·기록 갱신 명령은 2026-10-31 자동 승인 검사의 사용량 한도 때문에 실행되지 않았다. 2026-11-01 권한 검사가 다시 가능해진 뒤 같은 범위의 작업을 재개했다. 제한을 우회하거나 실행되지 않은 명령을 성공으로 기록하지 않았다.

CodeRabbit 지적에 따른 테스트 보강 후 설치 패키지 기준 전체 71개와 문법 검사가 다시 통과했다. GitHub PR 리뷰 제출은 로컬 CLI 리뷰와 별개다. 아래 실행 결과를 확인했다.

## PR과 실제 GitHub Actions

기능 커밋 e3055079fee417f0954ebaecd75ee783a48eb71d를 [PR #6](https://github.com/AtraFelis/pixelart-maker/pull/6)으로 제출했다. base는 선행 문서 PR #5의 codex/006-prompt-profiles-docs다. #5 → #6 순서로 병합하며 #5가 main에 병합된 뒤 #6의 base를 main으로 변경한다. 자동 병합하지 않는다.

[CI run 41271627262](https://github.com/AtraFelis/pixelart-maker/actions/runs/41271627262)의 여섯 Windows/Linux × Python 3.11/3.12/3.13 조합이 모두 completed/success였다. 각 조합은 잠금 설치·전체 테스트·문법·wheel·실제 설치 CLI 스모크를 실행했다. 이 기록은 해당 기능 커밋의 결과이며 이후 문서 기록 커밋의 실행은 PR에서 별도로 확인한다.

선행 PR #5는 ff7d3aef5aa4695023e5e66c99bec9efd8a5299f에서 문서 지적을 보완했다. [CI](https://github.com/AtraFelis/pixelart-maker/actions/runs/41271440221) 여섯 조합 성공, 원래 스레드 답변·해결과 CodeRabbit의 수정 확인 답변을 확인했다. 2026-11-01T04:02:09Z 재리뷰 요청 뒤 [요약 댓글](https://github.com/AtraFelis/pixelart-maker/pull/5#issuecomment-6544307265)의 04:03:57Z 갱신에서 검토 범위 7551020..ff7d3ae와 No actionable comments를 확인했고, 요청 응답도 04:04:03Z Review finished로 끝났다. 빈 COMMENTED 스레드 답변을 전체 리뷰로 계산하지 않았다.

저장소 전체 정상 요청 간격 60분을 지켜 PR #6의 GitHub CodeRabbit 리뷰는 다음 가능한 2026-11-01 14:02:09 Asia/Seoul부터 기존 coderabbit 예약에서 최신 SHA로 요청한다. 아직 요청·완료된 것으로 주장하지 않는다. 로컬 리뷰 지적은 위와 같이 판단·보완·검증했다.

## 미검증 범위

실제 다른 PC·원격 GPU·관리형 클라우드, 편집 UI, 동일 캐릭터·애니메이션·부분 편집은 이번 검사 범위 밖이다. 프롬프트 재현성은 모델의 픽셀별 동일 결과나 요청 자세 준수를 보장하지 않는다.

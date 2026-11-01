# Plan: 프롬프트 제어 구현

## 수락과 순서
사용자의 2026-10-31 “좋아. 진행해줘.”는 아래 범위의 구현 수락이다. 일상적 API 설계는 이 문서에 기록해 진행한다.

1. tests/test_prompts.py에서 기존 기본값의 인물 억제·오브젝트 강제를 실패로 재현한다.
2. prompts.py·request.py·workflow.py: 버전 있는 common/item/character와 문자열 대체, 예전 요청 로딩을 구현한다.
3. pipeline.py·cli.py: 실효 텍스트 저장·오프라인 미리보기·기존 워크플로 조회를 구현한다.
4. comparison.py·examples: 공유 설정 스키마와 정의 v2의 실효 텍스트 고정, v1 동등성 비교, 이전 아이템 벤치마크 보존을 구현한다.
5. 단위·패키지·문법·CLI 검사, 실제 로컬 ComfyUI 기사 생성과 기존 아이템 확인을 수행한다. README·project·verification·전체 계획·evidence에 실제 결과를 기록한다.
6. CodeRabbit 로컬 리뷰를 완료까지 확인하고 타당한 지적을 수정·검증한다. 별도 codex/007-prompt-controls PR을 만들고 CI를 확인한다. 006 문서 PR이 열려 있으면 이를 base로 삼고 병합 순서를 명시한다.

## 위험과 되돌리기
중립 기본값은 이전 생성과 달라진다. 명시적 item v1과 예전 요청 해석으로 호환성을 유지한다. 네거티브 충돌 해소만으로 자세 준수를 보장하지 않는다. 원본·기존 워크플로를 수정하지 않는다. 코드 되돌리기는 Git revert로 하되 새 필드가 있는 프로젝트는 이 버전 이상으로 연다.

## GitHub 리뷰 후속 — 2026-11-01

사용자가 승인한 리뷰 판단·수정 범위로 review 5726587859의 Minor 두 건을 처리한다. evidence의 관측 문장을 명확히 하고, comparison.check_existing에서 review 상태의 재사용에 workflow 자산이 필수임을 명시한다. 중단 프로젝트의 snapshot-only resume는 보존한다. tests/test_prompt_review.py에서 완료 결과의 잘못된 재사용을 먼저 실패로 재현하고 확인된 작업 수집·저장 원본의 오프라인 재처리가 계속 가능함도 검사한다. 전체 패키지 검사·문서 검사·기존 CI 확인 후 같은 PR에 push하고 새 head의 CI와 스레드 답변·해결을 확인한다. GPU 결과·기존 원본·프롬프트 구성은 바꾸지 않는다.

# Evidence: 프롬프트 기본값 후속 기록

- 변경 ID: 006-prompt-profiles.
- 날짜: 2026년 10월 31일.
- 상태: 문서 작성·로컬 문서 검사·PR 전 CodeRabbit 검토 및 보완 완료. 앱 수정 미착수.

## 확인한 사실

기존 README·docs·전체 개발 계획에서 네거티브·프리셋·캐릭터·인물 관련 내용을 검색했다. 캐릭터와 스타일 일관성의 장기 계획은 있었지만 공통 네거티브의 인물 억제 문제와 프롬프트 편집·소재별 프리셋 분리는 명시된 작업이 아니었다.

src/pixelart/workflow.py의 NEGATIVE와 build_workflow를 직접 읽어 human·person·body·face 및 single isolated object의 고정 적용을 확인했다. 본 기록은 초기 아이템 실험의 기본값 적용 범위가 잘못 넓어진 문제를 추적한다.

## 이번 변경과 검증

006 문서군과 README·프로젝트 기록·전체 계획을 연결했다. 로컬 Markdown 링크 65개, UTF-8·미입력 항목과 변경/신규 Markdown 7개의 공백 검사가 통과했다. 앱 코드가 변경되지 않았음을 파일 범위로 확인했다. PR 전 CodeRabbit CLI 0.9.2로 coderabbit review --agent --base origin/main --include-untracked를 실행했다. review_completed·outcome=completed, 문서 7개 검사, minor 1건으로 종료 코드 0이었다. 지적은 DOC-04의 실제 검토 결과를 evidence에 기록하라는 내용으로, 이를 수용해 이 상태와 실제 리뷰 결과를 보완했다. 원본 로그는 Git에서 제외된 tmp/coderabbit-prompt-docs-review.log에 보관한다. 앱 코드·의존성·모델·생성물은 변경하지 않는다.

## 구현 상태와 한계

공통 기본값 수정·프리셋 분리·네거티브 사용자 편집은 아직 미구현이다. 해당 기능의 수정·새 회귀 검사·실제 캐릭터 생성·표현 평가는 이번에 수행하지 않는다. 기존 자동 CI 실행과는 구별한다. 문서가 존재한다는 사실을 인물 생성 검증이나 구현 수락으로 취급하지 않는다.

## 기준과 반영

문서 작업 기준 코드는 origin/main 2e21edc71e392a83dc42729dbcdbbfeff1480d7e이다. 이번 변경은 Markdown 7개이며 앱 코드 수정·기능 검증 완료를 뜻하지 않는다. 후속 기능은 별도 구현 단계로 남는다.

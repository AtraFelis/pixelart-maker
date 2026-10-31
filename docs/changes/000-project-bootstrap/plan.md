# Plan: 템플릿 적용과 첫 구현 준비

- 변경 ID: 000-project-bootstrap
- 입력: [spec.md](spec.md)
- 상태: 요청 범위 구현 및 검증

## 파일과 이유

- 루트 AGENTS.md, CLAUDE.md, REVIEW.md: 공통 작업 규칙과 제품별 주의점.
- README.md: 프로젝트 상태와 문서 안내.
- .gitignore: 기존 비밀정보·캐시 규칙에 앱의 로컬 데이터 제외 추가.
- docs/project.md: 확인된 요구와 제안·승인·구현 상태.
- docs/workflow.md, verification.md, release.md, prompts.md: 프로젝트별 절차.
- docs/bootstrap.md: 원본 초기화 절차와 이번 적용 결과.
- docs/changes/TEMPLATE, docs/incidents/TEMPLATE.md: 양식 보존.
- docs/changes/000-project-bootstrap/: 이번 변경과 증거.
- docs/changes/001-generation-spike/: 첫 시제품의 검토 초안.
- docs/references/sdlc-playbook.md: 사용자 제공 플레이북의 적용 근거.
- .github/pull_request_template.md: 원격 연결 전 선택적 PR 양식.

## 작업 순서

1. 원본 템플릿과 기존 저장소 상태 확인.
2. 공통 파일을 복사하되 기존 두 문서를 보존.
3. 제품·절차·검증 문서를 구체화.
4. 초기 구성 기록과 첫 시제품 초안 작성.
5. 요청 중 제공된 플레이북 관련 절을 읽고 적용 근거 기록.
6. 파일·링크·공백·제외 규칙·원문 보존 검사.
7. 실제 결과와 미검증 범위를 evidence에 기록.

## 위험과 대안

전체 앱 골격을 지금 만드는 대안은 선택하지 않는다. 템플릿 적용 요청의 산출물은 구체적인 프로젝트 문서이며 첫 시제품은 별도 변경이다.

런타임·모델·외부 도구를 임의 설치하지 않는다. 기존 Git 상태와 사용자 데이터를 변경하지 않는다.

## 검증

[검증 계약](../../verification.md)의 초기 구성 검사를 수행한다. 필수 파일, Markdown 링크, 초안 상태, 공백, Git 제외 규칙, 기존 두 문서와 양식 보존을 확인한다.

## 되돌리기

새로 작성한 구성 파일만 선택적으로 복구한다. 재귀 삭제·Git 초기화·기존 문서 이동은 필요 없다.

## 수락 근거

사용자의 2026년 10월 31일 템플릿 기반 프로젝트 구성 요청. 독립 검토나 앱 구현 승인은 별개다.

## 진행 중 변경

사용자가 원본 PDF를 추가로 제공하여 관련 절 확인과 참고 문서를 추가했다. 제품 범위나 앱 구현 범위는 바뀌지 않았다.

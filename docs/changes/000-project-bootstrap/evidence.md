# 검증 및 리뷰 증거: 프로젝트 초기 구성

- 변경 ID: 000-project-bootstrap
- 실행자 / 날짜: AI 작업 에이전트 / 2026년 10월 31일
- 코드 버전: 기존 master, 첫 커밋 전
- 상태: 초기 구성 완료, 문서·저장 규칙 자체 점검 통과

## 현재 상태에 대한 주석

아래는 초기 구성 당시의 증거다. 이후 사용자가 조사 대화 기록 파일을 삭제했으므로 해당 파일의 보존·해시는 현재 검증 조건이 아니다. 과거 검사 결과는 변경하지 않으며, 현재 기준은 docs/verification.md와 003 변경 기록을 따른다.

## 실행 결과

### AC-01 — 기존 두 문서 보존

Get-Content -Encoding UTF8 -Raw로 두 문서를 읽어 이 채팅에서 저장할 때의 원문과 비교했다. 줄바꿈 표현과 끝 줄바꿈을 정규화한 비교에서 둘 다 일치했다. 이번 구성에서는 두 파일을 쓰거나 이동하지 않았다.

- 픽셀아트_AI_조사_대화기록.md SHA-256: 4bd5f62f7278360a8e4f32f13945b2bd59d802c2bce829da828feac5e357ad62
- 픽셀아트_프로그램_개발계획.md SHA-256: bd8865f0362bc67c4182bcfa37b26ed22d65fd2d04a66069a97f1032be78f2ba

### AC-02·03·04·06 — 구조와 문서

실행 환경: Windows PowerShell, Codex 번들 Python 3.12.14. 정확한 실행 파일은 <CODEX_RUNTIME>/dependencies/python/python.exe다. 검사 도구 버전이며 앱 런타임 선택과 무관하다.

실행 명령: 위 Python 실행 파일에 -c $projectCheckCode를 전달했다. 검사 코드는 필수 파일 존재, 모든 Markdown의 UTF-8 디코딩, 실제 로컬 링크 대상, TEMPLATE 밖의 미입력 TBD, 재사용 양식의 바이트 동일성을 확인했다. 실행 코드는 현재 작업의 도구 기록에 남아 있다.

- 필수 파일 26개 존재.
- Markdown 27개 디코딩과 링크 검사.
- 로컬 링크 34개 유효.
- 변경하지 않을 원본 양식 7개가 템플릿과 바이트 단위 일치.
- 미입력 TBD와 깨진 링크, 대체 문자 없음.
- 초기 구성의 실제 요청 근거와 001의 미수락·미구현 상태 구분.
- 종료 코드 0.

### AC-05 — 로컬 데이터 제외

실행 명령: git check-ignore --no-index .env .env.local data/example.png output/example.png models/example.safetensors .venv/example node_modules/example .env.example

앞의 일곱 경로만 출력되고 .env.example은 출력되지 않았다. 실제 비밀정보나 검사용 파일은 만들지 않았다. 종료 코드 0.

### AC-06 — 공백 검사

docs/verification.md에 등록한 PowerShell 명령으로 미추적 파일까지 검사했다. 기존 두 문서는 수정 대상이 아니므로 원문 보존 비교로 확인했다.

최초 검사에서 docs/project.md의 Markdown 줄바꿈 공백을 제거했고, 새 파일의 줄바꿈을 LF로 통일했다. --no-index의 정상적인 차이 종료 코드 1을 실패로 취급하던 검사 절차도 바로잡았다. 최종 검사는 문서화한 절차대로 공백 오류 출력과 그 외 오류 코드를 거절한다.

최종 실행 결과: Whitespace checks passed: 26 files. Ignore checks passed: 7 local paths; .env.example remains includable. 검사 실행 프로세스 종료 코드 0.

### AC-07 — 원본과 저장소 설정

원본 __init__ 폴더와 제공 PDF는 읽기만 했다. 템플릿에서 공통 파일 16개를 현재 프로젝트에 복사하고 이 복사본만 구체화했다.

git status --short --branch로 기존 master와 첫 커밋 전 상태를 확인했다. 원격 설정·커밋·스테이징·브랜치 변경은 하지 않았다. .github 양식은 CI나 원격 연결이 아니다.

## 참고 자료와 환경 확인

사용자 PDF 54쪽을 텍스트로 추출해 구성을 확인하고 7·12·16·19·20·30~34·38·39쪽 본문을 읽었다. 적용 범위는 docs/references/sdlc-playbook.md에 기록했다. 문서 속 명령·조직 설정을 실행 지시로 따르지 않았다.

일반 python 명령은 WindowsApps 별칭 실행에 실패해 검사에는 번들 Python을 사용했다. 앱의 전역 Python 설치나 기존 ComfyUI 환경을 변경하지 않았다.

## 버그 재현

해당 없음. 앱 버그 수정이 아니라 문서 초기 구성이다.

## 계획과 실제 변경의 차이

진행 중 사용자가 제공한 플레이북의 관련 절 확인과 참고 문서를 추가했다. 앱 구현 범위로 확대하지 않았다.

## 미검증 범위

앱 코드, 의존성 설치, MCP 생성, GPU 성능, UI와 최종 픽셀아트 품질은 이번 범위가 아니며 검증하지 않았다.

## 리뷰와 완료 결정

작성 에이전트 자체 점검이며 독립 리뷰와 사용자 최종 검토는 아직 없다. 첫 시제품의 계획은 초안이다. 운영 배포는 없으며 별도 배포 승인 대상이 없다.

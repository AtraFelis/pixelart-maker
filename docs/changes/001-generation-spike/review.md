# CodeRabbit PR #1 검토와 반영

- 검토일: 2026년 10월 31일.
- 대상: [PR #1](https://github.com/AtraFelis/pixelart-maker/pull/1)의 fd92fec 변경에 대한 CodeRabbit 리뷰 10건.
- 검토자: CodeRabbit의 실제 외부 리뷰를 작성 에이전트가 재현·판단. 작성 에이전트 자체 점검과 독립 리뷰를 구별한다.
- 사용자 근거: PR 전 CodeRabbit 확인과 합당한 수정 반영 요청. PR #1의 후속 수정이며 모델 비교는 별도 PR이다.

## 지적별 판단

1. 4431093640, 초기 evidence의 26개 파일: 현재 파일 수로 바꾸는 제안은 반영하지 않음. 초기 실행 당시 기록이며 현재 검증과 구분한 범위 주석을 추가함.
2. 4431093643, README에서 개발 절차·003 기록으로 이동 불가: 수용. 두 링크 추가.
3. 4431093647, 기존 샘플을 변경된 정의로 잘못 재사용: 수용. 정규화한 Request 전체 비교 후 불일치 거절. 미지정 체크포인트의 최초 서버 선택만 유지.
4. 4431093649, 복사한 로컬 프로필이 후속 명령에 적용되지 않음: 수용. doctor·generate·resume 모두 같은 --profile을 쓰는 예시 추가.
5. 4431093656, 원격 HTTP에서 Bearer 노출: 수용. 인증 대상은 HTTPS 또는 루프백 터널만 허용. 인증 없는 자체 운영 HTTP는 기존대로 허용.
6. 4431093659, 빈 전경의 grid 요청에서 후보 누락: 수용. 빈 전경에서는 명확한 ValueError로 거절하며 nearest·majority의 경고 동작은 유지.
7. 4431093668, 리다이렉트가 인증을 전달하고 POST를 GET으로 변경: 수용. 고정 API 주소에서 리다이렉트 전면 거절. 다른 포트의 실제 모의 수신 서버에 토큰과 요청이 도달하지 않음을 검사.
8. 4431093671, 명백한 접수 거절도 submission_unknown으로 저장: 수용. SubmissionRejected로 로컬 인증 누락·4xx·워크플로 거절을 구별. 5xx와 통신·해석 실패는 보수적으로 접수 불명 유지.
9. 4431093673, 부호·공백·밑줄이 든 팔레트 허용: 수용. 6자리 16진수 정규식과 문자열 타입 검사.
10. 4431093675, 허용한 Pillow 12.0에 없는 테스트 API 사용: 수용. NumPy로 동일한 세 RGBA 픽셀을 비교. 테스트 기대값이나 의존성 범위를 약화하지 않음.

## 재현과 검사

- 수정 전: .venv/Scripts/python.exe -m unittest discover -s tests -p test_review_regressions.py -v.
- 7개 테스트에서 예상한 원인으로 실패 19개·오류 2개 발생. 부호·밑줄·공백 허용, None·정수의 TypeError, 리다이렉트 대상의 테스트 토큰 수신, 4xx·인증 누락의 접수 불명 오분류, 샘플 불일치 재사용, 빈 grid 무오류, 비암호화 원격 인증 허용을 확인함.
- 수정 후: .venv/Scripts/python.exe -m unittest discover -s tests -v, 32개 전체 통과. 기존 25개와 추가 7개이며 재현 테스트를 약화하거나 삭제하지 않음.
- compileall src tests examples와 uv build --wheel 통과. 로컬 Markdown 링크 검사와 git diff --check 통과. 체크아웃의 CRLF를 기존 커밋과 같은 LF로 정규화한 뒤 공백 검사를 실행함.

실제 원격 GPU·외부 HTTPS 프록시·두 번째 PC는 미검증이다. HTTP 동작은 루프백의 실제 모의 서버로 검증했다. 생성 그래프와 픽셀 처리 기준선은 이번 오류 수정으로 변경하지 않았다.

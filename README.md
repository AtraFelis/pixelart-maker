# AI 픽셀아트 제작 시제품

Python 명령줄에서 소재를 생성하고 32×32·64×64 픽셀 PNG로 정리하는 시제품입니다. 생성 원본, 변환 후보, 16배 확대본, 설정·검사 보고서를 프로젝트 폴더에 저장합니다.

로컬 ComfyUI MCP 연결을 실제 검증했습니다. 자체 운영 ComfyUI HTTP 어댑터도 구현했으며 모의 서버로 검사했습니다. 실제 다른 PC·클라우드 실행과 편집 UI는 아직 검증하지 않았습니다.

## 준비와 설치

- Python 3.12와 uv.
- 로컬 생성에는 실행 중인 ComfyUI, 설치된 체크포인트, PATH에서 찾을 수 있는 comfy-mcp와 comfy-cli가 필요합니다.
- 설치 안내: [공식 Comfy MCP](https://docs.comfy.org/agent-tools/mcp).
- 프로그램 자체와 ComfyUI는 서로 다른 Python 환경을 사용합니다. 기존 ComfyUI 환경은 변경하지 않습니다.

저장소 루트에서 실행합니다.

~~~powershell
uv sync --locked
uv run --locked pixelart --help
uv run --locked pixelart doctor
~~~

PC별 실행 파일 위치가 PATH에 없으면 profiles/local.example.json을 profiles/my.local.json으로 복사해 command를 실제 경로로 바꿉니다. 이 로컬 설정 파일은 Git에서 제외됩니다. 앱 소스에 설치 경로를 고정할 필요가 없습니다.

프로필을 복사한 경우 아래처럼 doctor·generate·resume에 같은 파일을 지정합니다.

~~~powershell
uv run --locked pixelart doctor --profile profiles/my.local.json
uv run --locked pixelart generate --profile profiles/my.local.json --prompt "red potion bottle icon" --output output/local-potion
uv run --locked pixelart resume output/local-potion --profile profiles/my.local.json
~~~

## 물약 만들기

~~~powershell
uv run --locked pixelart generate --prompt "a small round bottle of red healing potion, brown cork, icon" --size 32 --colors 16 --output output/my-potion
~~~

기본값은 생성 1024×1024, 28 steps, CFG 7, seed 42입니다. --checkpoint로 대상 서버에 있는 모델을 선택할 수 있습니다. 기본 워크플로는 코어 노드만 사용합니다. 선택한 LoRA·VAE는 서버에 미리 설치되어 있어야 하며 앱이 자동 다운로드하거나 커스텀 노드·유료 API를 호출하지 않습니다.

기본 대기 시간 안에 끝나면 결과까지 저장합니다. 아직 생성 중이면 종료 코드 3과 프로젝트 경로를 출력합니다. 같은 폴더를 다시 generate하지 말고 다음으로 재개합니다.

~~~powershell
uv run --locked pixelart resume output/my-potion
~~~

--submit-only는 작업 ID를 저장하고 기다리지 않습니다. 접수 여부가 불명확한 작업은 자동 재제출하지 않습니다. 결과 수집이 끝난 프로젝트는 생성 서버 없이 다시 열고 후처리할 수 있습니다.

~~~powershell
uv run --locked pixelart inspect output/my-potion
~~~

## 결과물

프로젝트 폴더에는 다음 파일이 생깁니다.

- project.json: 상대 경로 자산 목록, 작업 상태·생성 ID, 설정.
- request.json, workflow.json: 생성 요청과 실행 그래프.
- original/: 생성 원본과 후처리 입력. 다시 생성하지 않고 재사용 가능.
- candidates/: nearest·majority, 주기적 격자가 검출되면 실험적 grid 후보.
- previews/: 각 후보의 정확한 16배 확대 PNG.
- final.png, preview.png: 선택한 후보와 확대본.
- report.json: 크기·보이는 색 수·알파·팔레트 검사, 처리 시간, 주의점.

--method로 nearest·majority·grid를 선택합니다. grid는 충분한 주기적 경계가 검출될 때만 사용할 수 있습니다. 격자 탐지는 일반적인 모든 생성물을 복원한다고 보장하지 않습니다.

## 이미지를 다른 규격으로 변환

~~~powershell
uv run --locked pixelart convert output/my-potion/original/source.png --size 64 --colors 16 --output output/my-potion-64
~~~

--background corner는 모서리와 비슷하며 가장자리에 연결된 배경만 제거합니다. 모서리 색이 서로 다르면 제거를 건너뛰고 보고서에 남깁니다. 흰색 장식이나 반사광이 손상될 수 있으므로 원본과 비교해야 합니다.

이미 투명한 PNG는 --background alpha로 원래 알파를 이진화합니다. 불투명 결과는 --background opaque를 사용합니다. --palette에 쉼표로 구분한 #RRGGBB 색을 지정하면 그 색만 사용합니다.

## 다른 PC와 원격 생성

완성된 프로젝트 폴더를 통째로 옮기면 상대 경로로 이미지를 열 수 있습니다. .venv는 복사하지 않고 새 PC에서 uv sync --locked를 실행합니다. 모델·인증·설치 경로는 프로젝트에 넣지 않습니다.

원격 자체 운영 ComfyUI는 profiles/remote.example.json을 로컬 설정으로 복사하고 url을 설정한 뒤 사용합니다.

~~~powershell
uv run --locked pixelart doctor --profile profiles/gpu.local.json
uv run --locked pixelart generate --profile profiles/gpu.local.json --prompt "golden key icon" --output output/key
~~~

인증이 필요하면 token_env에 환경변수 이름을 지정합니다. 값은 설정 파일에 넣지 않습니다. 인증 토큰을 사용하는 원격 주소는 HTTPS가 필요합니다. HTTP는 localhost·127.0.0.0/8·::1의 로컬 연결이나 SSH 터널에만 허용합니다. API 리다이렉트는 따라가지 않으므로 최종 서버 주소를 설정합니다. 이 어댑터는 자체 운영 ComfyUI용이며, 관리형 Comfy Cloud MCP는 별도 인증·도구 어댑터가 필요합니다.

현재 시제품의 생성 입력은 텍스트입니다. 참고 이미지 업로드·인페인트·취소와 전체 편집 UI는 후속 범위입니다.

## 검증과 샘플

~~~powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m compileall -q src tests examples
uv build --wheel
~~~

여섯 실제 샘플을 만들려면 다음을 실행합니다. 로컬 GPU를 사용하며 순차 생성합니다. 기존 작업 폴더가 있으면 새로 제출하지 않고 기록을 확인·재개합니다.

~~~powershell
uv run --locked python examples/run_samples.py
~~~

평가 대상과 시드는 examples/samples.json에 있습니다. 생성물은 output/evaluation 아래에 저장되며 Git에서 제외됩니다.

## PR 자동 검사

[CI 워크플로](.github/workflows/ci.yml)는 모든 PR과 main push에서 Windows·Linux × Python 3.11·3.12·3.13을 검사합니다. uv 0.9.3과 런타임 의존성 잠금 파일을 사용합니다. 아래 명령으로 동일한 검사를 로컬에서도 실행할 수 있습니다.

~~~powershell
uv sync --locked --no-editable
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python -m compileall -q src tests examples scripts
uv build --wheel
uv run --no-sync python scripts/smoke_cli.py
~~~

스모크 검사는 설치된 CLI로 합성 PNG 변환과 프로젝트 재열기를 확인합니다. ComfyUI·GPU·모델·생성용 비밀정보가 필요 없습니다. 실제 생성·그림 품질 평가는 별도입니다. --no-editable은 저장소 소스 대신 설치된 패키지의 CLI를 검사하기 위한 옵션입니다. 소스 수정이 바로 반영되는 개발 설치로 돌아가려면 uv sync --locked를 실행합니다.

CI의 실제 실행 증거와 CodeRabbit 검토는 [005 검증 기록](docs/changes/005-github-actions-ci/evidence.md)에 남깁니다. 브랜치 보호의 필수 검사 설정은 별도이며 이 워크플로 추가만으로 병합을 강제로 차단하지는 않습니다.

## 픽셀 전용 LoRA 비교

Pixel Art XL은 SDXL용 LoRA입니다. 아래 파일을 대상 ComfyUI의 checkpoints·loras·vae에 각각 준비합니다. 출처·고정 revision·SHA-256·라이선스는 [모델 기록](presets/pixel-art-xl.json)에 있습니다. SDXL base, LoRA, VAE 합계 약 7.4GB이며 모델을 저장소에 포함하지 않습니다.

~~~powershell
uv run --locked pixelart doctor --checkpoint sd_xl_base_1.0.safetensors --lora pixel-art-xl.safetensors --vae sdxl_vae_fp16_fix.safetensors
uv run --locked pixelart generate --checkpoint sd_xl_base_1.0.safetensors --lora pixel-art-xl.safetensors --lora-strength 1 --vae sdxl_vae_fp16_fix.safetensors --prompt "one round golden coin with an engraved star, icon" --seed 31417 --output output/pixel-coin
uv run --locked python examples/compare_models.py
~~~

로컬 프로필이 필요하면 세 명령에 같은 --profile profiles/my.local.json을 추가합니다. LoRA 강도는 0~2이며 모델과 CLIP에 함께 적용합니다. LoRA를 생략하면 기존 그래프를 사용합니다. VAE도 선택 사항입니다. 누락 파일·노드는 제출 전에 거절합니다.

비교는 기존 모델·SDXL base·같은 base에 Pixel Art XL을 적용한 세 구성에서 여섯 소재를 순차 생성합니다. [고정 조건](examples/model_variants.json), 기존 samples.json의 프롬프트·시드를 사용하며 output/model-comparison에 원본·32/64 최종·확대본·comparison.json을 저장합니다. 기존 결과는 요청이 일치할 때만 재사용합니다. 설정을 바꾸면 --output으로 새 폴더를 지정합니다. 접수 여부가 불명확하면 자동 재제출하지 않습니다.

실제 18개 생성의 기술 검사는 모두 통과했고 LoRA 구성에서 동전·닫힌 상자가 개선됐습니다. 그림자·라벨·방향과 작은 크기의 세부 손실은 남아 있습니다. [비교 평가](docs/changes/004-pixel-model-comparison/evaluation.md)를 참고하세요.

## 품질 범위

규격 검사 통과와 그림의 완성도는 별개입니다. 현재 결과는 모두 시각 검토 대상으로 표시합니다. 전용 픽셀 LoRA의 첫 비교는 완료했습니다. 더 정교한 배경·격자 복원, 고정 스타일과 부분 편집은 후속 범위입니다.

- [개발 계획](픽셀아트_프로그램_개발계획.md)
- [프로젝트 정의](docs/project.md)
- [개발 절차](docs/workflow.md)
- [삭제한 참고 대화 기록의 정리](docs/changes/003-remove-transcript-references/intent.md)
- [첫 시제품 계획](docs/changes/001-generation-spike/plan.md)
- [실행·검증 기록](docs/changes/001-generation-spike/evidence.md)
- [픽셀 모델 비교 계획](docs/changes/004-pixel-model-comparison/plan.md)
- [픽셀 모델 검증 기록](docs/changes/004-pixel-model-comparison/evidence.md)
- [검증 계약](docs/verification.md)
- [다른 PC·원격 실행 구조](docs/architecture/execution.md)

origin은 https://github.com/AtraFelis/pixelart-maker.git 입니다. 기준 브랜치는 main이며 각 작업 단위는 codex/ 브랜치와 별도 PR로 제출합니다. AI 작업 진입점은 AGENTS.md이며 Claude는 CLAUDE.md에서 시작합니다.

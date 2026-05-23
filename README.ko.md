# coord-smith

> Python CUA 런타임 — 외부 LLM 의 지시에 따라 OS 좌표를 결정적으로 누른다

![python](https://img.shields.io/badge/python-3.14-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![version](https://img.shields.io/badge/version-0.1.0-blue)
![tests](https://img.shields.io/badge/tests-354%20passing-brightgreen)
![runtime](https://img.shields.io/badge/runtime-LLM--free-orange)
[![CI](https://github.com/jazz1x/coord-smith/actions/workflows/ci.yml/badge.svg)](https://github.com/jazz1x/coord-smith/actions/workflows/ci.yml)

**coord-smith** 는 *손* 입니다. *머리* — OpenClaw 같은 외부 LLM — 가 무엇을 어디서 클릭할지 정하면, coord-smith 는 그 결정을 OS 위에서 좌표 클릭과 스크린샷 증거로 실행합니다. 추론은 런타임 바깥에 있고, 런타임 자체에는 LLM 호출이 0건입니다.

한 번의 실행은 LangGraph 상태 머신이 6 개 미션 (per-run 3개 + per-step 3개, recipe step 마다 반복) 을 순서대로 통과시키는 파이프라인입니다. 각 미션은 다음 미션이 시작되기 전에 evidence envelope (action-log JSONL, 스크린샷, 전환 diff) 를 디스크에 남깁니다. 브라우저 내부 (Playwright / CDP / Chromium) 는 건드리지 않습니다 — OS 좌표와 픽셀만 사용합니다.

[English](./README.md)

## 파이프라인

런타임은 **6 개 미션**을 통과합니다 — per-run 셋업/종결이 per-step 블록을 감싸고, per-step은 recipe의 각 step마다 한 번씩 실행됩니다. 각 미션은 결정적이며, 다음 미션이 시작되기 전에 evidence 를 디스크에 남깁니다.

| 미션 | Phase | 역할 |
|------|-------|------|
| `attach_session` | per-run | session-ref 로 기존 브라우저 세션에 부착. |
| `prepare_session` | per-run | 기대 인증 상태 / 대상 페이지 URL 검증. |
| `step_observe` | per-step | step의 pre-click 화면 상태 캡처. |
| `step_dispatch` | per-step | step의 클릭 실행 (image-or-coord prefer/fallback chain). |
| `step_capture` | per-step | post-click evidence (스크린샷, transition diff, optional signal) 캡처. |
| `run_completion` | per-run | sealed 상태 코드로 실행 종료. |

N-step recipe면 per-step 블록이 선언 순서대로 N번; N=0이면 per-step 블록 생략 (smoke target). 각 미션은 고정된 과거형 action key (예: `step_dispatch` → `step-dispatched`) 를 emit 하므로 action log 를 grep 으로 추적할 수 있습니다.

```
 OpenClaw (외부 LLM)
      │  결정 / 좌표 / 이미지 ref
      ▼
 coord-smith CLI ──▶ LangGraph 상태 머신 ──▶ 6 미션
                                              │
                            evidence envelope (JSONL + PNG)
                                              │
                                              ▼
                                          OS (PyAutoGUI)
                                              │
                                  픽셀  ◀──────────  커서
                                              │
                            OpenCV match / PIL diff 가 검증
```

## 필수 요구사항

- **Python 3.14** — 고정. 이전 마이너 버전은 더 이상 지원하지 않습니다.
- **macOS** 에서 real-binary 테스트: Accessibility + Screen Recording 권한 필요.
- **uv** 패키지 매니저 (`pip install uv` 또는 `brew install uv`).

```bash
python3.14 --version    # 반드시 3.14.x
uv --version
```

## 설치

### 1. 프로젝트 부트스트랩

```bash
git clone https://github.com/jazz1x/coord-smith.git
cd coord-smith
uv sync --extra dev
```

`uv` 는 `pyproject.toml` 의 `requires-python` 에 따라 Python 3.14 를 자동으로 잡아 옵니다. 시스템에 3.14 가 없으면 먼저 설치:

```bash
uv python install 3.14
```

### 2. 검증

```bash
uv run pytest -q                # 354 passed, 4 deselected (real-binary)
uv run ruff check .
uv run mypy
```

`-m real` 슈트는 기본적으로 제외됩니다 (실제 커서를 움직입니다).

### 3. git 훅 설치 (clone 당 1회)

```bash
uv run pre-commit install
```

### 4. (macOS) 실제 클릭을 위한 권한 부여

System Settings → Privacy & Security:

1. **Accessibility** — 사용 중인 터미널 앱을 체크 후 터미널 재시작.
2. **Screen Recording** — 같은 경로, 같은 앱.

그 다음:

```bash
uv run pytest -m real -q        # 4 passed: preflight + screenshot + coord click + image self-locate
```

권한이 없으면 `preflight()` 가 exit code `2` 로 중단됩니다.

## Quickstart

OpenClaw 없이 recipe 만으로 실제 클릭 발사:

```bash
coord-smith --click-recipe ./recipe.yaml \
      --session-ref my-session \
      --expected-auth-state authenticated \
      --target-page-url https://example.com \
      --site-identity example
```

macOS 에서 호출 직전 대상 브라우저가 포그라운드가 아닐 가능성이 있으면 (예: 호출 셸이 포커스를 빼앗길 수 있는 환경), `--target-window "Google Chrome"` (혹은 동등한 앱 이름) 을 붙입니다. CLI 가 `osascript -e 'tell application "<name>" to activate'` 를 실행하고 약 1초 settle 후 preflight + dispatch 로 진행합니다. 환경변수 `COORDSMITH_TARGET_WINDOW` 로도 같은 값을 줄 수 있고, CLI 플래그가 환경변수보다 우선합니다. caller 책임 (실행 도중 윈도우를 포그라운드로 유지) 은 [docs/architecture-boundaries.md §Window Ownership](docs/architecture-boundaries.md#window-ownership) 참고.

최소 좌표 recipe:

```yaml
version: 1
steps:
  - name: click-buy
    coord: { x: 800, y: 500 }
```

레이아웃 변화에 강건한 이미지 recipe (권장):

```yaml
version: 1
steps:
  - name: click-buy
    image: templates/buy-button.png
    confidence: 0.9
    grayscale: false
```

YAML이 정식 포맷이며, `.json` 파일은 backwards compatibility 용으로 받아들여집니다 (확장자 기반 자동 라우팅). 레거시 `missions: {name: target}` shape 는 여전히 로드되지만 `DeprecationWarning` 이 emit 됩니다 — 새 recipe 는 반드시 `steps:` 로 작성. 전체 스키마와 에이전트 계약은 [docs/recipe-guide.md](docs/recipe-guide.md) 참고.

**좌표 우선순위**: payload (OpenClaw) → step.coord → step.image → no-click.

## 결과 읽기

모든 invocation 은 하나의 `run.json` summary 를 남깁니다 — caller 가 JSONL 파일들을 하나씩 grep 하지 않고 한 번에 결과를 인식할 수 있습니다:

```jsonc
// artifacts/runs/<run_id>/run.json  (또는 run root 가 없는 경우 base_dir/run.json)
{
  "schema_version": 1,
  "run_id": "20260518-123045-...",
  "status": "success",       // success | failure | interrupted | host_busy
  "exit_code": 0,            // 0 성공 · 1 런타임 · 2 권한 · 3 recipe · 4 host busy
  "started_at": "...",
  "ended_at": "...",
  "elapsed_seconds": 1.2345,
  "step_count": 3,
  "failure": null            // 실패 시 compact diagnosis block
}
```

실패 시 `run.json` 안의 `failure` 키가 `step_idx`, `step_name`, `phase` (`pre_click` / `dispatch` / `post_click`), `error_class`, screenshot 경로, 그리고 전체 `failure.jsonl` 포인터를 담고 있습니다. (`failure` 는 JSON 필드이지, 별도 `run.json.failure` 파일이 아닙니다.)

## Click Recipes

### 이미지 기반 클릭 (OpenCV 템플릿 매칭)

| 필드 | 의미 |
|------|------|
| `image` | 템플릿 경로. 상대경로는 recipe 파일 기준. |
| `confidence` | 매칭 임계값 0.0–1.0. 기본 `0.9`. |
| `region` | `[left, top, width, height]` 검색 영역 제한. |
| `grayscale` | 색 무시 흑백 매칭. 기본 `false`. |

실패 모드는 모두 타입 있는 예외: `ImageTemplateNotFound`, `ImageMatchConfidenceLow`.

### Step 가드 — `wait_for` / `settle_ms` / `verify_transition` / `post_click_signal`

각 step 은 사전 anchor (`wait_for`), 클릭 후 settle 지연 (`settle_ms`, 기본 300 ms),
페이지 전환 검증 (`verify_transition` + 임계값), 클릭 후 신호 폴링 (`post_click_signal`) 을 가질 수 있습니다.

```yaml
steps:
  - name: confirm-purchase
    wait_for:
      image: templates/confirm-enabled.png
      timeout: 5.0
      interval: 0.1
    image: templates/confirm-button.png
    confidence: 0.9
    settle_ms: 500          # 무거운 SPA 면 500–1000, 즉시 반응 native 면 0–50
    verify_transition: true
    transition_threshold: 0.02
    post_click_signal:
      image: templates/success-toast.png
      timeout: 6.0
```

`wait_for` 타임아웃 → `ImageWaitTimeout` (phase `pre_click`).
`verify_transition` 미달 → `PageTransitionNotDetected` (phase `post_click`).
`post_click_signal` 타임아웃 → `ImageWaitTimeout` (phase `post_click`).
같은 error class 라도 `phase` 필드로 구별됩니다 — `failure.jsonl` 참고.

## CI & 검사

| 검사 | 명령 | 목적 |
|------|------|------|
| Lint | `uv run ruff check .` | 스타일·미사용 import·규칙 위반 |
| Type | `uv run mypy` | strict 타입 검사 |
| Test (기본) | `uv run pytest -q` | `-m real` 자동 제외 |
| Test (real) | `uv run pytest -m real -q` | macOS Accessibility + Screen Recording 필요 |
| Pre-commit | `uv run pre-commit run --all-files` | 전수 검사 |

GitHub Actions 가 `main` 으로의 push 와 모든 PR 에서 동작합니다 — [`.github/workflows/ci.yml`](.github/workflows/ci.yml) 참고. 워크플로우는 Python 3.14 + xvfb (Ubuntu, `import pyautogui` 가 실제 display 없이도 성공하도록) 를 설치한 뒤 ruff + mypy + pytest 를 돌리고, 별도 pre-commit job 도 함께 실행합니다. 로컬에서는 `uv run pre-commit install` 로 깔리는 pre-commit 훅이 같은 게이트입니다.

## 불변식

coord-smith 에는 네 개의 hard invariant 가 있습니다. 위반은 PR 단계에서 거절됩니다:

1. **LLM-free 런타임.** coord-smith 안에서 모델 호출 없음. 추론은 OpenClaw 에 있습니다.
2. **브라우저 내부 금지.** Playwright / CDP / Chromium 드라이버 없음. OS 좌표·픽셀만.
3. **`pyautogui.FAILSAFE = True`** 가 `PyAutoGUIAdapter.__init__` 에서 강제 설정됩니다. 커서를 화면 모서리로 빠르게 던지면 즉시 중단됩니다.
4. **좌표 우선순위 고정.** payload → recipe 좌표 → recipe 이미지 → no-click. 역순 허용 안 함.

OpenCV 는 결정적 픽셀 매칭 라이브러리이므로 LLM 도 브라우저도 아닙니다 — 허용됩니다.

## 프로젝트 구조

```
src/coord_smith/
  adapters/         실행 어댑터 (PyAutoGUI, page-transition diff)
  config/           설정 모델 (ClickRecipe, RuntimeSettings)
  evidence/         envelope 파싱·검증
  graph/            LangGraph 노드 + CLI 엔트리포인트
  missions/         미션 이름 레지스트리
  models/           런타임 상태·에러·체크포인트 모델
  reporting/        전환 요약 리포팅
  validation/       bootstrap asset 검증
tests/
  unit/             단위 테스트
  contract/         아키텍처 계약 테스트
  integration/      real-binary 테스트 (`-m real`)
  e2e/              풀 파이프라인 테스트
  fixtures/         공용 테스트 fixture
docs/
  prd.md                     진실의 원천
  current-state.md           현재 구현 스냅샷
  architecture-boundaries.md 액터 / 네임스페이스 경계
  recipes/                   샘플 click recipe
```

## 이름

- **coord-smith** — *easy axes*: 두 자루 도끼 (좌표와 픽셀) 만 휘두르고, 그 이상은 묻지 않는다.

## Triad

coord-smith 는 두 자매 도구 사이에 위치합니다 — 각각 독립 프로세스, 디스크 위 산출물로만 연결됩니다:

```
OpenClaw (think)  ──▶  coord-smith (act)  ──▶  evidence envelope (record)
   외부 LLM           결정적                JSONL + PNG (디스크)
                       OS 좌표 클릭
```

분리는 의도적입니다 — 각 컴포넌트는 다른 컴포넌트를 건드리지 않고도 교체 가능해야 합니다.

## 마지막 한 줄

> *"클릭은 진실에 거는 가장 단순한 베팅이다 — 픽셀이 움직이거나, 움직이지 않거나."*

coord-smith 는 페이지에 대해 추론하지 않습니다. 시킨 자리를 누르고, 화면에게 "뭐 변했어?" 라고 묻습니다. 화면이 아니라고 답하면 그 실행은 — 큰 소리로, 증거와 함께 — 실패합니다.

## 라이선스

MIT — [LICENSE](./LICENSE) 참고.

# ez-ax

> Python CUA 런타임 — 외부 LLM 의 지시에 따라 OS 좌표를 결정적으로 누른다

![python](https://img.shields.io/badge/python-3.14-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![tests](https://img.shields.io/badge/tests-703%20passing-brightgreen)
![runtime](https://img.shields.io/badge/runtime-LLM--free-orange)

**ez-ax** 는 *손* 입니다. *머리* — OpenClaw 같은 외부 LLM — 가 무엇을 어디서 클릭할지 정하면, ez-ax 는 그 결정을 OS 위에서 좌표 클릭과 스크린샷 증거로 실행합니다. 추론은 런타임 바깥에 있고, 런타임 자체에는 LLM 호출이 0건입니다.

한 번의 실행은 LangGraph 상태 머신이 12 개 미션을 순서대로 통과시키는 파이프라인입니다. 각 미션은 다음 미션이 시작되기 전에 evidence envelope (action-log JSONL, 스크린샷, 전환 diff) 를 디스크에 남깁니다. 브라우저 내부 (Playwright / CDP / Chromium) 는 건드리지 않습니다 — OS 좌표와 픽셀만 사용합니다.

[English](./README.md)

## 파이프라인

런타임은 12 개 미션을 정해진 순서로 통과합니다. 각 미션은 결정적이며, 다음 미션이 시작되기 전에 evidence 를 디스크에 남깁니다.

| 미션 | 역할 |
|------|------|
| `attach_session` | session-ref 로 기존 브라우저 세션에 부착. |
| `prepare_session` | 기대 인증 상태 / 대상 페이지 URL 검증. |
| `benchmark_validation` | 기록된 벤치마크에 대해 실행 검증. |
| `page_ready_observation` | 스크린샷으로 페이지 준비 상태 확인. |
| `sync_observation` | 로컬 상태와 페이지 상태 동기화. |
| `target_actionability_observation` | 대상이 클릭 가능한 상태인지 확인. |
| `armed_state_entry` | 클릭 발사 직전 armed 상태 진입. |
| `trigger_wait` | 결정적 트리거 신호 대기. |
| `click_dispatch` | 클릭 발사 — payload 좌표 / recipe 좌표 / recipe 이미지. |
| `click_completion` | 클릭 후 evidence (스크린샷, 전환 diff) 캡처. |
| `success_observation` | 기대한 상태 변화가 발생했는지 검증. |
| `run_completion` | sealed 상태 코드로 실행 종료. |

각 미션은 고정된 과거형 action key (예: `click_dispatch` → `click-dispatched`) 를 emit 하므로 action log 를 grep 으로 추적할 수 있습니다.

```
 OpenClaw (외부 LLM)
      │  결정 / 좌표 / 이미지 ref
      ▼
 ez-ax CLI ──▶ LangGraph 상태 머신 ──▶ 12 미션
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
git clone https://github.com/<your-org>/ez-ax.git
cd ez-ax
uv sync --extra dev
```

`uv` 는 `pyproject.toml` 의 `requires-python` 에 따라 Python 3.14 를 자동으로 잡아 옵니다. 시스템에 3.14 가 없으면 먼저 설치:

```bash
uv python install 3.14
```

### 2. 검증

```bash
uv run pytest -q                # 703 passed, 1 skipped, 4 deselected
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
ez-ax --click-recipe ./recipe.json \
      --session-ref my-session \
      --expected-auth-state authenticated \
      --target-page-url https://example.com \
      --site-identity example
```

최소 좌표 recipe:

```json
{
  "version": 1,
  "missions": {
    "click_dispatch": {"x": 800, "y": 500}
  }
}
```

레이아웃 변화에 강건한 이미지 recipe (권장):

```json
{
  "version": 1,
  "missions": {
    "click_dispatch": {
      "image": "templates/buy-button.png",
      "confidence": 0.9,
      "grayscale": false
    }
  }
}
```

**좌표 우선순위**: payload (OpenClaw) → recipe 좌표 → recipe 이미지 → no-click.

## Click Recipes

### 이미지 기반 클릭 (OpenCV 템플릿 매칭)

| 필드 | 의미 |
|------|------|
| `image` | 템플릿 경로. 상대경로는 recipe 파일 기준. |
| `confidence` | 매칭 임계값 0.0–1.0. 기본 `0.9`. |
| `region` | `[left, top, width, height]` 검색 영역 제한. |
| `grayscale` | 색 무시 흑백 매칭. 기본 `false`. |

실패 모드는 모두 타입 있는 예외: `ImageTemplateNotFound`, `ImageMatchConfidenceLow`.

### 페이지 전환 검증 (옵션, 기본 off)

```json
{
  "missions": {
    "click_dispatch": {
      "image": "templates/buy.png",
      "verify_transition": true,
      "transition_threshold": 0.02,
      "transition_region": [0, 100, 1920, 800]
    }
  }
}
```

클릭 직전 스크린샷 → 클릭 → 클릭 직후 스크린샷 → `PIL.ImageChops.difference` bbox 면적 / 영역 면적 > threshold 면 통과. 미달 시 `PageTransitionNotDetected` 예외.

### Post-click 신호 폴링 (옵션, 기본 off)

```json
{
  "missions": {
    "click_dispatch": {
      "image": "templates/buy.png",
      "post_click_signal": {
        "image": "templates/loading-spinner.png",
        "confidence": 0.85,
        "timeout": 5.0,
        "interval": 0.1
      }
    }
  }
}
```

지정 이미지가 화면에 나타날 때까지 `locateCenterOnScreen` 폴링. 타임아웃 시 `ImageWaitTimeout`.

## CI & 검사

| 검사 | 명령 | 목적 |
|------|------|------|
| Lint | `uv run ruff check .` | 스타일·미사용 import·규칙 위반 |
| Type | `uv run mypy` | strict 타입 검사 |
| Test (기본) | `uv run pytest -q` | `-m real` 자동 제외 |
| Test (real) | `uv run pytest -m real -q` | macOS Accessibility + Screen Recording 필요 |
| Pre-commit | `uv run pre-commit run --all-files` | 전수 검사 |

GitHub Actions 는 Python 3.14 단일 버전 (Ubuntu, pyautogui import 용 xvfb) + 별도 pre-commit job 을 실행합니다.

## 불변식

ez-ax 에는 네 개의 hard invariant 가 있습니다. 위반은 PR 단계에서 거절됩니다:

1. **LLM-free 런타임.** ez-ax 안에서 모델 호출 없음. 추론은 OpenClaw 에 있습니다.
2. **브라우저 내부 금지.** Playwright / CDP / Chromium 드라이버 없음. OS 좌표·픽셀만.
3. **`pyautogui.FAILSAFE = True`** 가 `PyAutoGUIAdapter.__init__` 에서 강제 설정됩니다. 커서를 화면 모서리로 빠르게 던지면 즉시 중단됩니다.
4. **좌표 우선순위 고정.** payload → recipe 좌표 → recipe 이미지 → no-click. 역순 허용 안 함.

OpenCV 는 결정적 픽셀 매칭 라이브러리이므로 LLM 도 브라우저도 아닙니다 — 허용됩니다.

## 프로젝트 구조

```
src/ez_ax/
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

- **ez-ax** — *easy axes*: 두 자루 도끼 (좌표와 픽셀) 만 휘두르고, 그 이상은 묻지 않는다.

## Triad

ez-ax 는 두 자매 도구 사이에 위치합니다 — 각각 독립 프로세스, 디스크 위 산출물로만 연결됩니다:

```
OpenClaw (think)  ──▶  ez-ax (act)  ──▶  evidence envelope (record)
   외부 LLM           결정적                JSONL + PNG (디스크)
                       OS 좌표 클릭
```

분리는 의도적입니다 — 각 컴포넌트는 다른 컴포넌트를 건드리지 않고도 교체 가능해야 합니다.

## 마지막 한 줄

> *"클릭은 진실에 거는 가장 단순한 베팅이다 — 픽셀이 움직이거나, 움직이지 않거나."*

ez-ax 는 페이지에 대해 추론하지 않습니다. 시킨 자리를 누르고, 화면에게 "뭐 변했어?" 라고 묻습니다. 화면이 아니라고 답하면 그 실행은 — 큰 소리로, 증거와 함께 — 실패합니다.

## 라이선스

MIT — [LICENSE](./LICENSE) 참고.

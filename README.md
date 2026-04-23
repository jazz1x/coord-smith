# coord-smith

좌표 기반 브라우저 자동화를 위한 Python-first 오케스트레이션 런타임.

## 주요 특징

- 12개 미션 deterministic 파이프라인 (세션 연결 → 클릭 → 완료)
- LangGraph 상태 머신 기반 미션 시퀀싱
- PyAutoGUI CUA 엔진 (좌표 클릭 + 스크린샷만 사용)
- 런타임에 LLM 없음 — 외부 LLM(OpenClaw)이 추론 담당
- 매 미션마다 evidence 기반 검증

## 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.11 ~ 3.14 |
| 상태 머신 | LangGraph |
| 브라우저 제어 | PyAutoGUI (좌표 클릭 + 스크린샷) |
| 외부 연동 | CLI + artifacts (OpenClaw ping-pong) |
| 데이터 모델 | Pydantic v2 |
| 타입 체크 | mypy (strict) |
| 린팅 | ruff |
| 테스트 | pytest + pytest-asyncio |
| 패키지 관리 | uv |

## What's New on `feat/click-flow-via-recipe`

본 브랜치는 main 대비 4 축으로 이전에 비어 있던 실행 경로를 메꿨습니다.

- **Direction realignment (SOT 정리)** — `runCompletion` ceiling 이 15+ 문서에 일관되게 반영. `pageReadyObserved` 를 current ceiling 으로 주장하던 문장 0건(드리프트 가드 `test_docs_ceiling_truth.py` 가 상시 감시). FINAL_STOP hard-halt 규약을 코드·YAML·PRD·RAG 4 중 일치.
- **PyAutoGUI 어댑터 견고화** — blanket-except 제거, `ExecutionTransportError` 하위 5 신규 typed exception (`AccessibilityPermissionDenied`, `ScreenCapturePermissionDenied`, `ScreenCaptureUnavailable`, `ClickExecutionUnverified`, `ClickCoordinatesOutOfBounds`). Preflight 로 권한 부재 즉시 포착 (exit code 2).
- **Real click flow (OpenClaw 없이)** — `--click-recipe PATH` 또는 `EZAX_CLICK_RECIPE` env 로 정적 좌표 table 주입 → 실제 `pyautogui.click` 발사. Payload 가 있으면 payload 우선, 없으면 recipe fallback, 없으면 no-click. 실제 바이너리 통합 테스트 3 건(`pytest -m real`) 상시 검증.
- **Tooling** — pre-commit (standard hooks + ruff/mypy/pytest unit+contract) + GitHub Actions CI (Python 3.11/3.12/3.13 matrix, Ubuntu + xvfb). 767 default passed + 3 real passed.

## Bootstrap

Fresh checkouts must sync dev extras before running tests; otherwise
`pytest` collection fails with `ModuleNotFoundError: PIL|pyautogui`.

```bash
uv sync --extra dev
uv run pytest -q            # expected: 767 passed, 1 skipped, 3 deselected
uv run pre-commit install   # one-time: wire git hook
```

## Development Checks

| Check | Command | 역할 |
|-------|---------|------|
| Lint | `uv run ruff check .` | 스타일·미사용 import·규칙 위반 |
| Type | `uv run mypy` | `strict` 모드 타입 검사 |
| Test (default) | `uv run pytest -q` | `-m real` 자동 제외 |
| Test (real binary) | `uv run pytest -m real -q` | 권한 있는 로컬에서만 (macOS Accessibility + Screen Recording 필요) |
| Pre-commit (전체) | `uv run pre-commit run --all-files` | 커밋 전 전수 검사 |

## CI

`.github/workflows/ci.yml` 은 다음을 수행:

- **lint-type-test matrix**: Python 3.11 / 3.12 / 3.13 에서 ruff + mypy + pytest (기본). Ubuntu + xvfb 로 pyautogui import 를 헤드리스 환경에서 로드.
- **pre-commit**: 모든 훅(표준 훅 + 로컬 ruff/mypy/pytest-unit-contract/bootstrap-assets) 전수 실행.

둘 다 push / pull_request (main) 에서 동작. 동일 브랜치 동시 실행은 자동 취소(concurrency group).

## Pre-commit

로컬 git hook:

```bash
uv run pre-commit install
```

등록되는 훅:
- 표준(`pre-commit-hooks v5`): trailing whitespace (`*.md` 제외), end-of-file, check-yaml/json/toml, large-file guard(2MB), merge-conflict, mixed-line-ending(LF).
- 프로젝트(`local`): ruff check, mypy, `tests/unit + tests/contract` pytest, bootstrap asset 테스트.

`-m real` 테스트는 무거우므로 pre-commit 에서 빠집니다. CI 에서도 default pytest 만 돌고, real 은 수동 invocation (`pytest -m real`) 로만 실행합니다.

## Permissions (macOS)

런타임(`ez-ax` 콘솔 스크립트) 이 실제로 클릭하고 스크린샷을 찍으려면
**호스트 터미널 앱** 에 두 권한이 필요합니다. 둘 다 없으면 entrypoint 의
`preflight` 단계에서 exit 코드 `2` 로 중단됩니다.

1. **Accessibility** — `System Settings → Privacy & Security → Accessibility`
   에서 사용 중인 터미널 앱(Terminal / iTerm / VS Code / Claude Code 등) 을
   체크. 체크 후 해당 앱 재시작 필요.
2. **Screen Recording** — 동일 경로의 `Screen Recording` 항목. 첫 실행 시
   권한 프롬프트가 뜰 수 있고, 한 번 거부하면 수동으로 추가해야 합니다.

권한 부여 후 real-binary integration 테스트로 검증:

```bash
uv run pytest -m real -q   # expected: 3 passed
```

`-m real` 을 붙이지 않은 기본 pytest 실행은 이 테스트들을 자동 skip 합니다.

## Click Recipes (OpenClaw 없이 실제 클릭하기)

런타임의 released 그래프는 click_dispatch 같은 미션에 **빈 payload** 를
넘긴다 — 원 설계상 OpenClaw 등 외부 액터가 payload 에 x/y 를 주입하도록
되어 있기 때문. OpenClaw 연동이 없는 환경에서도 실제 브라우저 클릭을
일으키려면 `click recipe` 를 사용한다. Recipe 는 미션 이름 → 좌표의
정적 표로, JSON 파일 한 개다.

**Recipe 파일 (`docs/recipes/sample-click-recipe.json`)**:

```json
{
  "version": 1,
  "missions": {
    "click_dispatch": {"x": 800, "y": 500}
  }
}
```

**실행**:

```bash
# CLI flag
ez-ax --click-recipe ./recipe.json \
    --session-ref my-session \
    --expected-auth-state authenticated \
    --target-page-url https://example.com \
    --site-identity example

# 또는 env var
EZAX_CLICK_RECIPE=./recipe.json ez-ax --session-ref ...
```

**우선순위**: 외부 액터가 payload 에 `x`/`y` 를 이미 넣어 보내면 그 값이
recipe 보다 우선한다. Recipe 에 없는 미션은 클릭하지 않고 그대로 통과.
Recipe 파일이 지정됐지만 로드 실패(파일 없음·JSON 오류·스키마 불일치) 시
entrypoint 는 exit 3 으로 실패한다.

**주의사항**: recipe 좌표는 고정이다 — 페이지 레이아웃이 바뀌면 recipe 도
함께 갱신해야 한다. 잘못된 좌표는 화면의 엉뚱한 UI 요소를 클릭할 수 있다.
`pyautogui.FAILSAFE=True` 상태라 커서를 화면 모서리로 빠르게 옮기면 루프를
중단시킬 수 있다.

## 시작하기

```bash
uv sync --extra dev          # 또는: pip install -e ".[dev]"
uv run pytest -q             # 테스트 실행 (744 passed, 1 skipped)
uv run mypy                  # 타입 체크
uv run ruff check .          # 린팅
```

## 아키텍처

```
OpenClaw (외부 LLM) --> coord-smith CLI --> 12 미션 --> PyAutoGUI --> OS
```

OpenClaw이 MCP를 통해 추론 결정을 제공합니다. coord-smith는 deterministic
오케스트레이션 루프를 담당합니다: 12개 순차 미션(attach_session ~ run_completion)을
순서대로 실행하고, PyAutoGUI로 좌표 클릭을 수행하며, 스크린샷을 evidence로
캡처하고, 각 전환을 검증한 후 다음 미션으로 진행합니다.

## 프로젝트 구조

```
src/ez_ax/          런타임 소스 (missions, graph, adapters, models)
tests/              유닛 및 통합 테스트
docs/               제품 스펙 및 아키텍처 문서
docs/product/       PRD 세트
```

전체 스펙은 [docs/product/prd.md](docs/product/prd.md)를 참조하세요.

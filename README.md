# ez-ax

좌표 기반 브라우저 자동화를 위한 Python-first 오케스트레이션 런타임.

## 개요

ez-ax는 OpenClaw(외부 LLM)의 지시에 따라 OS 좌표 클릭을 실행하는 deterministic 런타임입니다.
12개 미션으로 구성된 파이프라인을 LangGraph 상태 머신으로 순차 실행하며,
LLM 추론은 포함하지 않습니다.

```
OpenClaw (외부 LLM) → ez-ax CLI → 12개 미션 → PyAutoGUI → OS
```

## 주요 특징

- 12개 미션 deterministic 파이프라인 (attach_session → run_completion)
- LangGraph 상태 머신 기반 미션 시퀀싱
- PyAutoGUI CUA 엔진 (좌표 클릭 + 스크린샷만 사용)
- 런타임에 LLM 없음 — 외부 LLM(OpenClaw)이 추론 담당
- 매 미션마다 evidence 기반 검증
- `pyautogui.FAILSAFE = True` 강제 설정 — 화면 모서리 이동 시 즉시 중단
- 원자적 파일 쓰기 — 중간 종료 시에도 일관된 상태 유지
- 모든 이벤트 타임스탬프 UTC 통일

## 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 상태 머신 | LangGraph |
| 브라우저 제어 | PyAutoGUI (좌표 클릭 + 스크린샷) |
| 외부 연동 | CLI + artifacts (OpenClaw ping-pong) |
| 데이터 모델 | Pydantic v2 |
| 타입 체크 | mypy |
| 린팅 | ruff |
| 테스트 | pytest + pytest-asyncio |
| 패키지 관리 | uv |

## Bootstrap

```bash
uv sync --extra dev
uv run pytest -q            # expected: 794 passed, 1 skipped, 3 deselected
uv run pre-commit install   # 최초 1회: git hook 설치
```

> Python 3.14는 pyautogui / PIL 바이너리 휠이 없어 테스트 실행이 불가합니다.
> `uv venv --python 3.11 .venv311 && uv pip install --python .venv311/bin/python3.11 -e ".[dev]"`
> 로 3.11 전용 venv를 생성 후 `.venv311/bin/pytest` 를 사용하세요.

## Development Checks

| Check | Command | 역할 |
|-------|---------|------|
| Lint | `uv run ruff check .` | 스타일·미사용 import·규칙 위반 |
| Type | `uv run mypy` | 타입 검사 |
| Test (default) | `uv run pytest -q` | `-m real` 자동 제외 |
| Test (real binary) | `uv run pytest -m real -q` | macOS Accessibility + Screen Recording 필요 |
| Pre-commit (전체) | `uv run pre-commit run --all-files` | 커밋 전 전수 검사 |

## CI

`.github/workflows/ci.yml`:

- **lint-type-test matrix**: Python 3.11 / 3.12 / 3.13에서 ruff + mypy + pytest (기본).
  Ubuntu + xvfb로 pyautogui import를 헤드리스 환경에서 로드.
- **pre-commit**: 모든 훅 전수 실행 (ruff, mypy, pytest unit+contract, bootstrap-assets).

push / pull_request (main) 에서 동작. 동일 브랜치 동시 실행 자동 취소.

## Pre-commit

```bash
uv run pre-commit install
```

등록 훅:
- 표준(`pre-commit-hooks v5`): trailing whitespace (`*.md` 제외), end-of-file, check-yaml/json/toml, large-file guard(2MB), merge-conflict, mixed-line-ending(LF).
- 프로젝트(`local`): ruff check, mypy, `tests/unit + tests/contract` pytest, bootstrap asset 테스트.

`-m real` 테스트는 pre-commit 및 CI 기본 실행에서 제외됩니다.

## Permissions (macOS)

`ez-ax` 콘솔 스크립트가 실제 클릭·스크린샷을 수행하려면 호스트 터미널에 두 권한이 필요합니다.
권한 부재 시 `preflight()` 단계에서 exit code `2`로 중단됩니다.

1. **Accessibility** — `System Settings → Privacy & Security → Accessibility`에서 터미널 앱 체크 후 재시작.
2. **Screen Recording** — 동일 경로의 `Screen Recording` 항목.

권한 확인:
```bash
uv run pytest -m real -q   # expected: 3 passed
```

## Click Recipes (OpenClaw 없이 실제 클릭하기)

OpenClaw 없이도 정적 좌표를 주입해 실제 클릭을 발사할 수 있습니다.

**Recipe 파일**:
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

좌표 우선순위: payload(OpenClaw 주입) > recipe > no-click.
Recipe 파일 로드 실패 시 exit code `3`.

> **주의**: recipe 좌표는 고정입니다. 페이지 레이아웃 변경 시 recipe도 갱신해야 합니다.
> `pyautogui.FAILSAFE = True` 상태이므로 커서를 화면 모서리로 빠르게 이동하면 즉시 중단됩니다.

## Autoloop

저비용 자율 구현 루프:

```bash
# 드라이 런 (claude 바이너리 호출 없이 프롬프트만 출력)
uv run ez-ax-autoloop --dry-run

# 실행
uv run ez-ax-autoloop --model claude-haiku-4-5-20251001 --max-cycles 10
```

각 사이클 전 pytest/mypy/ruff 검증 게이트를 통과해야 다음 claude 호출이 진행됩니다.

## 프로젝트 구조

```
src/ez_ax/
  adapters/         실행 어댑터 (PyAutoGUI, MCP)
  config/           설정 모델 (ClickRecipe, RuntimeSettings)
  evidence/         evidence envelope 파싱·검증
  graph/            LangGraph 노드·엔트리포인트
  missions/         미션 이름 레지스트리
  models/           런타임 상태·에러·체크포인트 모델
  rag/              autoloop 프롬프트 드라이버·paths
  reporting/        전환 요약 리포팅
  validation/       bootstrap asset 검증
tests/
  unit/             단위 테스트
  contract/         아키텍처 계약 테스트
  e2e/              E2E 통합 테스트
  fixtures/         테스트 픽스처 (fake MCP SDK 등)
docs/
  product/          PRD 세트
  prd.md            시스템 진실 원천
  current-state.md  현재 구현 스냅샷
```

전체 스펙: [docs/prd.md](docs/prd.md)

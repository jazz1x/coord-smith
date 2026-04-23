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

## Bootstrap

Fresh checkouts must sync dev extras before running tests; otherwise
`pytest` collection fails with `ModuleNotFoundError: PIL|pyautogui`.

```bash
uv sync --extra dev
uv run pytest -q            # expected: 752 passed, 1 skipped, 2 deselected
```

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
uv run pytest -m real -q   # expected: 2 passed
```

`-m real` 을 붙이지 않은 기본 pytest 실행은 이 테스트들을 자동 skip 합니다.

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

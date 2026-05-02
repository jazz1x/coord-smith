# CLAUDE

Operational entrypoint for agents working in this repository.

## Project Goal

ez-ax는 **클릭 규칙(recipe)을 받아 OS 레벨에서 실행하고, 그 결과를 타입화된 증거로 반환하는 오케스트레이터**다.
브라우저를 직접 다루지 않는다. 클릭할 위치를 스스로 결정하지 않는다.

### 시스템 내 역할

```yaml
caller: OpenClaw          # 외부 AI 추론 레이어. ez-ax를 호출하는 쪽.
ez_ax_owns:
  - 미션 그래프 순회 (LangGraph)
  - 클릭 규칙 실행 (pyautogui)
  - 증거 수집 및 검증
  - 릴리스 경계 강제 (runCompletion 이하)
ez_ax_does_not_own:
  - 브라우저 내부 (DOM, CDP, Playwright)
  - 런타임 LLM 추론
  - "무엇을 클릭할지" 판단 — 그것은 호출자(OpenClaw)의 역할
```

### 입력 계약

```yaml
required:
  session_ref:         "세션 식별자"
  expected_auth_state: "인증 선행 조건"
  target_page_url:     "액션이 일어날 페이지 URL"
  site_identity:       "사이트 식별자"

click_rule:            # 선택. 없으면 클릭 없이 통과.
  source: "--click-recipe PATH  또는  EZAX_CLICK_RECIPE 환경변수"
  format: "YAML (.yaml/.yml) 또는 JSON — 둘 다 런타임 파싱 지원. YAML 권장."
  coord_priority: "payload(OpenClaw) > recipe coord > recipe image > no-click"
```

### 클릭 규칙 포맷 (YAML — 사람과 AI 모두 이 형태로 작성)

```yaml
version: 1
missions:
  click_dispatch:
    # 방법 A: 고정 픽셀 좌표
    x: 400
    y: 300

    # 방법 B: 스크린샷 템플릿 매칭 (OpenCV)
    # image: templates/submit-button.png
    # confidence: 0.9          # 0~1, 기본 0.9
    # region: [0, 500, 1920, 600]  # [x, y, width, height]

    # 선택: 클릭 후 페이지 전환 감지
    verify_transition: true
    transition_threshold: 0.01

    # 선택: 클릭 후 특정 이미지가 나타날 때까지 폴링
    post_click_signal:
      image: templates/success-toast.png
      confidence: 0.85
      timeout: 5.0
      interval: 0.1
```

AI에게 레시피 생성을 요청할 때는 Pydantic 스키마를 프롬프트에 첨부한다:

```bash
python -c "import json; from ez_ax.config.click_recipe import ClickRecipe; \
           print(json.dumps(ClickRecipe.model_json_schema(), indent=2))"
```

### 출력 계약

```yaml
artifacts: "artifacts/runs/<run_id>/"
evidence_types:
  action_log: "artifacts/action-log/<key>.jsonl"
  screenshot:  "artifacts/screenshot/<key>.png"
exit_codes:
  0: 정상
  1: 런타임 에러
  2: macOS Accessibility / Screen Recording 권한 없음
  3: 레시피 파일 누락·스키마 오류
```

## Bootstrap

Fresh checkouts run, in order:

1. `uv sync --extra dev` — installs runtime + dev deps from `pyproject.toml`.
2. `uv run pytest -q` — expected: 703 passing, 1 skipped, 4 deselected.

If pytest collection fails with `ModuleNotFoundError: PIL|pyautogui`, step 1
did not complete.

The 4 deselected items are real-binary integration tests (`pytest -m real`)
that require macOS Accessibility + Screen Recording permission on the host
terminal. Without those permissions, the `ez-ax` console script exits at
`preflight()` with code 2 instead of producing silent no-op clicks.

## Real clicks without OpenClaw

The released-scope graph dispatches click-bearing missions with empty
payloads. In the documented architecture an external actor (OpenClaw)
populates `x` / `y`. When that actor is absent, `ez-ax` accepts a
**click recipe** (`--click-recipe PATH` or `EZAX_CLICK_RECIPE` env) that
maps `mission_name` → coordinates or template image. The adapter resolves
click coords with priority: payload → recipe coord → recipe image → no
click. See `README.md` §Click Recipes for schema and examples.

## Primary Source Documents

Agents must read in this order:

1. [docs/prd.md](docs/prd.md) — invariant system truth
2. [docs/current-state.md](docs/current-state.md) — implementation snapshot
3. [README.md](README.md) — pipeline + invariants overview

Source code under `src/ez_ax/` is authoritative for runtime contracts
(missions, state model, adapters, evidence envelope). Read code, not historical
design docs.

## Priority Order

1. Repository-specific instructions in this file.
2. Layered entrypoint documents:
   [docs/prd.md](docs/prd.md), [docs/current-state.md](docs/current-state.md).
3. Source code under `src/ez_ax/` for runtime contracts.
4. Repository base config: `pyproject.toml`, `.pre-commit-config.yaml`,
   `.gitignore`.
5. For Python code writing / review / refactoring, follow
   `.claude/python-engineering.md` unless it conflicts with higher-priority
   sources. The same guidance is available as the `python-engineering` skill
   at `.claude/skills/python-engineering/SKILL.md`.

## Invariants

- **LLM-free runtime.** The ez-ax runtime graph contains no LLM inference.
  Reasoning lives outside (e.g. OpenClaw).
- **Browser-internals forbidden.** No Playwright, CDP, or Chromium driver.
  Only OS-level coordinates and pixels.
- **`pyautogui.FAILSAFE = True`** is enforced in `PyAutoGUIAdapter.__init__`.
- **Coordinate priority is fixed.** payload → recipe coord → recipe image →
  no click. Never the other way.
- **OpenClaw calls ez-ax**, not the reverse.

## Agent Expectations

- Keep `ez-ax` orchestration-centric.
- Prefer event-based waits over sleep-based timing.
- Prefer typed evidence over intuition.
- Do not introduce anti-detection logic.
- Do not describe modeled behavior as released behavior.
- Do not change anything above the current approved release ceiling
  (`runCompletion`) unless the PRD explicitly allows it.
- Use relevant available skills actively when they fit. Skills are
  execution aids, not scope authority — if a skill conflicts with the PRD,
  follow the PRD.

## Working Rules

- Each autonomous task must end with applicable validation
  (`pytest` / `mypy` / `ruff`) and a git commit before the next task begins.
- If a task cannot be validated or committed honestly, it must not be
  reported as complete.
- When the PRD and remembered prior repository state differ, follow the PRD
  and the currently existing files; ignore deleted or historical structure.

## Guardrails

- Planned or modeled features must not be presented as implemented or
  released.
- The active canonical implementation path is Python-only (3.14). Do not
  recreate `package.json`, `bun.lock`, `tsconfig.json`, or `biome.json` as
  active toolchain files.
- Do not add new TypeScript runtime source under `src/` or any alternate
  package root.
- If a proposed change would restore a removed execution path, stop and
  treat it as a policy violation unless the PRD explicitly changes.

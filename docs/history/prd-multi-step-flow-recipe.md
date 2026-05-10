# Multi-step Flow Recipe + Per-Step Fallback — PRD

> Created: 2026-05-10
> Status: draft
> Author decisions encoded (4 confirms 받음)
> Estimated scale: Medium (1–2 weeks)

---

## 1. Problem Definition

### 1.1 Current State (As-Is)

coord-smith는 한 번의 invocation으로 한 번의 click만 실행한다. recipe schema가 `missions: dict[str, MissionTarget]` 으로 다중 mission 표현은 가능하나, 12-mission graph 자체가 *"한 click의 lifecycle"* 로 설계되어 있어 click_dispatch 한 곳에서만 실제 클릭이 발생한다. 12-mission 외의 modeled 7개(release_gate_evaluation 등)는 코드에 살아있으나 영원히 도달하지 않는 dead-scaffold다.

실제 사용 시나리오 — *티켓팅 buy → seat → confirm → pay* 같은 — 는 **여러 클릭의 시퀀스**다. 현재 구조로 이걸 표현하려면 외부 head가 매 클릭마다 coord-smith를 다시 호출하고, 사이에서 직전 screenshot 보고 다음 recipe를 새로 작성해야 한다. 이는:

- per-step subprocess + artifact tree fragmentation 비용
- 브라우저 세션이 coord-smith 외부에 있어야 함 (anti-bot에 거의 불가능)
- 여러 클릭이 한 트리에 묶여야 할 evidence가 분산
- *"한 흐름이 한 recipe"* 라는 직관과 충돌

### 1.2 Why now

- v0.0.1 직전. spine 굳히지 않으면 후속 기능(DPI 정규화, retry, OpenClaw skill 등) 모두 잘못된 가정 위에 쌓임.
- 12-mission 중 6개가 이미 사실상 step-level 옵션(`verify_transition`, `post_click_signal`)으로 흡수 가능 — 하나로 정리할 좋은 시점.
- modeled 7개를 영구 삭제할 자연스러운 구실이 같이 발생.

### 1.3 Goal

- recipe가 **N step 시퀀스를 declarative로 표현**할 수 있게 한다.
- 각 step은 image와 coord를 **둘 다 first-class로** 선언할 수 있고, 하나가 실패하면 다른 것으로 fallback한다.
- mission graph를 **per-run / per-step 분리**로 단순화 — 3 per-run + 3 per-step (= 6 mission node)으로 12 + 7(modeled)을 대체.
- 단일-step recipe는 backwards-compat — 기존 사용자 마이그레이션 0건.

---

## 2. Design Decision

### 2.1 채택: Multi-step recipe + 단일-step backwards-compat

**Why this**: 실제 사용 패턴이 *"이 시퀀스를 그냥 자동 실행"* 이며 head가 step마다 끼어들 필요가 적음. Option 1이 1차 시민, Option 2(stateless chain)는 단일-step recipe를 N번 호출하는 형태로 자연 표현되어 별도 코드 경로 불필요.

### 2.2 Alternative A — Stateful session

`stdin` / 소켓으로 click-at-a-time 받는 long-running 프로세스.

**Why rejected**:
- 직전 PR(`prd-remove-mcp-scaffold`)의 영구 out-of-scope 결정과 같은 결의 단순성을 다시 깬다.
- "한 번 실행, exit cleanly" invariant 깨짐.
- 동시 실행/격리/세션 lifetime 새 문제 도입.

→ 본 PRD 종료 시점에 `docs/prd.md` §Non-Goals에 *"Stateful long-running session — permanently out of scope. coord-smith는 한 번 실행되고 종료된다."* 추가.

### 2.3 Alternative B — Status quo + 외부 chain

현재 그대로 유지하고 head가 N번 호출 + 외부에서 chain 처리.

**Why rejected**:
- evidence가 N개 run으로 분산 — 한 *flow*에 대한 single-source-of-truth 사라짐.
- per-step subprocess 비용 누적.
- 브라우저 세션 owner 모호 (coord-smith는 세션 안 잡음, head도 안 잡으면 닫힘).

→ 단, Option 2 fallback 경로로는 보존 — 단일-step recipe는 그대로 동작.

### 2.4 핵심 설계 결정 (사용자 4 confirm 답변 반영)

#### D1. Step DSL의 image · coord 동등 first-class

```yaml
- name: select-seat
  image: templates/seat.png      # 둘 다 1급 시민
  coord: { x: 400, y: 450 }       # 둘 다 1급 시민
  # 같은 step에 둘 다 있으면 기본 priority = image-first (정합성 우선)
```

**Default priority = image-first**. 정당화:
- image는 머신/DPI/해상도 변화에 더 강함 (정합성 ↑).
- coord는 동일 머신·동일 페이지 상태 가정에서만 안정.
- 즉 "같은 머신에서만 도는 demo recipe"가 아니라 "여러 환경에서 같이 도는 production recipe"가 default.

**Override**: recipe 작성자가 step 단위로 뒤집을 수 있음:

```yaml
- name: select-seat
  image: templates/seat.png
  coord: { x: 400, y: 450 }
  prefer: coord                   # 이 step만 coord-first → image fallback
```

`prefer` 기본값은 `image`. 명시 안 하면 image-first.

#### D2. 12-mission graph 단순화 (per-run / per-step 분리)

기존 12-mission은 *"한 click의 lifecycle"* 이었지만, 실제로는:
- 일부는 *invocation 수명* 의 일부 (per-run, 1회)
- 일부는 *각 click 수명* 의 일부 (per-step, N회)
- 일부는 step-level 옵션으로 흡수 가능 (이미 verify_transition / post_click_signal 형태로 존재)

**새 graph (6 mission node)**:

| Phase | Mission | 실행 횟수 | 역할 |
|-------|---------|----------|------|
| **Per-run setup** | `attach_session` | 1 | session-ref 부착 (외부 actor 책임 전제) |
|  | `prepare_session` | 1 | 인증 상태 / target URL 검증 |
| **Per-step loop** | `step_observe` | N | step 진입 시 화면 상태 capture (sync + actionability + ready 흡수) |
|  | `step_dispatch` | N | 실제 클릭 (image / coord priority + fallback) |
|  | `step_capture` | N | 클릭 직후 evidence (transition + signal + completion + success 흡수) |
| **Per-run teardown** | `run_completion` | 1 | sealed close, ceiling stop proof |

**삭제되는 mission (12 → 6 + modeled 7 → 0)**:

- `benchmark_validation` → **영구 삭제** (사용 사례 미확립, "정말 필요한 것만" 원칙)
- `page_ready_observation` → `prepare_session`에 흡수
- `sync_observation` → `step_observe`에 흡수
- `target_actionability_observation` → `step_observe`에 흡수
- `armed_state_entry` → `step_dispatch` 내부 단계로 흡수
- `trigger_wait` → step DSL의 `wait_for` 옵션으로 변환
- `click_dispatch` → `step_dispatch`로 개명
- `click_completion` → `step_capture`에 흡수
- `success_observation` → `step_capture`에 흡수

modeled 7개 (`release_gate_evaluation` / `retry_or_stop_decision` / `work_rag_update` / `work_rag_compression` / `lesson_promotion` / `e2e_replay_or_comparison` / `python_validation_execution`) → **영구 삭제** (MCP 스캐폴드와 같은 방식으로 prd.md §Non-Goals에 명시).

**Released ceiling**: 새로운 ceiling = `run_completion` (이름 유지).

#### D3. 단일-step recipe backwards-compat

기존 recipe (현재 형태):

```yaml
version: 1
missions:
  click_dispatch: { x: 400, y: 300 }
```

→ 자동으로 **N=1 step의 multi-step recipe로 normalize**:

```yaml
version: 1
steps:
  - name: click_dispatch     # 키 이름 유지
    coord: { x: 400, y: 300 }
```

- 사용자 마이그레이션 0건.
- `missions: {...}` 형태와 `steps: [...]` 형태 둘 다 파싱.
- 둘 다 동시에 있으면 `steps` 우선, `missions`는 deprecation warning.

---

## 3. Scope

### 3.1 In scope

1. recipe schema 확장: `steps: list[Step]` (기존 `missions: dict` 와 공존, 자동 normalize)
2. Step DSL 정의 — image · coord · region · confidence · grayscale · prefer · wait_for · verify_transition · transition_threshold · post_click_signal. fallback chain은 명시 필드가 아니라 image+coord 동시 선언으로 묵시적 형성 (step-level retry는 별 PRD)
3. mission graph 재설계 — 3 per-run + 3 per-step (총 6 노드)
4. modeled 7 mission + `benchmark_validation` 영구 삭제 (코드 + 테스트 + names registry)
5. step-level fallback chain 구현 — primary 실패 시 fallback 시도, 모두 실패 시 typed error + 부분 artifact
6. evidence priority gate — per-step 적용 (각 step_capture 후 호출)
7. artifact 디렉토리 구조 확장 — `artifacts/runs/<run_id>/steps/<step_idx>-<step_name>/...`
8. recipe-guide.md 업데이트 — 새 Step DSL 문서화, 단일-step → multi-step 마이그레이션 노트
9. prd.md §Non-Goals 업데이트 — Stateful session 영구 거부 명시
10. 테스트 — 단일-step (회귀) / multi-step happy / step-내 fallback / step 실패 + 부분 artifact / modeled mission 부재 검증

### 3.2 Out of scope (별 PRD)

- DPI / resolution 정규화 — recipe에 reference resolution 선언 + adapter 정규화
- mid-flow head reasoning hook — head가 step 사이에 끼어들고 싶으면 step 끊어 호출 (Option 2 stateless 경로)
- Stateful long-running session — 영구 거부
- step-level retry / jitter — anti-bot 대응 시 별 PRD
- cross-platform preflight (Linux / Windows) — 별 PRD
- OpenClaw skill 시연 — 별 작업 (이 repo 외부)
- recipe 자동 생성 (screenshot → recipe) — 별 PRD

---

## 4. Implementation Spec

### 4.1 Per-File Changes

**`src/coord_smith/config/click_recipe.py`**
- `Step` Pydantic 모델 추가. 필드:
  - `name: str` (required, recipe 내 unique)
  - `image: str | None` · image-template 경로 (image 매칭 옵션과 짝)
  - `coord: {x: int, y: int} | None` · 고정 픽셀 좌표
  - `region: tuple[int, int, int, int] | None` · image 매칭 검색 영역 (image 있을 때만 의미)
  - `confidence: float | None` · image 매칭 임계값 (image 있을 때만 의미)
  - `grayscale: bool | None` · image 매칭 흑백 여부 (image 있을 때만 의미)
  - `prefer: Literal["image", "coord"] | None` · 둘 다 있을 때 우선순위. default = `"image"` (정합성 우선)
  - `wait_for: WaitFor | None` · **pre-click 가드** — 클릭 직전에 이 image가 보일 때까지 대기 (구 `trigger_wait` 대체)
  - `verify_transition: bool` (default `False`) · post-click 픽셀 diff
  - `transition_threshold: float | None`
  - `post_click_signal: PostClickSignal | None` · post-click polling
- 문법적으로 image와 coord는 동등한 1급 필드. **fallback chain은 명시적 별 필드가 아니라**, 같은 step에 둘 다 선언되면 자동으로 형성됨 (primary는 `prefer`로 결정, 다른 하나가 fallback). step에 image도 coord도 없으면 schema fail.
- `ClickRecipe` 확장 — `steps: list[Step] | None = None` + `missions: dict[str, MissionTarget] | None = None` 둘 다 허용
- 기존 `MissionTarget` Pydantic 스키마는 그대로 유지 (backwards-compat)
- `model_validator` — 둘 다 None이면 error / 둘 다 있으면 warn + steps 우선 / missions만 있으면 자동 normalize to steps
- `prefer` 기본값 `"image"`, `"coord"` 가능

**`src/coord_smith/missions/names.py`**
- `RELEASED_MISSIONS` 변경: 6 entries — `attach_session`, `prepare_session`, `step_observe`, `step_dispatch`, `step_capture`, `run_completion`
- `ALL_MISSIONS` = `RELEASED_MISSIONS` (modeled 0건)
- 기존 12 mission 중 6개 이름 + modeled 7 mission 이름 + `benchmark_validation` deletion

**`src/coord_smith/graph/released_call_site.py`**
- 노드 12개 → 6개 재구성 (per-run × 3 + per-step × 3 in loop)
- `for step in recipe.steps:` 루프로 step_observe → step_dispatch → step_capture 직렬 실행
- step 실패 시 fallback (image ↔ coord) 시도, 다 실패하면 typed error + partial artifact, 다음 step 진행 안 함
- evidence priority gate — 각 step_capture 후 호출 (현재는 12 mission 노드 전부 → step_capture 만으로 좁힘)

**`src/coord_smith/adapters/pyautogui_adapter.py`**
- step_dispatch 어댑터 — primary (image or coord) 시도, 실패 시 fallback. priority는 step.prefer로 결정
- step_observe — pre-click screenshot capture, optional sync check
- step_capture — post-click screenshot, transition diff, signal poll 통합
- 기존 fallback ref 매트릭스 (`_FALLBACK_REFS`) — step-level로 좁혀짐

**`src/coord_smith/graph/runtime_graph.py`**
- LangGraph state machine 재정의 — step list 위 loop 표현
- StateModel에 `current_step_idx` / `step_results` 추가

**`src/coord_smith/graph/pyautogui_cli_entrypoint.py`**
- recipe parsing — multi-step / 단일-step 둘 다 핸들
- artifact path — `artifacts/runs/<run_id>/steps/<idx>-<name>/...`

**`docs/recipe-guide.md`**
- Step DSL 전체 문서화
- 단일-step → multi-step 마이그레이션 1줄 노트
- image-first default + `prefer: coord` override 설명
- 5-step 티켓팅 예제 추가

**`docs/recipes/`**
- 기존 3개 (coord-click, image-click, image-click-with-signal) → 단일-step 예제로 보존
- 신규 추가: `multi-step-flow.yaml` (3-step happy path 예제)
- 신규 추가: `multi-step-with-fallback.yaml` (image primary + coord fallback 예제)

**`docs/prd.md`** §Non-Goals
- *"Stateful long-running session — permanently out of scope"* 추가
- *"Modeled missions beyond runCompletion — permanently out of scope (release_gate_evaluation 등 7개 영구 삭제됨)"* 추가

**`tests/`**
- `tests/unit/test_step_dsl.py` — Step Pydantic validation
- `tests/unit/test_recipe_normalization.py` — missions ↔ steps 변환
- `tests/unit/test_step_fallback_chain.py` — primary 실패 → fallback → 다 실패
- `tests/unit/test_simplified_mission_graph.py` — 새 6-mission graph 구조
- `tests/e2e/test_multi_step_happy.py` — 3-step 시퀀스 happy path
- `tests/e2e/test_multi_step_partial_failure.py` — 2번째 step 실패 시 부분 artifact
- `tests/e2e/test_backwards_compat_single_step.py` — 기존 missions: dict recipe 회귀
- 모델드 7 mission 관련 테스트 (`test_modeled_mcp_*` 등)는 이미 삭제되었으므로 추가 작업 없음
- 12-mission 가정 깨지는 기존 테스트들 — 6-mission 가정으로 재작성

### 4.2 Migration Plan

이 PRD는 **single PR로 처리한다** (production-hardening PRD와 같은 방식). 단계 분할:

1. recipe schema 확장 + 단일-step 회귀 테스트 통과 (multi-step 미구현 상태)
2. mission graph 재설계 + 새 mission 이름 등록 + 기존 테스트 재작성
3. modeled 7 mission 코드/테스트 삭제
4. multi-step 어댑터 구현 + step fallback chain
5. evidence priority gate 재배치
6. e2e 테스트 추가
7. 문서 업데이트 (recipe-guide / prd.md / recipes/)

---

## 6. Test Criteria

다음이 모두 통과해야 "done"으로 간주한다:

- [ ] `uv run pytest -q` — 기존 721 → 새 카운트 (대략 720±10 범위 추정 — 12 mission 가정 테스트 재작성 + multi-step 신규)
- [ ] `uv run ruff check .` — clean
- [ ] `uv run mypy` — strict clean
- [ ] `find src/ tests/ -name "*release_gate*" -o -name "*retry_or_stop*" -o -name "*work_rag*" -o -name "*lesson_promotion*" -o -name "*e2e_replay*" -o -name "*python_validation*" -o -name "*benchmark_validation*"` 결과 0건 (modeled 7 + benchmark_validation 영구 삭제 검증)
- [ ] `grep -rn "benchmark_validation" src/ tests/` 결과 0건
- [ ] `RELEASED_MISSIONS` 길이 == 6
- [ ] 단일-step recipe (`missions: { click_dispatch: {...} }`) — 그대로 동작 + deprecation warning 1회 출력
- [ ] 3-step recipe — 한 invocation에서 직렬 실행 + 각 step별 artifact subdirectory 생성
- [ ] 2번째 step image 매칭 실패 + coord fallback도 실패 → typed error + 첫 step artifact 보존 + exit code != 0
- [ ] step DSL의 `prefer: coord` — coord 먼저 시도, 실패 시 image
- [ ] `prefer` 미지정 — image 먼저 (default)
- [ ] evidence priority gate — 각 step_capture 후 호출 검증 (test 추가)
- [ ] recipe-guide.md의 multi-step 예제 — schema 검증 통과
- [ ] backwards-compat: 기존 `docs/recipes/coord-click.yaml` / `image-click.yaml` / `image-click-with-signal.yaml` 모두 그대로 동작

---

## 7. Guardrails

### Project Guardrails (soft — warn on violation)

- Step DSL에서 image도 coord도 없으면 schema 검증 fail (no-click step은 wait-only step으로 별도 표현 — 후속 PRD)
- 단일 step에서 `prefer` 가 명시됐는데 그 값에 해당하는 필드가 없으면 schema fail
- step 이름은 unique — 같은 recipe 안에 중복 step.name 금지

### System Invariants (hard — never violate)

- LLM-free 런타임 — 변경 후에도 model 호출 0건
- 브라우저 내부 금지 — Playwright / CDP / Chromium 도입 0건
- `pyautogui.FAILSAFE = True` — 어댑터 init에서 강제 유지
- 단일 진입 / 단일 종료 — coord-smith는 한 invocation에 한 번 실행되고 exit (stateful session 영구 out)
- modeled scaffold 부활 금지 — 새 PRD 없이 ALL_MISSIONS == RELEASED_MISSIONS 위반 금지

### Test Strategy

- 기존 12-mission 가정 테스트 — 6-mission 가정으로 재작성 (가정만 바뀌고 의도는 유지)
- 단일-step recipe 회귀 — backwards-compat 안전망
- Multi-step happy + partial-fail — 새 핵심 기능 검증
- evidence priority gate per-step — invariant 유지 검증

---

## 8. Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| 12-mission 가정에 의존하는 테스트가 많아 재작성 비용 큼 | 단일 PR 안에서 mechanical rename + 가정 업데이트. 회귀 검증은 단일-step recipe 테스트가 안전망. |
| modeled 7 mission 삭제로 외부 의존성 깨질 수 있음 | grep으로 외부 import 확인 (MCP 스캐폴드 제거 시와 동일 방식). 외부 import 0건이면 안전. |
| step 사이 settle/wait 타이밍이 머신마다 다름 | 각 step의 `wait_for` / `verify_transition` / `post_click_signal` 옵션으로 명시적 표현 — 암묵적 sleep 의존 안 함. |
| recipe 작성자가 image와 coord 둘 다 채워놓고 fallback 의도 잊음 | recipe-guide.md에 "fallback은 명시적 의도"임을 강조 + `prefer` 필드 활용 예제 |
| backwards-compat normalization 버그 | 기존 3개 docs/recipes/* 그대로 통과시키는 회귀 테스트 + deprecation warning은 stderr only (stdout 영향 없음) |

---

## 9. Success Definition

이 PRD가 끝났을 때:

1. **5-step 티켓팅 recipe**가 한 번의 `coord-smith --click-recipe flow.yaml` 호출로 buy → seat-1 → seat-2(fallback) → confirm → pay 까지 자동 실행되어 한 트리의 evidence를 남긴다.
2. **단일-step 사용자**는 어떤 변경도 인지하지 못한다 (recipe 그대로 동작, deprecation warning만 1줄).
3. **graph가 깔끔하다** — 6 mission node, modeled 0건. `find . -name "*mission*" -type f` 결과가 한눈에 들어오는 수준.
4. **invariant** 5개 모두 유지 (LLM-free / 브라우저 금지 / FAILSAFE / 단일 진입 / 모델드 영구 out).
5. **다음 PRD가 자연스럽게 쌓인다** — DPI 정규화는 step의 `coord`에 reference resolution 추가하는 형태로, retry는 step의 `retry: {...}` 필드로, OpenClaw skill은 multi-step recipe 작성 helper로.

---

## 10. References

- Decision brief: [`docs/decisions/2026-05-flow-architecture-brief.html`](decisions/2026-05-flow-architecture-brief.html)
- Prior PRD (precedent for permanent removal): [`docs/history/prd-remove-mcp-scaffold.md`](history/prd-remove-mcp-scaffold.md)
- Project boundaries: [`docs/architecture-boundaries.md`](architecture-boundaries.md)
- Current invariants: [`docs/prd.md`](prd.md)

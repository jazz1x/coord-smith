# coord-smith PRD (제품 요구사항 정의서)

> **문서 지위 (Document Status)**
> 이 문서는 coord-smith의 **불변 시스템 진실(invariant system truth)** 을 정의한다.
> 구현 진행 상황·현재 단계 해석·즉시 후속 작업은 [`docs/current-state.md`](current-state.md)에 속한다.
> 기능 단위의 상세 계약(필드·인자·반환값)은 [`docs/functional-spec.md`](functional-spec.md)에 속한다.
> 본 문서와 다른 문서가 충돌하면 **본 PRD가 우선**한다. 단, 소스 코드(`src/coord_smith/`)는 런타임 계약의 최종 권위다.

---

## 1. 한 줄 정의 (BLUF)

**coord-smith는 "클릭 규칙(recipe)을 받아 OS 레벨에서 결정론적으로 실행하고, 그 결과를 타입화된 증거(typed evidence)로 반환하는 오케스트레이터"다.**

coord-smith는 *손(hands)* 이다. *머리(head)* — OpenClaw 같은 외부 LLM — 가 "무엇을 클릭할지" 결정하고, coord-smith는 그 결정을 OS 좌표 클릭과 스크린샷 증거로 집행한다. 추론은 런타임 바깥에 산다. 런타임 그 자체에는 LLM 호출이 0개다.

---

## 2. 배경과 문제 정의 (Why)

자율 에이전트가 브라우저/데스크톱 UI를 조작할 때, "추론(무엇을 누를지)"과 "집행(실제로 누르기)"이 한 프로세스에 뒤섞이면 세 가지가 깨진다.

첫째, **검증 가능성**이다. LLM이 클릭 위치를 즉석에서 정하고 곧바로 누르면, 그 클릭이 옳았는지 사후에 타입화된 증거로 증명할 길이 없다. 둘째, **재현성**이다. 런타임에 모델 추론이 끼어들면 같은 입력이 같은 행동을 보장하지 못한다. 셋째, **경계(boundary)** 다. 브라우저 내부(DOM·CDP·Playwright)에 손을 대기 시작하면 "OS 좌표만 만진다"는 단순함이 무너지고, 탐지 회피 같은 위험한 영역으로 미끄러진다.

coord-smith는 이 셋을 **집행 계층을 추론에서 물리적으로 분리**하여 해결한다. 추론은 OpenClaw가, 집행·검증·정지는 coord-smith가 소유한다. 둘은 디스크 위 아티팩트로만 연결된 독립 프로세스이며, 어느 쪽도 다른 쪽을 건드리지 않고 교체 가능하다.

---

## 3. 목표 / 비목표 (Goals / Non-Goals)

### 3.1 목표 (In Scope)

coord-smith가 책임지는 것:

- **미션 그래프 순회** — LangGraph 기반 결정론적 상태 전이
- **클릭 규칙 실행** — pyautogui를 통한 OS 좌표 클릭·스크린샷
- **증거 수집·검증** — 액션로그(JSONL)·스크린샷·전이 diff를 타입화하여 디스크에 봉인
- **릴리스 경계 강제** — `runCompletion` 이하에서만 동작하고 그 위로는 진행하지 않음
- **런(run) 간 비교가능성·검증가능성 보존**

### 3.2 비목표 — 가벼운 변경 금지 (Forbidden Directions)

다음은 **새 PRD가 명시적으로 이 결정을 대체하지 않는 한 영구히 범위 밖**이다.

| 금지 사항 | 이유 |
|-----------|------|
| coord-smith가 브라우저-facing이 되는 것 | 집행/추론 분리 붕괴 |
| OpenClaw를 대체하는 것 | 역할 경계 위반 |
| Playwright / CDP / Chromium 직접 제어를 제품 아키텍처로 채택 | ADR-001 위반 |
| `runCompletion` 위로 릴리스 경계 확장 (PRD 변경 없이) | 릴리스 경계 무력화 |
| 모델링된(modeled) 동작을 릴리스된 동작으로 표현 | 정직성 계약 위반 |
| 활성 런타임 경로에서 TypeScript 부활 | 정본 스택은 Python-only |
| Bun-first 정본 런타임/검증 방향 | 동일 |
| **MCP 전송(transport) 채택** | OpenClaw↔coord-smith 전송은 CLI 서브프로세스 호출이 정본. 과거 `mcp_stdio` 스캐폴드는 제거됨 |
| **상태 보존 장기 실행 세션(stateful daemon)** | coord-smith는 호출→`runCompletion`→종료. stdin/socket으로 클릭을 한 개씩 받는 영속 프로세스는 없음. 다단계 흐름은 단일 호출 안의 선언적 step 리스트로 표현 |
| **`runCompletion` 위 모델링 미션 부활** | `release_gate_evaluation`·`retry_or_stop_decision`·`work_rag_*`·`lesson_promotion`·`e2e_replay_or_comparison`·`python_validation_execution`·`benchmark_validation`는 제거됨. `ALL_MISSIONS == RELEASED_MISSIONS` |
| **레거시 12-미션 per-run 그래프 부활** | 평탄 시퀀스는 per-step 블록(`step_observe → step_dispatch → step_capture`)으로 접힘. `trigger_wait`는 `Step.wait_for`로 흡수됨 |

---

## 4. 시스템 경계 (System Boundary)

### 4.1 액터 정의

```
caller:  OpenClaw      # 외부 AI 추론 레이어. coord-smith를 호출하는 쪽.
runtime: coord-smith   # Python 오케스트레이션 런타임. 집행·검증·정지.
engine:  PyAutoGUI     # OS 레벨 CUA 엔진. click(x,y) + screenshot().
```

### 4.2 권위 경계 (Authority Boundary)

| 책임 | 소유자 |
|------|--------|
| 작업 선택, 상위 워크플로, "무엇을 클릭할지" 판단 | **OpenClaw** |
| 미션 그래프 순회, 증거 검증, 정지 결정, OS 클릭 집행 | **coord-smith** |
| `click(x, y)` · `screenshot()` 물리 실행 | **PyAutoGUI** (coord-smith 내부) |

핵심 사실(Key Facts):

- **OpenClaw가 coord-smith를 호출한다. 역방향은 없다.**
- OpenClaw에는 MCP 서버가 없다. skill 기반 CLI 실행으로 coord-smith를 부른다.
- coord-smith가 CUA 엔진을 소유한다. PyAutoGUI는 coord-smith 내부에서 돈다.
- 통신은 핑퐁(ping-pong): OpenClaw가 CLI 호출 → coord-smith가 stdout·`artifacts/`에 결과 기록 → OpenClaw가 읽고 다음 행동 결정.

### 4.3 런타임 추론 경계 (Runtime Inference Boundary)

- coord-smith 런타임은 **실행 시점에 어떤 LLM 추론도 호출하지 않는다.**
- 그래프 순회·증거 검증·정지 결정은 전부 결정론적 Python이다. 런 도중 모델 호출은 0회.
- `PyAutoGUIAdapter`가 유일한 집행 백엔드다. 좌표 클릭과 스크린샷만. LLM 호출 없음.

> OpenCV는 허용된다 — LLM도 브라우저도 아닌, 결정론적 픽셀 매칭 라이브러리이기 때문이다.

---

## 5. 사용자 / 호출자 (Personas)

coord-smith는 사람 최종 사용자를 위한 도구가 아니라 **에이전트/오케스트레이터를 위한 부품**이다.

| 페르소나 | 누구 | coord-smith에 기대하는 것 |
|----------|------|---------------------------|
| **자율 오케스트레이터 (OpenClaw)** | 외부 LLM 추론 레이어 | 인메모리로 생성한 레시피를 넘기면, 결정론적으로 집행하고 단일 `run.json`으로 결과를 돌려주기 |
| **레시피 작성 개발자** | coord-smith를 직접 호출하는 엔지니어 | YAML 레시피로 다단계 클릭 흐름을 선언하고, 실패 시 타입화된 증거로 원인 진단 |
| **CI / 검증 파이프라인** | 자동화 게이트 | `--dry-run`으로 권한 없는 호스트에서도 레시피 스키마를 싸게 검증 |

---

## 6. 입력 계약 (Input Contract)

### 6.1 필수 입력 (Required)

모든 dispatch 호출은 다음 네 값을 요구한다. 누락 시 **exit 3 (config error)**.

| 입력 | 의미 |
|------|------|
| `session_ref` | 세션 식별자 |
| `expected_auth_state` | 인증 선행 조건 |
| `target_page_url` | 액션이 일어날 페이지 URL |
| `site_identity` | 사이트 식별자 |

### 6.2 클릭 규칙 (Click Rule — 선택)

레시피가 없으면 클릭 없이 통과(no-click smoke target)한다. 레시피 소스와 우선순위:

```
priority: --recipe-json > --recipe-yaml > --recipe-stdin > --click-recipe > COORDSMITH_CLICK_RECIPE
format:   YAML (.yaml/.yml) 또는 JSON — 둘 다 런타임 파싱. YAML 권장.
```

### 6.3 좌표 우선순위 (Coordinate Priority — 고정 불변)

```
payload(OpenClaw)  >  step.coord  >  step.image  >  no-click
```

이 순서는 글로벌과 step 내부에서 동일하며 **절대 역전되지 않는다** (ADR-003). 한 step에 image와 coord를 모두 선언하고 `prefer: image`(기본)로 두면, image 매칭 실패 시 자동으로 coord로 fallback한다.

---

## 7. 릴리스 경계 (Release Boundary)

### 7.1 현재 릴리스 천장 (Released Ceiling)

```
runCompletion
```

### 7.2 릴리스된 6개 미션

per-run 3개가 per-step 블록을 감싼다. N-step 레시피에서 per-step 트리오는 N회 반복되고, `steps: []`(N=0)이면 per-step 블록은 생략된다(smoke target).

| Mission | Phase | Role |
|---------|-------|------|
| `attach_session` | per-run | 세션-ref로 기존 브라우저 세션에 attach |
| `prepare_session` | per-run | 기대 인증 상태·타깃 페이지 URL 검증 |
| `step_observe` | per-step | step의 클릭 전 화면 상태 캡처 |
| `step_dispatch` | per-step | step의 클릭 집행 (image-or-coord, prefer/fallback) |
| `step_capture` | per-step | 클릭 후 증거 캡처 (스크린샷·전이 diff·선택적 signal) |
| `run_completion` | per-run | 봉인된 상태 코드로 런 종료 |

`RELEASED_MISSIONS == ALL_MISSIONS`. 모델링-only 미션은 없다. 모든 단계가 릴리스되어 있다.

### 7.3 per-step 블록에 묶인 릴리스 런타임 기능

- **다단계 레시피 DSL** — `ClickRecipe.steps: list[Step]`가 순서 있는 클릭 시퀀스를 선언. 레거시 `missions: {name: target}`는 1-step 레시피로 자동 정규화되며 `DeprecationWarning`을 emit.
- **image-or-coord 타깃** — step당 image/coord 선언, `prefer`로 우선순위 전환, 둘 다 선언 시 암묵 fallback 체인.
- **pre-click `wait_for` 가드** — anchor 이미지가 나타날 때까지 `locateCenterOnScreen` 폴링(선택적 `region`으로 범위 한정). `trigger_wait` 미션의 후속.
- **post-click 검증** — `verify_transition`(PIL.ImageChops diff), `post_click_signal`(이미지 출현 폴링).
- **per-step `settle_ms`** (기본 300ms) — 전이/커서 검증 전 클릭 후 대기.
- **fail-fast 다단계 계약** — step `k`에서 타입화된 dispatch 실패 시 런 중단. step `k+1..N-1`은 실행 안 됨. `run_completion` 미도달.
- **타입화된 실패 증거** — 모든 타입화된 dispatch 실패는 진단 스크린샷과 구조화된 `failure.jsonl` 레코드를 예외 전파 전에 기록.

### 7.4 릴리스 CLI 표면

- `--click-recipe PATH` / `--recipe-json` / `--recipe-yaml` / `--recipe-stdin` / `COORDSMITH_CLICK_RECIPE` env
- `--target-window NAME` / `COORDSMITH_TARGET_WINDOW` (macOS only; preflight 전 best-effort AppleScript activate)
- `--dry-run` — preflight·클릭 없이 레시피+필수입력 검증. 권한 없는 호스트에서도 실행 가능. **green dry-run이 OS 권한을 보증하지는 않는다.**
- `--recipe-schema` — `ClickRecipe`의 JSON Schema를 stdout으로 emit
- `--cleanup` (+ `--max-runs` / `--max-age-days`) — `artifacts/runs/` 보존 정리. **`run.json`을 쓰지 않는 operator 명령.**
- per-host advisory lock (`fcntl.flock`) — preflight 전 획득. 두 번째 호출은 exit 4 (host busy).
- 모든 종료 경로에서 최상위 `run.json` 요약 기록 (success / failure / interrupted / host_busy).

---

## 8. 출력 계약 (Output Contract)

### 8.1 아티팩트 레이아웃

```
artifacts/runs/<run_id>/
  run.json                                  # 단일 결과 봉투 (caller가 가장 먼저 읽음)
  artifacts/action-log/<key>.jsonl          # 미션별 타입화 액션로그
  artifacts/screenshot/<key>.png            # 단계별 스크린샷
  artifacts/failure/<idx>-<step>-<error>.png # 실패 시 진단 스크린샷
```

### 8.2 Exit Codes

| Code | 의미 |
|------|------|
| `0` | 정상 |
| `1` | 런타임 에러 (typed dispatch failure 또는 `KeyboardInterrupt` — `run.json.status="interrupted"`로 구별) |
| `2` | macOS Accessibility / Screen Recording 권한 없음 |
| `3` | 설정 오류 — 레시피 누락·스키마 오류, 필수 입력 누락, `--cleanup` bound 오류, `--target-window` 활성화 실패, malformed payload coord override |
| `4` | 호스트 잠금 충돌 (다른 coord-smith 프로세스가 lock 보유 — backoff 후 retry) |

> 전체 enumeration은 `docs/functional-spec.md §Exit Codes` 및 `docs/recipe-guide.md §Exit Codes`가 authoritative.

### 8.3 호출자의 결과 읽기 (How callers read a run)

caller(OpenClaw)는 **다른 어떤 아티팩트보다 먼저 `run.json`을 읽어야** 한다.

```
1. run.json 읽기 (runs/<run_id>/run.json 또는 root 미생성 시 base_dir/run.json)
2. run.json.status 분기:
     "success"     → exit 0. 끝.
     "failure"     → run.json.failure로 컴팩트 진단 → failure.jsonl + 매칭 스크린샷
     "interrupted" → SIGINT. 일시적 실패로 취급, 1회 retry 안전.
     "host_busy"   → lock 충돌. 1~5s backoff 후 retry. exit 4.
```

파일의 **존재 유무로 결과를 추론하지 말 것**. `release-ceiling-stop.jsonl`은 성공 시에만 생성되지만, 그 부재가 host_busy인지 권한 실패인지 크래시인지를 유일하게 식별하지 못한다. `run.json`의 `status`+`exit_code`가 단일 진실원이다.

---

## 9. 증거 진실 모델 (Evidence Truth Model)

진실 우선순위(Truth priority):

```
1. dom
2. text
3. clock
4. action-log
```

fallback only: `screenshot`, `vision`
최후 집행 프리미티브 only: `coordinate`

규칙:

- 진실은 vision이나 좌표만으로 도출되어선 안 된다.
- 릴리스 범위 결정에는 타입화된 증거가 필수다.

---

## 10. 릴리스 천장 정지 증명 (Release-Ceiling Stop Proof)

`runCompletion`에서의 정지는 타입화된 액션로그 증거로 증명 가능해야 한다.

- 필수 증거 ref: `evidence://action-log/release-ceiling-stop`
- 기대 아티팩트: `artifacts/action-log/release-ceiling-stop.jsonl`
- 필수 타입 필드: `event`, `mission_name`, `ts`

이 아티팩트를 resolve할 수 없거나 필드가 누락되면, 시스템은 올바른 릴리스 천장 정지를 주장해선 안 된다.

---

## 11. 핵심 불변식 (Invariants)

PR 시점에 강제되는 4개 하드 불변식:

1. **LLM-free 런타임.** coord-smith 내부에 모델 호출 없음. 추론은 OpenClaw에. (ADR-001)
2. **브라우저 내부 금지.** Playwright·CDP·Chromium 드라이버 없음. OS 좌표·픽셀만. (ADR-001)
3. **`pyautogui.FAILSAFE = True`** — `PyAutoGUIAdapter.__init__`에서 강제. 커서를 화면 모서리로 밀면 런 즉시 중단.
4. **좌표 우선순위 고정** — payload → recipe coord → recipe image → no-click. 역방향 절대 불가. (ADR-003)

추가 운영 불변식:

- **per-host advisory lock** — 아티팩트 트리당 coord-smith 호출 1개. (ADR-005)
- **OpenClaw가 coord-smith를 호출**한다. 역방향 아님.

---

## 12. 성공 지표 (Success Metrics)

| 지표 | 목표 |
|------|------|
| 결정론 | 동일 레시피·동일 화면 입력 → 동일 액션로그·동일 exit code |
| 검증가능성 | 모든 dispatch 결과를 단일 `run.json`으로 진단 가능 (다른 파일 grep 불필요) |
| 실패 진단성 | 모든 타입화된 실패가 스크린샷+`failure.jsonl`로 원인 첨부 |
| 경계 무결성 | 런타임 LLM 호출 0회, 브라우저 드라이버 import 0개 (contract test로 강제) |
| 회귀 안전 | `pytest` 452 passing, 4 deselected; ruff·mypy strict clean |

---

## 13. 정본 스택 (Canonical Stack)

정본 구현 경로는 Python-first다.

```
Python 3.14 (pinned, >=3.14,<3.15)
LangGraph / LangChain-core
Pydantic v2
pyautogui + opencv-python + numpy + pyyaml
pytest · ruff · mypy
```

---

## 14. 아키텍처 결정 기록 (ADRs)

런타임 계약이나 caller-facing API를 건드리는 변경 전 반드시 읽을 것:

- [ADR-001 LLM-free 런타임 + 브라우저 내부 금지](../adr/ADR-001-llm-free-runtime-and-browser-ban.md)
- [ADR-002 다단계 레시피 DSL (`steps:` 정본)](../adr/ADR-002-multi-step-recipe-dsl.md)
- [ADR-003 좌표 우선순위](../adr/ADR-003-coordinate-priority.md)
- [ADR-004 실패 증거 정책](../adr/ADR-004-failure-evidence-policy.md)
- [ADR-005 per-host advisory lock](../adr/ADR-005-per-host-advisory-lock.md)
- [ADR-006 `run.json` 봉투 = caller 결과 계약](../adr/ADR-006-run-json-envelope.md)

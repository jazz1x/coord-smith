# coord-smith 기능명세서 (Functional Specification)

> **문서 지위**
> 이 문서는 coord-smith의 **기능 단위 상세 계약** — CLI 인자, Python API, 레시피 스키마, 미션 그래프, 증거 포맷, 에러·exit code — 을 정의한다.
> 불변 시스템 진실은 [`docs/prd.md`](prd.md)에, 구현 스냅샷은 [`docs/current-state.md`](current-state.md)에 속한다.
> 충돌 시 PRD가 우선하고, 런타임 계약의 최종 권위는 소스 코드(`src/coord_smith/`)다.
> 식별자·필드명·스키마·코드는 영어 원문을 유지한다.

---

## FS-0. 개요 (Overview)

coord-smith는 단일 호출(single-invocation) CLI 도구이자 Python 라이브러리다. 한 번 호출되면 LangGraph 상태 기계를 따라 **6개 미션**을 순회하고, 디스크에 타입화된 증거를 남긴 뒤 종료한다. 영속 프로세스도, stdin 스트리밍도 없다.

```
 OpenClaw (외부 LLM)
      │  결정·좌표·이미지 ref
      ▼
 coord-smith CLI ──▶ LangGraph 상태 기계 ──▶ 6 missions
                                        │
                      evidence envelope (JSONL + PNG)
                                        │
                                        ▼
                                  OS (PyAutoGUI)
                                        │
                          OpenCV match / PIL diff 검증
```

---

## FS-1. CLI 인터페이스

### FS-1.1 사용법 (Synopsis)

```
coord-smith [OPTIONS] --session-ref STR --expected-auth-state STR \
            --target-page-url URL --site-identity STR
```

### FS-1.2 필수 인자 (Required)

| Flag | Env | 의미 |
|------|-----|------|
| `--session-ref STR` | `COORDSMITH_SESSION_REF` | 세션 식별자 |
| `--expected-auth-state STR` | `COORDSMITH_EXPECTED_AUTH_STATE` | 기대 인증 상태 |
| `--target-page-url URL` | `COORDSMITH_TARGET_PAGE_URL` | 타깃 페이지 URL |
| `--site-identity STR` | `COORDSMITH_SITE_IDENTITY` | 사이트 식별자 |

넷 중 하나라도 누락되면 **exit 3** (`config error: <message>` stderr 라인 동반).

### FS-1.3 레시피 소스 (Recipe Sources)

| Flag | 의미 |
|------|------|
| `--click-recipe PATH` | YAML/JSON 레시피 파일 (확장자 라우팅; YAML 권장) |
| `--recipe-json TEXT` | 인메모리 JSON 레시피 |
| `--recipe-yaml TEXT` | 인메모리 YAML 레시피 |
| `--recipe-stdin` | stdin에서 YAML/JSON 레시피 읽기 |
| `COORDSMITH_CLICK_RECIPE` (env) | 파일 경로 폴백 |

**우선순위:** `--recipe-json` > `--recipe-yaml` > `--recipe-stdin` > `--click-recipe` > `COORDSMITH_CLICK_RECIPE`.
레시피가 전혀 없으면 클릭 없이 통과(no-click smoke target).

### FS-1.4 동작 플래그 (Behavioral)

| Flag | Env | 의미 |
|------|-----|------|
| `--dry-run` | — | 레시피 + 4개 필수입력만 검증하고 종료. **preflight·클릭 없음.** 권한 없는 호스트에서도 실행 가능 |
| `--target-window NAME` | `COORDSMITH_TARGET_WINDOW` | macOS 앱 이름. preflight 전 one-shot `osascript ... to activate`, ~1s 대기. flag가 env보다 우선 |
| `--json` | — | 런 종료 후 `run.json` 내용을 stdout으로 출력 (파일도 디스크에 기록됨) |
| `--recipe-schema` | — | `ClickRecipe`의 JSON Schema를 stdout으로 emit하고 종료 |
| `--verbose` / `-v` | — | 로그 레벨 DEBUG |
| `--quiet` / `-q` | — | 로그 레벨 WARNING (`-v`가 `-q`보다 우선) |
| `-V` / `--version` | — | 버전 출력 후 종료 |
| `-h` / `--help` | — | 도움말 |

### FS-1.5 Operator 명령 — Cleanup

| Flag | Default | 의미 |
|------|---------|------|
| `--cleanup` | — | `artifacts/runs/`를 보존 한도에 맞게 정리. **`run.json`을 쓰지 않음** (결과는 stderr INFO 한 줄). exit: 0 성공 / 1 부분 삭제 실패 / 4 host busy |
| `--max-runs N` | `100` | 보존할 최대 런 개수 |
| `--max-age-days N` | `14` | 보존할 최대 일수 |

### FS-1.6 알 수 없는 플래그 처리

플래그 모양(`-x` / `--long`)인데 알려진 coord-smith 플래그가 아니면 (예: `--click-recipie` 오타) **조용히 무시하지 않고** exit 3로 거절하며 해당 플래그를 명시한다. `--max-runs=5` 형태의 `flag=value`도 인식한다.

---

## FS-2. 레시피 스키마 (ClickRecipe DSL)

권위 출처: `src/coord_smith/config/click_recipe.py`. 머신리더블 스키마는 `coord-smith --recipe-schema`로 추출.

### FS-2.1 최상위 — `ClickRecipe`

| Field | Type | Default | 비고 |
|-------|------|---------|------|
| `version` | `Literal[1]` | `1` | v1만 존재. `version: 2`는 parse-time 실패 |
| `steps` | `list[Step] \| None` | `None` | **정본(preferred)**. 선언 순서대로 실행 |
| `missions` | `dict[str, MissionTarget]` | `{}` | **deprecated**. 로드 시 1-step씩 정규화 + `DeprecationWarning` |

규칙:
- `extra="forbid"` — 오타 키(예: `confidance:`)는 조용히 버려지지 않고 **parse-time 에러**(exit 3).
- `steps`와 `missions` 둘 다 선언 시 → `steps`가 source of truth, deprecation warning.
- 둘 다 비면(`version:`만) → no-click smoke target (정상).
- step 이름은 레시피 내 **유일**해야 함 (중복 시 액션로그 JSONL 충돌 → parse-time 거절).

### FS-2.2 `Step`

| Field | Type | Default | 의미 |
|-------|------|---------|------|
| `name` | `str` | (required) | step 식별자. 액션로그 파일명에 사용 → path separator·`..`·NUL·예약키 금지 |
| `image` | `str \| None` | `None` | 템플릿 경로 (레시피 파일 기준 상대 해석) |
| `coord` | `StepCoord{x:int,y:int} \| None` | `None` | 고정 픽셀 좌표 |
| `region` | `[left,top,width,height] \| None` | `None` | 이미지 검색 영역 (width/height > 0) |
| `confidence` | `float \| None` (0–1) | `None`→`0.9` | 매칭 임계값 |
| `grayscale` | `bool \| None` | `None`→`false` | 색 무시 |
| `prefer` | `"image" \| "coord" \| None` | 자동 | 둘 다 선언 시 primary 결정 (기본 `image`) |
| `wait_for` | `WaitFor \| None` | `None` | **pre-click** 가드 |
| `verify_transition` | `bool` | `false` | 클릭 후 페이지 전이 검증 |
| `transition_threshold` | `float` (0–1) | `0.01` | 변경 픽셀 비율 임계값 |
| `transition_region` | `[l,t,w,h] \| None` | `None` | 전이 diff 영역 |
| `post_click_signal` | `PostClickSignal \| None` | `None` | **post-click** 이미지 출현 폴링 |
| `settle_ms` | `int` (0–10000) | `300` | 클릭 후 정착 대기 |

검증 규칙:
- `image`와 `coord` 중 **최소 하나** 필수.
- coord-only step에 image-match 필드(`region`/`confidence`/`grayscale`) 선언 시 → "효과 없음" parse-time 거절.
- `prefer`는 실제 채워진 필드를 가리켜야 함.

### FS-2.3 `WaitFor` (pre-click 가드)

| Field | Type | Default |
|-------|------|---------|
| `image` | `str` | (required) |
| `confidence` | `float` (0–1) | `0.9` |
| `timeout` | `float` (>0) | `5.0` |
| `interval` | `float` (>0) | `0.1` |
| `region` | `[l,t,w,h] \| None` | `None` |

`locateCenterOnScreen`로 anchor 이미지가 나타날 때까지 폴링. 성공 시 step 이름 하위에 `wait_for_*` 액션로그 기록. `interval > timeout`이면 거절.

### FS-2.4 `PostClickSignal` (post-click 가드)

`WaitFor`와 동일 필드 구조. 클릭 후 signal 이미지가 나타날 때까지 폴링. 미출현 시 `ImageWaitTimeout`.

### FS-2.5 레시피 예시

좌표 단발:
```yaml
version: 1
steps:
  - name: click-buy
    coord: { x: 800, y: 500 }
```

이미지(권장) + 풀 가드:
```yaml
version: 1
steps:
  - name: confirm-purchase
    wait_for:
      image: templates/confirm-enabled.png
      timeout: 5.0
      interval: 0.1
    image: templates/submit-button.png
    confidence: 0.9
    settle_ms: 300
    verify_transition: true
    transition_threshold: 0.01
    post_click_signal:
      image: templates/success-toast.png
      confidence: 0.85
      timeout: 5.0
```

---

## FS-3. Python API

권위 출처: `src/coord_smith/graph/api.py`, `src/coord_smith/__init__.py`.

```python
import coord_smith
from pathlib import Path

result = await coord_smith.run_click_recipe(
    recipe=Path("./recipe.yaml"),       # Path | str(YAML/JSON) | dict | ClickRecipe
    session_ref="my-session",
    expected_auth_state="authenticated",
    target_page_url="https://example.com",
    site_identity="example",
    dry_run=False,
)
# 동기 래퍼
result = coord_smith.run_click_recipe_sync(...)
```

### FS-3.1 `RunResult` 반환 (dataclass)

| Field | Type | 의미 |
|-------|------|------|
| `status` | `str` | `success` \| `failure` \| `interrupted` \| `host_busy` |
| `exit_code` | `int` | `0`–`4` |
| `run_json_path` | `Path` | 기록된 `run.json` 경로 |
| `step_count` | `int` | 도달한 step 수 |
| `failure` | obj \| `None` | 실패 블록 (성공 시 `None`) |

함수는 레시피·필수입력 검증 → preflight → host lock 획득 → 그래프 실행 → 모든 종료 경로에서 `run.json` 기록을 수행한다.

---

## FS-4. 미션 그래프 (Mission Graph)

권위 출처: `src/coord_smith/graph/langgraph_released_execution.py`, `src/coord_smith/missions/names.py`.

### FS-4.1 토폴로지

레시피마다 그래프가 **정적으로** 빌드된다:

```
per-run setup → N × (step_observe → step_dispatch → step_capture) → run_completion
```

`RELEASED_MISSIONS` (= `ALL_MISSIONS`):

```python
("attach_session", "prepare_session",
 "step_observe", "step_dispatch", "step_capture",
 "run_completion")
```

각 미션은 고정된 과거형 액션키를 emit하여 액션로그가 grep 가능하다:

| Mission | Action key |
|---------|-----------|
| `attach_session` | `attach-session` |
| `prepare_session` | `prepare-session` |
| `step_observe` | `step-observed` |
| `step_dispatch` | `step-dispatched` |
| `step_capture` | `step-captured` |
| `run_completion` | `release-ceiling-stop` |

### FS-4.2 dispatch 좌표 해석 (Coordinate Resolution)

`step_dispatch`는 다음 순서로 클릭 좌표를 해석한다 (ADR-003, 절대 역전 불가):

```
payload(OpenClaw)  >  step.coord  >  step.image (locateCenterOnScreen)  >  no-click
```

한 step에 image+coord 동시 선언 + `prefer: image`(기본) → image 매칭 실패 시 coord로 fallback.

### FS-4.3 fail-fast 다단계 계약

step `k`에서 타입화된 dispatch 실패 발생 시:
- step `k+1..N-1`은 실행되지 않음.
- `run_completion` 미도달 → `release-ceiling-stop.jsonl` 미생성.
- caller는 `release-ceiling-stop.jsonl` 부재로 중단된 런을 (exit code 파싱 없이) 감지 가능.

---

## FS-5. 집행 엔진 (Execution Adapter)

권위 출처: `src/coord_smith/adapters/pyautogui_adapter.py`.

- `ExecutionAdapter` 프로토콜의 유일한 릴리스 구현 = `PyAutoGUIAdapter`.
- `pyautogui.click()` / `pyautogui.screenshot()` 만 사용. LLM 호출·브라우저 드라이버 없음.
- `__init__`에서 `pyautogui.FAILSAFE = True` 강제.
- 이미지 매칭은 OpenCV(via pyautogui), `confidence` 임계값 enforce.
- 템플릿 존재 검사: 어댑터 경계에서 `_assert_template_exists`로 defense-in-depth.

### FS-5.1 페이지 전이 검증 (`verify_transition`)

pre-click 스크린샷 → 클릭 → `settle_ms` 대기 → post-click 스크린샷 → **변경된 픽셀 수 / 영역 면적** > `transition_threshold` ⇒ pass. 미만이면 `PageTransitionNotDetected`.

> 메트릭은 diff의 **bounding-box 면적이 아니라 실제 변경 픽셀 수**다. 커서 깜빡임 + 포커스 링 같은 산발적 미세 변화는 거대한 bbox를 만들지만 픽셀은 거의 안 바꾸므로, bbox-area 방식이면 전이를 거짓 보고한다. (`adapters/page_transition.py`)

### FS-5.2 `settle_ms` 가이드

| UI class | 권장 `settle_ms` |
|----------|------------------|
| 동기적으로 상태 전환하는 네이티브 위젯 (토글·색 전환) | `0`–`50` |
| 표준 웹 페이지 (기본 React 렌더 사이클) | `300` (기본) |
| 애니메이션/가상화 리스트가 많은 헤비 SPA | `500`–`1000` |

---

## FS-6. 증거 봉투 (Evidence Envelope)

### FS-6.1 아티팩트 레이아웃

```
artifacts/runs/<run_id>/
  run.json
  artifacts/action-log/<key>.jsonl
  artifacts/screenshot/<key>.png
  artifacts/failure/<idx>-<step>-<error>.png   # 실패 시
  artifacts/action-log/failure.jsonl           # 실패 시
```

### FS-6.2 `run.json` 스키마 (ADR-006)

모든 **dispatch** 호출은 정확히 하나의 `run.json`을 쓴다 (`--cleanup`은 예외 — 쓰지 않음).

```jsonc
{
  "schema_version": 1,
  "run_id": "20260518-123045-...",
  "status": "success",        // success | failure | interrupted | host_busy
  "exit_code": 0,             // 0 success · 1 runtime · 2 perms · 3 recipe · 4 host busy
  "started_at": "...",
  "ended_at": "...",
  "elapsed_seconds": 1.2345,
  "step_count": 3,            // 도달한 step 수 (성공=레시피 길이, 중도 실패=더 적음)
  "failure": null             // 실패 시 컴팩트 블록
}
```

실패 시 `failure` 블록은 `step_idx`, `step_name`, `phase`(`pre_click`/`dispatch`/`post_click`), `error_class`, `screenshot` 경로, `failure.jsonl` 포인터를 담는다. (`failure`는 JSON 필드이지 별도 파일이 아님.)

### FS-6.3 릴리스 천장 정지 증거

`release-ceiling-stop.jsonl` 필수 타입 필드: `event`, `mission_name`, `ts`. 성공 시에만 생성.

---

## FS-7. 에러 계층과 Exit Codes

권위 출처: `src/coord_smith/models/errors.py`.

### FS-7.1 타입화된 예외 계층

```
AppError
├── ConfigError                      → exit 3
├── ValidationError
├── FlowError
└── ExecutionTransportError          → exit 1 (권한 계열 제외)
    ├── AccessibilityPermissionDenied    → exit 2
    ├── ScreenCapturePermissionDenied    → exit 2
    ├── ScreenCaptureUnavailable
    ├── ClickExecutionUnverified
    ├── ClickCoordinatesOutOfBounds
    ├── ImageTemplateNotFound
    ├── ImageMatchConfidenceLow
    ├── ImageWaitTimeout
    └── PageTransitionNotDetected
```

### FS-7.2 dispatch 실패 → 증거

다음 타입화된 dispatch 실패는 예외 전파 전에 스크린샷(`failure/<idx>-<step>-<error>.png`)과 `failure.jsonl` 레코드를 기록한다:

`ImageMatchConfidenceLow` · `ClickCoordinatesOutOfBounds` · `ClickExecutionUnverified` · `PageTransitionNotDetected` · `ImageWaitTimeout` · `ImageTemplateNotFound`

### FS-7.3 Exit Code 매핑

| Code | Status | 트리거 |
|------|--------|--------|
| `0` | success | 정상 |
| `1` | failure / interrupted | 비권한 `ExecutionTransportError` (image match·transition·click verify 등) 또는 `KeyboardInterrupt`(=`interrupted`) |
| `2` | failure | `AccessibilityPermissionDenied` / `ScreenCapturePermissionDenied` (preflight) |
| `3` | — | 레시피 로드/스키마 오류, 필수 입력 누락, `--cleanup` bound 오류, `--target-window` 활성화 실패, malformed payload coord override |
| `4` | host_busy | 다른 coord-smith 프로세스가 advisory lock 보유 (10s 내 미획득) |

---

## FS-8. 동시성·호스트 배타성 (Host Exclusivity)

권위 출처: `src/coord_smith/graph/host_lock.py`, ADR-005.

- PyAutoGUI는 호스트당 프로세스-전역(커서 1개·화면 1개)이므로 동시 실행은 금지.
- `base_dir/artifacts/.coord-smith.lock`에 `fcntl.flock` advisory lock을 preflight 전 획득, `_run` 끝에서 해제.
- 10초 내 획득 실패 시 `HostBusyError` → **exit 4**. caller는 backoff-and-retry 신호로 해석.
- lock은 `base_dir` 단위. 서로 다른 워크스페이스 트리는 병렬 가능하나, 여전히 호스트 커서/화면을 공유하므로 물리적 격리(세션별 별도 Mac mini 등)가 동반될 때만 의미 있음.

### FS-8.1 Caller 책임 (OpenClaw)

1. **타깃 윈도우를 호출 전 foreground로 활성화** (macOS: `osascript ... to activate`). 활성화 적용 여부를 smoke 스크린샷으로 검증.
2. 런 동안 타깃 윈도우를 foreground로 유지. coord-smith는 포커스를 중재하지 않음.
3. 다단계 레시피의 호출 길이를 고려 (4-step ≈ 1–2초). 포커스 탈취가 잦으면 single-step 호출로 쪼개고 사이에 재활성화.
4. 템플릿은 **프로덕션 호스트에서 새로 크롭**. headless 렌더에서 크롭한 템플릿은 실제 Chrome 렌더(폰트 힌팅·서브픽셀 AA·OS 렌더링 차이)와 매칭 실패하기 쉬움.
5. coord-smith 호출을 호스트에서 직렬화. exit 4는 작업 실패가 아니라 backoff-retry 신호. lock 파일을 우회 삭제하지 말 것.

---

## FS-9. 닮은 템플릿 모호성 해소 (Disambiguation)

기본 `confidence: 0.9`에서 타깃이 다른 화면 요소와 시각적으로 닮으면 매칭이 실패한다 (단일 숫자 날짜 셀, 반복 형태 리스트 행 등). 강도순 3패턴:

1. **Region 제한** — `region: [x,y,w,h]`로 검색을 알려진 부분 사각형에 한정. 레이아웃이 안정적일 때 가장 저렴.
2. **넓은 컨텍스트 크롭** — 인접 요소를 템플릿에 포함해 유일한 조합으로 매칭.
3. **caller 계산 좌표** — 고정 셀 크기 그리드(날짜 피커 등)는 caller가 정확 픽셀 좌표를 계산해 coord-only step으로 전달. 이미지 매칭 불필요. 그리드 수식을 알 때 최선.

---

## FS-10. 플랫폼·전제조건 (Platform & Prerequisites)

- **Python 3.14** (pinned, `>=3.14,<3.15`).
- **macOS** — real 클릭에는 Accessibility + Screen Recording 권한 필요. 미부여 시 `preflight()`가 exit 2.
- Linux/Windows preflight 미구현.
- **uv** 패키지 매니저.
- 검증 게이트: `uv run pytest -q` (452 passing, 4 deselected `-m real`), `uv run ruff check .`, `uv run mypy`.

---

## FS-11. 레거시·마이그레이션 노트

- `missions: {name: target}` 형태는 여전히 로드되지만 **deprecated** — 로드 시 `DeprecationWarning` emit + 자동 `steps` 정규화. 신규 레시피는 `steps:` 사용.
- `trigger_wait` 미션은 `Step.wait_for`로 흡수됨.
- `adapters/openclaw/` → `adapters/execution/`로 rename됨 (OpenClaw API 클라이언트가 아니라 coord-smith 내부 집행 프로토콜).
- MCP transport·stateful daemon·모델링 미션 tier는 **영구 제거** (부활은 새 PRD 필요).

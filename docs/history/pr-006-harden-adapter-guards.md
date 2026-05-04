# PR #6 — 어댑터 방어 코드 강화 + preflight 화면 경계 탐지 개선

## 한 줄 요약

> 화면 캡처 결과를 확인하는 코드 4곳 중 3곳이 이상한 값을 받아도 조용히 넘어갔습니다.
> 전부 명시적 에러로 교체하고, 화면 끝에서 커서 권한을 오탐하는 버그도 수정했습니다.

---

## 맥락 (왜 필요했나)

이 시스템의 원칙은 **"실패를 숨기지 않는다"**입니다.

제1원칙으로 분해하면:

| 상황 | 기존 동작 | 문제 |
|------|-----------|------|
| 화면 캡처 결과가 이상한 형태로 돌아옴 (3곳) | 그냥 통과 또는 건너뜀 | 검증이 실제로 안 됐는데 성공처럼 보임 |
| 커서가 화면 오른쪽 끝에 있을 때 | 항상 오른쪽 +10px 이동 시도 | 경계에서 잘려 "권한 없음"으로 오판 |
| optional 파일 목록 | 실제 존재 확인 없이 전부 포함 | 항목이 추가되면 항상 "없음"으로 오보고 |

---

## 무엇을 바꿨나

### 1. 화면 캡처 결과 타입 이상 → 조용한 통과/건너뜀 → **명시적 에러** (3곳)

화면을 캡처하는 함수가 예상치 못한 값을 반환했을 때 각 경로가 다르게 동작했습니다.

| 위치 | 기존 | 변경 |
|------|------|------|
| `execute()` baseline 캡처 | 결과 무시, `baseline_frame`을 None으로 유지 → 전환 검증 통째로 건너뜀 | 예상 밖 타입이면 `ScreenCaptureUnavailable` 발생 |
| `_verify_page_transition()` | 결과 무시하고 함수 종료 → 검증 없이 성공 반환 | 동일하게 `ScreenCaptureUnavailable` 발생 |
| `preflight()` | `None` 또는 빈 이미지만 확인 — 이상한 타입이면 `AttributeError` 전파 | 타입 확인 먼저 → `ScreenCaptureUnavailable` 발생 |

> 실제로 `pyautogui.screenshot()`은 항상 올바른 형태를 반환합니다.
> 하지만 방어 코드가 "조용한 성공"을 허용하면 나중에 진짜 문제가 숨겨집니다.

### 2. preflight 화면 경계 오탐 수정

커서 권한을 확인할 때 항상 오른쪽으로 +10px 이동을 시도했습니다.
화면 오른쪽 끝(예: 1918px / 1920px 화면)에 커서가 있으면
이동이 경계에서 잘려 "권한 없음"으로 잘못 판단했습니다.

```
before: probe_x = start.x + 10                          ← 무조건 우측
after:  probe_delta = 10 if start.x + 10 < screen.width else -10
        probe_x = start.x + probe_delta                 ← 공간 있는 방향으로
```

### 3. `bootstrap_asset_status` 잠재 버그 수정

optional 파일 목록을 "없는 것들"만 필터해야 하는데,
파일 존재 여부 확인 없이 전체 목록을 반환하고 있었습니다.

현재는 목록이 비어 있어 동작 변화가 없지만,
나중에 항목이 추가되면 항상 "전부 없음"으로 오보고하는 버그가 됩니다.

---

## 테스트

| 구분 | 내용 |
|------|------|
| 기존 preflight 테스트 2개 | `pyautogui.size()` mock 추가 (새 OS 호출 반영) |
| 기존 edge-case 테스트 1개 | screenshot mock을 `MagicMock()` → 실제 PIL Image로 교체 (새 타입 확인 통과용) |
| 신규 테스트 1개 | 화면 오른쪽 끝에서 probe 방향이 역전되는지 검증 |
| 신규 테스트 1개 | `preflight()` 비정상 캡처 타입 → `ScreenCaptureUnavailable` 발생 |
| 신규 테스트 1개 | `execute()` baseline 비정상 캡처 타입 → `ScreenCaptureUnavailable` 발생 |
| 신규 테스트 1개 | post-click 비정상 캡처 타입 → `ScreenCaptureUnavailable` 발생 |
| **전체 결과** | **702 passed**, 1 skipped, 4 deselected |

---

## 리뷰 포인트

1. **`pyautogui_adapter.py` 3곳의 타입 확인 통일** — `execute()`, `_verify_page_transition()`, `preflight()` 모두 이제 동일한 패턴으로 이상한 캡처 결과를 거부합니다. 발생하는 예외(`ScreenCaptureUnavailable`)는 `ExecutionTransportError` 하위 타입이며, 그래프 상위에서 올바르게 전파됩니다.

2. **`preflight()` 내 `pyautogui.size()` 추가** — 기존에도 `position()`, `moveTo()`, `screenshot()` OS 호출이 있던 함수입니다. `size()` 실패 시 `Exception`이 `main()`의 핸들러로 잡혀 exit code 2로 종료됩니다.

3. **`bootstrap.py` 수정** — 현재 `OPTIONAL_BOOTSTRAP_ASSETS = ()`이므로 동작 변화 없음. 예방적 수정입니다.

4. **테스트 mock 교체** — `test_preflight_probes_left_near_right_screen_edge` 의 screenshot mock이 `MagicMock()` 이었는데, 새 타입 확인에서 걸립니다. 실제 PIL Image로 교체했습니다.

---

## 변경하지 않은 것

- 12개 미션 실행 순서 (released scope)
- 릴리즈 천장 (`runCompletion`) 로직
- Evidence ref 스키마 및 action-log 기록 방식
- 공개 API / 인터페이스

---

## 검증 체크리스트

- [x] `uv run pytest -q` — **702 passed**, 1 skipped, 4 deselected
- [x] `uv run mypy --strict src/` — no issues (37 source files)
- [x] `uv run ruff check .` — all checks passed
- [x] e2e: released path (mocked display) — 2 passed

---

## ralphi 검증 이력

```
11 findings → 11 fixed (5 rounds)

Round 1:
  [fixed] pyautogui_adapter.py:488 — _verify_page_transition silent return → raise

  [fixed] pyautogui_adapter.py:558 — execute() baseline silent assign → raise

Round 2:
  [fixed] pyautogui_adapter.py:242 — preflight probe_x +10 무조건 → ±10 screen-aware
  [fixed] validation/bootstrap.py:32 — missing_optional 존재 확인 누락

Round 3:
  [fixed] pyautogui_adapter.py:216 — docstring "+10 px" 고정 문구 → 동적 설명
  [fixed] test_pyautogui_adapter.py — preflight 테스트 size mock 추가 + edge-case 신규 테스트

Round 4 (ralphi 재점검):
  [fixed] test_pyautogui_adapter.py — baseline 비정상 타입 → raise 경로 커버리지 누락
  [fixed] test_pyautogui_adapter.py — post-click 비정상 타입 → raise 경로 커버리지 누락
  [fixed] CLAUDE.md / docs/current-state.md — 테스트 수 698 → 701 업데이트

Round 5 (ralphi 재점검 — 일관성 완성):
  [fixed] pyautogui_adapter.py:275 — preflight() isinstance 가드 누락 → 3곳 패턴 통일
  [fixed] test_pyautogui_adapter.py — preflight 비정상 타입 커버리지 누락 → 신규 테스트 추가
  [fixed] test_pyautogui_adapter.py — edge-case test의 MagicMock screenshot → PIL Image 교체
  [fixed] CLAUDE.md / docs/current-state.md — 테스트 수 701 → 702 업데이트

Round 6 (최종 셀프리뷰 — 이상 없음):
  [ok] _capture_screenshot() isinstance 미추가: 의도된 스코프 확인
       (AttributeError 전파 — silent success 아님, 3곳 수정으로 목표 달성)
  [ok] preflight probe-flip 로직 경계 검증: start.x >= screen.width-10 시 probe_x >= 0 보장
  [ok] e2e 2 passed, 702 unit passed, mypy strict clean, ruff clean
  [ok] PR 문서 맥락 손실 없음 — 3개 수정 사항 모두 추적 가능
```

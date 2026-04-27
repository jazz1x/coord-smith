# PRD — Production Hardening (ez-ax)

## §1 Overview

**Problem**: ralphi 감사(2026-04-27)에서 발견된 9개의 미수정 버그·취약점·테스트 품질 결함이 프로덕션 레벨 운용을 저해함. FINAL_STOP 상태(767 tests passing)이나 해당 결함들은 배포 안전성과 유지보수성에 직접 영향을 미침.

**Status**: 완료. 794 tests passing (767 baseline + 27 신규). 후속 ralphi 재검증 5건 추가 수정 완료 (env_patch/mock_click 변수 정리, with_run_root·bool-as-int·atomic-write cleanup 테스트 3건 추가).

**Goal**: 9개 항목을 P1→P2→P3 순서로 수정하여 테스트 베이스라인을 유지하거나 개선하면서 프로덕션 레벨 코드 품질을 달성.

**Non-Goals**: SIGINT 핸들러, URL allowlist/SSRF 보호, CI matrix Python 3.14, 신규 e2e 시나리오.

---

## §2 Design Decisions

**선택: 계층화 직렬 실행 (P1→P2→P3)**

- 현재 `test_execution_wrapper.py`가 `execution.py`의 구버전 에러 메시지를 assert → `execution.py` shim 전환과 테스트 메시지 업데이트가 동일 단계 필요.
- 이 의존관계 해소 후 P2/P3 항목들은 독립적으로 실행 가능.
- **유효성 조건**: execution.py↔test_execution_wrapper.py 의존관계가 존재하는 한 유효. 두 파일이 분리되면 Alternative A(단일 패치)로 전환 가능.

---

## §4 Implementation Spec

### Phase 1 — P1 버그 수정 (3 tasks)

#### Task 1-1: execution.py → client.py re-export shim
- **File**: `src/ez_ax/adapters/execution/execution.py`
- **Change**: 전체 구현을 `client.py` re-export shim으로 교체
  ```python
  """Re-export shim — all symbols delegated to client.py to eliminate drift."""
  from ez_ax.adapters.execution.client import (
      action_log_artifact_path,
      execute_within_scope,
      validate_action_log_artifacts_contain_ref_events,
      validate_action_log_artifacts_have_minimum_schema,
      validate_action_log_evidence_refs_resolvable,
      validate_release_ceiling_stop_action_log,
  )
  __all__ = [...]
  ```
- **Also**: `tests/unit/test_execution_wrapper.py`의 에러 메시지 assert 2개를 `client.py` 기준으로 업데이트:
  - `"Failed to read release ceiling stop action-log artifact"` → `"Failed to read release-ceiling-stop action-log artifact"`

#### Task 1-2: pyautogui.FAILSAFE 명시 설정
- **File**: `src/ez_ax/adapters/pyautogui_adapter.py`
- **Change**: `PyAutoGUIAdapter.__init__` 첫 줄에 추가:
  ```python
  pyautogui.FAILSAFE = True
  ```
- **Test**: 새 단위 테스트 `test_pyautogui_adapter_sets_failsafe_on_init` 추가

#### Task 1-3: released_call_site.py UTC 타임스탬프 통일
- **File**: `src/ez_ax/graph/released_call_site.py`
- **Change**: `ZoneInfo("Asia/Seoul")` → `UTC` (from `datetime import UTC`)
- **Also**: 해당 파일의 `from zoneinfo import ZoneInfo` import 제거 (더 이상 불필요 시)
- **Test**: 기존 테스트 통과 확인; 새 assert `ts.endswith('+00:00') or ts.endswith('Z')` 테스트 추가

---

### Phase 2 — P2 취약점/품질 (4 tasks)

#### Task 2-1: playwright runtime → dev dep 이동
- **File**: `pyproject.toml`
- **Change**: `[project.dependencies]`의 `playwright>=1.50.0` 제거, `[project.optional-dependencies.dev]`에 추가
- **Verify**: `uv sync` 후 `from ez_ax` imports 정상 동작

#### Task 2-2: asyncio_default_fixture_loop_scope 설정
- **File**: `pyproject.toml`
- **Change**: `[tool.pytest.ini_options]`에 추가:
  ```toml
  asyncio_default_fixture_loop_scope = "function"
  ```
- **Expected**: `PytestUnknownMarkWarning` 경고 제거

#### Task 2-3: should_stop_after_cycle 예외 처리 강화
- **File**: `src/ez_ax/rag/autoloop_runner.py`
- **Change**: 현재 `except Exception: return False` →
  ```python
  except (json.JSONDecodeError, KeyError, TypeError):
      return False
  ```
  나머지 예외는 re-raise (무한 루프 방지)
- **Test**: `JSONDecodeError` → False 반환, `OSError` → re-raise 검증 테스트 추가

#### Task 2-4: auto_seed_next_phase 원자적 파일 재작성
- **File**: `src/ez_ax/rag/autoloop_runner.py`
- **Change**: 4개 파일 각각의 `path.write_text(content)` 호출을 temp-file-then-replace 패턴으로 교체:
  ```python
  import tempfile, os
  with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False, suffix='.tmp') as f:
      f.write(content)
  os.replace(f.name, path)
  ```
- **Test**: 기존 파일 재작성 테스트 통과 확인

---

### Phase 3 — P3 테스트 품질 (2 tasks)

#### Task 3-1: e2e 테스트 AsyncMock → MagicMock 교체
- **File**: `tests/e2e/test_released_path_e2e.py`
- **Change**: `pyautogui.click` patch에서 `new_callable=AsyncMock` → `new_callable=MagicMock` (또는 그냥 `patch(...)` 기본값)
- **Also**: `mock_click.assert_called_once()` assertion 추가
- **Also**: 동일 파일 내 `pyautogui.screenshot` mock 패턴 검토

#### Task 3-2: effective_scope_ceiling 미지정 값 경고
- **File**: `src/ez_ax/models/runtime.py`
- **Change**: 알 수 없는 ceiling 값 수신 시 `warnings.warn` 발생:
  ```python
  import warnings
  def effective_scope_ceiling(ceiling: str) -> str:
      if ceiling not in RELEASED_SCOPE_CEILINGS:
          warnings.warn(
              f"Unknown scope ceiling '{ceiling}'; defaulting to 'runCompletion'",
              stacklevel=2,
          )
      return ceiling if ceiling in RELEASED_SCOPE_CEILINGS else "runCompletion"
  ```
- **Test**: 알 수 없는 ceiling 값으로 호출 시 `pytest.warns(UserWarning)` 검증 테스트 추가
- **Constraint**: 기존 테스트(`test_runtime_graph_plan.py:88-102`)가 `"unknownCeiling"` → `"runCompletion"` 동작을 assert — 해당 테스트는 여전히 통과해야 함

---

## §6 Test Criteria

| Task | Command | Pass Condition |
|---|---|---|
| 1-1 | `.venv311/bin/pytest tests/unit/test_execution_wrapper.py -q` | 59 passed (기존 57 + 수정 2) |
| 1-2 | `.venv311/bin/pytest tests/unit/test_pyautogui_adapter.py -q` | 16+ passed (기존 15 + 신규 1) |
| 1-3 | `.venv311/bin/pytest tests/unit/ -q -k "timestamp or call_site or seed"` | 기존 통과 유지 |
| 2-1 | `.venv311/bin/pytest -q --tb=short -m "not real"` | 767+ passed |
| 2-2 | `.venv311/bin/pytest -q --tb=short -m "not real" 2>&1 \| grep -c Warning` | PytestUnknownMarkWarning 0건 |
| 2-3 | `.venv311/bin/pytest tests/unit/ -q -k "should_stop"` | 신규 2개 테스트 pass |
| 2-4 | `.venv311/bin/pytest tests/unit/ -q -k "auto_seed"` | 기존 통과 유지 |
| 3-1 | `.venv311/bin/pytest tests/e2e/ -q --tb=short` | RuntimeWarning 없음, assert_called_once 통과 |
| 3-2 | `.venv311/bin/pytest tests/unit/ -q -k "scope_ceiling"` | UserWarning 발생 확인 |
| **전체** | `.venv311/bin/pytest -q --tb=short -m "not real"` | **794 passed** (767 baseline + 27 신규: 9 hardening 항목 + 후속 ralphi 추적 테스트 18건) |

---

## §7 Guardrails

**Hard (즉시 중단):**
- `released_call_site.py` UTC 변경 시 기존 타임스탬프 파싱 테스트가 실패하면 롤백
- `execution.py` shim 교체 후 `test_execution_wrapper.py`가 import error 발생하면 롤백
- `playwright` 제거 후 `from ez_ax` import 실패하면 rollback

**Soft (경고 후 계속):**
- `autoloop_runner.py` temp-file-replace 패턴이 Windows 경로에서 실패할 수 있음 (macOS/Linux 전용 확인)
- `asyncio_default_fixture_loop_scope` 설정 추가 후 기존 테스트 suite에서 loop scope 충돌 경고 발생 시 `"session"` 또는 `"module"`로 조정

**Invariants (변경 금지):**
- `released_call_site.py` 변경 시 `REQUIRED_BOOTSTRAP_ASSETS` 목록은 건드리지 않음
- `pyproject.toml` 변경 후 `uv.lock` regeneration 없이 커밋 금지 (lock file drift)
- 기존 767 테스트 카운트를 감소시키는 변경 금지

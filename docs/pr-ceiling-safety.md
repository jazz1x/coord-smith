# PR — Scope Ceiling 안전성 + 문서 카운트 동기화

## 한 줄 요약

미션 순서가 바뀌어도 scope ceiling 검사가 틀어지지 않도록 **숫자 대신 미션 이름으로** 검사하게 바꿨고, 테스트 추가(+1)에 맞춰 활성 문서의 테스트 카운트를 모두 동기화했습니다.

## 왜 바꿨나 (Why)

기존 ceiling 검사는 이렇게 생겼습니다.

```python
ceiling_index_map = {
    "prepareSession": 1,       # prepare_session
    "pageReadyObserved": 3,    # page_ready_observation
    "runCompletion": 11,       # run_completion
}
```

여기 숫자 `1, 3, 11`은 `RELEASED_MISSIONS` 튜플 안의 자리(인덱스)입니다. 문제는 한 가지 — **튜플 순서가 바뀌면 같은 숫자가 다른 미션을 가리키게 됩니다.** 더 나쁜 건, 그래도 테스트가 통과해서 잘못된 동작이 조용히 숨는다는 점입니다. 운영에서 가장 찾기 어려운 종류의 버그입니다.

## 무엇이 바뀌었나 (What) — 핵심 변경

숫자 대신 **미션 이름**으로 매핑합니다. 인덱스는 그때그때 `.index()`로 찾습니다.

```python
_CEILING_TERMINAL_MISSION = {
    "prepareSession": "prepare_session",
    "pageReadyObserved": "page_ready_observation",
    "runCompletion": "run_completion",
}
```

미션 이름은 코드베이스 전체에서 안정적인 식별자입니다. 튜플 순서가 어떻게 재배열되든 같은 미션을 가리킵니다.

## 셀프 리뷰에서 발견한 추가 정리

기존 코드에는 "ceiling 이름이 매핑에 없으면 False 반환" 안전 분기가 있었습니다. 그런데 그 위에서 `effective_scope_ceiling()`이 이미 알 수 없는 ceiling을 정상값으로 바꿉니다. 즉 **그 분기는 절대 실행되지 않는 죽은 코드**입니다. CLAUDE.md의 "일어날 수 없는 시나리오에 안전망 두지 말기" 가이드에 따라 제거했습니다.

미래에 두 상수가 어긋나면 `KeyError`로 즉시 터지고, 기존 ceiling 테스트가 곧바로 잡습니다 (조용히 숨지 않음).

## 동작이 정말 같은가 — 회귀 테스트 추가

가장 의미 있는 경계를 못 박는 테스트를 추가했습니다 (`pageReadyObserved` ceiling 기준).

| 미션 | 기대 결과 | 의미 |
|---|---|---|
| `prepare_session` | True | ceiling 이전 |
| `page_ready_observation` | True | ceiling 자체 |
| `sync_observation` | False | ceiling 직후 |
| `run_completion` | False | ceiling 한참 뒤 |

기존 702개 테스트는 단 하나도 깨지지 않음 → **외부에서 본 동작은 동일**.

## 문서 카운트 동기화 (부수 변경)

테스트 1개 추가로 카운트가 702 → 703으로 바뀌었습니다. 활성 문서 4곳을 함께 업데이트:

- `README.md` — 배지와 설치 안내 코멘트
- `README.ko.md` — 한글판 (이미 698로 더 오래된 stale 상태였음 → 703으로 한 번에 정정)
- `CLAUDE.md` — 부트스트랩 기대값
- `docs/current-state.md` — 구현 스냅샷

이미 머지된 PR 문서들(`docs/pr-006-*.md` 등)은 그 시점의 기록이므로 손대지 않았습니다.

## 리뷰 포인트 (이 4개만 봐주세요)

1. **코드 동등성** — `_CEILING_TERMINAL_MISSION`의 세 값(`prepare_session`, `page_ready_observation`, `run_completion`)이 `src/ez_ax/missions/names.py`의 `RELEASED_MISSIONS`에 실제 존재하는지, 기존 인덱스 1·3·11과 같은 위치를 가리키는지.
2. **테스트 충분성** — 새 경계 테스트가 ceiling 검사의 4가지 의미 있는 케이스(이전·자체·직후·이후)를 모두 덮는지.
3. **죽은 분기 제거의 안전성** — 제거한 `if terminal is None: return False`가 정말 도달 불가한지. (`effective_scope_ceiling`이 모든 비정상 입력을 `runCompletion`으로 정규화하는 것을 확인)
4. **문서 정합성** — 활성 문서 4곳 카운트가 모두 `703`으로 일치하는지. historical PR 문서는 frozen record로 두는 정책에 동의하시는지.

## 검증 결과

| 항목 | 결과 |
|---|---|
| `uv run pytest -q` | **703 passed**, 1 skipped, 4 deselected |
| `uv run pytest tests/e2e/ -q` | **2 passed** (mocked-screen E2E) |
| `uv run ruff check .` | All checks passed |
| `uv run mypy` | Success: 37 files |
| `pytest -m real` (실제 커서 사용) | **실행 안 함** — 사용자 라이브 커서를 가로챌 위험. 명시적 승인 시 단일 실행만 권장 |

## 변경 파일 목록

```
README.md                          # 카운트 정정
README.ko.md                       # 카운트 정정
CLAUDE.md                          # 카운트 정정
docs/current-state.md              # 카운트 정정
src/ez_ax/models/runtime.py        # ceiling lookup: 숫자 → 이름, 죽은 분기 제거
tests/unit/test_runtime_state.py   # + 경계 회귀 테스트
docs/pr-ceiling-safety.md          # 이 PR 문서 (구 draft 대체)
```

## 셀프 리뷰 흐름 (3회 반복)

- **1차 — 저자 POV → 리뷰어 POV** : 변경 자체의 안전성·동작 동등성·테스트 갭을 점검. `pageReadyObserved` 경계 테스트 부재와 죽은 분기 제거 필요성 식별 → 적용.
- **2차 — 재점검** : 변경이 자체 완결인지 확인. 추가 수정 없음. E2E (mocked) 통과.
- **3차 — ralphi 자동 점검** : "README가 702인데 새 테스트 추가 후 실제는 703"이라는 최종 inconsistency 발견 + 한글 README와 CLAUDE.md, current-state.md도 stale. 5개 위치 일괄 정정 후 모든 검증 재통과.

## 본질환원 — 이 PR이 정말로 하는 것

> "ceiling 검사가 미션 순서 변경에 흔들리지 않도록 인덱스를 이름으로 바꾸고, 그 변경이 만든 카운트 차이를 활성 문서에 반영했다."

압축 과정에서 잃은 디테일은 `git diff`에서 그대로 확인 가능합니다 — 본 문서는 **왜·무엇·동등성·반복** 4가지 본질을 모두 보존합니다.

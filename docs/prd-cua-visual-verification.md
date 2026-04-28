# PRD — CUA Visual Verification (Image Click + Page Transition Detection)

## §1 Overview

**Status**: 완료. 827 tests passing (794 baseline + 33 신규: image clicking + page transition + wait_for_image + post_click_signal). 4 real-binary tests (3 baseline + image self-locate). opencv-python>=4.10 runtime dep 추가.

**Problem**: 현재 ez-ax 런타임은 좌표 기반 클릭만 지원하며, 클릭 후 검증은 cursor-position만 비교한다. 이는 OS가 커서 이동을 허용했는지(Accessibility 권한)만 검증하고, 실제 페이지 전환·버튼 응답·DOM 변화를 검증하지 못한다. 또한 정적 좌표 recipe는 페이지 레이아웃 변경에 매우 취약하다(픽셀 1개만 어긋나도 잘못된 위치 클릭).

프로덕션 레벨 자동화에 필요한 두 기능이 미구현 상태:

1. **이미지(템플릿) 기반 클릭**: 버튼 이미지를 화면에서 찾아 그 좌표를 클릭. 페이지 레이아웃이 바뀌어도 동작.
2. **시각적 페이지 전환 감지**: 클릭 후 화면이 실제로 변했는지 확인. DOM 접근 없이 스크린샷 비교만으로 deterministic 검증.

**Goal**: PyAutoGUI + OpenCV 기반으로 두 기능을 추가해 실제 production 자동화에서 신뢰성 있게 동작하는 CUA 런타임을 완성한다. PRD 핵심 invariant(LLM-free runtime, OS-coordinate-only, browser-internal 도구 금지)는 유지한다.

**Non-Goals**:
- ML/LLM 기반 vision (CLIP, GPT-V 등 — runtime LLM-free invariant 유지)
- OCR (별도 PRD 영역)
- Video frame analysis / 동영상 비교
- Browser-internal access (Playwright/CDP/Chromium — 명시적 금지)
- 다중 모니터 cross-display 매칭
- Anti-detection 로직

---

## §2 Design Decisions

### Alt A: Pure PIL template matching (no opencv)
- **Pros**: 신규 의존성 0건. 5MB 미만 footprint.
- **Cons**: O(W·H·w·h) 픽셀 비교 → 1920×1080 화면에서 200×100 템플릿 검색 시 ~3-5초. anti-aliasing/sub-pixel rendering에 매우 취약 → confidence threshold 미지원, exact match만 가능 → 실패율 높음.
- **Suitable**: 작은 템플릿 + 픽셀-perfect 환경 (드물다).
- **Reject**: 프로덕션에서 신뢰성 부족.

### Alt B: opencv-python + cv2.matchTemplate
- **Pros**: pyautogui가 이미 `confidence=` 인자로 opencv를 직접 호출. C-optimized FFT 기반 → 100ms 이내 매칭. anti-aliasing/scaling tolerance(`confidence=0.85` 같은 임계값)로 실전 신뢰성 높음.
- **Cons**: 30MB wheel(numpy 포함). ARM/x86 모두 wheel 제공 → 설치 이슈 거의 없음.
- **Suitable**: 프로덕션 자동화에서 표준 선택.

### Alt C: imagehash (perceptual hashing)
- **Pros**: 페이지 전환 감지에 적합. pHash/dHash로 16-byte hash 비교 → 매우 빠름.
- **Cons**: 클릭 좌표 분해(템플릿 찾기)는 부적합. 스크린샷 전체 vs 일부 영역 비교용.
- **Suitable**: 페이지 전환 감지 보조 — region별 hash diff 가능.

### 선택: Alt B (opencv-python) + PIL ImageChops (페이지 전환)

**근거**:
- 이미지 클릭은 pyautogui의 기존 API(`locateCenterOnScreen(image, confidence=)`)를 그대로 사용 — adapter 추가 의존성 0건.
- opencv는 PRD 금지 목록(Playwright/CDP/Chromium)과 무관. CV 라이브러리는 OS-coordinate paradigm과 호환.
- 페이지 전환은 PIL `ImageChops.difference` + bounding box 검사로 충분 (opencv 없이도 가능). 임계값 기반 단순 픽셀 diff %.
- **유효성 조건**: opencv-python wheel이 macOS/Linux/Windows에서 안정적으로 설치 가능한 동안 유효. wheel 부재 시 Alt A로 fallback.

### 차단 결정: opencv를 runtime dep로

playwright는 dev dep으로 옮겼지만 opencv는 runtime dep이어야 함. 이유: 콘솔 스크립트(`ez-ax`) 실행 시 image recipe 사용 가능해야 하고, 이는 dev install 없이도 동작해야 함. PRD invariant("browser-internal forbidden")와 무관 — opencv는 vision lib이지 browser control이 아님.

---

## §4 Implementation Spec

### Phase 1 — Image-based clicking (5 tasks)

#### Task 1-1: pyproject.toml runtime dep 추가
- **File**: `pyproject.toml`
- **Change**: `[project.dependencies]`에 `"opencv-python>=4.10.0"` 추가
- **Verify**: `uv sync` 후 `import cv2` 정상 동작
- **Acceptance**: `.venv311/bin/python -c "import cv2; print(cv2.__version__)"` exit 0

#### Task 1-2: ClickRecipe 스키마 확장 (image variant)
- **File**: `src/ez_ax/config/click_recipe.py`
- **Change**: 기존 `{"x": int, "y": int}` 외 `{"image": str, "confidence": float, "region": [x,y,w,h] | null, "grayscale": bool}` 지원. discriminator: `image` key 존재 여부.
- **Constraints**:
  - `image` path는 recipe 파일 기준 상대경로 또는 절대경로
  - `confidence` 기본 0.9, 범위 0.0–1.0
  - `region` 선택사항 — 검색 영역 제한 (성능 최적화)
  - `grayscale` 기본 False — True 시 흑백 매칭(빠름, 색 무시)
- **Test**: 단위 테스트 — schema 검증, 잘못된 confidence 거부, 상대/절대 경로 정규화

#### Task 1-3: PyAutoGUIAdapter 이미지 좌표 분해
- **File**: `src/ez_ax/adapters/pyautogui_adapter.py`
- **Change**: `_resolve_click_coords` 분기 추가 — image target일 때 `pyautogui.locateCenterOnScreen(path, confidence=, region=, grayscale=)` 호출
- **Errors**:
  - 이미지 파일 부재 → `ImageTemplateNotFound`
  - 매칭 실패(confidence 미달) → `ImageMatchConfidenceLow`
- **Action-log**: 이미지 매칭 시 매칭 좌표 + confidence를 action-log JSONL에 기록
- **Test**: 단위 — fake `locateCenterOnScreen`으로 좌표 반환 검증, 실패 시 typed error

#### Task 1-4: 신규 typed error
- **File**: `src/ez_ax/models/errors.py`
- **Change**: `ImageTemplateNotFound`, `ImageMatchConfidenceLow` 추가 (`ExecutionTransportError` 하위)
- **Test**: 단위 — 예외 hierarchy 검증

#### Task 1-5: 샘플 recipe + integration 테스트
- **File**: `docs/recipes/sample-image-click-recipe.json`, `tests/integration/test_pyautogui_real.py`
- **Change**: 샘플 recipe(스크린샷 일부를 템플릿으로 사용) + `-m real` 통합 테스트 1건. 자기 화면 일부를 캡처해 그 위치를 다시 찾는 self-locate 테스트.
- **Acceptance**: `.venv311/bin/pytest -m real` 4 passed (기존 3 + 신규 1)

---

### Phase 2 — Page transition detection (4 tasks)

#### Task 2-1: PageTransitionVerifier 클래스
- **File**: `src/ez_ax/adapters/page_transition.py` (신규)
- **API**:
  ```python
  class PageTransitionVerifier:
      def capture_baseline(self) -> Image.Image
      def verify_changed(self, baseline: Image.Image, *, threshold: float = 0.01,
                          region: tuple[int,int,int,int] | None = None) -> PageTransitionResult
  ```
- **알고리즘**:
  1. baseline = pre-click screenshot
  2. post = post-click screenshot (`_POST_CLICK_SETTLE_SECONDS` 후)
  3. `PIL.ImageChops.difference(baseline, post).getbbox()` → 변경 영역 bbox
  4. `(bbox 면적 / 전체 면적) > threshold` 면 changed=True
  5. `PageTransitionResult(changed: bool, change_ratio: float, bbox: tuple | None)`
- **Test**: 단위 — 동일 이미지 → not changed, 픽셀 변경 → changed

#### Task 2-2: ClickRecipe에 transition_check 필드
- **File**: `src/ez_ax/config/click_recipe.py`
- **Change**: 미션별 옵션 `{"verify_transition": bool, "transition_threshold": float, "transition_region": [x,y,w,h] | null}` 추가
- **Default**: `verify_transition=False` (기존 동작 유지 — 옵션 사용자가 명시적으로 켤 때만 작동)

#### Task 2-3: PyAutoGUIAdapter 통합
- **File**: `src/ez_ax/adapters/pyautogui_adapter.py`
- **Change**: `execute()` 시 transition_check 활성화 미션의 경우:
  1. 클릭 직전 baseline 캡처
  2. `_verified_click` 후 post 캡처 + `verify_changed()` 호출
  3. 미변경 시 `PageTransitionNotDetected` 예외
- **action-log**: change_ratio, bbox 기록

#### Task 2-4: 신규 typed error + 통합 테스트
- **File**: `src/ez_ax/models/errors.py`, `tests/unit/test_page_transition.py`, `tests/unit/test_pyautogui_adapter.py`
- **Change**: `PageTransitionNotDetected` 추가 + 단위 테스트 (변경/비변경 시나리오)

---

### Phase 3 — Wait-for-image (post-click signal) (3 tasks)

#### Task 3-1: PyAutoGUIAdapter.wait_for_image 메서드
- **File**: `src/ez_ax/adapters/pyautogui_adapter.py`
- **API**: `wait_for_image(path: str, *, timeout: float = 5.0, interval: float = 0.1, confidence: float = 0.9) -> tuple[int,int]`
- **알고리즘**: timeout 내에서 `locateCenterOnScreen` 폴링 → 발견 시 좌표 반환, 미발견 시 `ImageWaitTimeout`
- **action-log**: wait 시작·종료·발견된 좌표 기록
- **Test**: 단위 — fake `locateCenterOnScreen`으로 timeout/success 시나리오

#### Task 3-2: ClickRecipe post_click_signal 필드
- **File**: `src/ez_ax/config/click_recipe.py`
- **Change**: 미션별 `{"post_click_signal": {"image": str, "timeout": float, "confidence": float}}` 추가
- **Default**: 미설정(현재 동작 유지)

#### Task 3-3: PyAutoGUIAdapter 통합 + 신규 error
- **File**: `src/ez_ax/adapters/pyautogui_adapter.py`, `src/ez_ax/models/errors.py`
- **Change**: post_click_signal 설정된 미션은 클릭 후 `wait_for_image` 호출 → 미발견 시 `ImageWaitTimeout`. post_click_signal과 verify_transition은 둘 다 활성화 가능 (verify_transition으로 빠른 체크 + signal로 deterministic 확인).
- **Test**: 단위 통합 테스트

---

## §6 Test Criteria

| Phase | Task | Command | Pass Condition |
|---|---|---|---|
| 1 | 1-1 | `.venv311/bin/python -c "import cv2"` | exit 0, version >= 4.10 |
| 1 | 1-2 | `.venv311/bin/pytest tests/unit/test_click_recipe.py -q` | 신규 image variant 테스트 통과 |
| 1 | 1-3 | `.venv311/bin/pytest tests/unit/test_pyautogui_adapter.py -q` | 신규 image-resolve 테스트 통과 |
| 1 | 1-4 | `.venv311/bin/pytest tests/unit/test_errors.py -q` | typed error hierarchy 검증 통과 |
| 1 | 1-5 | `.venv311/bin/pytest -m real -q` | 4 passed (기존 3 + 신규 1) |
| 2 | 2-1 | `.venv311/bin/pytest tests/unit/test_page_transition.py -q` | 단위 테스트 통과 |
| 2 | 2-2 | `.venv311/bin/pytest tests/unit/test_click_recipe.py -q` | transition 필드 스키마 통과 |
| 2 | 2-3 | `.venv311/bin/pytest tests/unit/test_pyautogui_adapter.py -q` | 통합 테스트 통과 |
| 2 | 2-4 | 위 1·2·3 동일 명령 | typed error 검증 |
| 3 | 3-1 | `.venv311/bin/pytest tests/unit/test_pyautogui_adapter.py -q -k "wait_for_image"` | 신규 테스트 통과 |
| 3 | 3-2 | `.venv311/bin/pytest tests/unit/test_click_recipe.py -q` | post_click_signal 스키마 통과 |
| 3 | 3-3 | 위 동일 | 통합 통과 |
| **전체** | — | `.venv311/bin/pytest -q --tb=short -m "not real"` | **>=815 passed** (794 baseline + ~21 신규) |
| **전체** | — | `.venv311/bin/pytest -q --tb=short -m real` | **4 passed** (기존 3 + 신규 1) |
| **전체** | — | `.venv311/bin/ruff check src/ tests/` | clean |
| **전체** | — | `.venv311/bin/mypy src/ez_ax/` | clean |

---

## §7 Guardrails

### Hard (즉시 중단):
- opencv-python wheel 설치 실패 → Phase 1 중단, 사용자 보고
- `pyautogui.locateCenterOnScreen` 시그니처가 예상과 다르면 중단
- 기존 794 테스트 카운트 감소 시 롤백
- LLM-free runtime invariant 위반 시 즉시 중단 (CV는 LLM 아님 — OK)

### Soft (경고 후 계속):
- opencv 매칭이 30+ 초 걸리는 경우 → grayscale=True 또는 region 제한 권고
- 테스트가 화면 해상도/스케일링에 의존하면 fixture로 격리

### Invariants (변경 금지):
- LLM-free runtime invariant 유지 (CV inference만 사용, LLM/ML 추론 금지)
- Browser-internal 도구(Playwright/CDP/Chromium) 사용 금지
- 좌표 우선순위 유지: payload(OpenClaw) > recipe(coords) > recipe(image) > no-click
- `pyautogui.FAILSAFE = True` 유지
- 기존 `_verified_click` cursor-position verification 제거 금지 — 추가 검증으로 보강

---

## §8 Out-of-Scope (별도 PRD 영역)
- 다중 monitor 좌표 정규화
- ML 기반 element detection (LLM-free invariant 위반)
- OCR (별도 PRD)
- Video frame analysis
- 동적 confidence 자동 조정
- Recipe 자동 생성 (UI 녹화)

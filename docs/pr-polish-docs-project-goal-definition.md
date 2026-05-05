# PR Polish — `docs/project-goal-definition`

## 한줄 요약

ez-ax production hardening: MCP 스캐폴드 영구 제거 · YAML 레시피 지원 · 12 노드 증거 priority 게이트 · async correctness · doc 컨벤션 정리.

## 왜 이 변경이 필요한가 (배경)

ez-ax의 단일 transport은 CLI subprocess (`ez-ax --click-recipe`)이지만, 사용된 적 없는 MCP 스캐폴드 코드가 `src/`에 남아 dead-dependency(`mcp` package)와 의도-구현 혼선을 만들었다.

12개 미션 노드는 evidence priority를 런타임에서 강제하지 않아, 약한 증거(screenshot/coordinate)만 있는 결정도 통과시킬 수 있었다 — PRD가 요구하는 *"typed evidence is required for released-scope decisions"* 가 코드에 없었다.

자율 에이전트(OpenClaw)는 사람-친화적인 YAML로 레시피를 작성하길 원하지만 런타임은 JSON만 파싱했다. 또한 일부 어댑터 메서드가 `async def` 컨텍스트에서 동기 `time.sleep`을 호출해 event loop을 블로킹했다.

활성 docs와 코드 사이에 stale 테스트 카운트, orphan 레시피 샘플, 완료된 PRD의 미아카이브 등 정합성 갭이 누적되어 신규 에이전트의 부트스트랩 신뢰도를 떨어뜨렸다.

## 무엇이 바뀌었나 (변경 요약)

| 영역 | 변경 |
|------|------|
| 코드 — MCP 제거 | [src/ez_ax/config/mcp_stdio.py / mcp_stdio_cli.py](src/ez_ax/config/) 삭제, langchain context 삭제, `mcp` deps 제거 |
| 코드 — YAML 레시피 | [click_recipe.py](src/ez_ax/config/click_recipe.py) `.yaml`/`.yml` 확장자 자동 라우팅, JSON은 backwards-compat |
| 코드 — 증거 게이트 | [evidence/envelope.py](src/ez_ax/evidence/envelope.py)의 `enforce_evidence_priority_gate()` 신설, [released_call_site.py](src/ez_ax/graph/released_call_site.py) 12 노드 전부 적용 |
| 코드 — async 정합 | [pyautogui_adapter.py](src/ez_ax/adapters/pyautogui_adapter.py)의 `_verified_click` / `preflight` / `_await_post_click_signal` / `wait_for_image` 모두 `async` 전환, `time.sleep` → `asyncio.sleep` |
| 코드 — 검증 | [execution/client.py](src/ez_ax/adapters/execution/client.py)의 `ExecutionResult.__post_init__` validation, ghost evidence ref(`evidence://text/fallback-reason`) 12개 미션에서 일괄 제거, `parse_released_evidence_ref` 중복 호출부 통합 |
| 테스트 | [test_agent_acceptance.py](tests/e2e/test_agent_acceptance.py) (172 라인), [test_cli_exit_codes.py](tests/e2e/test_cli_exit_codes.py) (81 라인), [test_released_path_e2e.py](tests/e2e/test_released_path_e2e.py) (56 라인) 신규 |
| 문서 — 에이전트 가이드 | [docs/recipe-guide.md](docs/recipe-guide.md) 266 라인 신설 — 계약·exit code·priority·예제 |
| 문서 — 예제 | [docs/recipes/](docs/recipes/) YAML 매트릭스 정착 (coord, image, image+signal) |
| 문서 — 아카이브 | 완료 PR 2건 + production-hardening PRD + (this polish) MCP 제거 PRD를 [docs/history/](docs/history/)로 이동 |
| 문서 — 정책 | [docs/prd.md](docs/prd.md) §Out of scope에 *"MCP transport adoption — permanently out of scope"* 추가 |
| 문서 — 컨벤션 (this polish) | [CLAUDE.md](CLAUDE.md) / [README.ko.md](README.ko.md) 테스트 카운트 703→721 동기화, orphan JSON 샘플 2건 ([sample-click-recipe.json](docs/recipes/), [sample-image-click-recipe.json](docs/recipes/)) 제거 |

## 리뷰 포인트

- [ ] **MCP 영구 out-of-scope 결정**. [docs/prd.md](docs/prd.md) §Out of scope의 새 항목이 미래 부활을 새 PRD를 요구하는 정책으로 못박는다. 이 강도에 동의하는가?
- [ ] **Evidence priority gate 강화 범위**. released-scope 그래프의 12 노드 전부에서 highest evidence kind가 `screenshot`이나 `coordinate`이면 `FlowError`. 기존 정상 시나리오는 모두 action-log 이상을 생성하도록 어댑터가 보장하지만, 외부 caller가 inject하는 payload 결과가 이 조건을 어길 가능성이 있다 — 호출자 측 계약 가시화가 충분한가?
- [ ] **YAML/JSON dual-format**. `docs/recipes/`는 YAML-only로 통일했지만 `README.md` Quickstart 인라인 예제는 여전히 JSON. 두 형식의 가시성을 의도적으로 보존했으나, 단일 표준으로 좁힐지 결정 필요.
- [ ] **`.gitignore`의 머신별 항목**. `.claude/skills/python-*` 6 항목은 사용자별 인프라로, 글로벌 gitignore 후보. 프로젝트 .gitignore 잔류 결정 의도?
- [ ] **async sleep 마이그레이션**. 4개 어댑터 메서드가 async로 전환 — 호출자 await 처리는 그래프·CLI·테스트 모두 검증 완료(721 pass). 외부에서 직접 어댑터를 사용하는 코드가 있다면 호환성 깨짐.

## 테스트

| 구분 | 결과 |
|------|------|
| `uv run pytest -q` | **721 passed**, 1 skipped, 4 deselected |
| `uv run pytest -m real` | 4 deselected (macOS Accessibility + Screen Recording 권한 필요, 호스트별 실행) |
| `uv run ruff check .` | clean |
| `uv run mypy src` (strict) | clean (33 src files) |

## 영향 범위

| 파일 그룹 | 변경 |
|-----------|------|
| `src/ez_ax/config/` | MCP 모듈 삭제, YAML 레시피 라우팅 |
| `src/ez_ax/adapters/` | langchain/ 삭제, pyautogui_adapter async 전환·중복 제거, execution/client.py validation |
| `src/ez_ax/evidence/` | priority gate 신설 |
| `src/ez_ax/graph/` | 12 노드에 gate 적용, base_dir 와이어링 수정 |
| `tests/e2e/` | 에이전트 수용성·CLI exit code·released path 신규 (3 파일) |
| `tests/unit/` | mcp 테스트 6건 삭제, click_recipe·evidence·adapter 보강 |
| `docs/` | history 아카이브 정착, recipe-guide 신설, recipes YAML 매트릭스, prd MCP out-of-scope, this polish의 컨벤션 정리 |
| `pyproject.toml` | `mcp` 제거, `pyyaml`+`types-PyYAML` 추가, langchain `UserWarning` filter |
| `CLAUDE.md` / `README*` | 테스트 카운트 동기화, 컨벤션 정합 |

## 셀프리뷰 이력

| 회차 | 발견 | 수정 | 회귀 검증 |
|------|------|------|----------|
| 1 | 5건 (CLAUDE.md stale 703, README.ko.md badge·inline stale 703, sample-click-recipe.json orphan, sample-image-click-recipe.json orphan) | 카운트 동기화, JSON 2 파일 삭제 | 721 pass · ruff/mypy clean |
| 2 | 1건 (prd-remove-mcp-scaffold.md 활성 디렉토리 잔류, 작업 완료 검증됨) | docs/history/로 이동 | 721 pass · ruff/mypy clean |
| 3 | 0건 (TODO 0, 미션 카운트 정합 12 released / 19 total, exit code docs 정합) | — | 721 pass · ruff/mypy clean |
| ralphi false-positive | recipe-guide.md image-click-with-signal 누락 | 실제로는 line 266에 이미 참조 — false positive 기록 | — |

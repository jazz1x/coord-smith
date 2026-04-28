# Python 엔지니어링 스킬

> 이 파일은 모든 Python 리포에 공통 적용되는 코드 작성 원칙이다.
> Claude Code의 CLAUDE.md에서 참조하거나, 프로젝트 루트 `.claude/` 디렉토리에 포함시킨다.
> **모든 코드 작성, 리뷰, 리팩토링 시 이 원칙을 준수한다.**
>
> 저장소의 `CLAUDE.md`, PRD, `pyproject.toml`, 검증 계약과 충돌할 경우에는
> 저장소 canonical source가 우선한다.

---

## 핵심 사상

> "Haskell의 수학적 우아함보다, Python의 실용적 명확성을 선택한다."

- 함수형 철학(ADT, ROP, Fail-Fast)을 유지하되 Python 네이티브로 구현한다.
- 별도 함수형 라이브러리(`returns`, `msgspec`, `result`)는 사용하지 않는다.
- 추상화는 구현체가 2개 이상일 때만 도입한다.

---

## 코드 원칙

### SRP — 하나의 함수는 하나의 일만

```python
# ❌
def evaluate_and_update_and_log(obs):
    result = judge(obs)
    self.state = next_state(result)
    log(result)
    return result

# ✅
def evaluate(obs) -> EvalResult: ...     # 판정만
def advance_state(result) -> State: ...  # 전이만
def log_result(result) -> None: ...      # 로깅만
```

위반 신호: 함수 이름에 "and"가 들어간다.

### SSoT — 하나의 정보는 한 곳에서만 정의

```python
# ❌ YAML에도 코드에도 같은 값이 하드코딩
if cp_name == "PDP 로딩":  # 코드에 하드코딩

# ✅ YAML이 유일한 원천
cp_name = config["name"]
```

위반 신호: 같은 문자열이 2곳 이상에 존재한다.

### KISS — 지금 필요한 만큼만

```python
# ❌ 구현체가 1개인데 팩토리 패턴
class EvaluatorFactory:
    def create(self, type: str) -> BaseEvaluator: ...

# ✅
def evaluate_with_rules(config, obs): ...
def evaluate_with_llm(config, obs): ...
```

위반 신호: "이 추상화에 구현체가 1개뿐이다."

### 리니어 패턴 — 위에서 아래로 한 줄로 읽히는 코드

Early Return(가드 클로즈)으로 중첩을 제거한다. 최대 들여쓰기 3단계.

```python
# ❌ 중첩 if
def evaluate(config, obs):
    if obs:
        if not obs.get("error"):
            rules = config.get("rule_checks")
            if rules:
                for rule in rules:
                    if obs.get(rule["field"]) != rule["expect"]:
                        return fail(rule)
                return success()

# ✅ Early Return으로 선형
def evaluate(config, obs):
    if not obs:
        return fail("empty")           # 가드 1

    if obs.get("error"):
        return fail("error")           # 가드 2

    rules = config.get("rule_checks")
    if not rules:
        return pending()               # 가드 3

    for rule in rules:                 # 본 로직
        if obs.get(rule["field"]) != rule["expect"]:
            return fail(rule)

    return success()                   # 정상 경로가 맨 아래
```

자원 관리도 선형으로:

```python
@asynccontextmanager
async def get_session():
    session = await create_session()
    try:
        yield session
    finally:
        await session.close()

async with get_session() as db:
    await db.save(data)
```

### match 기반 리니어 분기

ADT나 상태 분기가 3개 이상이면 `if/elif` 연쇄보다 `match`를 우선한다.
가드 절은 Early Return으로 위에서 정리하고, 핵심 상태 분기는 `match` 한
블록에서 끝내 선형적으로 읽히게 한다.

```python
def handle_result(result: EvalResult) -> Command:
    if result is None:
        raise ValueError("result is required")

    match result:
        case EvalSuccess(checkpoint_id=cp):
            return advance(cp)
        case EvalFailure(failure_reason=reason):
            return stop(reason)
        case EvalPending(evaluation_context=ctx):
            return request_llm(ctx)
```

### Fail-Fast — 실패하면 즉시 멈춘다

```python
# ❌ 에러를 삼킨다
try:
    result = do_work()
except:
    result = None  # 삼킴 → 나중에 원인 모를 버그

# ✅ 즉시 터뜨린다
result = do_work()  # 실패하면 여기서 예외
```

경계(Entry Point)에서 검증, 내부에서는 신뢰:

```python
# 진입점: pydantic으로 엄격 검증
async def entry_point(raw_data: dict):
    validated = InputSchema.model_validate(raw_data)  # 여기서 실패 → 즉시 종료
    await process(validated)

# 내부: 이미 검증됨, 바로 사용
async def internal_node(state):
    data = state['data']  # 검증 안 함
```

### ROP — 예외 계층으로 경로 분리

Python에서는 모나드 대신 커스텀 예외 계층을 사용한다.

```python
class AppError(Exception): pass
class ValidationError(AppError): pass   # 입력 검증 실패
class EvaluationError(AppError): pass   # 판정 오류
class FlowError(AppError): pass         # 상태 오류
class ConfigError(AppError): pass       # 설정 오류
```

LangGraph 상태에 에러 필드를 포함하는 패턴:

```python
class AgentState(TypedDict):
    messages: list
    error: Optional[str]  # 에러 발생 시 기록

async def process_node(state):
    try:
        return {"messages": [result]}
    except CriticalError as e:
        return {"error": str(e)}  # 그래프가 에러 노드로 라우팅
```

### ADT — Pydantic Tagged Union

상태가 3개 이상이고 각 상태마다 데이터가 다르면 Tagged Union을 사용한다.

```python
from pydantic import BaseModel, ConfigDict
from typing import Literal, Union

class EvalSuccess(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["success"] = "success"
    checkpoint_id: str
    observation: dict

class EvalFailure(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["failure"] = "failure"
    checkpoint_id: str
    failure_reason: str

class EvalPending(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["pending"] = "pending"
    checkpoint_id: str
    evaluation_context: dict

EvalResult = Union[EvalSuccess, EvalFailure, EvalPending]
```

Python 3.10+ match로 분기:

```python
match result:
    case EvalSuccess(checkpoint_id=cp):
        advance()
    case EvalFailure(failure_reason=reason):
        stop(reason)
    case EvalPending(evaluation_context=ctx):
        request_llm(ctx)
```

상태가 2개뿐이면 Enum으로 충분. 억지로 ADT를 붙이지 않는다.

---

## 라이브러리 스택

| 분류 | 라이브러리 | 용도 |
|------|-----------|------|
| Orchestration | langgraph | 상태 머신, 그래프 기반 플로우 |
| LLM | langchain-core | langgraph 의존성, 표준 인터페이스 |
| Validation | pydantic v2 | 경계에서 데이터 검증, 직렬화 |
| HTTP | httpx | async HTTP |
| Retry | tenacity | 데코레이터 기반 재시도 |
| Logging | structlog | 구조화 로깅 (JSON) |

사용하지 않는 것: `returns`, `msgspec`, `result`

### pydantic 설정

```python
class OptimizedModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,               # 불변성
        validate_assignment=False,  # 성능
        extra='ignore',            # 불필요 필드 무시
    )
```

내부 상태는 TypedDict (pydantic 오버헤드 제거):

```python
class FlowState(TypedDict):
    current_cp_index: int
    checkpoint_results: list
    error: Optional[str]
```

### structlog 설정

```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(ensure_ascii=False),
    ],
)
logger = structlog.get_logger()

# 사용
logger.info("checkpoint_evaluated", cp="CP1", status="PASS")
logger.warn("llm_fallback", cp="CP3", missing_keys=["option_selected"])
```

### tenacity 패턴

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def call_api(url: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
```

---

## 테스트 원칙

파일당 **최소 20개**. 4개 카테고리 필수:

| 카테고리 | 개수 | 예시 |
|----------|------|------|
| Happy Path | 4~6 | 정상 입력, 다양한 조합 |
| Edge Case | 6~8 | 빈 입력, None, 경계값, 옵셔널 유무 |
| Error Case | 6~8 | 잘못된 타입, 필수 누락, 상태 불일치 |
| Chaos Monkey | 2~4 | 랜덤 키/값, 대량 데이터, 반복 호출 |

테스트 이름은 한글로:

```python
def test_모든_키가_있으면_규칙_판정(self): ...
def test_observation이_None이면_FAIL(self): ...
def test_랜덤_100개_키_observation(self): ...
```

mock 없이 테스트 가능해야 한다 (SRP 지키면 자연스럽게 됨).

---

## 주석 원칙

비즈니스 로직, 판정 규칙, 상태 전이에 **한글 주석**:

```python
# 규칙 기반 판정: 키가 모두 있으면 매칭
for rule in rule_checks:
    if observation.get(rule["field"]) != rule["expect"]:
        return fail  # 불일치 → 즉시 FAIL (fail-fast)
```

public 함수에 **docstring**:

```python
def evaluate_checkpoint(config: dict, obs: dict) -> EvalResult:
    """
    체크포인트를 평가한다.

    Args:
        config: YAML에서 로드한 CP 설정
        obs: openclaw가 수집한 관측 결과

    Returns:
        EvalSuccess | EvalFailure | EvalPending
    """
```

주석을 달지 않는 곳: import문, 단순 getter, 코드 자체가 명확한 곳.

---

## 빌드 & 버저닝

- 시맨틱 버저닝: MAJOR.MINOR.PATCH
- `__version__`을 패키지 `__init__.py`에 정의
- CHANGELOG.md 수동 작성
- 브랜치 클로징 전 문서 업데이트 필수 (README, CHANGELOG, PRD)

---

## 이 스킬의 위치

```
.claude/
├── python-engineering.md   # 이 파일
└── thinking-room.md        # 사색의 방 (선택)
```

또는 `CLAUDE.md`에서 참조:

```markdown
## 코드 원칙
이 프로젝트는 `.claude/python-engineering.md`를 따릅니다.
```

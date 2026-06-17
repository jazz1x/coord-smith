# coord-smith 전략 방향 점검 — 2026-05-29

> 질문: "OpenClaw가 저물고 있는데, 업계 관례·트렌드에 비춰 우리가 나아가야 할
> 방향을 온전히 체크하자."
>
> 방법: 3축 병렬 웹 리서치(head / hands / nerve) → invariant pressure-test.
> 지식 컷오프(2026-01) 이후 4개월은 전부 라이브 검색. 2차 출처는 명시.

---

## 0. TL;DR (한 문단)

coord-smith의 **핵심 베팅 — "추론하는 머리 + 멍청한 손(deterministic executor)"
분리 — 은 niche가 아니라 2026 업계 표준 형태다.** OpenAI·Anthropic·Google이
전부 "모델이 액션을 제안하면 caller의 harness가 실행한다"는 동일한 루프를
공식 문서에 명시한다. 따라서 *특정* 머리(OpenClaw)가 저물어도 coord-smith의
역할은 죽지 않는다 — 머리는 한 제품이 아니라 **표준화된 레이어**이고, 그
레이어가 손을 명시적으로 요구한다. 가장 잘 늙고 있는 부분은 **결정론 +
typed evidence**(audit crisis가 이걸 더 귀하게 만든다)와 **stateless-CLI**
("CLI is the new MCP"). 가장 나쁘게 늙고 있는 부분은 **OpenCV image-template
matching**(VLM grounding·a11y-ref 대비 DPI/해상도에 취약)과 **a11y-tree 전면
금지**(브라우저 한정으로는 2026 hybrid 컨센서스에 역행). 방향: 브라우저
자동화와 경쟁하지 말고 **native-OS executor + 감사가능 evidence 레이어**로
좁혀라.

---

## 1. 사용자 전제 정정 — "OpenClaw가 저물고 있다"

리서치 결과 이 전제는 **사실과 어긋난다**. 짚고 넘어가야 합니다:

| 항목 | 발견 | 출처 |
|---|---|---|
| 공개 OpenClaw 실존 | Peter Steinberger의 오픈소스 autonomous agent. Clawdbot(2025-11-24) → Moltbot(2026-01-27, Anthropic 상표 이의) → **OpenClaw(2026-01-30)** | [openclaw.ai](https://openclaw.ai/) · [Wikipedia/OpenClaw](https://en.wikipedia.org/wiki/OpenClaw) |
| 추세 | **떠오르는 중** — 2026-03-02 기준 ~247k GitHub stars / 47.7k forks. "저물고 있다"의 정반대 | [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) |
| 행동 모순 | 공개 OpenClaw는 **Playwright로 브라우저를 직접 운전**하고 SKILL.md 플러그인을 쓰는 generalist. coord-smith가 가정하는 "좌표 x/y를 주입하는 caller"와 **반대로 동작** | 리서치 종합 |

**해석(추론):** coord-smith CLAUDE.md의 "OpenClaw"는 실제 그 제품과의 연동이
아니라 **"외부 추론 레이어"라는 역할 placeholder**일 가능성이 높다. 공개
제품은 브라우저를 직접 잡으므로 coord-smith의 브라우저 금지 invariant와
애초에 양립하지 않는다.

**그런데 이게 핵심이 아니다.** 전략적으로 중요한 진실은 ↓

> **누가 caller인지는 중요하지 않다.** "reasoner가 dumb executor를 호출"하는
> 형태가 업계 전체의 표준이므로, OpenClaw가 저물든 떠오르든 coord-smith의
> 손-역할 수요는 그 한 제품에 묶여 있지 않다. 머리는 갈아끼우면 된다.

---

## 2. 3축 발견 요약

### 2-A. 머리(CUA 모델·제품) — "손은 표준이다"

- **"모델 제안 → caller harness 실행" 루프가 3社 공통.** *문서 직접 인용*:
  - OpenAI: "your harness acts as the hands on the keyboard and mouse… your
    harness executes those actions." ([developers.openai.com, 2026-05-29 조회](https://developers.openai.com/api/docs/guides/tools-computer-use))
  - Anthropic: "your application executes the action… capture the screenshot,
    transform coordinates, execute the click." ([platform.claude.com, 조회](https://platform.claude.com))
  - Google: "the client-side code then executes the received action" (1000×1000
    정규화 좌표). ([blog.google, 2025-10-07](https://blog.google))
- **상태(2026-05):** Anthropic computer use는 여전히 **개발자 API는 beta**
  (claude.ai 소비자판은 2026-03 GA). OpenAI Operator 독립앱 **2025-08-31 종료**
  → ChatGPT agent에 흡수, `computer-use-preview`는 research preview 유지. Google
  Project Mariner 독립제품 **2026-05-04 종료** → Gemini Agent에 흡수.
- **경계가 "위로" 이동 중:** 벤더가 full default loop(sandbox VM)를 제공해
  *일반* 사용자는 harness를 안 짠다. → standalone executor의 시장은 **벤더
  sandbox를 거부하는 세그먼트**: on-prem · real-OS/native-app · 감사/규제 ·
  벤더-중립 배포.
- **신뢰도 궤적:** OSWorld 인간 baseline(~72.4%)을 frontier가 **돌파**(2026
  82~83% 보고, 단 2차 출처). → 추론은 신뢰 가능해지고, **실행+증거 floor의
  상대 가치가 오른다**("plan은 믿어도 act는 증명해야 한다").

### 2-B. 손(실행 패러다임) — "픽셀-온리는 절반만 옳다"

- **2026 web 컨센서스 = hybrid(DOM/a11y 기본 + vision fallback), 순수 픽셀 아님.**
  browser-use(hybrid) 89.1% vs a11y-only 73.1% WebVoyager. ([zylos.ai, 2026-02-08](https://zylos.ai/research/2026-02-08-computer-use-gui-agents))
- **툴 진영이 modality로 양분:** Playwright MCP는 **a11y-tree 기본**(vision은
  opt-in), Stagehand·browser-use는 DOM/a11y-first, Skyvern은 visually ground
  하되 **DOM으로 execute**. ([playwright-mcp](https://github.com/microsoft/playwright-mcp) · [skyvern, 2025-07-16](https://www.skyvern.com/blog/how-skyvern-reads-and-understands-the-web/))
- **반대 증거도 있음:** end-to-end frontier 모델(UI-TARS, Operator)은 **순수
  픽셀**이고 OSWorld 리드. UGround/SeeAct-V는 vision-only가 a11y-text 대비
  grounding +20%p. ([arxiv 2501.12326](https://arxiv.org/abs/2501.12326) · [UGround](https://osu-nlp-group.github.io/UGround/))
- **순수 픽셀의 약점은 문서화됨:** 해상도/DPI 일반화 실패(arXiv 2510.03230),
  screenshot 관측은 "expressive but deeply unstable", 짧은 액션·알림을 놓침
  (Anthropic 자인). 
- **검증/증거 컨벤션이 등장 — coord-smith 설계를 검증함.** "programmatic
  postcondition validation checks final application state rather than
  model-as-oracle"; Playwright를 "verification/observability layer(failure
  dossier: traces+screenshots+logs)"로 포지셔닝. ([playwright.dev/docs/test-agents, v1.56](https://playwright.dev/docs/test-agents))
- **벤치마크 ≠ 프로덕션 신뢰도(중요 경고):** UC Berkeley(2026) OSWorld-Verified
  점수 게이밍 가능 입증; Operator 실측 "5건 중 2건만 성공, 3건은 조용히 실패".
  ([coasty.ai, 2026-05](https://coasty.ai/blog/osworld-benchmark-2026-results-ai-computer-use))

### 2-C. 신경(오케스트레이션·프로토콜) — "CLI 베팅이 때를 만났다"

- **MCP는 2026 중반 de facto 표준**(~97M/월 다운로드, 2025-12 Linux
  Foundation/AAIF로 거버넌스 이관). 단 수치는 2차 출처. ([anthropic.com, 2025-12](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation))
- **그러나 executor 티어에서 CLI/subprocess로의 역류가 실재.** 토큰 비용:
  MCP는 tool schema를 context에 front-load(4~32×). **Perplexity가 MCP를 내부
  폐기**("컨텍스트의 72%를 schema가 잠식") → API+CLI 전환. "CLI is the new MCP"가
  named pattern. ([nevo.systems, 2026-03](https://nevo.systems/blogs/news/perplexity-drops-mcp-protocol-72-percent-context-window-waste) · [oneuptime.com, 2026-02-03](https://oneuptime.com/blog/post/2026-02-03-cli-is-the-new-mcp/view))
- **stateless-worker / stateful-supervisor 분리가 권장 패턴.** 메모리는 추론
  레이어에, executor는 ephemeral. ([computer-agents.com, 2026-03](https://computer-agents.com/blog/persistent-vs-ephemeral-agents-2026))
- **Observability는 OpenTelemetry GenAI semconv로 수렴 중이나 agent span은
  아직 experimental.** eval harness는 JSONL trace + per-run report로 표준화 —
  **coord-smith가 emit하는 바로 그 모양.** ([opentelemetry.io](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/))

---

## 3. coord-smith invariant pressure-test

| invariant / 결정 | 2026 컨벤션 대비 | 신뢰도 | 근거 |
|---|---|---|---|
| **LLM-free 런타임** (추론은 외부) | ✅ ALIGNED — supervisor/worker 분리는 교과서 | high | 2-A, 2-C |
| **reasoner + dumb executor 분리** | ✅ ALIGNED — 3社 공식 루프와 동일 형태 | high | 2-A 인용 |
| **stateless run-once CLI** | ✅ ALIGNED — ephemeral worker 권장과 일치 | high | 2-C |
| **MCP transport 거부** | 🟡 ALIGNED-with-caveat — executor 티어 역류가 정당화. 단 MCP는 여전히 frameworks의 first reach. **server facade까지 영구 거부**는 discoverability를 잃는 소수-correct 입장 | high | 2-C |
| **typed evidence / run.json** | 🟡 ALIGNED, 약간 idiosyncratic — eval-harness 형태와 일치하나 **OTel wire 비호환** | med-high | 2-B, 2-C |
| **좌표·픽셀만, 브라우저 내부 금지** | ⚠️ 절반만 — native-OS엔 자산, **web엔 hybrid 컨센서스 역행** | med | 2-B |
| **OpenCV image-template fallback** | ❌ LIABILITY — DPI/해상도/테마에 취약. VLM grounding·a11y-ref가 더 robust | high | 2-B |

---

## 4. 가장 잘 늙는 것 / 가장 나쁘게 늙는 것

### 🟢 자산 (double-down 후보)
1. **결정론 + 감사가능 evidence.** 머리가 비결정론적일수록 손의 증거가 귀해진다.
   2026 "audit crisis"(규제기관이 screenshot 선언 넘어 tamper-evident 운영
   증거 요구)와 정확히 맞물림. coord-smith의 가장 강한 차별점.
2. **stateless-CLI 통합.** "CLI is the new MCP" 흐름이 베팅을 추인.
3. **native-OS 도달.** 브라우저 밖(native app·canvas·게임·remote desktop·
   DOM-less)은 픽셀-좌표가 유일하게 균일히 작동하는 modality.

### 🔴 부채 (재고 후보)
1. **image-template matching을 1급 locator로 두는 것.** 좌표 우선순위가
   payload > coord > image이므로 **image는 진짜 마지막 fallback이어야** 한다.
   caller가 좌표를 주는 payload-path가 healthy, image-fallback이 fragile.
2. **a11y-tree 전면 금지.** native desktop에서도 a11y-tree가 ground-truth로
   재부상(agent-desktop, MS UFO²). web에선 더더욱 역행. ban의 *범위*가 업계
   실제 입장보다 강하다.

---

## 5. 방향 제안 (forki 후보 — 사용자 결정 필요)

| # | 방향 | 무엇을 | 리스크 |
|---|---|---|---|
| **F1** | **포지셔닝 좁히기** | "browser automation"이 아니라 **"audit-grade native-OS executor"**로 정체성 고정. PRD/README 메시징을 evidence·compliance·native로 | 낮음(문서). 시장 좁아 보일 수 있음 |
| **F2** | **evidence 레이어 강화** | run.json/JSONL에 OTel GenAI semconv 호환 export shim(opt-in). 감사 추적을 APM에 떨굴 수 있게 | 낮음. OTel agent span이 아직 experimental이라 급하진 않음 |
| **F3** | **image-fallback 정직화** | image-template를 "best-effort 마지막 수단"으로 문서/코드에서 명확히 강등. caller-coords path를 정식 경로로 승격(이미 우선순위는 그러함) | 낮음. 기능 축소 아님, 메시징 정정 |
| **F4** | **a11y-ban 재검토** | 브라우저 금지는 유지하되 **native a11y-tree는 evidence 보강용으로 허용**할지 ADR로 토론. (실행 modality가 아니라 *검증* 신호로) | 중간. invariant 변경은 PRD 개정 필요 |
| **F5** | **현상 유지** | 트렌드 확인만 하고 코드/문서 불변 | 없음. 단 image-fallback 부채 잔존 |

권장(주관): **F1 + F3을 먼저**(저비용·고정합, 정체성 명확화). F2는 backlog
B-DX-2(telemetry)와 합류. F4는 가장 무겁고 invariant를 건드리니 별도 ADR
토론으로 분리. backlog의 B-DX-1(MCP wrapper opt-in)은 §2-C 역류를 감안해
**우선순위를 낮춰도** 무방.

---

## 6. 불확실성 / 한계 (정직성)

- **2026 모델·벤치 수치 상당수가 aggregator/blog 2차 출처**(coasty·benchlm·
  llm-stats). OSWorld *궤적*은 견고하나 정확한 소수점은 low-confidence.
- **MCP 정량치(97M DL, 72% 토큰, 4~32×)는 널리 인용되나 1차 미도달**(openai.com
  403, spec 사이트 unreachable). well-corroborated-but-secondary.
- **coord-smith 특정 설계(caller-coords + OpenCV + typed evidence)를 직접
  평가한 출처는 없음.** §3·§4의 verdict는 아키텍처를 트렌드에 매핑한 **추론**.
- **OpenClaw 정체성:** 공개 제품 실존은 *사실*, "coord-smith의 OpenClaw =
  role placeholder"는 *추론*(repo 문서의 행동 기술이 공개 제품과 모순됨).
- OSWorld는 modality(픽셀 vs a11y) 효과를 점수에서 분리하지 못함 — "어느 클릭
  방식이 더 신뢰적인가"의 약한 proxy.

---

*생성: 3× general-purpose 리서치 에이전트(head/hands/nerve) 병렬 → 합성.
원시 findings는 세션 트랜스크립트 참조. 코드·문서 변경 없음(분석 전용).*

---

# 부록 A — 1차 출처 재검증 (2026-05-29, 같은 날)

> 사용자 지시 "추가 검증 먼저". §6에서 자인한 2차-출처 의존을 교정하기 위해
> 3개 핵심 주장을 **1차 출처 전용 + adversarial(반증 우선)** 에이전트로
> 재검증. 도달 실패는 정직 보고하도록 강제. **결과: 본문 여러 주장이 정정됨.**

## A-1. 무엇이 1차에서 살아남았나 / 무엇이 깎였나

| 본문 주장 | 1차 검증 결과 | 영향 |
|---|---|---|
| **reasoner+executor 분리가 3社 공식 루프** | ✅ **CONFIRMED-PRIMARY** (3社 docs 직접 인용) | **load-bearing 주장 생존.** 본문 §2-A 유효 |
| OpenAI computer-use는 research **preview** | ❌ **CONTRADICTED** — GPT-5.4/5.5에 **GA built-in tool**, `computer-use-preview`는 2026-07-23 shutdown 예정 | 본문 §2-A 정정 필요 |
| Operator 종료(2025-08) → ChatGPT agent 흡수 | 🟡 secondary-only (openai.com 403). 2차로는 **2025-07-17** | 날짜·확신 하향 |
| Project Mariner "종료" | 🟡 UNCONFIRMED — "Gemini Agent로 흡수" 방향은 Google 자체 표현으로 지지되나 "discontinued" 단어는 1차 부재 | 확신 하향 |
| Anthropic computer use 개발자 API beta | ✅ CONFIRMED-PRIMARY (beta header 필수) | 유지 |
| OSWorld OS-level·인간 baseline ~72% | ✅ CONFIRMED-PRIMARY (72.36%, arxiv 2404.07972) | 유지 |
| **MCP→AAIF/Linux Foundation 이관(2025-12-09)** | ✅ CONFIRMED-PRIMARY. **단 co-founder는 Anthropic·Block·OpenAI** (Google/MS/AWS는 supporter) | 본문 "Google 공동설립" 뉘앙스 정정 |
| **"Perplexity가 MCP 내부 폐기, 72% 잠식"** | ❌ **UNCONFIRMED/오귀속** — Perplexity 1차 출처 전무. **72%는 Apideck 자체 측정치**(MCP와 Perplexity 무관). Perplexity는 **여전히 MCP server 운영** | **본문 §2-C 핵심 근거 붕괴** |
| MCP 토큰 비용 자체 (55K/58툴, 150K→2K) | ✅ CONFIRMED-PRIMARY — **Anthropic 자체 포스트** | 비용 문제는 사실 |
| "CLI is the new MCP" (executor 역류) | 🟡 secondary framing. **Anthropic 자체 해법은 CLI가 아니라 code-execution/tool-search** | **"트렌드 추인" 약화** |
| MCP 스케일 97M DL / 10K servers | ✅ CONFIRMED-PRIMARY | MCP는 여전히 ascendant |
| Agent Skills(SKILL.md) MCP 보완 | ✅ CONFIRMED-PRIMARY (Anthropic 2025-10-16) | 유지 |
| image-template이 fragile limb | ✅ CONFIRMED (구조적 귀결) — 단 **OpenCV docs가 "not scale-invariant"라 명시하진 않음**; algorithm spec(평행이동 검색, scale/rotation 파라미터 없음)에서 *귀결* | §3·§4 유지, 인용 방식 정정 |
| DPI/해상도 grounding 실패 | ✅ CONFIRMED-PRIMARY (arxiv 2510.03230) — 단 이건 **VLM grounding의 약점**을 다룬 논문(픽셀 일반이 아님) | nuance 추가 |
| "VLM이 a11y agent보다 +20%p" | ⚠️ **오해석** — 20%는 VLM grounding vs **다른 grounding 모델** 비교. a11y agent 대비가 아님 | §2-B 정정 |
| "theme/색상에 취약" | ⚠️ 1차 근거 없음 — 추론(raw-pixel 상관)일 뿐 | 인용 금지 |
| a11y/DOM ref이 더 robust(staleness 감지·semantic) | ✅ CONFIRMED-PRIMARY (Playwright locators, MS UIA docs) — 단 AutomationId는 **버전 간 안정성 보장 안 됨** | F4 논거 보강 |

## A-2. 가장 큰 정정 — "MCP 거부가 트렌드에 부합" 하향

본문 §3은 reject-MCP를 "ALIGNED-with-caveat (high)"로 평가하며 *Perplexity
defection*과 *"CLI is the new MCP"*를 근거로 들었다. **1차 검증 결과 그 두
근거 모두 약하다:**

- Perplexity 폐기 서사 = **1차 출처 0건**, 72% 수치는 **타사(Apideck) 측정치
  오귀속**, Perplexity는 여전히 MCP server를 게시한다.
- 토큰 비용 문제 자체는 **Anthropic 1차로 확실**하나, Anthropic의 *해법*은
  **CLI 전환이 아니라 code-execution + Tool Search**(on-demand 로딩)다. 즉
  업계는 "MCP를 버리고 CLI로" 가 아니라 "**MCP를 더 똑똑하게**"로 가고 있다.
- MCP는 거버넌스(AAIF)·스케일(97M DL)에서 **여전히 부상 중**(1차 확인).

**수정된 판정:** coord-smith의 MCP 거부는 *토큰-비용 논리로는 방어 가능*하지만
**"트렌드를 타고 있다"는 과장**이었다. 정확히는 **contrarian-but-defensible**.
→ backlog **B-DX-1(MCP wrapper opt-in)의 우선순위를 낮추라던 본문 §5 권고는
철회**한다. MCP가 여전히 frameworks의 first-reach이므로, *내부 transport는
CLI 유지 + 외부에 opt-in MCP server facade 제공*(둘 다)이 더 균형 잡힌 방향일
수 있다. 이건 forki 거리.

> **[forki 결과 2026-05-29 — 같은 날 종결]:** 위 "둘 다(CLI+facade)" 가능성을
> forki로 실제로 돌린 결과, 결정자는 **A(순수 CLI 영원)** 를 선택 — facade조차
> 만들지 않는다. 환원된 질문은 "외부 에이전트의 discovery+invocation 책임을
> 누가 지는가 — 호출자 vs coord-smith". 유지보수 단순성↔외부 발견가능성 축에서
> **단순성**을 택함(facade 패키지의 영구 유지보수·의존성 부담 > 호출자의
> subprocess glue 부담). **B-DX-1은 REJECTED로 종결**, PRD의 MCP-거부 조항은
> 그대로 유지. 재오픈 조건: 실제 caller가 MCP discovery를 요구할 때.

## A-3. 정정 후에도 견고한 결론 (안심하고 진행 가능)

1. **reasoner+executor 분리는 1차로 확실** → coord-smith 손-역할의 존재
   이유는 굳건. OpenClaw 흥망과 무관. (가장 중요한 결론, 무상처 생존)
2. **F1**(audit-grade native-OS executor로 포지셔닝) → 영향 없음, 견고.
3. **F3**(image-fallback 정직 강등 + caller-coords 정식 승격) → **1차로
   강화됨.** 단 코드/문서에 쓸 때: ⓐ "OpenCV docs가 scale-invariant 아니라
   말한다"고 쓰지 말 것(docs는 그렇게 안 씀; algorithm에서 귀결이라 써야).
   ⓑ "theme 취약" 인용 말 것(추론). ⓒ "VLM +20%p vs a11y" 쓰지 말 것(오해석).
   robust 대체재는 **caller-supplied(이상적으로 VLM-grounded) 좌표**.
4. **F4**(native a11y를 *검증 신호*로) → 반대편 논거(a11y가 staleness 감지·
   semantic)가 1차로 보강됨. 단 AutomationId 버전-간 불안정도 1차로 확인 →
   "은탄환 아님". 여전히 무거운 PRD-급 결정.

## A-4. 여전한 한계 (정직성)

- **openai.com/index/* 및 help.openai.com 은 fetcher에 일괄 403** — Operator
  종료·ChatGPT agent 흡수는 1차 확인 불가, 2차 snippet뿐. (단 developers.
  openai.com 개발자 docs는 도달 → computer-use GA·preview shutdown은 1차 확인)
- Project Mariner "discontinued" 단어의 1차 확정 부재(방향만 지지).
- MCP "4~32× vs CLI" 배수와 "9,600 registry servers" 정밀치는 2차-only 잔존.
- image C5(a11y 우월)는 1차로 강하나 **coord-smith가 ADR-001로 DOM 금지**이므로
  "그러니 coord-smith를 바꿔라"의 근거로 직수입 금지 — 프로젝트 정체성과 충돌.

*검증: 3× adversarial general-purpose 에이전트(MCP/executor-split/image-
fragility), 1차 출처 전용 지시. 코드·런타임 변경 없음(분석 전용).*

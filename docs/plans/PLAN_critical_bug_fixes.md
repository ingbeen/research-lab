# Implementation Plan: 치명 버그 수정 — 원장 무결성 · 막힘 판정 · 진입점 · 게이트 · 자립성

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: `/impl-plan` 스킬의 "3) 스킵 및 완료 규칙" 참고
- 위 조건은 `~/.claude/hooks/plan_lint.py`가 저장 시 자동 검사합니다

---

**작성일**: 2026-09-26 11:59
**마지막 업데이트**: 2026-09-26 11:59
**관련 범위**: runner(원장·회차·탐색·조립·계보) · gate(채워짐 판정·자격증명·자립성·계보) · agent(예외 위치) · scripts(진입점) · 데이터 카탈로그·리서치 스킬 문구 · 이미 나간 근거 문서 3장
**관련 문서**: `src/research_lab/CLAUDE.md` · `.claude/skills/dossier-research/SKILL.md` · `docs/DATA_CATALOG.md`

> **실행 순서**: 이 계획서가 **1번**이다. 끝나면(✅ Done · 사용자 커밋) 다음 계획서
> [PLAN_docs_consolidation.md](PLAN_docs_consolidation.md) 를 **새 세션에서** 실행한다.
> 다음 계획서는 이 계획서의 «진행 로그»와 «변경 파일 목록»을 읽고 시작하므로,
> **바뀐 파일·새로 생긴 주석·예상과 달랐던 것을 진행 로그에 빠짐없이 남긴다.**

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 `/impl-plan` 스킬을 따릅니다.

- 품질 검증 명령은 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] G1 (B1): 원장이 에이전트가 낸 한 줄 주장의 **줄바꿈·빈 값**으로 깨지지 않는다 — 한 번 담으면 한 줄, 같은 주장은 중복으로 걸러지고, 표시 변경이 그 줄을 찾는다
- [ ] G2 (B2): 「같은 단계 3회차 연속 막힘」 판정이 **그 회차의 «마지막» 실패 갈래**로 센다 — 한도·인증·예산으로 끝난 회차는 세지 않는다
- [ ] G3 (B3): 잘못된 `--budget-usd`(0 이하 · `nan` · `inf`)는 **돌기 전에 종료 코드 5** 로 거부된다
- [ ] G4 (B4·L5): 탐색 호출의 비용이 원장 기록 도중의 예외와 무관하게 결정 로그에 남고, 상한으로 잘린 후보도 「버렸다」로 남는다
- [ ] G5 (B7·B8): 자격증명 검사가 **실제로 쓴 원장 폴더**를 보고, 잠금 충돌 사유가 어느 잠금인지 오도하지 않는다
- [ ] G6 (B5·B6): 네 게이트의 「채워짐」 판정이 하나로 같고, 근거 문서의 「대상 시장」에 파이썬 표기가 새지 않는다
- [ ] G7 (L4·O4): 근거 문서가 저장소 안 데이터 카탈로그를 가리키는 문장을 자립성 게이트가 막고, 이미 나간 근거 문서 3장의 그 문장을 고친다
- [ ] G8 (O1): 6번 칸의 「복제를 뺀 독립 소스 수」를 에이전트가 적지 않고 **러너가 덩어리 수로 센다**
- [ ] G9 (O3): `agent` 계층이 `runner` 를 import 하지 않는다 — `StepFailed` 를 `agent` 로 옮기고 `TYPE_CHECKING` 우회를 없앤다
- [ ] G10 (O2): 테스트의 `# type: ignore` 8건을 **인자 타입을 맞춰** 없앤다

## 2) 비목표(Non-Goals)

- **문서 정리 전부** — `docs/DESIGN.md` 삭제 · `docs/OPERATIONS.md` 축약 · 옛 계획서 삭제 · 낡은 서술 정정은 다음 계획서 [PLAN_docs_consolidation.md](PLAN_docs_consolidation.md) 의 일이다. 이 계획서는 **자기가 바꾼 코드의 주석**만 맞춘다
- 사용자가 「공수 대비 효율이 낮다」로 패스한 것(2026-09-26 결정): 상수화(단계 이름·게이트 이름·상태 키·출력 키) · 리팩토링(단계 `run()` 머리 중복 · 출처 모으기 중복 · 이중 읽기) · 데드코드(탐색 건너뛰기의 「미룬 후보」 계산) · 테스트 함수 안 import 정리 · `scripts/run_cycle.py` 의 `sys.path` 조작 · 코드 주석의 이력·수치 정리
- 이번에 고치지 않는 잠재 결함(목록만 남김): 산문 속 URL 미검사 · `invoke._result_from` 의 `payload.get("result", raw)` fallback · `--run-dir` 로 망가진 상태 파일을 지정했을 때의 `UnknownStepError` · 후보가 이미 닫힌 폴더를 이어받으면 그 회차 루프가 멈추는 것 · `payload.as_text` 의 목록 `str()` 전반(이번엔 근거 문서 「대상 시장」 한 자리만)
- `runs/` 원자료는 **고치지 않는다** — 근거물이다. 이미 나간 근거 문서는 `dossier/` 쪽만 고친다
- `Dockerfile` · 이미지 · 실행 명령 · 종료 코드 체계는 바꾸지 않는다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

2026-09-26 전수 분석(이 계획서를 만든 세션)에서 나온 것 중 **사용자가 「무조건 진행」으로 정한 버그**와 **함께 넣기로 고른 네 항목**이다.
줄 번호는 2026-09-26 기준(`09c4e13` + 미커밋 문서 변경)이며 **함수·상수 이름으로 찾는다.**

| # | 자리 | 무엇이 잘못됐나 | 근거 |
| --- | --- | --- | --- |
| B1 | `runner/ledger.py` — `canonical_claim`(346행 부근) · `append` · `load` · `_rewrite` | 정규화가 앞뒤 공백과 앞머리 백틱만 뗀다. 주장에 줄바꿈이 들어가면 **한 번 담았는데 원장 항목이 둘**로 쪼개지고(뒷줄이 새 후보로 끼어든다), **같은 주장을 다시 담아도 중복으로 안 걸리며**, `mark_rejected` 가 `UnknownCandidateError` 를 낸다. 백틱만 있는 주장은 **읽히지 않는 `- [ ] ` 줄**로 쌓인다. 탐색 `_store` 는 담은 뒤 기각을 적는 순서라 이 예외가 탐색 단계 전체를 「그 외」 실패로 만들고, 재시도가 쪼개진 줄을 또 쌓는다 | **[재현]** 아래 재현 절차 1 |
| B2 | `runner/cycle.py` — `_failed_cycles`(397-421행) | 「3회차 연속 막힘」을 **1번째 시도(`attempt == 1`)의 갈래**로 센다. 첫 시도가 「그 외」(네트워크 등)였고 재시도가 한도(`limit`)로 끝난 회차도 한 번으로 세어, 그런 회차가 셋이면 **멀쩡한 후보가 `- [!]` 로 걷힌다.** 같은 파일의 `COUNTED_FAILURE_KINDS` 주석 「한도·인증·예산은 세지 않는다」와 어긋난다. 새벽 회차는 한도에 자주 걸리므로(예: 2026-09-20 · 09-21 종료 코드 2) 운용 중에 일어날 수 있다 | **[재현]** 아래 재현 절차 2 |
| B3 | `scripts/run_cycle.py` — `_parse_args` 의 `--budget-usd`(714-719행) · `agent/invoke.py` `build_command`(116행) | 인자 단계에서 값을 검사하지 않는다. 0 이하·`nan` 은 각 단계 안에서 `ValueError`(또는 CLI 오류)로 터지고, `cycle._execute_with_retries` 의 `except Exception` 이 「그 외」로 분류해 **30초 간격으로 세 번 재시도**한 뒤 막힘 횟수에 센다. 3회차 뒤 수집 단계면 `_block_candidate` 가 원장의 다음 후보를 집어 **물어본 적도 없는 후보를 걷어낸다.** `--cycle-dossiers` 는 이미 `_dossier_count` 로 막고 있다(같은 관용) | [확인] 코드 |
| B4 | `runner/explore.py` — `run`(112행 `_store` · 135행 `record_cost`) | 비용 줄을 원장 기록 «뒤»에 적는다. `_store` 에서 예외(B1 의 `UnknownCandidateError` · `OSError`)가 나면 그 호출의 비용이 **회차 집계에서 빠진다** — `except Exception` 경로는 `StepFailed.spent` 가 없어 러너도 못 적는다. 다른 단계는 전부 게이트 «앞»에서 적는다 | [확인] 코드 |
| L5 | `runner/explore.py` — `_store`(163행 `candidates[:MAX_CANDIDATES]`) | 상한을 넘는 후보가 **기록 없이** 버려지고, `judged` 줄의 `proposed` 는 전체 수를 적어 숫자가 안 맞는다 | [확인] 코드 |
| B5 | `runner/dossier.py` — `_feasibility_section`(323행) | 「대상 시장」만 `_flatten` 이 아니라 `payload_helpers.as_text` 를 쓴다. `market` 이 목록이면 `['국내', '미국']` 이 문서에 실린다. 같은 파일의 「문서에 값을 싣는 자리는 전부 `_flatten` 을 지난다」와 어긋난다. 지금까지 실행 9건은 전부 문자열이었다 | [잠재] |
| B6 | `gate/mechanism.py` `_is_filled`(74-84행) · `gate/verdict.py` `_is_filled`(66-72행) | 빈 컨테이너만 걸러 **`[""]` · `{"k": ""}` 를 「채워짐」으로 통과**시킨다. 조립부는 같은 값을 「(적히지 않았습니다)」로 찍는다. `gate/feasibility.py` · `gate/measurement.py` 의 `_is_filled` 는 재귀로 이미 고쳐져 있다(같은 이름 네 벌 · 뜻 두 가지). 두 단계는 JSON 스키마로 문자열이 강제돼 실제로는 드물지만, 호출 계층은 스키마를 믿지 않는 것이 계약이다 | [잠재] |
| B7 | `gate/secrets.py` — `scan_roots`(74행) | 원장 자리를 `common_constants.LEDGER_DIR` 상수로 박는다. `--ledger` 로 다른 원장을 쓰면 **실제로 쓴 원장은 검사하지 않고** 기본 원장 폴더를 검사한다 | [확인] 코드 |
| B8 | `scripts/run_cycle.py` — `_run_cycles` 의 `AlreadyRunningError` 갈래(267행) | 원장 잠금 때문에 막혀도 「그 폴더를 잡지 못했습니다 — {폴더명}」으로 적혀 **어느 잠금인지 오도**한다(`cycle.run_cycle` 은 원장 잠금을 먼저 잡는다) | [확인] 코드 |
| L4 | `gate/selfcontained.py` — `POINTER_TERMS`(44-52행) | 「카탈로그」류가 없다. 자립성 게이트가 생긴 뒤 나간 3장이 **저장소 안 데이터 카탈로그를 가리킨다**(아래 O4). 실현가능성 지시문이 금지한 바로 그 표현이다. 1순위 제약 위반이 이미 저장소 밖으로 나갔다 | [확인] 산출물 |
| O4 | `dossier/` 3장 | `20260915_exec-cluster-buy.md` 242행 「(카탈로그에 실측 없음)」 · `20260916_sell-in-may.md` 266행 「카탈로그는 ETF 전수조회가 된다고만 확인했지」 · `20260919_ipo-lockup-short.md` 83행 「이는 카탈로그에 없어 이번에 확인한 내용이다」 | [확인] 산출물 |
| O1 | `runner/lineage.py` · `gate/lineage.py`(83-88행) | 독립 소스 수를 **에이전트가 적고** 게이트는 정수인지만 본다. 정의상 「자기 혼자인 덩어리 = 독립 1」이라 덩어리 수와 같아야 하는데 틀려도 에러가 없다. 지금까지 실행 10건 전부 `count == len(groups)` 였다 | [확인] 데이터 |
| O3 | `agent/invoke.py` 22행 `from research_lab.runner.steps import StepFailed` · `runner/steps.py` 10-13행 `TYPE_CHECKING` | 계층 계약 「agent 와 gate 는 runner 를 import 하지 않는다」(`src/research_lab/CLAUDE.md`) 위반. `steps.py` 는 그 순환을 피하려고 `AgentResult` 를 `TYPE_CHECKING` 으로만 가져온다 | [확인] 코드 |
| O2 | `tests/test_agent_invoke.py` 43행 · `tests/test_gate_urls.py` 274 · 411 · 441 · 466 · 492 · 519 · 569행 | `# type: ignore[...]` 8건. **[재현]** 8건을 전부 지워도 현재 설정의 PyRight 는 0 errors — 274행은 어떤 설정에서도 불필요하고, 나머지 7건은 `pyrightconfig.json` 의 tests 환경 `reportArgumentType: none` 이 이미 막는 **이중 억제**다. 진짜 원인은 `dict[str, object]` 를 `**kwargs` 로 넘기는 헬퍼와 `HTTPError(..., {}, None)` 의 `hdrs` 타입 | **[재현]** PyRight |

#### 재현 절차 (Phase 0 테스트의 원형 — 고친 뒤 다시 돌려 «재현 안 됨»을 확인한다)

1. **B1** — 임시 폴더의 원장에 `ledger.append(p, "소형주를 12월 말에 산다\n- [ ] 주입된 후보", identifier="x")` 를 두 번 → 수정 전: `load` 가 항목 4개(`x`, 주입된 후보, `x-2`, 주입된 후보) · 두 번째 `append` 도 `True` · `mark_rejected` 가 `UnknownCandidateError`. `ledger.append(p2, "```")` 두 번 → 수정 전: 둘 다 `True`, `load` 는 빈 목록, 파일에 `- [ ] ` 두 줄
2. **B2** — `cycle.RETRY_DELAY_SECONDS = 0` 으로 두고, 상태에 `settled: [explore, collect]` + 후보를 박은 폴더에서, 첫 호출은 `StepFailed("connection reset by peer")` · 이후 호출은 `StepFailed("You've hit your session limit - resets 4:40pm")` 을 올리는 실행자로 `run_cycle` 을 세 번 → 수정 전: 세 회차 모두 갈래 `limit` 인데 3회차에 `blocked_claim` 이 채워지고 원장 표시가 `blocked`

### 사용자 결정 (2026-09-26 — 다시 정하지 않는다)

- 치명 버그는 무조건 진행 · 공수 대비 효율이 낮은 것은 패스 · 최종 항목은 재검증
- 함께 넣는 선택 항목: **O1 독립 소스 수를 러너가 계산 · O2 type: ignore 제거 · O3 StepFailed 이동 · O4 나간 문서 3장 소급 수정**
- `docs/DESIGN.md` 는 **다음 계획서에서 삭제**한다. 그래서 이 계획서의 **근거 승격은 DESIGN.md 로 하지 않는다** — 「왜」는 **그 코드 자리의 주석**에 남기고(짧게, 전역 「주석은 코드가 못 하는 말만」 규칙대로), 경위는 이 계획서의 진행 로그에 남긴다. 다음 계획서가 루트 `CLAUDE.md` 의 근거 규약을 새로 쓴다
- 두 계획서는 **각각 새 세션**에서 **순서대로**(이 계획서 → 다음 계획서) 실행한다

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 (값이 아니라 **판단 근거**)
- `src/research_lab/CLAUDE.md` — 계층 구조 · 계층 간 계약(특히 §3 판정을 못 하는 것과 실패로 판정하는 것 · §4 후보의 주인 · §5 게이트 · §12 같은 가드를 두 곳에 두지 않는다)
- 전역 `~/.claude/rules/python.md` — **`.py` 를 `Read` 도구로 열 때만** 주입된다. 코드 파일은 `Read` 로 연다
- `.claude/skills/dossier-research/SKILL.md` · `docs/DATA_CATALOG.md` — L4 에서 문구를 고친다

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [ ] G1 ~ G10 이 모두 충족됐다 (각 Phase 의 체크리스트)
- [ ] 재현 절차 1 · 2 를 수정 후 다시 돌려 **재현되지 않음**을 진행 로그에 원문으로 남겼다
- [ ] 회귀/신규 테스트 추가 (Phase 0 의 계약 테스트가 전부 그린)
- [ ] **독립 재검증** 기록 — 작업 맥락을 물려받지 않은 서브에이전트가 이 계획서의 G1 ~ G10 과 미커밋 diff 를 대조한 결과 (마지막 Phase)
- [ ] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [ ] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [ ] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [ ] 필요한 문서 업데이트 — `docs/COMMANDS.md` 변경 없음 · `.claude/skills/dossier-research/SKILL.md` 변경 있음(L4 문구) · `docs/DATA_CATALOG.md` 변경 있음(L4 문구) · `src/research_lab/CLAUDE.md` 변경 없음(O3 로 import 방향 규칙이 «참»이 될 뿐) · 루트 `CLAUDE.md` 변경 없음
- [ ] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (위 「사용자 결정」대로 **코드 주석**으로 이관. DESIGN.md 에는 추가하지 않는다)
- [ ] 진행 로그에 **다음 계획서가 읽을 «변경 파일 목록»과 참고사항**을 남겼다
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/research_lab/runner/ledger.py` — B1 (정규화 · 빈 값 거부 · 읽기/비교 양쪽 정규화)
- `src/research_lab/runner/cycle.py` — B2 (`_failed_cycles`) · O3 (`StepFailed` 참조)
- `scripts/run_cycle.py` — B3 (`--budget-usd` 타입 함수) · B7 (`_report_secrets` 가 원장 폴더를 넘김) · B8 (사유 문구)
- `src/research_lab/runner/explore.py` — B4 · L5 · B1 (빈 정규형 건너뛰기 · `seen` 정규화)
- `src/research_lab/runner/dossier.py` — B5
- `src/research_lab/gate/filled.py` **(신설)** — B6 공용 「채워짐」 판정
- `src/research_lab/gate/{feasibility,measurement,mechanism,verdict}.py` — B6 (사설 `_is_filled` 제거 · 공용 사용)
- `src/research_lab/gate/secrets.py` — B7 (`scan_roots` 가 원장 폴더를 필수 키워드로 받음 · `LEDGER_DIR` import 제거)
- `src/research_lab/gate/selfcontained.py` — L4 (사전 · 그 이유 주석)
- `src/research_lab/runner/feasibility.py` — L4 (지시문 상수가 새 사전을 스스로 통과하도록 문구 조정)
- `docs/DATA_CATALOG.md` · `.claude/skills/dossier-research/SKILL.md` — L4 (프롬프트로 실려 가는 문구)
- `dossier/20260915_exec-cluster-buy.md` · `dossier/20260916_sell-in-may.md` · `dossier/20260919_ipo-lockup-short.md` — O4
- `src/research_lab/runner/lineage.py` · `src/research_lab/gate/lineage.py` — O1
- `src/research_lab/agent/invoke.py` · `src/research_lab/runner/steps.py` + `StepFailed` 을 참조하는 runner 모듈 전부 — O3
- `tests/` — 계약 테스트 추가 · O3 import 경로 · O2 타입 정리 · O1/B7 로 바뀐 시그니처
- `docs/COMMANDS.md`: **변경 없음** — 실행 명령·옵션이 안 바뀐다. 종료 코드 5(「인자가 잘못됐다」)가 B3 을 이미 덮는다

### 데이터/결과 영향

- **원장**: 기존 줄 동작 불변 — 현재 원장에 연속 공백·탭이 든 주장은 0건이다([확인] 2026-09-26). 새로 담는 줄만 정규형이 바뀐다
- **막힘 판정**: 기존 실행 폴더의 누적 횟수가 새 규칙으로 다시 세어진다 — 한도로 끝난 회차가 빠지므로 **줄어들기만** 한다
- **계보 산출물**: `independent_source_count` 열쇠와 근거 문서 6번 칸의 모양은 그대로, 값의 출처만 러너로 바뀐다
- **근거 문서 3장**: 가리키는 문장만 자립 서술로 바뀐다. 사실은 그대로 둔다
- **이미지 재빌드 불필요** — `Dockerfile` 불변, 소스는 bind mount

## 6) 단계별 계획(Phases)

### Phase 0 — 계약과 재현을 테스트로 먼저 고정(레드)

**작업 내용**:

- [ ] B1: 줄바꿈 든 주장을 담으면 원장 항목이 **정확히 1개** · 같은 주장 재담기는 `False` · 그 주장으로 `mark_rejected`/`mark_explored`/`status_of` 가 동작 · 정규형이 빈 주장은 `append` 가 `ValueError` · 탐색 `_store` 는 빈 정규형을 원장에 안 담는다
- [ ] B2: (a) 「그 외 → 한도」 회차 3번은 **안 걷힌다**(재현 절차 2) (b) 「그 외」가 상한까지 간 회차는 센다 (c) 품질 실패는 센다 (d) 「그 외 → 성공」은 안 센다 (e) 「그 외 → 품질 실패」는 한 번만 센다
- [ ] B3: `--budget-usd` 에 `0` · `-1` · `nan` · `inf` 를 주면 `SystemExit(5)` · `8.0` 은 통과
- [ ] B4 · L5: 원장 기록이 예외를 내도 탐색의 비용 줄이 결정 로그에 있다 · 상한을 넘는 후보가 `discarded` 로 남는다
- [ ] B5: `market` 이 목록인 실현가능성 산출물로 조립하면 4번 칸에 파이썬 표기(`[`·`'`)가 없다
- [ ] B6: 메커니즘·판정 게이트가 `[""]` · `{"k": ""}` · `[[]]` 를 「비었다」로 막는다 (실현가능성·측정의 기존 테스트는 그대로 통과)
- [ ] B7: `scan_roots` 결과에 **넘긴 원장 폴더**가 들어 있고 기본 원장 폴더 상수를 쓰지 않는다
- [ ] L4: O4 의 세 문장(원문 그대로를 고정값으로)이 새 사전에 걸린다 · 모든 단계의 지시문 상수가 여전히 자립성 게이트를 통과한다(기존 `tests/test_prompt_selfcontained.py`) · **`docs/DATA_CATALOG.md` 본문도 통과한다**(신규 — 러너가 프롬프트에 싣는 입력이라)
- [ ] O1: 계보 게이트가 `independent_source_count` 를 요구하지 않는다 · 러너가 저장하는 값이 dict 덩어리 수와 같다
- [ ] O3: `research_lab.agent` 아래 어떤 모듈도 `research_lab.runner` 를 import 하지 않는다(소스 문자열 검사 계약 테스트)

**Validation**: 새 테스트가 **의도한 이유로** 빨갛다는 것만 확인한다 (품질 검증은 돌리지 않는다)

---

### Phase 1 — 원장·회차: 상태 무결성 (B1 · B2)

**작업 내용**:

- [ ] B1 `canonical_claim`: 공백류(줄바꿈·탭 포함) 연속을 공백 하나로 접고 → 앞머리 백틱 제거 → 앞뒤 공백 제거. **읽는 쪽도 같은 함수를 지나게** `load` 가 정규형으로 읽고, `_rewrite` 의 비교도 정규형끼리 한다(한쪽만 정규화하면 에러 없이 어긋난다 — 파일 머리 주석이 이미 경고한 모양)
- [ ] B1 빈 정규형: `append` 는 `ValueError`(외부 입력 검증). 탐색 `_store` 는 호출 «전»에 빈 정규형을 걸러 `discarded`(사유 「주장이 비어 있다」)로 남기고, `seen` 집합도 정규형으로 채운다
- [ ] B2 `_failed_cycles`: 한 회차의 «마지막» 실패만 센다 — `kind == quality`(재시도 없음) 이거나 `kind == other` 이면서 `attempt == 그 줄의 max_retries`(상한까지 간 것). 한도·인증·예산으로 끝난 회차는 그 회차의 1번째 시도가 「그 외」였어도 세지 않는다. 주석의 「왜」를 새 규칙에 맞게 고친다(`attempt == 1` 로 좁히던 이유는 사라진다)
- [ ] Phase 0 의 B1 · B2 테스트 그린

---

### Phase 2 — 진입점·탐색·자격증명 (B3 · B4 · L5 · B7 · B8)

**작업 내용**:

- [ ] B3: `_dossier_count` 와 같은 관용으로 `--budget-usd` 타입 함수를 둔다 — 실수 · 유한 · 0 초과가 아니면 `argparse.ArgumentTypeError`(→ `_Parser.error` → 종료 코드 5). `build_command` 의 `ValueError` 가드는 라이브러리 계약이라 **남긴다**
- [ ] B4: 탐색이 응답을 파싱한 «직후» `record_cost` 를 적는다(읽은 것 → 비용 → 원자료 파일 → 원장 순)
- [ ] L5: 상한을 넘는 후보를 `discarded`(사유에 상한 이름, 잘린 주장 목록)로 남기고 `proposed` 의 뜻을 주석 없이도 맞게(받은 수 · 본 수를 갈라 적는 등)
- [ ] B7: `secrets.scan_roots(run_dir, *, ledger_dir, dossier_path)` — 원장 폴더를 **기본값 없는 키워드**로 받는다(기본값을 두면 부르는 쪽이 빠뜨려도 조용히 돈다). `run_cycle._report_secrets` 가 `args.ledger.parent` 를 넘긴다. `gate/secrets.py` 의 `LEDGER_DIR` import 제거
- [ ] B8: 잠금 충돌 사유를 「이미 도는 회차가 원장이나 그 실행 폴더를 잡고 있다」처럼 **어느 잠금인지 단정하지 않는** 문구로(절대경로는 계속 회차 로그에 싣지 않는다)
- [ ] Phase 0 의 B3 · B4 · L5 · B7 테스트 그린

---

### Phase 3 — 게이트·조립·자립성 (B5 · B6 · O1 · L4 · O4)

**작업 내용**:

- [ ] B5: `_feasibility_section` 의 「대상 시장」을 `_flatten` 으로
- [ ] B6: `gate/filled.py` 에 공용 `is_filled` 를 두고(재귀 — `None` 은 빔, dict/list/tuple/set 은 «안에 채워진 것이 하나라도 있나», 나머지는 `str(...).strip()`), 네 게이트의 사설 `_is_filled` 를 지운다. 실현가능성·측정 게이트에 있던 「왜 재귀로 보나」 주석을 그 한 곳으로 옮긴다. 게이트끼리의 import 는 계층 계약 안이다(`runner` 를 import 하지 않는다)
- [ ] O1: 계보 러너가 `independent_source_count` 를 **dict 덩어리 수**로 계산해 저장·로그에 적는다. 지시문의 JSON 모양에서 그 열쇠를 빼고, 지시문 본문 중 「독립 소스 수를 적으면」처럼 **에이전트에게 그 수를 적게 하는 문장**도 「덩어리를 빠짐없이 나누면 러너가 센다」는 뜻으로 고친다. 계보 게이트의 정수 검사를 뺀다(URL 누락 검사는 그대로). 근거 문서 6번 칸 코드는 손대지 않는다
- [ ] L4 사전: 관찰된 세 문장이 걸리도록 「카탈로그」 포인터를 `POINTER_TERMS` 에 더한다. **조사 결합형**(예: 「카탈로그에」 · 「카탈로그는」 · 「카탈로그가」)으로 좁힐지 명사 전체로 할지는 아래 두 조건을 동시에 만족하는 쪽으로 정하고 이유를 사전 주석에 적는다 — ① O4 의 세 원문이 걸린다 ② 모든 지시문 상수와 `docs/DATA_CATALOG.md` 본문이 통과한다(문구를 바꿔서라도). 판단이 서지 않으면 **사용자에게 묻는다**
- [ ] L4 문구: `runner/feasibility.py` 의 지시문 상수(「카탈로그에 있다」를 금지하는 문장 · 구분선 · JSON 모양의 설명 · `CATALOG_MISSING_NOTE`)와 `docs/DATA_CATALOG.md` 본문, `SKILL.md` 실현가능성 절의 해당 표현을 새 사전에 걸리지 않게 고친다. **뜻은 바꾸지 않는다** — 「그 목록을 가리키지 말고 내용을 풀어 적으라」는 지시는 남긴다. 지시문이 자기가 금지한 표현을 쓰면 예시가 된다는 것이 기존 `test_prompt_selfcontained.py` 의 이유다
- [ ] O4: 세 문장을 **가리키지 않고 사실만** 적는 문장으로 바꾼다(예: 「카탈로그에 실측 없음」 → 「이 파이프라인이 실측한 기록 없음」 류). 바꾼 전후 원문을 진행 로그에 남긴다. `runs/` 의 같은 문장은 **고치지 않는다**
- [ ] O4 확인 필요: `dossier/20260915_spinoff-buy-listing.md` 33행 · 202행의 「이 스킬」 두 곳도 같은 성질이다(자립성 게이트 도입 «전» 문서). **포함할지 사용자에게 묻고** 답을 진행 로그에 남긴다
- [ ] Phase 0 의 B5 · B6 · O1 · L4 테스트 그린

---

### Phase 4 — 구조: 계층 위반 해소와 타입 억제 제거 (O3 · O2)

**작업 내용**:

- [ ] O3: `StepFailed` 를 `agent/invoke.py`(`AgentResult` 와 같은 모듈 — 이 예외는 호출 계층이 올리고 `spent: AgentResult | None` 을 나른다)로 옮긴다. `runner/steps.py` 는 그것을 import 해 `StepQualityFailed` 의 부모로 쓰고, `TYPE_CHECKING` 블록을 지운다. 참조하는 곳(2026-09-26 기준 src 11개 파일 · tests 5개 파일)을 **새 자리에서 import** 하도록 바꾼다 — `steps` 를 거친 재노출에 기대지 않는다
- [ ] O3 이름: 호출 계층에 「Step」이 붙은 이름이 남는 것(계약: agent 는 어느 단계가 자기를 쓰는지 몰라야 한다)을 이번에는 **이름 그대로 둔다** — 개명은 diff 가 두 배다. 바꾸고 싶으면 사용자에게 묻는다
- [ ] O2: `tests/test_agent_invoke.py` 의 `_command` 헬퍼를 명시적 키워드 인자(`session_id: str` · `budget_usd: float` · `tools` · `json_schema`)로 · `tests/test_gate_urls.py` 의 `HTTPError(..., {}, None)` 을 `hdrs=email.message.Message()` 로 · 274행은 억제만 지운다. `# type: ignore` 8건 제거
- [ ] O2 확인: `pyrightconfig.json` 의 tests 환경에서 `reportArgumentType` 를 **잠시 켠 사본**으로 두 파일을 검사해 0 errors 인지 본다(설정 자체는 바꾸지 않는다 — 결과만 진행 로그에)
- [ ] Phase 0 의 O3 테스트 그린

---

### 마지막 Phase — 재검증·문서 정리·최종 검증

**작업 내용**

> 🔴 **`/commit` 이 «맨 마지막»인 것은 의도다.** 그 스킬은 「후보 뒤에는 아무것도 덧붙이지 말 것」으로
> 끝나므로 **호출하는 순간 그 턴이 거기서 닫힌다.** 중간에 두면 뒤에 적힌 항목이 그 벽 너머에 남는다 —
> 실제로 두 번 그렇게 샜다(`[실측] 2026-09-14` 후보를 계획서에 안 옮김 · `2026-09-16` 옮기고 체크박스를 안 닫음).
> **체크박스와 상태를 먼저 확정하고, 커밋 후보를 마지막에 만든다.**

- [ ] 필요한 문서 업데이트 (`docs/COMMANDS.md` 변경 없음 — DoD 의 문서 줄대로)
- [ ] 재현 절차 1 · 2 를 다시 돌려 **재현되지 않음**을 진행 로그에 원문으로
- [ ] **독립 재검증** — 서브에이전트(대화 맥락 없음)에게 이 계획서 경로와 「G1 ~ G10 이 미커밋 diff 에서 실제로 충족됐는지, 비목표를 넘은 변경이 없는지」를 맡기고 결과를 진행 로그에. 서브에이전트는 사용자에게 묻지 못하므로 **판정만** 받고 수정은 이 세션이 한다
- [ ] 진행 로그에 **변경 파일 목록**(경로 · 한 줄 요약)과 **다음 계획서가 알아야 할 것**(새로 생긴 주석 · 옮긴 심볼 · 예상과 달랐던 것)을 남긴다
- [ ] 자동 포맷 적용 (`poetry run black .`)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [ ] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      `/commit` 은 계획서를 모르고 「후보 뒤에 아무것도 덧붙이지 말 것」으로 끝나므로,
      **대화에만 내면 그 절이 빈 채로 남는다.** 체크박스 갱신이 diff 에 더 들어가지만
      커밋 메시지의 내용을 바꾸지 않는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서를 지킨다 — 리뷰에서 고치면 코드가 바뀌므로 품질 검증이 마지막 관문이어야 한다.
> **버그가 0 인 회차에서 끝낸다.** 2회차에도 버그가 나오면 사용자에게 보고하고 3회차 여부를 묻는다 —
> 「그 외」는 목록만 남기고 고치지 않는다. `/impl-plan` 의 「코드 리뷰」 절이 SoT 다.

- [ ] `/code-review xhigh` **1회차** (발견 \_\_건 — 버그 \_\_ · 그 외 \_\_ · 조치: \_\_)
- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=\_\_, skipped=\_\_)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다.**
> 계획서를 쓰는 시점에는 diff 가 없어 여기 적는 것은 전부 추측이고,
> **추측으로 적은 줄은 그대로 나간다.** 형식·문체 규칙은 `/commit` 이 정한다.

- [ ] (미작성 — `/commit` 을 실행하고 후보 5개를 **이 자리에** 번호 붙은 줄로 옮긴 뒤 이 줄을 지운다)

## 7) 리스크(Risks)

- **B2 판정 변경이 기존 폴더의 누적을 줄인다** — 한도로 끝난 회차가 빠지므로 「막힘」이 늦어질 수는 있어도 앞당겨지지 않는다. 계약 테스트 (a) ~ (e) 로 고정
- **B1 정규화가 기존 원장 비교를 바꿀 수 있다** — 현재 원장에 연속 공백·탭 주장 0건([확인])이라 기존 줄은 불변. 읽기·쓰기·비교 세 자리를 한 함수로 묶어 한쪽만 바뀌는 일을 막는다
- **L4 사전 오탐** — 막는 목록이라 계통 오탐은 3회차 뒤 후보를 걷는다(`gate/selfcontained.py` 머리 주석). 조건 ① ② 를 테스트로 고정하고, 좁힐지 넓힐지는 근거와 함께 정한다
- **L4 문구 변경이 에이전트 행동을 바꾼다** — 지시의 뜻은 유지하고 표현만 바꾼다. 효과는 다음 회차들의 산출물에서만 드러난다(이번에 재지 않는다)
- **O3 import 이동 누락** — 옮긴 뒤 옛 경로 import 가 남으면 `ImportError` 로 즉시 드러난다(조용히 새지 않는다). 계약 테스트가 역방향 import 를 막는다
- **O1 이 계보 게이트의 한 갈래를 없앤다** — 「출처를 빠뜨리지 않았나」 검사는 그대로라 게이트의 목적(누락 막기)은 유지된다
- **이 세션은 WSL** 이고 예약 회차는 mac 에서 돈다. mac 이 이 변경을 받는 것은 사용자가 커밋·pull 한 뒤다 — 편집 도중의 코드가 예약 회차에 섞이지 않는다

## 8) 메모(Notes)

- **착수 전 확인**: 이 계획서를 만든 세션의 미커밋 변경(`docs/PROMPT_next_phase.md` 삭제 · `docs/INDEX.md` 한 줄 · `docs/OPERATIONS.md` 의 WSL 결정 문단 · 이 계획서와 다음 계획서)이 **먼저 커밋돼 있어야** `/code-review`(미커밋 diff 전체를 봄)가 이 계획서의 변경만 본다. 안 돼 있으면 사용자에게 먼저 커밋을 요청한다
- 이 계획서의 근거가 된 전수 분석 결과는 대화에만 있었다. 위 「현재 문제점」 표가 그 요약이며 **자리 · 증상 · 근거 등급**을 담았다 — 줄 번호는 함수 이름으로 다시 찾는다
- 패스한 항목 목록은 「비목표」에 있다 — 다시 제안하지 않는다
- 다음 계획서: [PLAN_docs_consolidation.md](PLAN_docs_consolidation.md)

### 진행 로그 (KST)

- 2026-09-26 11:59: 계획서 작성. 전수 분석 결과 중 사용자가 「무조건 진행」으로 정한 버그(B1 ~ B8 · L4 · L5)와 선택 항목 넷(O1 ~ O4)을 범위로 잡았다. B1 · B2 · O2 는 작성 세션에서 재현을 마쳤다(위 재현 절차 · 표)

---

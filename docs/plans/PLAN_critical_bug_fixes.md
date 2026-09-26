# Implementation Plan: 치명 버그 수정 — 원장 무결성 · 막힘 판정 · 진입점 · 게이트 · 자립성

> 작성/운영 규칙(SoT): `/impl-plan` 스킬(`~/.claude/skills/impl-plan/SKILL.md`)을 반드시 참고하세요.  
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 해당 스킬을 포인터로 두고 준수합니다.)

**상태**: ✅ Done

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
**마지막 업데이트**: 2026-09-26 17:04
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

- [x] G1 (B1): 원장이 에이전트가 낸 한 줄 주장의 **줄바꿈·빈 값**으로 깨지지 않는다 — 한 번 담으면 한 줄, 같은 주장은 중복으로 걸러지고, 표시 변경이 그 줄을 찾는다
- [x] G2 (B2): 「같은 단계 3회차 연속 막힘」 판정이 **그 회차의 «마지막» 실패 갈래**로 센다 — 한도·인증·예산으로 끝난 회차는 세지 않는다
- [x] G3 (B3): 잘못된 `--budget-usd`(0 이하 · `nan` · `inf`)는 **돌기 전에 종료 코드 5** 로 거부된다
- [x] G4 (B4·L5): 탐색 호출의 비용이 원장 기록 도중의 예외와 무관하게 결정 로그에 남고, 상한으로 잘린 후보도 「버렸다」로 남는다
- [x] G5 (B7·B8): 자격증명 검사가 **실제로 쓴 원장 폴더**를 보고, 잠금 충돌 사유가 어느 잠금인지 오도하지 않는다
- [x] G6 (B5·B6): 네 게이트의 「채워짐」 판정이 하나로 같고, 근거 문서의 「대상 시장」에 파이썬 표기가 새지 않는다
- [x] G7 (L4·O4): 근거 문서가 저장소 안 데이터 카탈로그를 가리키는 문장을 자립성 게이트가 막고, 이미 나간 근거 문서 3장의 그 문장을 고친다
- [x] G8 (O1): 6번 칸의 「복제를 뺀 독립 소스 수」를 에이전트가 적지 않고 **러너가 덩어리 수로 센다**
- [x] G9 (O3): `agent` 계층이 `runner` 를 import 하지 않는다 — `StepFailed` 를 `agent` 로 옮기고 `TYPE_CHECKING` 우회를 없앤다
- [x] G10 (O2): 테스트의 `# type: ignore` 8건을 **인자 타입을 맞춰** 없앤다

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

- [x] G1 ~ G10 이 모두 충족됐다 (각 Phase 의 체크리스트)
- [x] 재현 절차 1 · 2 를 수정 후 다시 돌려 **재현되지 않음**을 진행 로그에 원문으로 남겼다
- [x] 회귀/신규 테스트 추가 (Phase 0 의 계약 테스트가 전부 그린)
- [x] **독립 재검증** 기록 — 작업 맥락을 물려받지 않은 서브에이전트가 이 계획서의 G1 ~ G10 과 미커밋 diff 를 대조한 결과 (마지막 Phase)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` 변경 없음 · `.claude/skills/dossier-research/SKILL.md` 변경 있음(L4 문구) · `docs/DATA_CATALOG.md` 변경 있음(L4 문구) · `src/research_lab/CLAUDE.md` 변경 없음(O3 로 import 방향 규칙이 «참»이 될 뿐) · 루트 `CLAUDE.md` 변경 없음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (위 「사용자 결정」대로 **코드 주석**으로 이관. DESIGN.md 에는 추가하지 않는다)
- [x] 진행 로그에 **다음 계획서가 읽을 «변경 파일 목록»과 참고사항**을 남겼다
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/research_lab/runner/ledger.py` — B1 (정규화 · 빈 값 거부 · 읽기/비교 양쪽 정규화)
- `src/research_lab/runner/cycle.py` — B2 (`_failed_cycles`) · O3 (`StepFailed` 참조)
- `scripts/run_cycle.py` — B3 (`--budget-usd` 타입 함수) · B7 (`_report_secrets` 가 원장 폴더를 넘김) · B8 (사유 문구)
- `src/research_lab/runner/explore.py` — B4 · L5 · B1 (빈 정규형 건너뛰기 · `seen` 정규화)
- `src/research_lab/runner/dossier.py` — B5 · B6 확장(`single_value_reason` 빈 판정 — 2026-09-26 16:41 조정)
- `src/research_lab/gate/filled.py` **(신설)** — B6 공용 「채워짐」 판정
- `src/research_lab/gate/{feasibility,measurement,mechanism,verdict}.py` — B6 (사설 `_is_filled` 제거 · 공용 사용)
- `src/research_lab/gate/{rebuttal,quantified}.py` — B6 확장(반증 게이트의 `not_found_reason` · 정성 표현 게이트의 축 이름 — 2026-09-26 16:41 조정)
- `src/research_lab/gate/secrets.py` — B7 (`scan_roots` 가 원장 폴더를 필수 키워드로 받음 · `LEDGER_DIR` import 제거)
- `src/research_lab/common_constants.py` — **최종 변경 없음** (12:14 에 원장 «파일»로 조정하며 더했다가, 16:57 3회차 리뷰 뒤 원안인 «폴더»로 되돌려 HEAD 와 같다)
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

- [x] B1: 줄바꿈 든 주장을 담으면 원장 항목이 **정확히 1개** · 같은 주장 재담기는 `False` · 그 주장으로 `mark_rejected`/`mark_explored`/`status_of` 가 동작 · 정규형이 빈 주장은 `append` 가 `ValueError` · 탐색 `_store` 는 빈 정규형을 원장에 안 담는다
- [x] B2: (a) 「그 외 → 한도」 회차 3번은 **안 걷힌다**(재현 절차 2) (b) 「그 외」가 상한까지 간 회차는 센다 (c) 품질 실패는 센다 (d) 「그 외 → 성공」은 안 센다 (e) 「그 외 → 품질 실패」는 한 번만 센다
- [x] B3: `--budget-usd` 에 `0` · `-1` · `nan` · `inf` 를 주면 `SystemExit(5)` · `8.0` 은 통과
- [x] B4 · L5: 원장 기록이 예외를 내도 탐색의 비용 줄이 결정 로그에 있다 · 상한을 넘는 후보가 `discarded` 로 남는다
- [x] B5: `market` 이 목록인 실현가능성 산출물로 조립하면 4번 칸에 파이썬 표기(`[`·`'`)가 없다
- [x] B6: 메커니즘·판정 게이트가 `[""]` · `{"k": ""}` · `[[]]` 를 「비었다」로 막는다 (실현가능성·측정의 기존 테스트는 그대로 통과)
- [x] B7: `scan_roots` 결과에 **넘긴 원장 폴더**가 들어 있고 기본 원장 폴더 상수를 쓰지 않는다
- [x] L4: O4 의 세 문장(원문 그대로를 고정값으로)이 새 사전에 걸린다 · 모든 단계의 지시문 상수가 여전히 자립성 게이트를 통과한다(기존 `tests/test_prompt_selfcontained.py`) · **`docs/DATA_CATALOG.md` 본문도 통과한다**(신규 — 러너가 프롬프트에 싣는 입력이라)
- [x] O1: 계보 게이트가 `independent_source_count` 를 요구하지 않는다 · 러너가 저장하는 값이 dict 덩어리 수와 같다
- [x] O3: `research_lab.agent` 아래 어떤 모듈도 `research_lab.runner` 를 import 하지 않는다(소스 문자열 검사 계약 테스트)

**Validation**: 새 테스트가 **의도한 이유로** 빨갛다는 것만 확인한다 (품질 검증은 돌리지 않는다)

---

### Phase 1 — 원장·회차: 상태 무결성 (B1 · B2)

**작업 내용**:

- [x] B1 `canonical_claim`: 공백류(줄바꿈·탭 포함) 연속을 공백 하나로 접고 → 앞머리 백틱 제거 → 앞뒤 공백 제거. **읽는 쪽도 같은 함수를 지나게** `load` 가 정규형으로 읽고, `_rewrite` 의 비교도 정규형끼리 한다(한쪽만 정규화하면 에러 없이 어긋난다 — 파일 머리 주석이 이미 경고한 모양)
- [x] B1 빈 정규형: `append` 는 `ValueError`(외부 입력 검증). 탐색 `_store` 는 호출 «전»에 빈 정규형을 걸러 `discarded`(사유 「주장이 비어 있다」)로 남기고, `seen` 집합도 정규형으로 채운다
- [x] B2 `_failed_cycles`: 한 회차의 «마지막» 실패만 센다 — `kind == quality`(재시도 없음) 이거나 `kind == other` 이면서 `attempt == 그 줄의 max_retries`(상한까지 간 것). 한도·인증·예산으로 끝난 회차는 그 회차의 1번째 시도가 「그 외」였어도 세지 않는다. 주석의 「왜」를 새 규칙에 맞게 고친다(`attempt == 1` 로 좁히던 이유는 사라진다)
- [x] Phase 0 의 B1 · B2 테스트 그린

---

### Phase 2 — 진입점·탐색·자격증명 (B3 · B4 · L5 · B7 · B8)

**작업 내용**:

- [x] B3: `_dossier_count` 와 같은 관용으로 `--budget-usd` 타입 함수를 둔다 — 실수 · 유한 · 0 초과가 아니면 `argparse.ArgumentTypeError`(→ `_Parser.error` → 종료 코드 5). `build_command` 의 `ValueError` 가드는 라이브러리 계약이라 **남긴다**
- [x] B4: 탐색이 응답을 파싱한 «직후» `record_cost` 를 적는다(읽은 것 → 비용 → 원자료 파일 → 원장 순)
- [x] L5: 상한을 넘는 후보를 `discarded`(사유에 상한 이름, 잘린 주장 목록)로 남기고 `proposed` 의 뜻을 주석 없이도 맞게(받은 수 · 본 수를 갈라 적는 등)
- [x] B7: `secrets.scan_roots(run_dir, *, ledger_dir, dossier_path)` — 원장 폴더를 **기본값 없는 키워드**로 받는다(기본값을 두면 부르는 쪽이 빠뜨려도 조용히 돈다). `run_cycle._report_secrets` 가 `args.ledger.parent` 를 넘긴다. `gate/secrets.py` 의 `LEDGER_DIR` import 제거 (12:14 폴더 → 파일 조정 · 16:57 파일 → 폴더 되돌림은 진행 로그)
- [x] B8: 잠금 충돌 사유를 「이미 도는 회차가 원장이나 그 실행 폴더를 잡고 있다」처럼 **어느 잠금인지 단정하지 않는** 문구로(절대경로는 계속 회차 로그에 싣지 않는다)
- [x] Phase 0 의 B3 · B4 · L5 · B7 테스트 그린

---

### Phase 3 — 게이트·조립·자립성 (B5 · B6 · O1 · L4 · O4)

**작업 내용**:

- [x] B5: `_feasibility_section` 의 「대상 시장」을 `_flatten` 으로
- [x] B6: `gate/filled.py` 에 공용 `is_filled` 를 두고(재귀 — `None` 은 빔, dict/list/tuple/set 은 «안에 채워진 것이 하나라도 있나», 나머지는 `str(...).strip()`), 네 게이트의 사설 `_is_filled` 를 지운다. 실현가능성·측정 게이트에 있던 「왜 재귀로 보나」 주석을 그 한 곳으로 옮긴다. 게이트끼리의 import 는 계층 계약 안이다(`runner` 를 import 하지 않는다)
- [x] O1: 계보 러너가 `independent_source_count` 를 **dict 덩어리 수**로 계산해 저장·로그에 적는다. 지시문의 JSON 모양에서 그 열쇠를 빼고, 지시문 본문 중 「독립 소스 수를 적으면」처럼 **에이전트에게 그 수를 적게 하는 문장**도 「덩어리를 빠짐없이 나누면 러너가 센다」는 뜻으로 고친다. 계보 게이트의 정수 검사를 뺀다(URL 누락 검사는 그대로). 근거 문서 6번 칸 코드는 손대지 않는다
- [x] L4 사전: 관찰된 세 문장이 걸리도록 「카탈로그」 포인터를 `POINTER_TERMS` 에 더한다. **조사 결합형**(예: 「카탈로그에」 · 「카탈로그는」 · 「카탈로그가」)으로 좁힐지 명사 전체로 할지는 아래 두 조건을 동시에 만족하는 쪽으로 정하고 이유를 사전 주석에 적는다 — ① O4 의 세 원문이 걸린다 ② 모든 지시문 상수와 `docs/DATA_CATALOG.md` 본문이 통과한다(문구를 바꿔서라도). 판단이 서지 않으면 **사용자에게 묻는다**
- [x] L4 문구: `runner/feasibility.py` 의 지시문 상수(「카탈로그에 있다」를 금지하는 문장 · 구분선 · JSON 모양의 설명 · `CATALOG_MISSING_NOTE`)와 `docs/DATA_CATALOG.md` 본문, `SKILL.md` 실현가능성 절의 해당 표현을 새 사전에 걸리지 않게 고친다. **뜻은 바꾸지 않는다** — 「그 목록을 가리키지 말고 내용을 풀어 적으라」는 지시는 남긴다. 지시문이 자기가 금지한 표현을 쓰면 예시가 된다는 것이 기존 `test_prompt_selfcontained.py` 의 이유다
- [x] O4: 세 문장을 **가리키지 않고 사실만** 적는 문장으로 바꾼다(예: 「카탈로그에 실측 없음」 → 「이 파이프라인이 실측한 기록 없음」 류). 바꾼 전후 원문을 진행 로그에 남긴다. `runs/` 의 같은 문장은 **고치지 않는다**
- [x] O4 확인 필요: `dossier/20260915_spinoff-buy-listing.md` 33행 · 202행의 「이 스킬」 두 곳도 같은 성질이다(자립성 게이트 도입 «전» 문서). **포함할지 사용자에게 묻고** 답을 진행 로그에 남긴다
- [x] Phase 0 의 B5 · B6 · O1 · L4 테스트 그린

---

### Phase 4 — 구조: 계층 위반 해소와 타입 억제 제거 (O3 · O2)

**작업 내용**:

- [x] O3: `StepFailed` 를 `agent/invoke.py`(`AgentResult` 와 같은 모듈 — 이 예외는 호출 계층이 올리고 `spent: AgentResult | None` 을 나른다)로 옮긴다. `runner/steps.py` 는 그것을 import 해 `StepQualityFailed` 의 부모로 쓰고, `TYPE_CHECKING` 블록을 지운다. 참조하는 곳(2026-09-26 기준 src 11개 파일 · tests 5개 파일)을 **새 자리에서 import** 하도록 바꾼다 — `steps` 를 거친 재노출에 기대지 않는다
- [x] O3 이름: 호출 계층에 「Step」이 붙은 이름이 남는 것(계약: agent 는 어느 단계가 자기를 쓰는지 몰라야 한다)을 이번에는 **이름 그대로 둔다** — 개명은 diff 가 두 배다. 바꾸고 싶으면 사용자에게 묻는다
- [x] O2: `tests/test_agent_invoke.py` 의 `_command` 헬퍼를 명시적 키워드 인자(`session_id: str` · `budget_usd: float` · `tools` · `json_schema`)로 · `tests/test_gate_urls.py` 의 `HTTPError(..., {}, None)` 을 `hdrs=email.message.Message()` 로 · 274행은 억제만 지운다. `# type: ignore` 8건 제거
- [x] O2 확인: `pyrightconfig.json` 의 tests 환경에서 `reportArgumentType` 를 **잠시 켠 사본**으로 두 파일을 검사해 0 errors 인지 본다(설정 자체는 바꾸지 않는다 — 결과만 진행 로그에)
- [x] Phase 0 의 O3 테스트 그린

---

### 마지막 Phase — 재검증·문서 정리·최종 검증

**작업 내용**

> 🔴 **`/commit` 이 «맨 마지막»인 것은 의도다.** 그 스킬은 「후보 뒤에는 아무것도 덧붙이지 말 것」으로
> 끝나므로 **호출하는 순간 그 턴이 거기서 닫힌다.** 중간에 두면 뒤에 적힌 항목이 그 벽 너머에 남는다 —
> 실제로 두 번 그렇게 샜다(`[실측] 2026-09-14` 후보를 계획서에 안 옮김 · `2026-09-16` 옮기고 체크박스를 안 닫음).
> **체크박스와 상태를 먼저 확정하고, 커밋 후보를 마지막에 만든다.**

- [x] 필요한 문서 업데이트 (`docs/COMMANDS.md` 변경 없음 — DoD 의 문서 줄대로)
- [x] 재현 절차 1 · 2 를 다시 돌려 **재현되지 않음**을 진행 로그에 원문으로
- [x] **독립 재검증** — 서브에이전트(대화 맥락 없음)에게 이 계획서 경로와 「G1 ~ G10 이 미커밋 diff 에서 실제로 충족됐는지, 비목표를 넘은 변경이 없는지」를 맡기고 결과를 진행 로그에. 서브에이전트는 사용자에게 묻지 못하므로 **판정만** 받고 수정은 이 세션이 한다
- [x] 진행 로그에 **변경 파일 목록**(경로 · 한 줄 요약)과 **다음 계획서가 알아야 할 것**(새로 생긴 주석 · 옮긴 심볼 · 예상과 달랐던 것)을 남긴다
- [x] 자동 포맷 적용 (`poetry run black .`)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] Validation 절에 `/code-review` 와 품질 검증 **실행 결과**를 적는다
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정
- [x] 🔴 **마지막에 `/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      `/commit` 은 계획서를 모르고 「후보 뒤에 아무것도 덧붙이지 말 것」으로 끝나므로,
      **대화에만 내면 그 절이 빈 채로 남는다.** 체크박스 갱신이 diff 에 더 들어가지만
      커밋 메시지의 내용을 바꾸지 않는다. **커밋은 사용자가 한다 — 후보만 낸다**

**Validation**:

> 순서를 지킨다 — 리뷰에서 고치면 코드가 바뀌므로 품질 검증이 마지막 관문이어야 한다.
> **버그가 0 인 회차에서 끝낸다.** 2회차에도 버그가 나오면 사용자에게 보고하고 3회차 여부를 묻는다 —
> 「그 외」는 목록만 남기고 고치지 않는다. `/impl-plan` 의 「코드 리뷰」 절이 SoT 다.

- [x] `/code-review xhigh` **1회차** (발견 9건 — 버그 4 · 그 외 5 · 조치: 버그 3건 수정(원장 정규형 멱등 · 같은 주장 두 줄이면 앞 줄 · 시도 번호 없는 실패 줄 안 셈) + 회귀 테스트 5 · 버그 1건(반증 게이트 `not_found_reason` 의 `[""]` 통과 — 계획 범위 밖 기존 결함)은 사용자 결정 대기 · 그 외 5건은 목록만)
- [x] `/code-review xhigh` **2회차** (발견 9건 — 버그 3 · 그 외 6 · 조치: 규칙대로 멈추고 사용자에게 보고 — 버그 1건(L4 문구가 새 지칭어 「카탈로그 본문」을 만듦)은 이 diff 의 결함, 2건(정성 표현 게이트 축 이름 · 조립부 `single_value_reason`)은 계획 범위 밖 기존 결함)
- [x] `/code-review xhigh` **3회차** (발견 9건 — 버그 3 · 그 외 6 · 조치: 버그 1건(계보 수가 주소 없는 덩어리를 셈) 수정 · 1건(원장 «파일»만 검사해 남은 `원장.md.tmp` 를 못 봄 — B7 조정의 부작용)은 사용자 결정으로 원안(원장 폴더)으로 되돌림 · 1건(반증 러너의 `as_text` 저장)은 계획서 비목표라 목록만)
- [x] `poetry run python validate_project.py` (passed=604, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다.**
> 계획서를 쓰는 시점에는 diff 가 없어 여기 적는 것은 전부 추측이고,
> **추측으로 적은 줄은 그대로 나간다.** 형식·문체 규칙은 `/commit` 이 정한다.

1. 러너 / 원장 · 막힘 판정 · 진입점 · 게이트 · 자립성 치명 버그 일괄 수정
2. 러너 / 원장 줄바꿈 분할과 한도로 끝난 회차의 막힘 오판 수정
3. 러너 / 원장 정규형 멱등화 · 마지막 실패 기준 막힘 판정 · 단계 상한 인자 검증 · 공용 채워짐 판정 · 카탈로그 포인터 사전 확장 · StepFailed 호출 계층 이동
4. 러너 / 멀쩡한 후보가 걷히거나 저장소 밖으로 포인터가 새는 경로 차단
5. 러너 / 근거 문서 자립성과 원장 무결성 보강 및 계층 역방향 import 제거

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
- 2026-09-26 12:14: 실행 세션 착수. 착수 전 확인 — 이전 세션 변경이 스테이징만 돼 있어 사용자에게 커밋을 요청했고 `d5b485d` 로 커밋돼 작업 트리가 깨끗한 것을 확인했다. 계획서의 자리·증상 서술을 현재 코드와 대조해 전부 일치함을 확인했다 — 원장 16줄 중 새 정규형(공백류 접기)으로 달라지는 줄 0 · 비는 줄 0, 과거 결정 로그 11개의 `attempt` 가 있는 실패 줄은 전부 `max_retries` 를 달고 있고 `kind` 가 있으면서 `attempt` 가 없는 줄 0(B2 새 규칙이 과거 폴더에 그대로 맞는다), `StepFailed` 참조 src 11 · tests 5, `runs/` 에서 에이전트가 「카탈로그」를 쓴 곳은 O4 의 세 문장뿐이고 가리키지 않는 용법 0
  - **B7 조정(사용자 승인)**: 계획서의 `args.ledger.parent`(원장 «폴더»)를 원장 «파일»(`args.ledger`)로 바꿨다. 폴더를 넘기면 `--ledger ./x.md` 처럼 저장소 루트의 파일을 줄 때 검사 범위가 저장소 루트가 되어, 테스트 파일의 `sk-ant-` 리터럴에 걸려 회차마다 종료 코드 4 로 끝난다 — `gate/secrets.py` 머리 주석과 `test_scan_scope_excludes_the_repository_root` 가 막으려던 모양이다. 기본 원장 폴더에는 `원장.md` 와 빈 `lock` 뿐이라 파일을 넘겨도 기본 경우의 범위는 같다. 그래서 `common_constants.py` 의 `WRITABLE_ROOTS` 주석 한 줄이 변경 파일에 더해졌다
  - **O4 확인 필요 → 포함(사용자 결정)**: `20260915_spinoff-buy-listing.md` 33행 · 202행의 「이 스킬」 두 곳도 이번에 고친다
  - **L4 사전 형태 → 조사 결합형 · 조사는 에 · 는 · 가 · 를 · 의(사용자 결정)**: 명사 전체를 막으면 지시문과 카탈로그 본문이 그 이름을 못 쓰게 되어 다른 이름으로 불러야 하고, 에이전트는 그 새 이름으로 가리키기 시작해 사전 밖으로 샌다(2026-09-16 에 에이전트가 프롬프트의 말을 되돌려 쓴 실측 — `tests/test_prompt_selfcontained.py` 머리). 조사는 실제 산출물에 나온 둘(에 · 는)에 **에이전트가 읽는 글(지시문 · 카탈로그 본문 · 리서치 스킬)에 적혀 있던 형태**(가 · 를 · 의)를 더했다
- 2026-09-26 12:23: Phase 0 완료. 대상 13개 파일을 돌려 **27 failed · 225 passed** — 빨간 것은 전부 의도한 이유였다(원장 항목 2 == 1 · 중복 재담기 True · 표시 조회 None · `ValueError` 안 오름 · 탐색 비용 줄 [] · 상한 초과 기록 없음 · 한도로 끝난 회차에 후보가 걷힘 · 회복한 회차의 실패를 1 로 셈 · `--budget-usd` 에 `SystemExit` 안 오름 · 검사 범위에 기본 원장 폴더 · `scan_roots` 에 `ledger_path` 키워드 없음 · 「대상 시장」에 `['국내', '미국']` · `['']` 통과 · 카탈로그 문장 안 걸림 · 계보 게이트의 정수 검사 · 저장된 수 5 · 지시문에 열쇠 있음 · `invoke.py: research_lab.runner.steps`)
  - **초록인 채 넣은 계약 테스트**: B2 (b) 「그 외」 상한까지 간 회차 세기 · (e) 「그 외 → 품질 실패」 한 번 세기(지금 규칙도 우연히 맞는다 — 새 규칙이 깨지 않게 고정) · (c) 품질 실패 세기는 기존 `test_a_stuck_candidate_is_blocked_on_the_third_cycle` 이 덮는다 · L4 카탈로그 본문 통과(`test_the_data_catalog_passes_the_gate_it_is_fed_into`)는 사전을 넓히는 순간 빨개지는 것이 정상이며 Phase 3 에서 문구를 고쳐 초록으로 되돌린다 · 조사 없이 이름만 부르는 말은 안 걸린다(`test_naming_the_catalog_without_a_particle_is_not_caught` — 조사 결합형을 고른 이유를 고정)
  - **기존 테스트를 고친 것**: `test_gate_lineage.py::test_missing_independent_source_count_is_blocked` → `test_the_gate_does_not_ask_for_the_independent_source_count`(계약이 뒤집힘) · `test_rebut_and_lineage.py::test_lineage_does_not_probe_when_a_cheaper_gate_already_blocked` 는 정수 검사가 없어지므로 «출처를 빠뜨린» 응답으로 값싼 게이트를 막게 바꿨다(의도 불변) · `test_gate_secrets.py` 의 `scan_roots` 호출 다섯 곳에 `ledger_path` · 「원장 폴더가 들어 있다」 단언 둘을 「원장 파일」로
  - **새 파일**: `tests/test_layer_direction.py` — O3 계약. 계층 계약이 agent 와 gate 를 함께 묶고 B6 에서 gate 끼리의 import 가 새로 생기므로 **gate 도 같이** 검사한다(ast 로 import 를 모아 `TYPE_CHECKING` 블록 안의 것까지 잡는다). `tests/` 는 `docs/INDEX.md` 등록 대상이 아니다(`tests/test_index.py` 의 `REGISTERED_DIRS = ("docs",)`)
- 2026-09-26 16:06: Phase 1 ~ 3 완료. 각 Phase 끝에 해당 테스트 파일을 돌려 그린 확인 — Phase 1 175 중 173 passed(남은 2 는 Phase 2 몫인 B4 · L5) · Phase 2 155 passed · Phase 3 194 중 193 passed → 아래 「지시문 부분 일치」를 고친 뒤 36 passed(재실행분)
  - **B1**: `ledger.canonical_claim` 이 공백류를 접는다(`" ".join(claim.split())` → 앞머리 백틱 → 앞뒤 공백). `load` · `_rewrite` 의 비교 · `append` 가 모두 이 함수를 지난다. `append` 는 정규형이 비면 `ValueError`. `load` 가 정규형을 돌려주게 되어 `next_unexplored` 의 `canonical_claim(entry.claim)` 은 필요 없어져 `entry.claim` 으로 줄이고 그 자리 주석의 전제(「`load` 는 앞뒤 공백만 뗀다」)를 고쳤다. 탐색 `_store` 는 정규형으로 비교하고, 비는 주장은 에이전트가 낸 글자 그대로 `discarded`(사유 「주장이 비어 있다」, `claims=[...]`)로 남긴다 — `_store` 의 반환이 4-튜플이 됐다(기존 관용이 튜플이라 따랐다)
  - **B2**: `cycle._failed_cycles` 가 «그 회차의 마지막 실패 줄»만 센다 — `not failures.should_retry(kind) or attempt == 그 줄의 max_retries`. 재시도 여부를 `failures.should_retry` 한 곳에서 읽어 「무엇을 재시도하나」를 두 벌로 두지 않았다. `COUNTED_FAILURE_KINDS` 는 그대로
  - **B3**: `scripts/run_cycle.py` 에 `_step_budget` 타입 함수(`_dossier_count` 관용) — `float` 변환 실패 · `not math.isfinite` · `<= 0` 이면 `ArgumentTypeError`. `import math` 추가
  - **B4 · L5**: 탐색 순서를 「읽은 것(READ) → 비용 → 원자료 파일 → 원장」으로. 상한 밖은 `run` 에서 잘라 `discarded`(사유 「한 회차에 담는 후보 상한(MAX_CANDIDATES=15)을 넘었다」, `claims=[에이전트가 낸 글자]`)로 남기고, `judged` 줄에 `proposed`(받은 수)와 **`considered`(본 수, 새 열쇠)** 를 갈라 적는다. `_store` 는 자르지 않는다(부르는 쪽이 자른 목록을 넘긴다)
  - **B7**: `secrets.scan_roots(run_dir, *, ledger_path, dossier_path=None)` · `run_cycle._report_secrets(run_dir, ledger_path)` · `LEDGER_DIR` import 제거 · `common_constants.WRITABLE_ROOTS` 주석
  - **B8**: 사유 문구 「이미 도는 회차가 원장이나 실행 폴더를 잡고 있어 시작하지 못했습니다 — {폴더 이름}」 + 그 자리에 「어느 잠금인지 단정하지 않는다」 주석. **같은 오도가 `cycle.run_cycle` 독스트링 Raises 에도 있어 함께 고쳤다**(「원장이나 같은 실행 폴더를」)
  - **B5**: `_feasibility_section` 의 「대상 시장」을 `_flatten` 으로
  - **B6**: `gate/filled.py`(신설) 의 `is_filled` 로 네 게이트의 사설 `_is_filled` 를 걷었다. **계획서의 「재귀」를 «명시적 스택»으로 구현했다** — 뜻(None 빔 · 컨테이너는 안에 채워진 것이 하나라도 있나 · 나머지는 `str().strip()`)은 같다. 재귀판은 한 겹마다 프레임 둘(함수 + `any` 의 생성기)을 써 json 이 읽어 낸 깊이의 절반쯤에서 `RecursionError` 를 낼 수 있고, 게이트는 어떤 입력에도 예외를 올리지 않는다는 계약(§5)과 같은 파일 `_as_text` 의 「파이썬 재귀로 훑지 않는다」 관용이 이미 있었다. 이를 고정하는 **새 테스트 파일 `tests/test_gate_filled.py`**(내용 있음 · 빈 값만 든 컨테이너 · 5,000겹 중첩에서 예외 없음)를 더했다. `gate/measurement.py` `_distinct` 독스트링의 `_is_filled` 를 `filled.is_filled` 로
  - **O1**: 계보 러너가 `independent_source_count = dict 덩어리 수` 로 세어 저장 · 로그에 적는다. 지시문 JSON 모양에서 그 열쇠를 빼고 「빠뜨린 채 독립 소스 수를 적으면」 → 「빠뜨리면 독립 소스 수가 통째로 틀리고」 + 「따로 적지 않는다 — 덩어리 수가 곧 그 수」. 계보 게이트의 정수 검사와 `KEY_INDEPENDENT_SOURCE_COUNT` 상수(내 변경으로 생긴 orphan)를 걷고 머리 주석 · 누락 사유 문구를 맞췄다. **리서치 스킬 계보 절 225행도 같은 전제(「독립 소스 수를 적으면」)라 같은 뜻으로 고쳤다** — 지시문과 스킬이 갈리면 에이전트가 어느 쪽을 따를지 모른다
  - **L4 사전**: `POINTER_TERMS` 에 「카탈로그에 · 는 · 가 · 를 · 의」와 그 이유 주석(조사 결합형인 이유 · 조사를 고른 기준). 문구 조정 — 지시문 `PROMPT` 의 「카탈로그에 있다」 인용 → 「답에서 아래 목록을 가리키지 마세요 — 「그 문서를 보라」처럼 적지 않습니다」 · `CATALOG_MISSING_NOTE` 「데이터 카탈로그를」 → 「데이터 카탈로그 본문을」 · `docs/DATA_CATALOG.md` 20 · 24 · 253행(「카탈로그에 있다」 인용 → 「이 문서를 가리키지 않습니다」, 「이 카탈로그는/가」 → 「이 문서는/가」) · 리서치 스킬 실현가능성 절 4곳. 스킬의 「이렇게 적지 마세요」 표(금지 표현을 예시로 싣는 자리)는 손대지 않았다 — `tests/test_prompt_selfcontained.py` 머리가 같은 이유로 스킬을 검사에서 뺐다
  - **기존 테스트를 하나 더 고쳤다**: `tests/test_feasibility.py::test_prompt_demands_self_standing_prose` 가 지시문에 「카탈로그에 있다」가 «들어 있기를» 단언하고 있었다 — 새 사전과 정면으로 부딪힌다. 요구 자체(목록을 가리키지 말고 내용을 풀어 적으라)를 새 문구로 확인하게 바꿨다
  - **예상과 달랐던 것 ① 지시문 부분 일치**: 새로 쓴 문장 「이 산출물**이 저장소** 밖으로」가 「이 저장소」에 부분 일치로 걸렸다(`test_every_prompt_passes_the_gate_it_enforces[feasibility]`). 원래 구조 「이 산출물은 저장소 밖으로」로 되돌려 풀었다. **사전 매칭은 조사 경계를 모르므로 지시문을 고칠 때는 문장 단위로 다시 돌려 봐야 한다**
  - **예상과 달랐던 것 ② 계획서 전제 하나가 틀렸다**: 「자립성 게이트가 생긴 뒤 나간 3장」 — git 이력으로 보면 `gate/selfcontained.py` 는 `0ebaa8f` 2026-09-15 22:34 에 들어왔고 `20260915_exec-cluster-buy.md` 는 `5cd0864` 같은 날 14:54 로 **게이트보다 먼저**다. 게이트 뒤에 나간 것은 `20260916_sell-in-may.md`(`163b70e` 09-16) · `20260919_ipo-lockup-short.md`(`8f1f90e` 09-23) 두 장. 고칠 대상이라는 결론은 같으므로 범위는 그대로 두고, 사전 주석 · 테스트 주석에 「게이트 뒤」라는 말을 쓰지 않았다
  - **O4 전후 원문** (`runs/` 의 같은 문장은 고치지 않았다):
    - `20260915_exec-cluster-buy.md` 242행 — 전 「…어디서 받을 수 있는지(카탈로그에 실측 없음)」 → 후 「…어디서 받을 수 있는지(이 파이프라인이 실측한 기록 없음)」
    - `20260916_sell-in-may.md` 266행 — 전 「…실측된 적이 없다 — 카탈로그는 ETF 전수조회가 된다고만 확인했지 이 특정 상품군으로 실측하지는 않았다」 → 후 「…실측된 적이 없다 — ETF 전수조회가 된다는 것까지만 확인됐고 이 특정 상품군으로 실측하지는 않았다」
    - `20260919_ipo-lockup-short.md` 83행 — 전 「…못 빌릴 수 있다는 뜻이며, 이는 카탈로그에 없어 이번에 확인한 내용이다.」 → 후 「…못 빌릴 수 있다는 뜻이며, 이는 기존에 실측된 자료가 없어 이번에 확인한 내용이다.」
    - `20260915_spinoff-buy-listing.md` 33행(2번 칸) — 전 「이는 이 스킬이 예로 든 「신호가 연 1회라 20년을 재도 20건」과 사실상 같은 모양이다.」 → 후 「이는 「신호가 연 1회면 20년을 재도 20건이라 시기를 쪼갤 수 없다」는 표본 부족과 사실상 같은 모양이다.」 (리서치 스킬의 「이렇게 적지 마세요」 표가 권하는 대체 문장 그대로)
    - `20260915_spinoff-buy-listing.md` 202행(9번 칸) — 전 「이 스킬에서 준 국내 반증(2016년 이후 45건 중 76% 하락, 다음뉴스 2023-06-25)은」 → 후 「8번 칸에 실린 국내 반증(…)은」 — 그 자료는 같은 문서 8번 칸 표의 첫 줄이다(문서 «안»을 가리키는 것은 자립을 깨지 않는다)
    - 고친 뒤 `dossier/*.md` 8장 전부를 새 사전으로 훑어 걸리는 줄 0
- 2026-09-26 16:09: Phase 4 완료 — 대상 7개 파일 157 passed
  - **O3**: `StepFailed` 를 `agent/invoke.py`(`AgentResult` 바로 아래)로 옮기고 「이 계층이 정의한다 — 러너에 두면 의존 방향이 뒤집힌다」 한 단락을 더했다. 독스트링의 「분류는 `failures.classify` 가 하고」 → 「분류는 러너가 하고」(호출 계층이 러너 모듈 이름을 알 이유가 없다). `DESIGN.md §11.14` 포인터는 옮긴 문장 그대로 남겼다 — 다음 계획서가 grep 으로 걷는다. `runner/steps.py` 는 `from research_lab.agent.invoke import StepFailed` 로 `StepQualityFailed` 의 부모를 삼고 `TYPE_CHECKING` 블록을 지웠다. **실제로 기호를 쓰는 곳은 src 3개(`agent/invoke.py` · `runner/steps.py` · `runner/cycle.py`)였다** — 계획서의 「src 11개」는 독스트링의 `Raises: StepFailed:` 언급까지 센 수이고 그 8개는 이름이 그대로라 손대지 않았다. `cycle.py` 는 새 자리에서 import(`except` · `_record_spent` 타입 · `run_cycle` 독스트링의 `steps.StepFailed`). tests 5개도 새 자리에서 import(`test_runner_cycle.py` 는 이미 가진 `invoke` 모듈로 `invoke.StepFailed(` 10곳)
  - **O3 이름**: 계획서대로 「Step」이 붙은 이름을 그대로 두었다
  - **O2**: `_command` 를 명시적 키워드 넷(`session_id` · `budget_usd` · `tools` · `json_schema`)으로 · `HTTPError(..., {}, None)` 6곳을 `email.message.Message()` 로 · 274행은 억제만 지웠다. `# type: ignore` 는 저장소 전체에서 0건
  - **O2 확인**: 저장소 설정은 건드리지 않고 스크래치 폴더에 `pyrightconfig.json` 사본을 만들어 tests 환경의 `reportArgumentType` · `reportUnnecessaryTypeIgnoreComment` 를 `error` 로 켜고 두 파일만 검사 → `Found 2 source files` · **0 errors**. 대조군으로 HEAD 의 두 파일에서 `# type: ignore` 만 지운 사본을 같은 설정으로 돌리면 **10 errors**(`_command` 한 줄에서 `object` → `str`/`float`/`Sequence[str]`/`str | None` 4 · `hdrs` 에 `dict` 6) · 274행은 오류 없음 — 계획서의 재현과 같다. [주의] 첫 시도에서 include 에 절대경로를 주자 pyright 가 「not relative」로 무시해 **0 files 로 0 errors** 가 나왔다. 설정 사본 기준 상대경로로 다시 돌렸다 — 「0 errors」는 `Found N source files` 와 함께 읽어야 한다
- 2026-09-26 16:11: **재현 절차 1 · 2 재실행 — 재현 안 됨.** 스크래치 스크립트로 위 절차를 그대로 돌렸다(절차 2 의 「첫 호출은 그 외 · 이후는 한도」는 «매 회차»의 첫 호출로 읽었다 — 그래야 수정 전에 「세 회차 모두 갈래 limit 인데 3회차에 걷힘」이 나온다). 출력 원문:

  ```
  == 재현 절차 1 (B1)
  append 1: True
  append 2: False
  load: [('x', '소형주를 12월 말에 산다 - [ ] 주입된 후보')]
  mark_rejected: ok -> rejected
  append ``` 1: ValueError 정규 형태가 빈 주장은 원장에 담을 수 없습니다: '```'
  append ``` 2: ValueError 정규 형태가 빈 주장은 원장에 담을 수 없습니다: '```'
  load p2: [] · 파일 존재: False
  == 재현 절차 2 (B2)
  회차 1: 갈래=limit blocked_claim=None closed=None
  회차 2: 갈래=limit blocked_claim=None closed=None
  회차 3: 갈래=limit blocked_claim=None closed=None
  원장 표시: unexplored
  막힌 회차 수: 0
  ```
- 2026-09-26 16:24: **독립 재검증 결과**(대화 맥락 없는 서브에이전트, 판정만) — G2 ~ G10 충족, **G1 부분 충족**. 그 에이전트가 직접 돌린 검사: pytest 전체 595 passed · pyright 0 errors · ruff 통과 · black 변경 없음 · 위 스크래치 pyright 설정 0 errors(2 files). 비목표 침범 없음. 진행 로그에 없던 변경으로 `tests/test_run_cycle_entrypoint.py::test_the_ledger_actually_used_is_scanned`(진입점 수준 B7 테스트)와 `tests/test_gate_lineage.py` 머리 주석 수정을 짚었다 — 둘 다 이 계획서의 변경이다. G1 이 부분 충족인 이유는 아래 코드 리뷰 ④ 와 같은 결함
- 2026-09-26 16:24: **`/code-review xhigh` 1회차 — 발견 9건**(버그 4 · 그 외 5)
  - **버그 — 고침** (각각 먼저 빨간 테스트를 쓰고 고쳤다. 5건 빨강 → 수정 후 관련 4개 파일 130 passed)
    - ④ `ledger.canonical_claim` 이 **멱등이 아니었다**(제 변경의 회귀) — `.lstrip("`").strip()` 은 「` `abc」를 한 번에 「`abc」로, 두 번에 「abc」로 만든다. 읽기가 쓴 글자를 다시 이 함수에 통과시키므로 쓴 형태와 읽은 형태가 갈려, 그 주장은 중복으로 안 걸리고 기각이 `UnknownCandidateError` 를 냈다(탐색이 「그 외」로 재시도하며 줄을 또 쌓는 B1 의 증상 그대로). `" ".join(claim.split()).lstrip("` ")` 로 백틱과 공백을 섞인 채 한꺼번에 떼고 「두 번 지나도 같아야 한다」 주석. 테스트: `test_the_canonical_form_does_not_change_when_applied_again` · `test_a_claim_starting_with_mixed_backticks_and_spaces_round_trips` · 빈 값 테스트에 「` `」 추가
    - ① 같은 정규형의 줄이 둘이면 `next_unexplored` 는 «뒤» 안 판 줄을, `status_of`·`_rewrite` 는 «앞» 줄을 봐 **같은 후보를 회차마다 다시 꺼냈다**(뒤 단계는 「이미 판 것」으로 건너뛰고 표시는 앞 줄에만). 글자까지 같은 중복 줄에서는 원래도 났고, B1 이 공백만 다른 줄까지 같은 주장으로 묶어 넓혔다. `next_unexplored` 가 앞에서 본 주장의 뒤 줄을 건너뛰게 했다(「앞 줄이 그 후보」). `load` 에서 걸러 내는 안은 버렸다 — 걸러진 줄의 식별자가 `_resolve_identifier` 의 「이미 쓴 이름」에서 빠져 폴더명이 겹칠 수 있다. 테스트: `test_a_later_row_with_the_same_claim_is_not_picked`
    - ⑥ `_failed_cycles` 의 `attempt == max_retries` 가 두 열쇠가 다 없을 때 `None == None` 으로 참이 되어 «센다»로 떨어졌다(옛 `attempt == 1` 은 안 셌다). 시도 번호가 정수가 아닌 줄은 세지 않게 했다. 테스트: `test_a_failure_line_without_an_attempt_is_not_counted`
    - 실제 원장 16줄은 새 정규형에서도 옛 읽기와 다른 줄 0 · 정규형이 겹치는 줄 0
  - **버그 — 사용자 결정 대기**: ⑤ `gate/rebuttal.py` 가 `not_found_reason` 을 `str(...).strip()` 으로 봐 `[""]`·`{"k": ""}` 를 통과시킨다(반증 단계엔 JSON 스키마가 없다). 조립부는 그 값을 `as_text` 로 찍어 8번 칸에 「**0건.** ['']」가 실릴 수 있다. B6 과 같은 성질이지만 **계획서 B6 은 `_is_filled` 를 가진 네 게이트만 짚었고** 이 게이트는 이 diff 가 건드리지 않은 기존 결함이라, 수술적 변경 원칙상 고칠지는 사용자가 정한다
  - **그 외 — 목록만**(고치지 않음)
    - ② 계보 수가 «dict 덩어리 수»라 `{}` 덩어리나 원본이 같은 두 덩어리를 그대로 센다 — 계획서가 정한 정의이고, 덩어리를 잘못 나눈 것은 에이전트의 잘못이라 러너가 판정하지 않는다(판정하면 또 하나의 판단자가 된다). 옛 방식(에이전트가 수를 적음)도 같은 응답을 막지 못했다
    - ③ 조사 결합형 사전이 외부 카탈로그를 말하는 정상 문장(「FRED 데이터 카탈로그에서 받는다」)과 출처 **제목**에 든 「카탈로그의」까지 막는다 — 사용자가 고른 L4 (b) 의 오탐 비용이다. 제목은 에이전트가 고칠 수 없어 같은 자리에서 3회차면 후보가 걷힌다. `runs/` 전체에서 가리키지 않는 용법은 아직 0건
    - ⑦ `invoke.build_command` 의 가드는 여전히 `<= 0` 만 봐 `nan`·`inf` 가 지나간다 — 진입점을 거치지 않는 호출자는 지금 없다. 계획서는 그 가드를 「남긴다」고만 정했다
    - ⑧ `tests/test_layer_direction.py` 가 `from research_lab import runner` 와 상대 import(`from ..runner import steps`)를 못 잡는다 — 저장소는 지금 절대 import 만 쓴다
    - ⑨ 새 주석·독스트링에 개수가 있다(「아래 다섯은 … 세 장이」 · `test_gate_filled.py` 머리의 「네 게이트」) — 전역 「구체적 수치를 적지 않는다」와 어긋난다
- 2026-09-26 16:39: **`/code-review xhigh` 2회차 — 발견 9건**(1회차 ① ~ ⑨ 제외 · 버그 3 · 그 외 6). `/impl-plan` 규칙대로 **여기서 멈추고 사용자에게 보고**한다
  - **버그 — 이 diff 의 결함**: R2-1 L4 문구 조정이 사전에 걸리던 말을 **사전에 없는 새 지칭어**로 바꿨다 — 스킬 「카탈로그에 없는 축은」 → 「카탈로그 **본문에** 없는 축은」 · `CATALOG_MISSING_NOTE` 「데이터 카탈로그 **본문을**」. 새어 나간 「(카탈로그에 실측 없음)」이 그 스킬 문장을 되돌려 쓴 것이었으므로 다음엔 「(카탈로그 본문에 실측 없음)」이 나올 수 있고 `pointers_in` 이 `()` 를 돌려준다(리뷰가 직접 확인). **L4 사전 주석에 적은 「새 이름으로 가리키기 시작해 사전 밖으로 샌다」를 이 diff 가 스스로 만든 것**이다
  - **버그 — 계획 범위 밖 기존 결함**: R2-2 `gate/quantified.py` 의 축 이름 검사가 `str(name).strip()` 이라 `[""]` 이름이 통과(탐색·수집엔 JSON 스키마가 없다) · R2-5 `runner/dossier.py` `_measurement_section` 이 `single_value_reason` 을 `str(value or "").strip()` 으로 따로 판정해 게이트(`is_filled`)와 갈린다(`0` 이면 게이트는 해명됨, 조립부는 그 칸을 뺀다). 1회차 ⑤(반증 게이트)와 같은 성질
  - **그 외 — 목록만**: R2-3 `_failed_cycles` 가 `_execute_with_retries` 의 멈춤 규칙을 다시 적는다(루프에 조기 종료가 더해지면 조용히 안 센다) · R2-4 탐색 상한을 중복 제거 «전» 목록에 걸어 중복이 자리를 먹으면 새 후보가 「상한 초과」로 버려진다(기존 동작 — L5 는 기록만 요구) · R2-6 계보 수(dict 덩어리)와 6번 칸이 펼치는 덩어리 수가 dict 아닌 항목에서 어긋난다(1회차 ② 와 같은 축) · R2-7 `state.AlreadyRunningError` 독스트링이 「같은 실행 폴더」만 말하고, 예외가 잠긴 폴더 이름을 실으면 사유를 단정 없이 정확히 적을 수 있다 · R2-8 `_store` 의 4-튜플에 같은 타입이 둘이라 순서를 바꿔 풀어도 타입 검사가 못 잡는다 · R2-9 새 주석의 수치(「3회차면」 · 「30초 간격으로 세 번」 · 「사흘 만에」)
  - **중간 품질 검증**(최종 기록 아님 — 수정이 남아 있다): `poetry run python validate_project.py` → Ruff 통과 · PyRight 통과 · Pytest passed=599, failed=0, skipped=0
- 2026-09-26 16:41: **2회차 뒤 사용자 결정**
  - R2-1 → **긍정 예시 + 지칭어 걷기**: 스킬 · 카탈로그 본문 · 지시문의 「없는 축」 설명에 「어디에 없는지가 아니라 「이 파이프라인이 실측한 기록 없음」처럼 사실만 적는다」를 넣고, 제가 만든 「카탈로그 본문」 표현을 걷는다. 어떤 이름을 쓰든 에이전트는 그 이름을 되돌려 쓰므로, 되돌려 쓸 말 자체를 «자립 문장»으로 준다
  - 범위 밖 기존 결함 3건(1회차 ⑤ 반증 게이트 · R2-2 정성 표현 게이트 축 이름 · R2-5 조립부 `single_value_reason`) → **포함** — B6 확장으로 `filled.is_filled` 에 맞추고 각각 빨간 테스트부터. 변경 대상 파일 목록에 `gate/{rebuttal,quantified}.py` 와 `dossier.py` 의 B6 확장을 더했다(본문 조정 — 이 줄이 근거)
  - 수정 뒤 **3회차를 돈다**
  - 「그 외」 → 「추천안만 진행」 — 제가 짚은 ⑨ · R2-9(새 주석에 적은 수치 제거)만 고치는 것으로 읽었다(사용자에게 그 해석을 알렸다). 나머지 그 외는 목록만
- 2026-09-26 16:52: **2회차 뒤 조치 완료** — 전체 테스트 602 passed(검사 3건을 먼저 빨갛게 확인: 반증 게이트 · 정성 표현 축 이름 · 조립부 사유 칸 모두 `['']` 통과)
  - **R2-1**: 에이전트가 읽는 글에서 「카탈로그 본문」을 걷고 «되돌려 쓸 자립 문장»을 넣었다 — 스킬 실현가능성 절(지칭을 「「이미 밝혀진 것」 자리 · 그 자리 · 거기」로, 「없는 축」 끝에 「답에는 어디에 없는지가 아니라 「이 파이프라인이 실측한 기록 없음」처럼 사실만 적는다」) · 지시문 `PROMPT`(「답이 아래를 가리키게 쓰지 마세요」 + 같은 자립 문장) · `CATALOG_MISSING_NOTE`(「이번에는 이 자리에 실을 내용을 읽지 못했습니다」) · `docs/DATA_CATALOG.md`(머리 인용 블록과 6절 머리에 같은 자립 문장, 6절 머리 「이 문서가 답을 갖고 있지 않은 축」 → 「실측이 아직 없는 축」). 사전 주석에 「지칭어를 바꿔 피하지도 않는다 — 되돌려 쓸 말 자체를 자립 문장으로 준다」를 더했다. `test_feasibility.py::test_prompt_demands_self_standing_prose` 가 그 자립 문장이 지시문에 있는지도 고정한다. 「카탈로그 본문」은 코드 주석 · 독스트링 · 테스트에만 남았다(에이전트에게 안 간다)
  - **범위 밖 3건 → `filled.is_filled`**: `gate/rebuttal.py`(`not_found_reason` — 「게이트는 러너 helper 를 못 쓴다」 주석은 이제 거짓이라 지웠다) · `gate/quantified.py` `_is_usable_axis`(축 이름) · `runner/dossier.py` `_measurement_section`(`single_value_reason` 칸을 싣는지 — 게이트와 같은 판정). 테스트: `test_gate_rebuttal.py::test_a_reason_holding_only_empty_values_is_blocked` · `test_gate_quantified.py::test_a_name_holding_only_empty_values_does_not_count` · `test_dossier.py::test_the_single_value_reason_slot_follows_the_gate`(빈 목록이면 칸 없음 · `0` 이면 칸 있음)
  - **⑨ · R2-9**: 새 주석·독스트링에서 상수나 바깥 사정에 묶인 수치를 걷었다 — 사전 주석(「아래 다섯은 … 세 장이」 → 「아래 「카탈로그」 꼴들은 … 근거 문서들이」, 「실제로 나온 둘」 → 「실제로 나온 꼴」) · `_step_budget`(「3회차면」 → 「막힘 상한에 닿으면」) · `_failed_cycles`(「사흘 만에」 → 「막힘 상한에 닿아」, 「멈추는 두 자리」 → 「멈추는 자리」) · 테스트 독스트링(「30초 간격으로 세 번 … 3회차면」 · 「사흘」 · 「세 장 · 세 문장」 · `test_gate_filled.py` 머리 「네 게이트 · 네 곳」 · 새 테스트 Then 의 「셋 다」 → 「모두」). 테스트가 바로 옆에서 도는 값을 말하는 것(「3회차에 걷힌다」 · 「둘 다 2」)은 그 코드와 함께 바뀌므로 두었다. 기존 줄은 손대지 않았다(diff 의 삭제 줄에 「셋 다」 0)
- 2026-09-26 16:57: **`/code-review xhigh` 3회차 — 발견 9건**(버그 3 · 그 외 6). 그 시점 품질: Ruff · PyRight · Pytest 602 passed 0 failed 0 skipped(리뷰가 보고)
  - **버그 — 고침**: R3-2 계보 수가 **주소가 하나도 없는 덩어리**까지 셌다 — 모은 출처가 0건일 때 에이전트가 지시문의 JSON 틀(`{"origin": {"url": ""}, ...}`)을 되돌려 쓰면 6번 칸에 「독립 소스 수: 1」. 제 주석(「게이트가 다룬 것으로 보지 않는 항목은 세지 않는다」)과도 어긋났다. `_cited_sources([group])` 에 주소가 하나라도 있는 덩어리만 세게 했다. 테스트 `test_a_group_without_any_url_is_not_counted`(먼저 빨강: 2 == 0) → 관련 3개 파일 62 passed. 같은 주소를 두 덩어리에 넣은 경우는 여전히 두 번 센다(그 외 ② · R2-6 과 같은 축)
  - **버그 — 사용자 결정 대기**: R3-3 B7 을 원장 «파일»로 좁힌 결과 `atomic_write` 가 강제 종료로 남긴 `ledger/원장.md.tmp` 를 검사하지 않는다(`finally` 가 못 돌고 `.gitignore` 에도 없어 커밋된다). 옛 «폴더» 검사는 잡았다. **12:14 에 제가 권한 조정이 «시끄러운 실패»(넓은 폴더에 원장을 두면 매 회차 종료 코드 4)를 «조용한 누락»으로 바꾼 셈**이다
  - **버그 — 비목표라 목록만**: R3-1 `runner/rebut.py` 가 `not_found_reason` 을 `payload_helpers.as_text` 로 저장해 목록이면 8번 칸에 `['…']` 가 실린다 — 계획서 비목표 「`payload.as_text` 의 목록 `str()` 전반(이번엔 「대상 시장」 한 자리만)」에 해당. 이 diff 전에도 같았다
  - **그 외 — 목록만**: R3-4 조사형 사전의 「가 · 를 · 의」는 입력에서도 걷혀 근거가 약해졌고 출처 제목의 오탐은 에이전트가 못 고친다(사용자 결정 L4 (b)) · R3-5 `next_unexplored` 가 가린 뒤 줄을 로그에 안 남긴다 · R3-6 탐색 상한을 거르기 «전»에 건다(R2-4 와 같음) · R3-7 `build_command` 와 진입점의 단계 상한 가드가 두 벌(⑦ 과 같음) · R3-8 계층 테스트의 상대 import(⑧ 과 같음) · R3-9 `src/research_lab/CLAUDE.md` §12 와 계층 표가 `gate/filled.py` 를 모르고 `docs/DESIGN.md` 3474행이 「탐색의 비용 줄 앞당기기는 별도 작업으로 미뤘다」로 남아 있다 — **다음 계획서(문서 정리)가 볼 것**
- 2026-09-26 17:02: **R3-3 → 사용자 결정으로 B7 을 원안(원장 «폴더»)으로 되돌렸다.** `secrets.scan_roots(run_dir, *, ledger_dir, dossier_path=None)` · `run_cycle._report_secrets(run_dir, ledger_dir)` 에 `args.ledger.parent`. 되돌린 이유를 `scan_roots` 독스트링에 적었다 — 러너가 원장 폴더에 원장 말고도 쓰고(강제 종료로 남은 임시 파일도 커밋된다), 넓은 폴더에 원장을 두는 오용의 실패는 소리가 나지만 빠뜨린 파일은 소리가 없다. `common_constants.py` 는 HEAD 와 같아졌다(12:14 에 고친 주석을 Edit 로 원문 그대로 되돌림 — `git checkout` 은 Git 처리라 쓰지 않았다). 테스트: `test_the_scope_follows_the_ledger_it_is_given` 을 폴더 계약으로 · **`test_a_leftover_temporary_ledger_file_is_scanned`**(원장 폴더에 남은 `원장.md.tmp` 의 자격증명 모양이 발견된다) 추가 · 진입점 `test_the_ledger_actually_used_is_scanned` 는 `used.parent` · 기존 범위 테스트 다섯 곳은 `ledger_dir=LEDGER_DIR` 과 원래의 「원장 폴더가 들어 있다」 단언으로 돌아갔다. 관련 2개 파일 56 passed
- 2026-09-26 17:02: **4회차는 돌지 않았다** — 사용자가 「필요 없다고 판단되면 마무리」로 맡겼다. 3회차 뒤 변경은 R3-2(한 줄 + 먼저 빨갛게 확인한 테스트)와 R3-3(이미 리뷰를 지난 원안으로 되돌림 + 테스트 하나) 둘뿐이고 둘 다 테스트로 고정돼 있어 필요 없다고 판단했다. **「버그 0 인 리뷰 회차」 없이 끝났다**는 사실을 여기 남긴다
- 2026-09-26 17:02: **최종 확인** — 재현 절차 1 · 2 재실행 결과가 16:11 원문과 같다(재현 안 됨) · `docs/COMMANDS.md` diff 0줄 · `poetry run black .` 84개 파일 변경 없음 · `poetry run python validate_project.py` → Ruff 통과 · PyRight 통과 · Pytest passed=604, failed=0, skipped=0
- 2026-09-26 17:02: **변경 파일 목록** (다음 계획서가 읽는다)
  - 소스
    - `src/research_lab/runner/ledger.py` — `canonical_claim` 이 공백류를 접고 앞머리 백틱·공백을 한꺼번에 뗀다(멱등) · `load` · `_rewrite` 비교 · `append` 가 같은 정규형 · `append` 는 빈 정규형이면 `ValueError` · `next_unexplored` 는 같은 주장의 뒤 줄을 건너뛴다
    - `src/research_lab/runner/cycle.py` — `_failed_cycles` 가 회차의 마지막 실패 줄만 센다(시도 번호가 정수가 아닌 줄은 세지 않음) · `StepFailed` 를 `agent.invoke` 에서 import · `run_cycle` Raises 문구
    - `src/research_lab/runner/explore.py` — 비용 줄을 파싱 직후로 · 상한 초과 후보를 `discarded` 로 · `judged` 에 `considered`(새 열쇠) · `_store` 가 정규형으로 비교하고 빈 주장을 `discarded`(4-튜플 반환)
    - `scripts/run_cycle.py` — `_step_budget` 타입 함수 · `_report_secrets(run_dir, ledger_dir)` · 잠금 충돌 사유 문구
    - `src/research_lab/gate/filled.py` **(신설)** — 공용 `is_filled`(명시적 스택)
    - `src/research_lab/gate/{feasibility,measurement,mechanism,verdict,rebuttal,quantified}.py` — 빈 판정을 `is_filled` 로(`rebuttal` 의 「게이트는 러너 helper 를 못 쓴다」 주석은 지웠다)
    - `src/research_lab/gate/secrets.py` — `scan_roots` 가 원장 폴더를 기본값 없는 키워드로 · `LEDGER_DIR` import 제거
    - `src/research_lab/gate/selfcontained.py` — `POINTER_TERMS` 에 「카탈로그에 · 는 · 가 · 를 · 의」와 그 이유 주석
    - `src/research_lab/gate/lineage.py` — 독립 소스 수 정수 검사 · `KEY_INDEPENDENT_SOURCE_COUNT` 제거 · 머리 주석 · 누락 사유 문구
    - `src/research_lab/runner/lineage.py` — 독립 소스 수를 «주소가 있는 덩어리 수»로 센다 · 지시문에서 그 열쇠와 「수를 적으면」 문장 제거
    - `src/research_lab/runner/dossier.py` — 「대상 시장」을 `_flatten` 으로 · `single_value_reason` 칸을 `is_filled` 로 판정
    - `src/research_lab/runner/feasibility.py` — 지시문 `PROMPT` · `CATALOG_MISSING_NOTE` 문구(「카탈로그」 조사형 제거 · 자립 문장 「이 파이프라인이 실측한 기록 없음」)
    - `src/research_lab/agent/invoke.py` — `StepFailed` 이동(정의 · 「이 계층이 정의한다」 단락)
    - `src/research_lab/runner/steps.py` — `StepFailed` 를 `agent.invoke` 에서 import · `TYPE_CHECKING` 블록 제거
  - 문서 · 스킬 · 산출물
    - `docs/DATA_CATALOG.md` — 20 · 24행 문구 · 머리 인용 블록과 6절 머리에 자립 문장
    - `.claude/skills/dossier-research/SKILL.md` — 계보 절(독립 소스 수는 적지 않는다) · 실현가능성 절(지칭 · 자립 문장)
    - `dossier/` 4장 5문장 — 위 16:06 의 전후 원문
  - 테스트
    - 새 파일: `tests/test_gate_filled.py` · `tests/test_layer_direction.py`
    - 고친 파일: `test_ledger` · `test_explore_and_collect` · `test_runner_blocked` · `test_runner_cycle` · `test_run_cycle_entrypoint` · `test_gate_secrets` · `test_dossier` · `test_gate_mechanism` · `test_gate_verdict` · `test_gate_rebuttal` · `test_gate_quantified` · `test_gate_selfcontained` · `test_prompt_selfcontained` · `test_feasibility` · `test_gate_lineage` · `test_rebut_and_lineage` · `test_agent_invoke` · `test_agent_response_shape` · `test_gate_urls`
- 2026-09-26 17:02: **다음 계획서(`PLAN_docs_consolidation.md`)가 알아야 할 것**
  - **옮긴 심볼**: `StepFailed` 는 이제 `research_lab.agent.invoke` 에 있다(`runner.steps` 는 import 해 `StepQualityFailed` 의 부모로만 쓴다). 그 독스트링에 `docs/DESIGN.md §11.14` 포인터가 그대로 옮겨져 있다 — D2 의 grep 대상
  - **새 모듈**: `gate/filled.py`. `src/research_lab/CLAUDE.md` 의 계층 설명과 §12(「같은 가드를 두 곳에 두지 않는다」 표)가 이 모듈을 모른다(R3-9). §12 의 「게이트는 이 helper 를 못 씁니다」는 **러너의 `payload` helper** 이야기라 여전히 참이지만, 게이트 계층 안의 공용 판정이 생겼다는 사실은 적혀 있지 않다
  - **새 주석의 포인터**: 없음 — 이 계획서가 새로 쓴 주석에는 `DESIGN.md` · `설계 §` 포인터를 넣지 않았다(`invoke.py` 로 «옮긴» 독스트링의 한 곳만 예외)
  - **낡은 서술(이 계획서가 만든 것 아님, 리뷰가 짚음)**: `docs/DESIGN.md` 3474행 「탐색의 비용 줄 앞당기기는 별도 작업으로 미뤘다」 — B4 로 해소됐다. DESIGN 삭제로 사라지지만 개선거리 5건을 옮길 때 섞지 않는다
  - **리서치 스킬**: 실현가능성 절과 계보 절을 이 계획서가 고쳤다. 다음 계획서 Phase 4 의 스킬 정정(URL 검사 표 · §5 · §6 · 탐색 절)은 다른 절이다
  - **예상과 달랐던 것 요약**: 계획서 전제 「게이트 뒤에 나간 3장」은 2장이었다 · 지시문을 고칠 때 사전 부분 일치(「산출물이 저장소」 ⊃ 「이 저장소」)에 걸렸다 · 지칭어를 바꾸면 새 지칭어로 샌다(R2-1) — 되돌려 쓸 자립 문장을 주는 쪽으로 풀었다 · B7 을 파일로 좁힌 조정은 되돌렸다
  - **남은 개선거리(이 계획서가 목록만 남긴 것)**: 계보 수가 같은 주소를 두 덩어리에 넣으면 두 번 센다 · 조사형 사전의 제목 오탐 · `build_command` 가드와 진입점 가드가 두 벌 · 계층 테스트의 상대 import · 탐색 상한을 거르기 전에 건다 · `next_unexplored` 가 가린 줄을 로그에 안 남긴다 · `_failed_cycles` 가 재시도 루프의 멈춤 규칙을 다시 적는다 · `_store` 4-튜플 · 반증 러너의 `as_text` 저장(비목표)

---

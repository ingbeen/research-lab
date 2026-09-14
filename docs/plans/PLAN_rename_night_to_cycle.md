# Implementation Plan: 「밤」 명칭을 「회차」(영문 `cycle`)로 개명

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

**작성일**: 2026-09-14 14:05
**마지막 업데이트**: 2026-09-14 14:43
**관련 범위**: 러너 · 에이전트 · 게이트 · 테스트 · 문서 · 리서치 스킬 · 컨테이너
**관련 문서**: `CLAUDE.md`, `docs/DESIGN.md`, `src/research_lab/CLAUDE.md`, `docs/INDEX.md`, `docs/COMMANDS.md`

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

- [x] 목표 1: 실행 단위를 가리키는 「밤」을 **「회차」**로 바꾼다 — 저장소가 낮에도 돌아가므로 시간을 함축하는 이름이 사실과 맞지 않는다
- [x] 목표 2: 영문 식별자 `night` 계열을 **`cycle`** 로 바꾼다 — 파일·심볼·테스트 함수명 포함
- [x] 목표 3: 리서치 스킬 폴더 `night-research` 를 **`dossier-research`** 로 바꾸고 그 참조를 전부 따라 고친다
- [x] 목표 4: 「밤」이 안 들어가지만 같은 시간 가정을 깐 말(「아침에 보면」·「매일」·「어제」)을 시간 중립 표현으로 바꾼다 — 「그날」의 파이프라인 의미 8곳도 사용자 승인으로 함께 바꿨다

## 2) 비목표(Non-Goals)

- **`runs/` 아래 과거 산출물을 고치지 않는다.** 결정 로그와 단계 산출물은 **근거물**이라 원문 그대로 둔다 (해당 2곳)
- **`docs/plans/` 의 기존 계획서 4개를 고치지 않는다.** 전부 `✅ Done` 이고 주기적으로 비워지는 임시 문서다 (「밤」 216곳). 이 개명으로 그 안의 `night-research` 경로 참조 16곳이 죽은 링크가 되지만, `tests/test_index.py` 가 `docs/plans/` 를 검사 범위에서 빼두어 **테스트는 깨지지 않는다**
- **「야간」(8곳)을 건드리지 않는다.** 「미국장은 한국시간 야간」처럼 **도메인 내용**이며 파이프라인 실행 단위와 무관하다
- **`docs/DESIGN.md` 의 quant-notify 인용 블록을 건드리지 않는다.** 다른 저장소의 원문이다
- 실행 폴더(`runs/` · `run_dir` · `RUNS_DIR` · `MAX_STEP_FAILURES_PER_RUN`)의 이름을 바꾸지 않는다 — **「회차」와 다른 층위**다(아래 Context 참고)
- 동작 변경 없음. 순수 개명이다

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

저장소가 「밤사이 무인으로 돈다」는 전제로 쓰여, 실행 단위 자체를 **「밤」**이라 불러 왔다.
그런데 개발 중에는 **낮에도 돌린다.** 「다음 밤이 이어받는다」·「3밤 연속 막혔습니다」 같은
문장과 로그가 낮 실행에서는 사실과 어긋나고, 사용자에게 나가는 문자열에도 그대로 실린다.

🔴 **「밤」은 두 가지를 가리키고 있어 이름이 하나로는 안 된다.**

| 갈래 | 뜻 | 예 | 바꿀 말 |
| --- | --- | --- | --- |
| **A. 실행 단위** | `run_night()` 호출 한 번 | 「다음 **밤**이 이어받는다」 | **회차** |
| **B. 시간 맥락** | 무인으로 돈다는 서술 | 「**밤사이** 혼자 돌며」 | **무인으로** · **회차마다** |

🔴 **A 를 「실행」으로 부를 수 없다.** 저장소는 `runs/` · `run_dir` · `RUNS_DIR` 를 이미
**실행 폴더**에 쓰고 있고, **둘은 다른 층위**다 — 실행 폴더 하나(한 후보를 파는 단위)를
**여러 회차가 이어받는다**. `scripts/run_night.py` 의 `_resolve_run_dir()` 가 미완성 폴더를
찾아 재사용하는 분기가 그 근거다. 그래서 `MAX_STEP_FAILURES_PER_RUN`(= 한 실행 폴더당)은
이름 그대로 두고, 그것이 세는 대상인 `_failed_nights()` 만 `_failed_cycles()` 로 바꾼다.

**영문은 `cycle`** 을 쓴다 — `session` 은 에이전트 세션이 선점했고(파이썬 10곳), `run` 은
실행 폴더가 선점했으며(156곳), `pass` 는 파이썬 예약어다. `cycle` 은 저장소 충돌 0건이다.

### 🔴 치환이 기계적이지 않은 이유 — 조사 받침

**「밤」은 받침이 있고 「회차」는 없다.** 그래서 붙는 조사가 **전부 바뀐다.**
`s/밤/회차/` 같은 단순 치환은 **736곳 전부를 비문으로 만든다.**

| 원형 | 치환 | 원형 | 치환 |
| --- | --- | --- | --- |
| 밤**이** | 회차**가** | 밤**은** | 회차**는** |
| 밤**을** | 회차**를** | 밤**과** | 회차**와** |
| 밤**으로** | 회차**로** | 밤**의** | 회차**의** |

그 외 `밤에·밤마다·밤도·밤에서·밤들의·밤처럼·밤에는·밤만·밤들이` 는 조사가 그대로다.

**문맥 판단이 필요한 활용형** — 아래는 표로 못 푼다.

| 원형 | 곳 | 치환 |
| --- | --- | --- |
| 세 밤 · 3밤 · 3밤마다 | 28 | 세 회차 · 3회차 · 3회차마다 |
| 매일 밤 | 21 | 회차마다 |
| 첫 밤 | 16 | 첫 회차 |
| 그날 밤 | 7 | 그 회차 |
| 밤새 | 6 | 한 회차 내내 |
| 하룻밤(에/의) | 6 | 한 회차(에/의) |
| 밤사이 | 3 | 무인으로 |
| 오늘 밤 | 1 | 이번 회차 |

**「밤」이 안 들어간 인접 시간어**(사용자 승인 완료): 「아침에 보면」→「나중에 보면」·
「아침에 사람이」→「나중에 사람이」(46곳), 「매일 다시 돈다」→「회차마다 다시 돈다」(48곳 중
파이프라인 주기를 뜻하는 것만), 「어제 끊긴 밤」→「지난 회차」(4곳).

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절과 「산출물 하나가 독립이어야 한다」 절
- `src/research_lab/CLAUDE.md` — 계층 간 계약
- `docs/DESIGN.md` — 확정 설계·탈락안·실측 기록
- 전역 `~/.claude/CLAUDE.md` — 특히 「수술적 변경」·「조회 결과·데이터를 임의로 가공하지 않는다」·「코드 파일에는 이모지를 쓰지 않는다」

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] 기능 요구사항 충족 — 실측값은 아래와 같다
      ① 「밤」 **0곳** (`docs/DESIGN.md` §11.6 개명 기록 7줄은 «의도된 예외» — 아래 주석 참고)
      ② `night` **0곳** (같은 §11.6 의 2줄 예외. **`grep -i` 로 쟀다**)
      ③ `runs/` 2곳 · `docs/plans/` 216곳 — **착수 전과 동일**
      ④ 「야간」 **6곳**(plans 제외 기준) 그대로. `git diff` 에 야간이 든 줄 **0건**
- [x] 회귀/신규 테스트 추가 — 새 테스트는 만들지 않았다. 기존 테스트의 심볼·파일명·문자열 assert 를 따라 고쳤다
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적었다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적었다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트(`docs/COMMANDS.md` / CLAUDE.md / plan 등 — 각각 변경 여부 명시)
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다
      (`docs/DESIGN.md` §11.6 로 이관: 탈락안과 그 이유 · 「회차」와 「실행 폴더」가 다른 층위인 근거 ·
      조사 받침과 구분자 함정의 실측 · 고치지 않은 것과 그 이유)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

> 🔴 **①②의 「0곳」에는 예외가 하나 있고, 의도한 것이다.** `docs/DESIGN.md` §11.6 은
> **개명 자체의 기록**이라 옛 이름을 부르지 않고는 「무엇을 무엇으로 바꿨나」를 쓸 수 없다.
> 탈락안 표와 함정 기록이 성립하려면 「밤」·`night` 이 그 절 안에 있어야 한다.
> **그 절 밖에는 한 곳도 없다.**

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상) — 62개

| 묶음 | 파일 | 「밤」 | `night` |
| --- | --- | --- | --- |
| 진입점·러너 | `scripts/run_night.py` · `src/research_lab/runner/*.py` (16) | 약 170 | 약 15 |
| 에이전트·게이트 | `src/research_lab/agent/*.py` (3) · `gate/*.py` (8) | 약 35 | 0 |
| 공통 | `src/research_lab/{__init__,common_constants}.py` | 10 | 0 |
| 테스트 | `tests/*.py` (26) | 약 220 | 약 60 |
| 문서 | 루트 `CLAUDE.md` · `src/research_lab/CLAUDE.md` · `docs/{DESIGN,INDEX,COMMANDS,DATA_CATALOG,PROMPT_next_phase}.md` · `ledger/원장.md` | 약 180 | 약 5 |
| 스킬 | `.claude/skills/night-research/SKILL.md` (폴더째 rename) | 20 | 1 |
| 설정·컨테이너 | `Dockerfile` · `docker/run.sh` · `.gitignore` · `pytest.ini` | 7 | 1 |

**파일·폴더 rename 5건**

| 현재 | 변경 후 |
| --- | --- |
| `scripts/run_night.py` | `scripts/run_cycle.py` |
| `src/research_lab/runner/night.py` | `src/research_lab/runner/cycle.py` |
| `tests/test_runner_night.py` | `tests/test_runner_cycle.py` |
| `tests/test_run_night_entrypoint.py` | `tests/test_run_cycle_entrypoint.py` |
| `.claude/skills/night-research/` | `.claude/skills/dossier-research/` |

**심볼 rename**

| 현재 | 변경 후 | 곳 |
| --- | --- | --- |
| `run_night()` | `run_cycle()` | 22 |
| `NightResult` | `CycleResult` | 6 |
| `_failed_nights()` | `_failed_cycles()` | 2 |
| `_run_nights` (테스트 헬퍼) | `_run_cycles` | 9 |
| `test_*_night_*` 등 테스트 함수 | `test_*_cycle_*` | 17 |

- `docs/COMMANDS.md`: **변경 있음** — 실행 명령이 `poetry run python scripts/run_night.py` → `scripts/run_cycle.py` 로 바뀐다
- `docs/INDEX.md`: **변경 있음** — 스킬 경로 `night-research/SKILL.md` → `dossier-research/SKILL.md`
- `Dockerfile`: **변경 있음** — `ENTRYPOINT` 가 `/work/scripts/run_night.py` 를 가리킨다

### 데이터/결과 영향

- 출력 스키마 변경 **없음.** 결정 로그의 키(`step`·`event`·`kind`)와 산출물 파일명(한글)은 손대지 않는다
- **사용자에게 나가는 문자열은 바뀐다** — 「「계보」 단계가 3밤 연속 막혔습니다」 → 「…3회차 연속 막혔습니다」. 원장에 적히는 문구도 같다
- **과거 `runs/` 산출물과 표기가 갈린다.** 의도한 것이다 — 과거 기록은 그때의 사실이므로 고치지 않는다

## 6) 단계별 계획(Phases)

> Phase 0을 두지 않는다. 인바리언트·정책·에러 처리 규칙이 하나도 바뀌지 않는 **순수 개명**이라
> 먼저 고정할 레드 테스트가 없다. 기존 테스트 전체가 그대로 회귀 그물 역할을 한다.

### Phase 1 — 영문 식별자·파일명 개명 (`night` → `cycle`)

> **파일 rename 과 그 참조를 한 Phase 안에서 닫는다.** 갈라 놓으면 `Dockerfile` 의
> `ENTRYPOINT` 가 없는 스크립트를 가리키는 상태가 생기고, **컨테이너가 안 뜨는데 테스트는
> 통과한다** — 파이썬 테스트는 컨테이너를 띄우지 않는다.

**작업 내용**:

- [x] 파일 4개 rename (프로젝트 규칙상 git 처리는 하지 않으므로 `mv` 사용) (`scripts/run_night.py` · `runner/night.py` · 테스트 2개)
- [x] 심볼 rename — `run_night`→`run_cycle` · `NightResult`→`CycleResult` · `_failed_nights`→`_failed_cycles` · `_run_nights`→`_run_cycles`
- [x] 테스트 함수명 17개의 `night` → `cycle`
- [x] import 경로 `runner.night` → `runner.cycle` 전수 교체
- [x] `Dockerfile` 의 `ENTRYPOINT` 경로 교체
- [x] `docs/COMMANDS.md` 의 실행 명령 교체
- [x] 🔴 **문서 안의 영문 식별자 참조도 여기서 함께 고친다** — `docs/DESIGN.md` 3곳(`scripts/run_night.py` 경로 · `run_night` 심볼 등). Phase 4 는 «한글 산문»만 다루므로 여기서 안 잡으면 영문 참조가 남는다
- [x] 🔴 진입점 테스트의 `spec_from_file_location(...)` 은 **문자열 경로라 Ruff·PyRight 가 못 잡는다.** 테스트 실패로만 드러나므로 직접 확인한다
- [x] `docker/run.sh` 는 `"$@"` 만 넘기고 `pytest.ini` · `.gitignore` 에는 스크립트 경로 참조가 없음을 확인 — 실측으로 확인했으나 Phase 1 에서 다시 본다

**Validation**:

- [x] `poetry run pytest` 전체 통과 (여기서는 결과를 적지 않는다 — 품질 검증은 마지막 Phase)
- [x] `grep -rIn 'night' . --exclude-dir=.git --exclude-dir=runs --exclude-dir=plans` 결과가 **스킬 경로(`night-research`)뿐**임을 확인 — 저장소 전체를 본다. 좁은 범위로 재면 문서·설정에 남은 영문 참조를 놓친다

---

### Phase 2 — 스킬 폴더 개명 (`night-research` → `dossier-research`)

> 소스 5곳이 **프롬프트 문자열 안에서** 이 경로를 가리킨다. 경로가 어긋나면 에이전트가
> 규율 문서를 못 읽는데 **에러가 나지 않는다** — 그냥 규율 없이 돈다. 그래서 별도 Phase 로 떼어
> `tests/test_index.py` 로 링크 실재를 닫는다.

**작업 내용**:

- [x] `mv .claude/skills/night-research .claude/skills/dossier-research`
- [x] `SKILL.md` 의 frontmatter `name` 과 본문의 자기 경로 참조 교체
- [x] 소스 5곳(`runner/{collect,explore,feasibility,lineage,rebut}.py`)의 프롬프트 문자열 경로 교체
- [x] `docs/INDEX.md` 의 스킬 줄 경로 교체

**Validation**:

- [x] `poetry run pytest tests/test_index.py` 통과 — INDEX 의 링크가 전부 실재함을 확인
- [x] `grep -rn 'night-research' src/ docs/INDEX.md .claude/` 결과 0건
- [x] `docs/plans/` 안의 죽은 참조 16곳은 **의도된 잔여**임을 확인 (Non-Goals)

---

### Phase 3 — 코드 계층 한글 산문 개명 (`src/` · `scripts/` · `tests/`)

> 조사 받침이 바뀌므로 **단순 치환을 쓰지 않는다.** Context 의 매핑표대로 조사 결합형을
> 먼저 일괄 처리하고, 문맥 판단형은 파일을 열어 손으로 고친다.

**작업 내용**:

- [x] 조사 결합형 일괄 치환 (`밤이`→`회차가` 등 매핑표 전체)
- [x] 문맥 판단형 손질 — `세 밤`·`3밤`·`매일 밤`·`첫 밤`·`그날 밤`·`밤새`·`하룻밤`·`밤사이`
- [x] 남은 맨 「밤」의 앞뒤를 읽고 개별 처리
- [x] 인접 시간어 — 「아침에」→「나중에」 · 「매일 다시」→「회차마다 다시」 · 「어제 끊긴」→「지난 회차에 끊긴」
- [x] 문자열 assert 3곳 갱신 (`test_runner_cycle.py` 1곳 · `test_ledger.py` 2곳 — 「세 밤 연속 막혔다」)
- [x] 사용자에게 나가는 문자열 확인 — `runner/cycle.py` 의 `reason` f-string, `scripts/run_cycle.py` 의 `print`·`argparse` description

**Validation**:

- [x] `grep -rn '밤' src/ scripts/ tests/` 결과 0건
- [x] `poetry run pytest` 전체 통과
- [x] 조사 오류 육안 확인 — `git diff` 에서 「회차이」·「회차을」·「회차은」·「회차과」·「회차으로」 가 없는지 `grep`
- [x] 🔴 **닫는 괄호가 끼인 조사도 잡는다** — 「조사한 밤」으로 처럼 `」` 가 사이에 있으면 위 매핑표가 못 잡는다. 코드 계층에서 4곳 발견해 고쳤다 (`cycle.py` · `payload.py` · `run_cycle.py` · `test_run_cycle_entrypoint.py`)

---

### Phase 4 — 문서·설정 계층 한글 산문 개명

> 문서는 **왜 그렇게 만들었는지**를 담고 있어 치환이 가장 조심스럽다. `docs/DESIGN.md` 한
> 파일이 138곳으로 전체의 19%다.

**작업 내용**:

- [x] `docs/DESIGN.md` · 루트 `CLAUDE.md` · `src/research_lab/CLAUDE.md` 개명
- [x] `docs/{INDEX,COMMANDS,DATA_CATALOG,PROMPT_next_phase}.md` 개명
- [x] `ledger/원장.md` 의 안내 블록 개명
- [x] `Dockerfile` · `docker/run.sh` · `.gitignore` · `pytest.ini` 의 주석 개명
- [x] 🔴 `docs/DESIGN.md` 의 quant-notify 인용 블록(「매일 갱신되는 누적 상태를 만들지 않습니다」)을 **건드리지 않았는지** 확인
- [x] 🔴 「야간」이 **그대로인지** 확인 — diff 에 야간이 든 줄 0건. 착수 전 기준선 8은 `docs/plans/` 를 포함해 잰 값이고, 그 2곳을 빼면 6으로 일치한다

**Validation**:

- [x] `grep -rn '밤' . --exclude-dir=runs --exclude-dir=plans --exclude-dir=.git` 결과 0건
- [x] `야간` 곳 수 동일 — 6곳(plans 제외 기준). diff 에 야간이 든 줄 0건
- [x] `runs/` 와 `docs/plans/` 의 「밤」 곳 수가 착수 전과 동일 (각 2곳 · 216곳)
- [x] 「그날」의 «파이프라인 의미» 8곳도 「그 회차」로 바꿨다 (사용자 승인 2026-09-14). 장 마감·상장주식수·날짜를 뜻하는 도메인 6곳은 그대로 둔다

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 — `docs/COMMANDS.md` **변경 있음**(실행 명령 경로) · `docs/INDEX.md` **변경 있음**(스킬 경로) · 루트 `CLAUDE.md` · `src/research_lab/CLAUDE.md` · `docs/DESIGN.md` **변경 있음**
- [x] 자동 포맷 적용 (`poetry run black .`) — 1개 파일 재포맷(`tests/test_ledger.py`, 개명으로 길어진 줄 재래핑)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] 🔴 **`/commit` 을 실행하고 그 후보를 «이 계획서» 의 `#### Commit Messages` 절에 옮긴다** —
      `/commit` 은 계획서를 모르고 「후보 뒤에 아무것도 덧붙이지 말 것」으로 끝나므로,
      **대화에만 내면 그 절이 빈 채로 남는다**
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

> 순서를 지킨다 — 리뷰에서 고치면 코드가 바뀌므로 품질 검증이 마지막 관문이어야 한다.

- [x] `/code-review xhigh` (발견 8건 · 조치: 6건 수정 · 2건 미조치)
- [x] `poetry run python validate_project.py` (passed=336, failed=0, skipped=0)

**리뷰 8건의 처리** — 수정한 6건 중 넷은 이 개명이 만든 결함이고 둘은 사용자 승인을 받아 고쳤다.

| # | 지적 | 처리 |
| --- | --- | --- |
| 1 | 정렬된 import 블록에서 `cycle` 이 `night` 자리에 들어가 isort 순서가 깨짐 (Ruff I001 4건) | **수정** — `ruff check --fix` |
| 2 | 굵게 표시(`**`)가 명사와 조사 사이에 끼어 `회차**이` 3곳 | **수정** — `회차**가`. `src/research_lab/CLAUDE.md` 가 포함돼 있었다 |
| 3 | `docs/DESIGN.md` §2 의 「회차에 돌면 나중에 파일 하나가 생깁니다」 비문 | **수정** — 「한 회차를 돌면 파일 하나가 생깁니다」 |
| 4 | `runner/ledger.py` 의 「매일」 1곳 누락 (줄바꿈에 걸려 규칙이 못 잡음) | **수정** — 「회차마다」 |
| 5 | `docs/DESIGN.md` §6 표가 검색어 게이트를 「수집·반증 둘만」이라 적었으나 `explore.py:139` 도 같은 게이트를 건다 | **수정**(사용자 승인) — 「탐색·수집·반증 셋 다」로 바로잡고, 「별도 파일로 남기는 것」과 「게이트를 받는 것」이 다른 질문임을 덧붙였다 |
| 6 | `docs/DESIGN.md` §6 의 「2단계 세션·1단계」가 단계 다섯으로 늘며 어긋남 | **수정**(사용자 승인) — 단계 이름(「반증 세션」·「수집」)으로 교체 |
| 7 | 파일 rename 을 `mv` 로 해 새 경로가 미추적·옛 경로가 미스테이징 삭제 상태 | **미조치** — 프로젝트 규칙상 Git 처리는 사용자가 한다. 아래 Notes 에 커밋 전 주의로 남긴다 |
| 8 | `docs/plans/PLAN_phase4_feasibility.md` 의 `night-research` 참조 5곳이 죽은 링크 | **미조치**(사용자 결정) — 계획서는 주기적으로 비워지는 임시 문서이고 `tests/test_index.py` 가 `docs/plans/` 를 검사 범위에서 뺀다 |

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다.**
> 계획서를 쓰는 시점에는 diff 가 없어 여기 적는 것은 전부 추측이고,
> **추측으로 적은 줄은 그대로 나간다.** 형식·문체 규칙은 `/commit` 이 정한다.

1. `하네스 / 실행 단위 명칭을 「밤」에서 「회차」로 개명`
2. `하네스 / 시간 중립 명칭 「회차」 도입과 night→cycle 식별자 정리`
3. `하네스 / 낮 실행과 어긋나던 「밤」 표현 제거 및 조사 매핑 기반 산문 개명`
4. `하네스 / 「회차」 개명 — 파일·심볼·스킬 폴더 이동과 §11.6 근거 승격`
5. `하네스 / 실행 단위·리서치 스킬 명칭 정비와 개명 함정 실측 기록`

> 🔴 **커밋 대상에 무관한 덩어리가 하나 섞여 있습니다** — `docs/plans/PLAN_phase4_feasibility.md`
> 의 상태 `In Progress`→`Done` 은 **다른 세션의 Phase 4 뒷정리**이고 개명과 무관하다.
> 분리 여부는 사용자가 정한다.

## 7) 리스크(Risks)

| 리스크 | 왜 위험한가 | 완화 |
| --- | --- | --- |
| 🔴 **조사 받침 변화** | 「밤」은 받침이 있고 「회차」는 없어 `이/가`·`을/를`·`은/는`·`과/와`·`으로/로` 가 전부 바뀐다. 단순 치환은 736곳을 비문으로 만들고 **테스트는 통과한다** — 산문이라 아무 검사에도 안 걸린다 | 매핑표로 치환하고, Phase 3·4 Validation 에서 「회차이·회차을·회차은·회차과·회차으로」를 `grep` 으로 잡는다 |
| 🔴 **`Dockerfile` ENTRYPOINT 가 갈린다** | 스크립트 rename 과 따로 놀면 컨테이너가 안 뜨는데 **파이썬 테스트는 컨테이너를 띄우지 않아 통과한다** | Phase 1 안에서 함께 고치고 Validation 에 `grep` 을 둔다 |
| 🔴 **스킬 경로가 어긋난다** | 프롬프트 문자열이라 경로가 틀려도 **에러가 아니라 「규율 없이 도는」 상태**가 된다 | Phase 2 를 떼어 `tests/test_index.py` 로 링크 실재를 닫는다 |
| **과거 산출물을 건드림** | `runs/` 는 근거물이라 고치면 재현·검증이 불가능해진다 | Non-Goals 에 명시하고 Phase 4 Validation 에서 곳 수 동일을 확인 |
| **도메인어 오염** | 「야간」(미국장 시간대)과 quant-notify 인용문은 파이프라인 실행 단위와 무관하다 | Phase 4 작업 항목과 Validation 양쪽에 확인을 둔다 |
| **다른 세션과 동시 편집** | `docs/DESIGN.md` 는 736곳 중 138곳을 차지해 거의 전면 수정된다. 동시에 만지면 한쪽이 조용히 덮인다 | 사용자가 다른 세션 종료를 확인함 (2026-09-14 14:00) |
| **표기 불일치 잔존** | 코드는 「회차」, 문서는 「밤」이 남으면 용어가 갈린다 | Phase 3·4 를 모두 `grep` 0건으로 닫는다 |

## 8) 메모(Notes)

### 결정 근거 (Done 시 `docs/DESIGN.md` 로 승격 대상)

- **왜 「회차」인가** — 후보 6개를 실제 문장에 넣어 봤다. `실행`은 기존 「실행 폴더」(323곳)와 겹쳐 「그 실행의 실행 폴더」가 되고, `세션`은 「반증 세션」(133곳)이 선점했다. `사이클`은 「3사이클 연속」이 어색해 수사 표현이 깨진다. 「회차」는 충돌 0건이고 「다음 회차가 이어받는다」·「3회차 연속 막혔습니다」 두 관용 문형이 모두 살아남는다
- **왜 영문은 `cycle` 인가** — 파이썬 파일 기준 충돌 수: `session` 10 · `run` 156 · `pass` 15(예약어) · `round` 1(내장) · **`cycle` 0**
- **왜 「회차」와 「실행 폴더」를 구분하는가** — 실행 폴더 하나를 여러 회차가 이어받는다. `_resolve_run_dir()` 의 미완성 탐색 분기가 그 구조의 근거이며, 그래서 `MAX_STEP_FAILURES_PER_RUN`(실행 폴더당)은 이름을 유지하고 그것이 세는 `_failed_nights()` 만 `_failed_cycles()` 가 된다
- **왜 스킬을 `dossier-research` 로 부르는가** — 산출물 이름으로 부르면 전역 `web-research` 스킬과 한눈에 갈린다

### 스킵

없음.

### 진행 로그 (KST)

- 2026-09-14 14:05: 계획서 작성. 착수 전 실측 — 「밤」 736곳(`runs/`·`docs/plans/` 제외) · `night` 110곳 · 영향 파일 62개 · 「야간」 8곳 · `runs/` 2곳 · `docs/plans/` 216곳
- 2026-09-14 14:12: Phase 1 완료. 파일 4개 rename · 심볼 4종 · 테스트 함수 17개 · `Dockerfile` ENTRYPOINT · `docs/DESIGN.md` 영문 참조 3곳. pytest 336 통과
- 2026-09-14 14:16: Phase 2 완료. 스킬 폴더를 `dossier-research` 로 옮기고 소스 5곳의 프롬프트 문자열·`docs/INDEX.md` 를 따라 고침. `tests/test_index.py` 11 통과
- 2026-09-14 14:24: Phase 3 완료. 조사 매핑표로 코드 계층 치환. **닫는 괄호가 끼인 조사 4곳을 1차에서 놓쳐** 규칙을 보강해 재적용
- 2026-09-14 14:31: Phase 4 완료. 문서·설정 계층 치환. 「그날」의 파이프라인 의미 8곳도 사용자 승인으로 함께 처리
- 2026-09-14 14:36: 🔴 **검증 `grep` 이 대소문자를 구분해 `NightResult` 7곳을 「0건」으로 잘못 통과시켰다.** `-i` 로 다시 재어 발견하고 수정. `docs/DESIGN.md` §11.6 에 승격
- 2026-09-14 14:39: `black` 적용(1개 파일 재래핑) → `/code-review xhigh` 8건 → 6건 수정 → `validate_project.py` **passed=336, failed=0, skipped=0**
- 2026-09-14 14:43: 🔴 **`/commit` 후보를 대화에만 내고 계획서로 돌아오지 못해 사용자가 지적했다.** 이 계획서의 마지막 Phase 체크리스트가 그 함정을 명시하고 있었는데도 그대로 밟았다 — 원인은 `/commit` 의 마지막 규칙(「후보 뒤에 아무것도 덧붙이지 말 것」)이 턴을 끊는 데 있다. 재발 방지는 사용자와 별도 논의

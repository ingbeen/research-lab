# Implementation Plan: 문서 정리 — DESIGN.md 삭제 · OPERATIONS 축약 · 옛 계획서 삭제 · 낡은 서술 정정

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

**작성일**: 2026-09-26 12:02
**마지막 업데이트**: 2026-09-26 21:28
**관련 범위**: 문서(루트 `CLAUDE.md` · `src/research_lab/CLAUDE.md` · `docs/` · 리서치 스킬) · 코드·테스트의 **주석과 독스트링** · `tests/test_index.py` 한 줄 · `.claude/plan-config.json` · `.gitignore` 주석
**관련 문서**: 선행 계획서 [PLAN_critical_bug_fixes.md](PLAN_critical_bug_fixes.md)

> 🔴 **실행 순서**: 이 계획서는 **2번**이다. 선행 계획서
> [PLAN_critical_bug_fixes.md](PLAN_critical_bug_fixes.md) 가 **✅ Done 이고 사용자가 커밋한 뒤에** 새 세션에서 시작한다.
> 아니면 멈추고 사용자에게 알린다.
>
> **착수하면 먼저 그 계획서의 「진행 로그」를 읽는다** — 변경 파일 목록 · 새로 생긴 주석 · 옮긴 심볼
> (`StepFailed` 의 새 자리 · 공용 `gate/filled.py` · 자립성 사전과 바뀐 지시문 문구 등)이 거기 있다.
> 이 계획서의 줄 번호는 선행 계획서 «이전» 기준이라 어긋날 수 있다 — **문구로 찾는다.**

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

- [x] D1: `docs/DESIGN.md` 를 지운다 — 그 전에 **남은 개선거리 5건**을 루트 `CLAUDE.md` 로 옮기고, 앞으로의 **근거 승격 규약**을 새로 쓴다
- [x] D2: 저장소 어디에도 `DESIGN.md` · `설계 §N` 포인터가 남지 않는다(옛 계획서 제외 — D4 에서 지운다). 가리키던 자리의 «이유»는 그 자리에 남긴다
- [x] D3: `docs/OPERATIONS.md` 를 **절차와 함정만** 남겨 제자리에서 축약한다
- [x] D4: `docs/plans/` 의 ✅ Done 옛 계획서 19개를 지운다(`.gitkeep` · 두 새 계획서는 남긴다)
- [x] D5: 전수 분석에서 나온 **낡은·틀린 서술**을 코드와 맞춘다(루트 `CLAUDE.md` · `src/research_lab/CLAUDE.md` · `docs/INDEX.md` · `docs/COMMANDS.md` · 리서치 스킬 · 코드 주석)

## 2) 비목표(Non-Goals)

- **동작 변경 없음** — 코드는 주석·독스트링만, 테스트는 `tests/test_index.py` 의 필수 문서 목록 한 줄만 바꾼다
- 사용자가 패스한 것(2026-09-26): 코드 주석의 **이력·수치 정리 전반**(「예전에는 …」 류 · `[실측 날짜]` 근거 주석) — **틀린 서술만** 고친다
- `docs/DATA_CATALOG.md` 내용 개편(선행 계획서가 문구만 고쳤다) · `dossier/` · `runs/` · `ledger/` 는 손대지 않는다
- 두 새 계획서(`PLAN_critical_bug_fixes.md` · 이 파일)는 지우지 않는다 — 삭제는 사용자가 정한다
- 새 문서를 만들지 않는다(개선거리는 루트 `CLAUDE.md` 로 — 사용자 결정)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `docs/DESIGN.md`(3,793행)는 설계·탈락안·실측 기록 문서였으나 로드맵이 끝난 뒤 **낡은 「현재」 서술**이 쌓였고(예: 트리거 「아직 안 붙었다」 · 디스크 여유 검사 · 「1회 재시도」 · 「남은 것은 G·C·I 셋뿐」 — 표에는 P·R 도 남아 있음), 사용자가 **삭제**를 정했다(2026-09-26)
- 그 문서를 가리키는 곳이 **약 50곳**이다 — 코드·테스트 주석의 `설계 §N` / `DESIGN.md` 포인터, `src/research_lab/CLAUDE.md` 4곳, `.gitignore` 2곳, 루트 `CLAUDE.md` 세션 시작 표, `docs/INDEX.md`, `docs/OPERATIONS.md` 3곳, 그리고 **`tests/test_index.py` 의 필수 문서 목록**(지우면 이 테스트가 깨진다)
- `docs/OPERATIONS.md`(491행)는 기계를 옮기는 날 필요한 절차(plist 템플릿 · 절전 해제 · 엔진 자동 시작 · 한도 보정 · 끄기/켜기)를 담지만 실측 이야기·중복 수치·낡은 값(「회차 하나는 $2 ~ 5」 — 최근 Opus 회차는 $12.87 · $14.60)이 절차를 덮는다
- `docs/plans/` 의 옛 계획서 19개는 **전부 ✅ Done** 이다([확인] 2026-09-26). 그 근거는 DESIGN.md 로 승격돼 있었으므로 둘을 함께 지우면 그 근거는 **git 이력에만** 남는다(사용자 수용)

### 사용자 결정 (2026-09-26 — 다시 정하지 않는다)

- DESIGN.md **삭제**. 남은 개선거리 **5건만 루트 `CLAUDE.md` 로** 옮긴다
- 앞으로의 근거는 **그 코드 자리의 주석**(짧게, 「왜」만)과 **루트 `CLAUDE.md`** 에 남긴다 — 계획서 규약 문구를 그렇게 고친다
- OPERATIONS 는 **축약해 제자리 유지**(COMMANDS 로 합치거나 지우지 않는다)
- 「실체 없음 조기 종료」는 **문서를 코드에 맞춘다** — 찬성 근거 0건이어도 끝까지 돌아 판정에서 결론낸다
- 옛 계획서는 필요 없으면 지운다 → 19개 전부 Done 이라 전부

### 옮길 개선거리 5건 (DESIGN.md §10.1 — 지우기 «전»에 본문을 읽고 한 줄씩 요약)

| # | 요지 | 언제 다시 보나 |
| --- | --- | --- |
| G | URL 실재 게이트가 **가짜 «도메인»**(`URLError`)을 못 잡는다 — 죽음으로 보면 네트워크가 한 번 끊긴 회차가 통째로 죽으므로 판정 못 함으로 통과시킨다 | 결정 로그의 `unknown_details` 에 `URLError` 가 실제 회차에서 쌓이는지 보고 |
| C | 정성 표현**마다** 대응하는 축을 요구하지 않는다 — 「옥석을 가려 전저점 대비」에 전저점 축만 내면 옥석은 해명 없이 통과 | 원장에 남은 「옥석」 후보(코스닥 스팩)를 파는 회차 |
| I | WSL 파일시스템에서 `flock` 이 표준대로 도는지 [미검증] — 잠금이 안 풀리면 정지 버그, 안 잠기면 두 회차가 한 폴더를 씀 | WSL 에서 품질 검증을 돌리면 `tests/test_runner_state.py` 의 그 계약 테스트가 답한다(저장소가 Windows 드라이브가 아닌 리눅스 파일시스템에 있을 것) |
| P | 회차 로그의 「한 장당 한도 %」가 이어받기 회차에서는 앞 단계 토큰이 빠져 작게 나온다(실측 19.06% vs 처음부터 끝까지 약 23%) — 같은 이름으로 다른 것을 잰다 | 처음부터 끝까지 한 장을 낸 회차가 몇 건 쌓인 뒤. 그때까지 그 칸을 회차끼리 비교하지 않는다 |
| R | 복제 출처가 7번 칸(찬성 근거)에 별도 행으로 실려 근거 수가 부풀려 보인다 — 계보는 「독립 1곳」인데 7번 칸은 원본과 미러를 두 줄로 센다. `kind`(1차/2차)와 원본/복제는 직교하는 축이라 분류 대조로는 못 잡는다 | 계수 문제라 다른 장치가 필요 — 판단 보류 |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `.claude/plan-config.json` — 이 저장소의 검증 명령·자동 포맷·근거 승격 목적지 (**값의 SoT**)
- 루트 `CLAUDE.md` — 특히 「계획서 규약 — 이 프로젝트의 설정」 절 (값이 아니라 **판단 근거**) · 「dossier 는 독립」 절(**dossier 만 복제 허용 예외**, 다른 문서는 포인터·SoT 규칙을 따른다)
- `src/research_lab/CLAUDE.md`
- 전역 `~/.claude/CLAUDE.md` — 「문서와 주석은 리팩토링을 견디게 쓴다」 · 「문서 참조 방향」 · 「주석은 코드가 못 하는 말만 한다」 · 「새 파일은 이웃을 먼저 열고 넣는다」(**옮기거나 지울 때도 색인을 함께**)
- 선행 계획서 [PLAN_critical_bug_fixes.md](PLAN_critical_bug_fixes.md) — 진행 로그의 변경 파일 목록과 참고사항

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 `/impl-plan` 스킬)

- [x] D1 ~ D5 가 모두 충족됐다 (각 Phase 의 체크리스트)
- [x] `grep -rnE "DESIGN\.md|설계 §|DESIGN §" --exclude-dir=.venv --exclude-dir=plans --include=*.py --include=*.md --include=*.sh --include=.gitignore .` 결과가 **아래 허용 1건 말고 0건**이고 그 출력을 진행 로그에 남겼다. 허용: `tests/test_dossier.py` 의 금지 문자열 목록에 든 `"DESIGN.md"` — 러너 고정 문구에 문서 파일명이 없어야 한다는 계약이라 **지우지 않는다**(`docs/plans/` 는 두 새 계획서가 이 이름을 설명으로 담고 있어 제외한다)
- [x] 「OPERATIONS.md 의 절 번호」를 가리키는 곳(`scripts/trigger.sh` 의 사용자 메시지·주석, `src/research_lab/runner/usage.py` 주석, `docs/COMMANDS.md`)이 **여전히 맞는 절**을 가리킨다
- [x] **독립 재검증** 기록 — 작업 맥락을 물려받지 않은 서브에이전트가 D1 ~ D5 와 미커밋 diff 를 대조한 결과 (마지막 Phase)
- [x] 코드 리뷰 실행 및 결과 기록 (마지막 Phase 의 Validation 에 적는다 — 주석·테스트 한 줄이 바뀌므로 «해당 없음» 이 아니다)
- [x] 품질 검증 통과 (마지막 Phase 의 Validation 에 passed/failed/skipped 수를 적는다)
- [x] 자동 포맷 적용 완료 (마지막 Phase에서 실행)
- [x] 필요한 문서 업데이트 — 루트 `CLAUDE.md` 변경 있음 · `src/research_lab/CLAUDE.md` 변경 있음 · `docs/INDEX.md` 변경 있음 · `docs/COMMANDS.md` 변경 있음(교차 참조·중복 수치만, **명령과 옵션은 불변**) · `docs/OPERATIONS.md` 변경 있음 · 리서치 스킬 변경 있음
- [x] 근거 승격 완료 — 이 계획서를 지금 삭제해도 잃을 정보가 없다 (개선거리 5건 이관 · 규약 문구 변경이 그 자체다)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- 루트 `CLAUDE.md` — 「남은 개선거리」 절 신설(5건) · 「계획서 규약」의 근거 승격 문구 · 「세션 시작 규칙」 표에서 DESIGN 행 제거 · 낡은 서술 정정(Phase 4)
- `.claude/plan-config.json` — `evidence_home` 을 **`./`** 로(근거가 루트 `CLAUDE.md` 와 코드 주석으로 가므로 `docs/` 가 더는 맞지 않는다. `/impl-plan` 은 이 값을 «폴더 하나»로만 읽고 훅은 이 키를 쓰지 않는다)
- `docs/DESIGN.md` — **삭제**
- `tests/test_index.py` — 필수 문서 목록에서 `docs/DESIGN.md` 한 줄 제거
- `docs/INDEX.md` — DESIGN 행 제거 · OPERATIONS 행의 설명 정정
- `src/research_lab/CLAUDE.md` — DESIGN 포인터 4곳 · 서로 모순되는 두 문장 정정
- `.gitignore` — 주석 속 DESIGN 포인터 2곳
- `src/` · `tests/` · `scripts/` 의 주석·독스트링 — `설계 §N` · `DESIGN.md` 포인터(파일 목록은 Phase 2 의 grep 이 정한다) · 틀린 서술(Phase 4 목록)
- `docs/OPERATIONS.md` — 축약
- `docs/COMMANDS.md` — OPERATIONS 교차 참조 확인 · 중복 수치 정리 · 불필요한 `sys.path.insert` 한 줄 · 「(마지막 Phase에서만)」
- `.claude/skills/dossier-research/SKILL.md` — 틀린 서술 정정
- `docs/plans/PLAN_*.md` 19개 — 삭제(목록은 Phase 5)
- `docs/COMMANDS.md`: **명령·옵션 변경 없음** — 위 정정만

### 데이터/결과 영향

- 동작 불변. 에이전트가 매 회차 읽는 **리서치 스킬 문구**가 코드와 맞아진다(「실체 없음 조기 종료」를 지시하던 문장이 사라진다)
- 저장소에서 설계·실측 이력 문서가 사라진다 — 필요하면 git 이력에서 꺼낸다

## 6) 단계별 계획(Phases)

### Phase 0 — 해당 없음

동작을 바꾸지 않으므로 먼저 고정할 정책 테스트가 없다. 삭제 전후는 Phase 2 의 grep 과 `tests/test_index.py` 가 가른다.

---

### Phase 1 — 지우기 «전»에 옮길 것을 옮긴다 (D1 의 앞 절반)

**작업 내용**:

- [x] 선행 계획서의 진행 로그를 읽고, 이 계획서가 건드릴 파일 중 이미 바뀐 곳을 진행 로그에 적는다
- [x] DESIGN.md §10.1 의 G · C · I · P · R 본문을 읽고, 루트 `CLAUDE.md` 에 **「남은 개선거리」** 절을 만들어 위 표의 형태(요지 · 왜 아직 안 고치나 · 언제 다시 보나)로 한 줄씩 옮긴다. 숫자와 날짜는 결론에 필요한 것만
- [x] 루트 `CLAUDE.md` 「계획서 규약」 절에 **근거 승격 목적지 규약**을 적는다 — 「왜」는 그 코드 자리의 주석에(짧게), 저장소 전반의 결정·남은 개선거리는 루트 `CLAUDE.md` 에. 계획서를 링크하지 않는다
- [x] `.claude/plan-config.json` 의 `evidence_home` 을 `./` 로
- [x] 판단 기준 확인: DESIGN.md 에만 있고 **지금 코드가 의지하는 «왜»** 가 주석에 이미 있는지 Phase 2 에서 포인터를 지울 때 자리마다 본다(없으면 그 자리 주석에 한두 줄로 남긴다)

---

### Phase 2 — DESIGN.md 삭제와 포인터 정리 (D1 · D2)

**작업 내용**:

- [x] `docs/DESIGN.md` 삭제
- [x] `tests/test_index.py` 필수 문서 목록에서 `docs/DESIGN.md` 제거 · `docs/INDEX.md` 의 DESIGN 행 제거 · 루트 `CLAUDE.md` 「세션 시작 규칙」 표의 DESIGN 행 제거(번호 정리)
- [x] `src/research_lab/CLAUDE.md` 의 DESIGN 포인터(머리말 · §2 · §6 · §7)를 지운다 — 뒤따르는 문장이 이미 이유를 말하면 포인터만, 아니면 필요한 사실 한 줄을 그 자리에
- [x] `.gitignore` 주석의 DESIGN 포인터 2곳 — 이유 문장은 이미 있으므로 포인터만
- [x] `src/` · `tests/` · `scripts/` 의 `설계 §N` · `DESIGN.md` 포인터를 전부 처리한다(주석·독스트링만). 원칙: **포인터를 지우고 그 문장이 혼자 서게** 다듬는다 — 「설계 §7 이 자리마다 적어 두었다」 → 「자리마다 안 적으면 생기는 일이 있다」처럼. 기계적 교체라 서브에이전트에 맡겨도 된다(사용자에게 묻지 못하므로 «원칙만» 주고 결과 diff 는 이 세션이 읽는다)
- [x] **번호 없이 그 문서를 가리키는 문장**도 찾는다 — `grep -rnE "설계가|설계의|설계 표|로드맵은" --exclude-dir=.venv --exclude-dir=plans --include=*.py --include=*.sh .` 로 훑어, 가리키는 내용이 **루트 `CLAUDE.md` 에 이미 있으면 그대로 두고**(그 문서도 「설계」다), 삭제된 문서에만 있던 것(예: 「설계의 채워 본 예시」 · 「설계 §9 의 ①」 · 「로드맵은 …라 적었고」)이면 같은 원칙으로 다듬는다
- [x] 위 DoD 의 grep 을 돌려 남은 것이 옛 계획서(아직 안 지움)와 허용 1건뿐인지 본다

---

### Phase 3 — OPERATIONS 축약 (D3)

**작업 내용**:

- [x] 🔴 **절 번호 1 ~ 8 과 하위 번호 3.0 · 3.1 · 3.2 · 3.3 · 4.1 · 5.1 · 5.2 · 8.1 · 8.2 · 8.3 을 유지한다** — 밖에서 번호로 가리킨다: `scripts/trigger.sh`(사용자에게 나가는 메시지 「docs/OPERATIONS.md 7절」 · 「3절」 포함, 주석의 6절 · 5.1 · 8.3 · 3.3) · `src/research_lab/runner/usage.py`(5.2 절) · `docs/COMMANDS.md`(5.1 · 3.3). 번호를 바꾸면 그곳들을 함께 고친다
- [x] **남길 것**: 운용기(mac) 결정과 **WSL 은 예약 없이 손으로 돌린다는 2026-09-26 결정의 내용**(빠진 것은 트리거뿐 · WSL 예약을 붙이려면 절차를 새로 씀 · 두 기계를 동시에 돌리지 말 것) · 착수 전 확인 명령 셋 · 엔진 자동 시작과 「stopped 공회전」 판별법 · plist 템플릿과 「조용히 틀어지는 자리 셋」 · 등록 · 절전 해제와 「그 시각에 못 돈다 / 안 돈다」 표 · 등록 뒤 확인과 $0 찔러보기 · 결과를 어디서 보나 · 중단 판정 표 · 한도 보정 절차와 함정 표 · 기계가 안 막는 것 · 기계 이전 표 · 끄기/켜기(두 동작)와 되돌리기 · 정의 파일을 고친 뒤 · 이미지 재빌드 조건
- [x] **걷어낼 것**: 실측 경위 이야기(「사흘간」 · 「열나흘」 · 「24초」 류 — 결론 한 줄만) · DESIGN 포인터 · 다른 문서와 중복된 수치(한 장당 23% · 25.6% · 27.5% 등) · **틀린 값**(「회차 하나는 $2 ~ 5」 → 값 없이 「에이전트를 부르지 않아 비용 0」만) · 가리키는 곳이 없는 문구(3.1 표의 「아래 「12시 이후 줄이 아예 없다」」 → 5.1 의 「그 회차의 줄이 아예 없다」 · 3.3 안의 「아래 3.3 은」)
- [x] 분량 기준은 «절차와 함정만»이다(대략 원래의 1/4 을 목표로 하되 절차를 자르지 않는다)
- [x] `docs/COMMANDS.md`: OPERATIONS 교차 참조가 맞는지 · 「기본값이 네 장인 근거」의 중복 수치를 뜻만 남기기 · 「(마지막 Phase에서만)」 제거 · 중단 회차 조회 명령의 `sys.path.insert(0,'src')` 제거(poetry 환경에 패키지가 `.pth` 로 설치돼 있어 불필요 — **고친 명령을 한 번 실제로 돌려** 결과를 진행 로그에)

---

### Phase 4 — 낡은·틀린 서술 정정 (D5)

**작업 내용** (줄 번호는 선행 계획서 이전 기준 — 문구로 찾는다):

- [x] 루트 `CLAUDE.md`
  - 「실행 스크립트가 명시적으로 unset 하고」 → 실제는 **거부만** 한다(`docker/run.sh` · `scripts/run_cycle.py`)
  - `--max-budget-usd` 가 구독에서 동작하는지 「[미검증]」 · 「무시된다면 러너가 세션 로그의 토큰을 더해 직접 끊습니다」 → 실측으로 **동작한다**(`scripts/run_cycle.py` 의 `DEFAULT_BUDGET_USD` 주석) · 그 대체 장치는 없다
  - 「게이트가 dossier 안의 **모든 URL** 을 실제로 호출」 → 출처 칸(`evidence` · `rebuttals` · `sources` · 계보)의 URL. **산문 속 URL 은 검사하지 않는다**를 사실대로
  - 「회차는 돕니다」 표의 「탐색으로 전환 · 남은 예산을 로그에」 → 지금 루프는 **요청한 장수**가 상한이고 금액으로 판정하지 않는다(`scripts/run_cycle.py` `_loop_stop_reason`)
  - 「실패를 셋으로 가른다」 → 셋(한도 · 인증 · 그 외)에 더해 **예산(폭주 감지 상한)** 과 **품질(게이트가 막음)** 이 따로 있고 둘 다 재시도하지 않는다(`runner/failures.py` `FailureKind`)
- [x] `docs/INDEX.md` OPERATIONS 행 — 「등록과 설정은 사람이 직접 하므로 «넘기는 가이드»」 → 등록은 에이전트가 하고 `sudo`·설치만 사람 몫(OPERATIONS 머리말과 루트 `CLAUDE.md` 「트리거 등록은 «제가» 합니다」)
- [x] `src/research_lab/CLAUDE.md` — 「`gate` 는 파일을 읽고 판정만 합니다」(계층 구조 절)와 §5 「파일을 열지 않고 파싱된 값을 받아」가 서로 반대다. 사실은 **게이트는 값을 받아 판정하되 `gate/secrets.py` 만 러너가 쓴 파일을 직접 훑는다** — 그렇게 한 문장으로 맞춘다
- [x] 리서치 스킬(`.claude/skills/dossier-research/SKILL.md`)
  - 「[현재 상태] 러너가 기계로 검사하는 것」 표: URL 검사 단계에 **계보 · 메커니즘** 추가 · **자립성(가리키는 말) 검사** 행 추가 · 「[현재 상태]」 꼬리표 제거
  - §5 「하나라도 있으면 그 회차는 미완성으로 끝나고, 산출물은 저장되지 않는다」 → 수집은 그 주소를 짚어 **한 번 다시 묻고**, 그래도 죽으면 그 후보를 미루고 다음 후보로 간다. 나머지 단계는 미완성으로 끝난다
  - §6 「찬성 근거가 0건이면 「실체 없음」으로 조기 종료한다」 → **(사용자 결정) 0건도 정상 결과이며 그대로 적고, 나머지 칸을 채워 판정에서 결론낸다**
  - 탐색 절 「숫자와 판정 시점을 담은 한 문장」 → 「무엇을 언제 사고 언제 파는가」 한 문장. 값이 빈 말은 파라미터 축으로(같은 문서 §7 과 일치)
- [x] 코드 주석·독스트링의 틀린 서술(동작 불변)
  - `runner/lineage.py` 머리: 「판 것」 표시 자리가 「실현가능성」이라는 문장 → 마지막 단계(판정)
  - `gate/feasibility.py` 머리: 「판정(2번 칸)이 아직 없으므로」 → 판정 단계가 있다(선행 계획서가 이 파일의 `_is_filled` 를 옮겼으니 현재 문구를 확인)
  - `runner/collect.py` `_reject` 독스트링: 「부르는 자리가 둘」 → 하나(두 번째 답의 축 누락은 `_carry_forward` 가 되돌린다)
  - `runner/prose_check.py` 머리: 「여섯 번」 → 자립성 검사를 부르는 단계 수(현재 7)와 맞게 — **개수를 적지 않는 문장**으로
  - `runner/url_check.py` 머리 「네 단계가 같은 값을 적는 일을」 · `runner/payload.py` 머리 「네 단계가 같은 모양의 JSON」 → 개수 없이
  - `agent/invoke.py` `AgentResult.usage` 주석: 「한도는 그 토큰도 먹으므로」 → 같은 파일 `ALL_USAGE_KEYS` 주석과 `runner/usage.py` 머리의 실측대로(한도 비율의 분자는 새 토큰이며 캐시 읽기는 세지 않는다 · 성분은 다시 계산할 재료로 남긴다)
  - `runner/usage.py` `Tokens.all_total` 독스트링: 「회차 로그에 그대로 실려」 → 실제로는 회차 로그에 성분 넷과 `tokens_new_total` 이 실리고 이 합은 실리지 않는다(함수 존폐는 비목표 — 서술만)
  - `gate/quantified.py` 머리 표: 네 번째 갈래 「주체가 없는 예측」(사전의 「예상되는」 류) 행 추가

---

### Phase 5 — 옛 계획서 삭제 (D4)

**작업 내용**:

- [x] 삭제 전 19개 모두 `**상태**: ✅ Done` 인지 다시 확인하고 그 출력을 진행 로그에
- [x] 삭제: `PLAN_agent_model_opus.md` · `PLAN_cycle_dossier_count.md` · `PLAN_failed_call_cost.md` · `PLAN_opus_limit_calibration.md` · `PLAN_output_values_and_decode_errors.md` · `PLAN_phase1_skeleton.md` · `PLAN_phase2_rebuttal_lineage.md` · `PLAN_phase3_url_liveness.md` · `PLAN_phase4_feasibility.md` · `PLAN_phase5_dossier.md` · `PLAN_phase6_schedule.md` · `PLAN_phase7_usage_logging.md` · `PLAN_prompt_via_stdin.md` · `PLAN_rename_night_to_cycle.md` · `PLAN_retry_path_gates.md` · `PLAN_selfcontained_priming.md` · `PLAN_trigger_control.md` · `PLAN_unenforced_guarantees.md` · `PLAN_url_gate_false_dead.md`
- [x] 남는 것: `.gitkeep` · `PLAN_critical_bug_fixes.md` · `PLAN_docs_consolidation.md`
- [x] DoD 의 grep 을 다시 돌려 허용 1건 말고 0건

---

### 마지막 Phase — 재검증·최종 검증

**작업 내용**

> 🔴 **`/commit` 이 «맨 마지막»인 것은 의도다.** 그 스킬은 「후보 뒤에는 아무것도 덧붙이지 말 것」으로
> 끝나므로 **호출하는 순간 그 턴이 거기서 닫힌다.** 중간에 두면 뒤에 적힌 항목이 그 벽 너머에 남는다 —
> 실제로 두 번 그렇게 샜다(`[실측] 2026-09-14` 후보를 계획서에 안 옮김 · `2026-09-16` 옮기고 체크박스를 안 닫음).
> **체크박스와 상태를 먼저 확정하고, 커밋 후보를 마지막에 만든다.**

- [x] 필요한 문서 업데이트 (`docs/COMMANDS.md` — Phase 3 의 정정만, 명령·옵션 불변)
- [x] **링크 점검** — 바뀐 문서들의 상대 링크가 실재 파일을 가리키는지(특히 DESIGN · 옛 계획서로 가는 링크 0건)
- [x] **독립 재검증** — 서브에이전트(대화 맥락 없음)에게 이 계획서 경로와 「D1 ~ D5 가 미커밋 diff 에서 충족됐는지 · 동작이 바뀐 코드 줄이 없는지 · 옮긴 개선거리 5건이 원문과 뜻이 같은지(삭제 전 원문은 `git show HEAD:docs/DESIGN.md` 로 읽는다)」를 맡기고 결과를 진행 로그에. 서브에이전트는 판정만, 수정은 이 세션이 한다
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

- [x] `/code-review xhigh` **1회차** (발견 13건 — 버그 0 · 그 외 13 · 조치: 독립 재검증 지적과 합쳐 사용자 결정으로 A(이 diff 가 만든 틀림) · B(이 변경과 어긋나게 된 기존 서술) 고침, C 는 목록만 — 진행 로그 17:40 · 17:44 · 17:48)
- [x] `/code-review xhigh` **2회차** (발견 11건 — 버그 0 · 그 외 11 · 조치: 사용자 결정으로 좁게 8건 고침(R2-1 ~ R2-7 · R2-11), R2-8 ~ R2-10 은 목록만 — 진행 로그 21:24 · 21:28)
- [x] `poetry run python validate_project.py` (passed=603, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

> **Done 직전에 `/commit` 을 실행해 이 절을 채운다. 그전에는 비워 둔다.**
> 계획서를 쓰는 시점에는 diff 가 없어 여기 적는 것은 전부 추측이고,
> **추측으로 적은 줄은 그대로 나간다.** 형식·문체 규칙은 `/commit` 이 정한다.

1. 문서 / 설계 문서 삭제와 운용·규약 문서 정리
2. 문서 / DESIGN.md · 완료 계획서 19개 삭제 및 남은 개선거리의 루트 CLAUDE.md 이관
3. 문서 / 삭제한 설계 문서의 포인터 제거와 코드와 어긋난 문서·주석 서술 정정
4. 문서 / DESIGN.md 삭제 · OPERATIONS 절차 중심 축약 · 리서치 스킬의 URL 검사·실체 없음 서술을 러너 동작과 일치 · 근거 승격 목적지 변경
5. 문서 / 코드와 떨어져 낡아 가던 설계 문서 폐지와 근거의 코드 주석 · 루트 CLAUDE.md 일원화

## 7) 리스크(Risks)

- **지운 뒤에야 필요했던 근거를 찾는다** — 원문은 git 이력에 있다(`git show <커밋>:docs/DESIGN.md`). 포인터를 지울 때 그 자리 주석이 혼자 서는지 자리마다 보는 것으로 대부분 막는다
- **OPERATIONS 절 번호가 바뀌어 밖의 참조가 조용히 틀어진다** — 번호 유지를 Phase 3 의 첫 조건으로 두고 DoD 에서 참조처를 다시 본다. `trigger.sh` 의 해당 줄은 **사용자에게 나가는 메시지**다
- **주석 대량 편집이 동작을 건드린다** — 주석·독스트링만 바꾼다. 독립 재검증과 `/code-review` 가 「동작이 바뀐 줄」을 찾는다
- **리서치 스킬 문구가 에이전트 행동을 바꾼다** — 코드와 맞추는 방향이라 기대 동작은 지금과 같다(0건이어도 끝까지 돈다)
- **계획서 게이트** — 이 계획서가 `docs/plans/` 에 있어 훅이 계속 동작한다. 옛 계획서를 지워도 `.gitkeep` 과 두 새 계획서가 폴더를 유지한다

## 8) 메모(Notes)

- 선행 계획서: [PLAN_critical_bug_fixes.md](PLAN_critical_bug_fixes.md) — 착수 시 진행 로그부터 읽는다
- 이 계획서를 만든 세션(2026-09-26)의 전수 분석에서 «문서/주석/코드 불일치»로 나온 것 중 DESIGN.md 안의 항목은 **삭제로 해소**되고, 나머지가 Phase 4 목록이다
- 코드 주석의 이력·수치 정리는 사용자가 패스했다 — 틀린 서술만 고친다(비목표)

### 진행 로그 (KST)

- 2026-09-26 12:02: 계획서 작성. 사용자 결정(DESIGN 삭제 · 개선거리 5건 루트 CLAUDE.md 이관 · OPERATIONS 제자리 축약 · 「실체 없음」은 문서를 코드에 맞춤 · 옛 계획서 삭제)을 범위로 잡았다. 옛 계획서 19개가 전부 ✅ Done 인 것과 OPERATIONS 절 번호를 밖에서 가리키는 곳을 작성 세션에서 확인했다
- 2026-09-26 17:11: 실행 세션 착수. **착수 조건 확인** — 선행 계획서 `**상태**: ✅ Done` · 사용자 커밋 `67a151c` · 작업 트리 깨끗
  - **선행 계획서 진행 로그에서 이 계획서가 건드릴 파일 중 이미 바뀐 곳**: `agent/invoke.py`(`StepFailed` 가 옮겨 오며 `DESIGN.md §11.14` 포인터를 그 독스트링에 달고 왔다) · `gate/feasibility.py`(사설 `_is_filled` 가 `gate/filled.py` 로 빠졌다 — Phase 4 의 「판정(2번 칸)이 아직 없으므로」 문장은 그대로 있다) · 리서치 스킬(계보 절 · 실현가능성 절을 고쳤다 — Phase 4 의 표 · §5 · §6 · 탐색 절은 손대지 않았다) · `gate/quantified.py`(`is_filled` 로 바뀐 것뿐 머리 표는 그대로). 선행 계획서가 이 계획서에 넘긴 것: R3-9(`src/research_lab/CLAUDE.md` §12 와 계층 설명이 `gate/filled.py` 를 모른다)
  - **Phase 4 의 주장을 현재 코드와 대조 — 전부 여전히 참**: `docker/run.sh` · `scripts/run_cycle.py` 는 API 키를 unset 하지 않고 거부만 한다 · `DEFAULT_BUDGET_USD` 주석이 구독 인증에서 플래그가 동작한다고 실측으로 적는다 · URL 검사는 `evidence` · `rebuttals` · 실현가능성/메커니즘 `sources` · 계보 덩어리만 본다(`payload.urls_in`) · 루프는 `_loop_stop_reason` 이 실패 · 0장 · 요청 장수 도달로만 멈추고 금액을 보지 않는다 · `FailureKind` 는 한도 · 인증 · 예산 · 품질 · 그 외 다섯이고 재시도는 그 외만(`should_retry`), 막힘 횟수는 품질 · 그 외만 센다(`COUNTED_FAILURE_KINDS`) · 자립성 검사를 부르는 단계는 수집 · 반증 · 계보 · 실현가능성 · 메커니즘 · 측정 설계 · 판정 · `collect._reject` 를 부르는 곳은 하나 · 찬성 근거 0건이면 수집은 「실체 없음」을 로그에 적고 회차는 계속 돈다
  - **DoD grep 이 못 잡는 포인터를 더 찾았다**(D2 범위라 함께 처리한다): 루트 `CLAUDE.md` 「§2 의 채워 본 예시」 · `tests/test_ledger.py` · `tests/test_runner_blocked.py` 의 「§10.1 E」 · `tests/test_runner_blocked.py` 의 「§9 의 ①」 · `src/research_lab/CLAUDE.md` §9 의 「§7 의 범위를 좁힌 것」(그 문서의 §7 은 잠금 이야기라 이미 엉뚱한 곳을 가리키고 있었다) · `docs/OPERATIONS.md` 의 「(§11.9)」 · 「(§11.15)」
  - **범위 조정 (사용자 결정)** — 본문은 고치지 않고 이 줄이 근거다
    - 선행 계획서에만 남은 목록(비목표 「잠재 결함」 5 · 진행 로그 「남은 개선거리」 9) 중 **결과를 틀어지게 할 수 있는 것만** 루트 `CLAUDE.md` 「남은 개선거리」에 더한다 — 산문 속 URL 미검사 · 닫힌 폴더를 이어받은 반복이 루프를 멈춤 · 목록 값의 파이썬 표기(반증 러너의 `not_found_reason` 저장 포함) · 계보 수가 같은 주소를 두 번 셈 · 조사형 사전의 출처 제목 오탐 · 탐색 상한을 중복 제거 전에 걺. 스타일 · 중복 가드 · 테스트 공백 · 로그 누락 · 수동 경로 한정(`--run-dir` 로 망가진 상태 파일) · 추측성(`_result_from` fallback)은 옮기지 않는다
    - Phase 4 에 **계획서 목록 밖의 틀린 서술 3건**을 더한다 — `agent/invoke.py` 모듈 머리의 「[미검증] 응답 모양과 한도 소진 실패 모양은 아직 실측되지 않았다」(둘 다 2026-09-12 실측, `tests/test_agent_response_shape.py`) · `common_constants.py` `DATA_CATALOG_PATH` 주석의 「회차의 마지막 단계가 먹는 입력」(실현가능성 단계다) · `src/research_lab/CLAUDE.md` 가 `gate/filled.py` 를 모른다(R3-9)
- 2026-09-26 17:15: Phase 1 완료
  - **예상과 달랐던 것 ① 개선거리 I 는 이미 답이 나와 있었다 → 닫고 옮기지 않음(사용자 결정)**. 「다시 볼 때」가 「WSL 에서 품질 검증을 돌리면 `tests/test_runner_state.py` 의 계약 테스트가 답한다(저장소가 리눅스 파일시스템일 것)」인데 이 세션이 그 조건이다. `uname -r` → `6.6.87.2-microsoft-standard-WSL2` · 저장소와 스크래치 폴더 모두 `df -T` → `/dev/sdd ext4` · `poetry run pytest tests/test_runner_state.py -q -k lock --basetemp=<스크래치>` → `10 passed, 14 deselected`(SIGKILL 된 보유자의 잠금 회수 포함). 선행 계획서의 품질 검증(604 passed)도 같은 기계였다. 남는 단서(Windows 드라이브에서는 재지 않았다)는 Phase 3 에서 OPERATIONS 기계 이전 절에 한 줄로 남긴다
  - **예상과 달랐던 것 ② DESIGN 의 C 본문이 틀린 것을 하나 들고 있었다** — 「로그에 걸린 표현이 남아 있어(`triggered_terms`)」. 그 이름은 `gate/quantified.py` 의 함수일 뿐 결정 로그의 열쇠가 아니다(`grep` 으로 `runner/collect.py` 의 지시문 조립에서만 쓰임). 그래서 C 행의 「언제 다시 보나」에 그 로그를 적지 않았다
  - 루트 `CLAUDE.md` 「남은 개선거리」 — 「판단을 기다리는 것」(G · C · P · R — DESIGN 이 사라지면 글자 이름이 뜻을 잃으므로 이름 없이 옮겼다) · 「미뤄 둔 잠재 결함」(위 17:11 범위 조정의 여섯). 「계획서 규약」에 근거 승격 목적지 한 항목(코드 자리의 주석 · 이 문서 · 설계 문서를 따로 두지 않는 이유). `.claude/plan-config.json` 의 `evidence_home` → `./`
- 2026-09-26 17:21: Phase 2 완료 — 서브에이전트에 맡기지 않고 이 세션이 자리마다 직접 고쳤다(문장이 혼자 서는지를 자리마다 판단해야 해서)
  - **포인터를 지우며 그 자리에 사실을 남긴 곳**(나머지는 뒤 문장이 이미 이유를 말해 포인터만 걷었다): 루트 `CLAUDE.md` 1번 칸 절의 「§2 의 채워 본 예시」 → 「「1월 효과」를 채워 본 설계 예시부터 진입 … 청산 … 격자로 받았다」(`gate/quantified.py` · `tests/test_gate_quantified.py` 의 「설계의 채워 본 예시」가 이제 이 문장을 가리킨다) · `gate/feasibility.py` · `tests/test_gate_feasibility.py` · `tests/test_dossier.py` 의 「§2 의 예시」 → 「「1월 효과」를 채워 본 설계 예시」 · 「§10.1 A 가 실측으로 뒤집은 함정」 → 「한 줄 주장의 정성 표현 사전이 실측으로 뒤집은 함정(그 사전이 기각 목록이었다면 후보 13개 중 12개가 죽었다)」 · `gate/rebuttal.py` · `tests/test_gate_rebuttal.py` 의 「로드맵은 …, 설계 §5.5 A 는 …」 → 두 규정을 그 자리에 · `runner/cycle_log.py` 의 「실측은 `docs/DESIGN.md`」 → 「실측은 `usage` 모듈 머리」(그 표가 거기 있다) · `src/research_lab/CLAUDE.md` §9 의 「§7 의 범위를 좁힌 것」 → 「스캔 범위에서 회차마다 쌓이는 폴더를 빼고 그 회차의 것만 보는 것」 · 테스트의 「§10.1 E」 → 「막힘」
  - **Phase 4 항목 중 같은 줄을 만진 김에 먼저 고친 것**: `gate/feasibility.py` 머리의 「판정(2번 칸)이 아직 없으므로」 · `agent/invoke.py` 모듈 머리의 [미검증] · `AgentResult.usage` 주석 · `runner/usage.py` `Tokens.all_total` · `common_constants.py` `DATA_CATALOG_PATH` 주석. 그리고 **목록에 없던 형제 하나** — `tests/test_gate_feasibility.py::test_cost_terms_are_counted_but_not_blocked` 독스트링에도 같은 「판정(2번 칸)이 아직 없으므로 그 값이 결론을 만들 자리도 아직 없다」가 있어 게이트 쪽과 같은 문장으로 맞췄다
  - `docs/INDEX.md` 3절 제목 「설계·실행 문서」 → 「실행·참고 문서」(설계 문서가 없어져 제목이 거짓이 된다. 이 제목을 가리키는 곳 0건)
  - **그대로 둔 「설계가 …」 문장**(가리키는 내용이 루트 `CLAUDE.md` 나 그 코드 자리에 있다): `runner/failures.py` 두 곳 · `tests/test_agent_response_shape.py` 두 곳(실패 셋의 갈래 · 한도 재시도 안 함) · `scripts/run_cycle.py` · `tests/test_runner_cycle.py`(미완성 최대 1개) · `tests/test_run_cycle_entrypoint.py` · `tests/test_runner_state.py`(컨테이너가 죽어도 같은 방식으로 복구) · `gate/mechanism.py` · `tests/test_gate_mechanism.py`(3 · 9번 칸의 갈래) · `gate/quantified.py` · `tests/test_gate_quantified.py`(위 채워 본 예시) · `tests/test_gate_feasibility.py` 376행(「분포를 쌓아 나중에 판단한다」 — `gate/feasibility.py` `cost_terms_in` 독스트링에 있다)
  - DoD grep(삭제 뒤): `tests/test_dossier.py:43` 허용 1건 + `docs/OPERATIONS.md` 3줄(Phase 3 몫). `§11.` · `§10.1` · `§9 의` 등 번호만 쓴 꼴은 `docs/OPERATIONS.md` 349 · 350 행 말고 0건
- 2026-09-26 17:25: Phase 3 완료
  - **OPERATIONS 절 번호**: `## 1` ~ `## 8` 과 `3.0 · 3.1 · 3.2 · 3.3 · 4.1 · 5.1 · 5.2 · 8.1 · 8.2 · 8.3` 전부 그대로(`grep -nE "^#{2,4} "`). 밖의 참조가 기대하는 내용도 그 절에 남았다 — 7절(다른 기계의 트리거) · 6절(이미지 이름으로 거르지 않는 이유) · 5.1(끊긴 회차는 전원 차단과 구별되지 않는다) · 8.3(파일만 고치면 올라간 정의가 그대로 돈다) · 3절(작업 정의 파일 만드는 절차) · 3.3(`pmset -g sched` 빈 출력의 오판) · 5.2(보정 절차) · COMMANDS 의 5.1 · 3.3
  - **걷어낸 것**: DESIGN 포인터 3 · 「(§11.9)」 「(§11.15)」 · 한 장당 23% · 25.6% · 27.5% 블록 · 「회차 하나는 $2~5」(→ 「에이전트를 한 번도 부르지 않아 비용이 0」) · 실측 경위(엔진 시작이 부팅보다 열나흘 늦음 · 24초 복귀 · 사흘간 놓침 · 더미 LaunchAgent 의 로그 줄 수와 `rc=113` · WSL 예약 이력 조사 경위) → 결론 한 줄씩 · 3.1 표의 「아래 「12시 이후 줄이 아예 없다」」 → 「5.1 의 「그 회차의 줄이 아예 없다」」 · 3.3 끝의 「아래 3.3 은 …」 · 5.2 분자 규칙의 근거 → `src/research_lab/runner/usage.py` 모듈 머리의 표를 가리킴(저장소 안의 살아 있는 코드) · 함정 표 「관찰자 몫」의 예전 방식 비교(같은 말이 `usage.py` `CALIBRATION` 주석에 있다) · 5.1 뒤 「이 파일이 있는 이유」 문단은 한 문장으로
  - **더한 것**: 7절 끝 「저장소는 리눅스 파일시스템에 둡니다 — WSL 의 리눅스 파일시스템에서 확인(2026-09-26), Windows 드라이브에서는 재지 않았다」(17:15 의 개선거리 I 종결). 오타 하나 — 함정 표 「「전» 값」의 짝이 안 맞는 괄호
  - **분량 — 1/4 에 못 미쳤다**: 490 → 440 행 · 31,312 → 26,256 바이트. 구성을 재 보니 지금 440 행 중 코드 블록 119 · 표 60 · 제목 20 · 빈 줄 96(합 295)이 「남길 것」 목록의 절차와 표이고, 산문은 183 → 145 행이다. 원래 문서가 이미 대부분 절차 · 함정이라 1/4 은 절차를 자르지 않고는 닿지 않는다 — 계획서가 「절차를 자르지 않는다」를 앞에 두었으므로 여기서 멈췄다
  - **COMMANDS**: 「(마지막 Phase에서만)」 제거 · 「기본값이 네 장인 근거」의 수치를 걷고 그 실측이 있는 자리(`scripts/run_cycle.py` 의 `DEFAULT_CYCLE_DOSSIERS` 주석)를 가리킴 · 중단 회차 조회의 `sys.path.insert` 제거. OPERATIONS 교차 참조 둘(5.1 · 3.3)은 그대로 맞다. 명령 · 옵션 변경 없음
  - **고친 조회 명령 실행 결과**(저장소 루트에서 `poetry run python -c "…"` 그대로): `['5daee239-c7e9-4d7f-9394-6150e84cd672']` · 종료 코드 0. 패키지가 `.venv/lib/python3.12/site-packages/research_lab.pth`(내용 `/home/yblee/workspace/research-lab/src`)로 잡혀 있어 `sys.path` 조작이 필요 없다. 나온 한 건은 `runs/cycles.jsonl` 5행 — 2026-09-15 17:15 에 시작하고 종료 줄이 없는 회차다(이번 변경과 무관, 참고로만)
- 2026-09-26 17:29: Phase 4 완료 — 고친 문장마다 근거 코드를 다시 읽고 맞췄다
  - **루트 `CLAUDE.md`**: API 키 행 → 「실행 스크립트와 러너가 시작을 거부 · 값이 비어도 거부」(`docker/run.sh` 29행 · `scripts/run_cycle.py` 의 `assert_subscription_only` → `EXIT_AUTH` · `billing_guard` 독스트링의 빈 문자열 거부) · `--max-budget-usd` → 「구독 인증에서도 실제로 끊는다(2026-09-15 실측) · 러너가 따로 끊는 장치는 없다」 · 「없는 출처」 → URL 을 내는 단계마다 출처 칸만 · 수집은 다시 묻고 나머지는 미완성 · 산문 속 URL 은 안 봄(→ 「남은 개선거리」) · 「회차는 돕니다」 표 → 장수가 상한 · 금액으로 판정 안 함 · 한도 소진은 깨끗이 멈춤 · 한 장도 못 낸 반복은 멈추고 이유를 결정 로그에(`_loop_stop_reason`), 뒤 문장의 「예산이 모자라면」 → 「한도가 모자라면」 · 「실패를 셋으로 가른다」 뒤에 예산 · 품질 두 갈래(재시도 안 함 · 막힘에는 품질과 그 외만 셈 — `should_retry` · `COUNTED_FAILURE_KINDS`)
  - **`docs/INDEX.md`** OPERATIONS 행 — 등록은 에이전트 · `sudo` 와 설치만 사람 몫
  - **`src/research_lab/CLAUDE.md`**: 계층 절 「`gate` 는 파일을 읽고」 → 「값을 받아 … 예외는 자격증명 검사 하나(§5)」 · §5 에 같은 예외와 이유(검사 대상이 «파일에 실제로 쓰인 것» · 범위는 러너가 넘김) · (범위 조정 3건 중 R3-9) 계층 트리의 gate 설명에 「게이트 공용 「채워졌나」 판정」 · §12 표에 `gate/filled.py` 행(조립부가 게이트와 같은 판정을 해야 하는 자리도 쓴다 — `runner/dossier.py` 의 `single_value_reason`) · §12 마지막 항목 「게이트는 이 helper 를 못 쓴다 … 자리마다 테스트로」 → 「러너의 helper 를 못 쓴다 · 게이트끼리 겹치는 판정은 게이트 계층 안 한 곳 · 한 게이트에서만 쓰는 가드는 테스트로」
  - **리서치 스킬**: 검사 표의 「[현재 상태]」 꼬리표 제거 · URL 행에 계보 · 메커니즘을 더하고 수집만 다시 묻는다고 · 자립성 행 신설 · §5 의 「그 회차는 미완성으로 끝나고, 산출물은 저장되지 않는다」 → 수집은 다시 묻고 미루며 나머지는 미완성 · §6 「실체 없음으로 조기 종료」 → 빈 목록 그대로, 회차는 멈추지 않고 판정에서 결론(수집 지시문의 「「실체 없음」도 정상 결과입니다」와 같은 뜻) · 탐색 절 「숫자와 판정 시점을 담은」 → 탐색 지시문과 같은 「무엇을 언제 사고 언제 파는가」 + 값이 빈 말은 파라미터 축
  - **코드 주석**(Phase 2 에서 먼저 고친 다섯은 17:21 에): `runner/lineage.py`(표시 자리 → 판정) · `runner/collect.py` `_reject`(부르는 자리 하나 · 둘째 답의 축 누락은 `_carry_forward` 가 되돌림) · `runner/prose_check.py` · `runner/url_check.py` · `runner/payload.py`(개수 → 「단계마다」 · 「여러 단계」) · `gate/quantified.py` 머리 표에 「주체가 없는 예측」 행과 「뒤의 둘」 → 「뒤의 셋」
- 2026-09-26 17:30: Phase 5 완료 — 삭제 전 확인 출력(19개 전부 한 줄씩): `PLAN_agent_model_opus.md` · `PLAN_cycle_dossier_count.md` · `PLAN_failed_call_cost.md` · `PLAN_opus_limit_calibration.md` · `PLAN_output_values_and_decode_errors.md` · `PLAN_phase1_skeleton.md` · `PLAN_phase2_rebuttal_lineage.md` · `PLAN_phase3_url_liveness.md` · `PLAN_phase4_feasibility.md` · `PLAN_phase5_dossier.md` · `PLAN_phase6_schedule.md` · `PLAN_phase7_usage_logging.md` · `PLAN_prompt_via_stdin.md` · `PLAN_rename_night_to_cycle.md` · `PLAN_retry_path_gates.md` · `PLAN_selfcontained_priming.md` · `PLAN_trigger_control.md` · `PLAN_unenforced_guarantees.md` · `PLAN_url_gate_false_dead.md` → 각각 `**상태**: ✅ Done`. 계획서 폴더 밖에서 이 파일들을 가리키는 곳 0건(`grep -rn "PLAN_"` — 루트 `CLAUDE.md` 의 `PLAN_*.md` 패턴 설명 한 줄뿐). 삭제 뒤 폴더: `.gitkeep` · `PLAN_critical_bug_fixes.md` · `PLAN_docs_consolidation.md`
  - **DoD grep 출력**(삭제 뒤, `--exclude-dir=plans`): `tests/test_dossier.py:43:    "DESIGN.md",` — 허용 1건뿐
- 2026-09-26 17:40: 마지막 Phase 진행
  - **링크 점검**: 저장소의 `.md` 11개(`runs/` · `dossier/` · `.venv` 제외)의 상대 링크 24개 전부 실재 — 깨진 것 0
  - **자동 포맷**: `poetry run black .` → 84개 파일 변경 없음
  - **동작 불변 확인**: 변경된 `.py` 28개를 HEAD 와 «독스트링을 걷은 AST» 로 비교 — 코드가 달라진 파일은 `tests/test_index.py`(필수 문서 목록에서 한 줄) 하나뿐
  - **중간 품질 검증**(최종 기록 아님): Ruff 통과 · PyRight 통과 · Pytest passed=603, failed=0, skipped=0. 선행 계획서 최종 604 에서 1 줄어든 것은 `tests/test_index.py::test_core_documents_linked` 의 `docs/DESIGN.md` 파라미터가 빠졌기 때문이다
  - **`/code-review xhigh` 1회차 — 발견 13건(버그 0 · 그 외 13)**. 실행되는 코드의 변경은 테스트 한 줄뿐이라 전부 문서·주석 지적이다 — `/impl-plan` 규칙대로 **목록만 남기고 고치지 않은 채 사용자에게 보고**한다. 이 diff 가 만든 것과 원래 있던 것을 갈라 적는다
    - **이 diff 가 만든 것**: ① `docs/OPERATIONS.md` 함정 표 「창이 리셋을 가로지른다」 — 「회차 종료 예상보다 뒤인지」를 보라면서 그 예상의 유일한 재료(「Opus 한 장은 40 ~ 50분」)를 지웠다 ② 리서치 스킬 검사 표 URL 행 · §5 — 수집이 «미룬 후보가 상한(`MAX_DEFERRALS`)에 닿거나 남은 후보를 전부 미루면» 그 단계가 실패한다는 것을 빠뜨렸다(`collect._give_up_on_deferred`) ③ `src/research_lab/CLAUDE.md` 계층 절 · §5 — 「예외는 자격증명 검사 하나」라 했으나 `gate/urls.py` 에도 네트워크 I/O(`probe_url`)가 있고(판정 함수는 주입받는다), 「범위는 러너가 넘긴다」는 틀렸다 — 범위 정책은 `gate/secrets.scan_roots` 가 정하고 러너는 재료(실행 폴더 · 원장 폴더 · 문서 경로)만 넘긴다 ④ 루트 `CLAUDE.md` 개선거리 P 행의 「19% 대 약 23%」 — 모델을 바꾸기 전의 수치라 지금 회차와 대조하면 오판한다(지금은 한 장 25.6% · 27.5%) ⑤ `tests/test_explore_and_collect.py` 665행 — 「로드맵의」를 걷어 「검증 조건은 …」의 출처가 사라졌다
    - **원래 있던 것(이 diff 와 어긋나게 됐거나 같은 성질)**: ⑥ `agent/invoke.py` `FORBIDDEN_FLAGS` · `tests/test_agent_invoke.py` 186행 · `docker/run.sh` 16행 — 「세션 로그로 폭주를 감지하는 fallback」을 근거로 드는데 그 장치는 없다(루트 `CLAUDE.md` 를 「러너가 따로 끊는 장치는 없다」로 고친 것과 정면으로 어긋난다) ⑦ `src/research_lab/CLAUDE.md` 계층 트리의 runner 설명 「예산 판정」 — 루프는 금액으로 판정하지 않는다 ⑧ `gate/mechanism.py` 25행 · `tests/test_gate_mechanism.py` 5행 「설계가 셋으로 적어 두었다」 — 남은 「설계」(루트 `CLAUDE.md` 3번 칸)는 넷으로 적는다(코드는 제도 · 미시구조를 한 자리로 묶은 셋) ⑨ 루트 `CLAUDE.md` 로그 표의 「토큰 · 비용 → 회차 예산을 정할 근거」 — 「금액으로 판정하지 않는다」와 읽기에 따라 부딪힌다(장수를 정할 근거로 읽으면 맞다) ⑩ `runner/usage.py` `Tokens.all_total` — 운영 코드 호출 0건(테스트만)인 기존 데드 코드. 고친 독스트링이 남겨 둘 이유를 스스로 지웠다 ⑪ `docs/COMMANDS.md` 중단 회차 조회 — `sys.path` 조작을 걷었으므로 루트 패키지가 설치되지 않은 venv(`--no-root`)에서는 `ModuleNotFoundError`. 계획서가 정한 변경이고 이 기계에서는 동작을 확인했다 ⑫ `gate/feasibility.py` 머리 — 판정 단계가 5번 칸을 읽으니 「막지 않고 센다」의 안전 논거가 약해졌다는 설계 지적(동작 변경이라 이 계획서 범위 밖) ⑬ `runner/url_check.py` 「다섯 단계 · 나머지 넷」 · `src/research_lab/CLAUDE.md` §6 「나머지 네 단계」 — 개수를 적은 자리(값은 지금 맞다 — 사용자가 패스한 수치 정리)
- 2026-09-26 17:44: **독립 재검증 결과**(대화 맥락 없는 서브에이전트, 판정만) — D1 충족 · 옮긴 항목 뜻 보존 **부분 충족** · D2 충족 · D3 충족(분량 미달은 로그 설명대로) · D4 충족 · D5 충족(형제 서술 하나 남음) · 동작 불변 충족. 그 에이전트가 직접 돌린 것: DoD grep · `.py` 28개 AST 비교 · pytest 603 passed · ruff 통과 · black 변경 없음 · 링크 점검 0 깨짐 · 지운 계획서 19개를 `git show` 로 하나씩 Done 확인
  - **리뷰와 겹치지 않는 새 지적**: ⑭ 지운 계획서를 이름 없이 가리키는 테스트 주석 5곳(D4 의 부작용 — `tests/test_trigger_script.py` 9행 「계획서의 실기계 왕복 검증이 맡는다」 · 170행 「이 계획서가 존재하는 이유」 · `tests/test_gate_selfcontained.py` 78행 · `tests/test_rebut_and_lineage.py` 662행 「이 계획서가 고치고 있는 고장」 · `tests/test_explore_and_collect.py` 251행 「이 계획서의 기능 요구사항」 — 이 세션이 `grep` 으로 확인) ⑮ 루트 `CLAUDE.md` 「미뤄 둔 잠재 결함」의 「드러나는 모양」 열이 실제 로그 문구와 다르다 — 자립성 사유에는 걸린 표현만 실린다(`selfcontained.py`) · 탐색 사유는 「상한 초과」가 아니라 「한 회차에 담는 후보 상한(…)을 넘었다」(`explore.py`) · 머리말 인용이 원문(`dossier.py`)과 다르다 ⑯ 그 절 제목의 「공수 대비로 미뤘다」는 선행 계획서가 이 항목들에 붙인 이유가 아니다(그 말은 상수화 · 리팩토링 쪽) · 계보 행에 원문의 「계획서가 정한 정의 · 러너가 판정하지 않는다」 단서가 빠졌다 ⑰ `runner/lineage.py` 12행 「그 칸들」이 앞 문장(「그 뒤 단계」로 바꿈)에서 가리킬 칸을 잃었다 ⑱ OPERATIONS 3.0 의 두 번째 탈락안(「재부팅한 날 손으로 띄운다」 — 기억할 사람이 없다)이 빠졌다 ⑲ 루트 `CLAUDE.md` 「실패를 셋으로 가른다」 제목 아래 「둘이 더 있다」 문단 — 틀리진 않으나 제목과 어긋난다 ⑳ 계획서 머리 「마지막 업데이트」가 17:11 에 머묾
  - **⑥ 확인**: 러너에 세션 로그를 읽어 끊는 코드는 없다(`budget.py` · `decision_log.py` 는 「세션 로그에 기대지 않는다」고 적는다). 세션을 남기는 쪽의 이유로 참인 것은 `--resume` 되붙기 «보험»뿐이다(`runner/steps.py` 4행 「`--resume` 은 보험이지 뼈대가 아니다」 · `invoke.build_command` 의 미리 정한 `--session-id`)
- 2026-09-26 17:48: **1회차 리뷰 · 재검증 뒤 사용자 결정 — A(이 diff 가 만든 틀림) + B(이 변경과 어긋나게 된 기존 서술) 고침, C 는 목록만**. 조치:
  - **A**: ① OPERATIONS 5.2 함정 표 「창이 리셋을 가로지른다」에 「[실측 2026-09-23] Opus 한 장은 40 ~ 50분」 복원 · ⑱ 3.0 에 두 번째 탈락안 한 문장 복원 ② 리서치 스킬 URL 행 · §5 에 「미룬 후보가 상한에 닿거나 남은 후보를 전부 미루면 그 회차가 미완성」 ③ `src/research_lab/CLAUDE.md` 계층 절 → 「파일을 직접 읽는 게이트는 자격증명 검사 하나(§5) · 네트워크를 찌르는 URL 검사는 수단을 주입으로 받는다(§6)」, §5 → 「러너는 재료(실행 폴더 · 원장 폴더 · 문서 경로)만 넘기고 범위는 `scan_roots` 가 정한다」 ④ 루트 개선거리 P 행의 수치 → 「같은 모델에서 처음부터 끝까지 돈 회차보다 작게 실측됐다」 ⑮ 「드러나는 모양」 열을 실제 문구로(머리말은 `dossier.py` 원문 · 자립성은 「사유에는 걸린 표현만 실린다 — 산출물을 열어 본다」 · 탐색은 `explore.py` 의 「한 회차에 담는 후보 상한(…)을 넘었다」) ⑯ 절 제목 「공수 대비로 미뤘다」 → 「고치지 않고 목록으로 남겼다」 · 계보 행에 「정의가 주소가 있는 덩어리 수 · 러너가 판정하지 않는다」 ⑰ `runner/lineage.py` 「그 칸들」 → 「그 단계들의 칸」 ⑤ `tests/test_explore_and_collect.py` 665행 → 「그래서 여기서는 없는 URL 을 섞은 «산출물»을 단계에 넣어 잡히는지를 본다」
  - **B**: ⑥ 「폭주 감지 fallback」 3곳(`agent/invoke.py` `FORBIDDEN_FLAGS` · `tests/test_agent_invoke.py` · `docker/run.sh` — 「5시간 창 합산」도 같은 없는 장치라 함께) → 「끊긴 호출을 `--resume` 으로 되붙을 보험」 ⑭ 지운 계획서를 가리키던 테스트 주석 5곳 → 그 자리의 사실(「실기계에서 손으로 왕복해 확인한다」 · 「이 스크립트가 존재하는 이유」 · 「「기계가 본다」고 적어 두고 실제로는 안 보는 고장」 ×2 · 「모든 단계의 결과는 파일로 남아야 한다」) ⑧ `gate/mechanism.py` · `tests/test_gate_mechanism.py` 의 「설계가 셋으로」 → 설계를 가리키지 않고 갈래를 그 자리에 ⑦ `src/research_lab/CLAUDE.md` 트리의 「예산 판정」 → 「쓴 돈 세기」(`budget.py` 머리 「판정하지 않고 세기만 한다」) ⑨ 루트 로그 표 「회차 예산을 정할 근거」 → 「한 회차에 몇 장을 낼지 정할 근거」 ⑲ 루트 제목 → 「실패를 셋으로 가른다 — 러너가 스스로 거는 둘은 따로」(`failures.py` · `tests/test_runner_failure.py` 머리의 「실패를 셋으로 가른다」와 검색이 이어지게 앞부분을 살렸다)
  - **C(목록만)**: ⑩ `Tokens.all_total` 데드 코드 · ⑪ 조회 명령의 `--no-root` venv 위험(`pytest.ini` 에 `pythonpath` 가 없어 테스트도 설치된 패키지에 기대므로, 품질 검증이 도는 venv 라면 조회 명령도 돈다) · ⑫ 「5번 칸 비용은 막지 않고 센다」 설계 재검토(동작 변경) · ⑬ 개수 표기 · OPERATIONS 분량
  - **조치 뒤 기계 확인**: `.py` 34개 AST 비교 → 코드 변경 `tests/test_index.py` 하나 · `docker/run.sh` 변경 줄 전부 주석 · DoD grep 허용 1건 · 한 줄에 `~` 둘 이상 0건 · 「이 계획서」 · 「폭주 감지 fallback」 잔여 0건
- 2026-09-26 21:24: **`/code-review xhigh` 2회차 — 발견 11건(버그 0 · 그 외 11)**. 17:48 첫 시도는 세션 한도 소진(「You've hit your session limit · resets 9pm」)으로 결과 없이 끝나 한도가 풀린 뒤 다시 돌렸다. 버그 0 인 회차라 `/impl-plan` 규칙대로 리뷰는 여기서 끝내고, 「그 외」는 사용자에게 보고한다
  - **이 diff 가 만들었거나 바로 옆에 남긴 것**: R2-1 `docs/OPERATIONS.md` 1절 「옮길 때 바뀌는 것이 트리거뿐입니다」 — 원문의 「…라는 전제」 한정을 빼 단정이 됐는데 7절 「바뀐다」 표는 여섯을 든다 R2-2 리서치 스킬 131행 「지어낸 URL 은 그 회차를 통째로 버린다」 — 바로 위에 고친 §5(수집은 다시 묻고 미룬다)와 어긋난다 R2-3 `docs/INDEX.md` 루트 `CLAUDE.md` 행이 새 「남은 개선거리」 절을 말하지 않는다(지운 DESIGN 행이 「§10.1 이 알려진 개선거리」를 안내하던 자리) R2-4 `src/research_lab/CLAUDE.md` 계층 절 — 「URL 검사는 수단을 주입으로 받는다」는 판정 함수 이야기이고, 네트워크를 찌르는 `probe_url` 자체는 `gate/urls.py` 에 있다(러너가 그것을 주입한다) R2-5 개선거리 C(다른 표현에 축 하나만 내면 「옥석」이 통과)가 새로 문서화됐는데 루트 `CLAUDE.md` 1번 칸 절의 「기계가 못 막는 것 둘」 · `gate/quantified.py` 머리의 「뒤의 셋은 … 자연히 걸린다」 · 「못 막는 것 둘」은 그 구멍을 모른다
  - **원래 있던 형제 서술**: R2-6 `tests/test_agent_response_shape.py` 116행 · `tests/test_decision_log.py` 109행 「한도는 캐시에서 읽은 토큰도 먹는다」(`invoke.py` 에서 고친 것과 같은 부정된 가정 — 이 세션이 원문 확인) R2-7 루트 `CLAUDE.md` 439행 개발 원칙 「분류기 · 게이트 · 예산 판정 모두」 R2-8 「예산」 서술 여러 곳 — `src/research_lab/CLAUDE.md` §8 「예산이 조기 소진」 · 72행 「회차 예산 집계」 · `scripts/run_cycle.py` 109 · 249 · 590행 · `runner/collect.py` 47 · 406행 · `tests/test_agent_response_shape.py` 92행(일부는 「토큰 예산」으로 읽으면 지금도 맞다)
  - **1회차 C 와 같은 것**: R2-9 `Tokens.all_total` 데드 코드 · R2-10 조회 명령의 `--no-root` 위험
  - **규약 판단**: R2-11 새 「남은 개선거리」 절(「언제 다시 보나」 열 · 날짜 붙은 목록)이 같은 문서의 「진행 상태 문서와 인계 문서를 두지 않습니다」와 부딪혀 보일 수 있다 — 사용자 결정으로 넣은 절이라 규칙 문장에 한 줄 단서를 달지 판단이 필요하다
- 2026-09-26 21:28: **2회차 뒤 사용자 결정 — 좁게 고침**(R2-1 ~ R2-7 · R2-11). R2-8 · R2-9 · R2-10 은 목록만. 리뷰 상한(2회차)에서 버그 0 이라 3회차는 돌지 않았다
  - R2-1 OPERATIONS 1절 → 「저장소는 그대로이고, 다시 하는 것은 기계 쪽 설정뿐이라는 전제(트리거 · 절전 해제 · 엔진 자동 시작 · 이미지 빌드 · 토큰) — 그 목록이 7절」, 3.0 의 인용도 같은 말로 · R2-2 스킬 131행 → 「지어낸 URL 은 그 단계를 막아 회차를 헛돌게 한다」 · R2-3 `docs/INDEX.md` 루트 `CLAUDE.md` 행에 「남은 개선거리(알려진 결함과 미룬 판단)」 · R2-4 `src/research_lab/CLAUDE.md` 계층 절 → 「찌르는 함수(`gate/urls.probe_url`)는 게이트 모듈이 갖되, 판정 함수는 주입으로 받고 러너가 넣어 준다」 · R2-5 루트 1번 칸 절과 `gate/quantified.py` 머리의 「못 막는 것」에 ③(표현이 여럿인 주장에서 한 표현에만 축 — `_usable_axes` 가 1 이상이면 통과하는 것을 코드로 확인) · 「뒤의 셋은 그 표현만 있으면 … 자연히 걸린다」 · R2-6 `tests/test_decision_log.py` · `tests/test_agent_response_shape.py` 의 부정된 가정 문장 제거 · R2-7 루트 개발 원칙 「예산 판정」 → 「잠금 판정」(`src/research_lab/CLAUDE.md` §7 「판정을 못 하면 「잠김」으로 떨어뜨립니다」) · R2-11 루트 「진행 상태 문서와 인계 문서를 두지 않습니다」 뒤에 「「남은 개선거리」는 진행 상황이 아니라 코드에 남아 있는 알려진 결함과 미룬 판단이라, 고치면 그 줄을 지운다」
  - **최종 확인**: `.py` 35개 AST 비교 → 코드 변경 `tests/test_index.py` 하나 · `docker/run.sh` 변경 줄 전부 주석 · DoD grep 허용 1건(`tests/test_dossier.py:43`) · 링크 깨짐 0 · 한 줄 물결표 둘 이상은 이 diff 밖의 두 파일(`ledger/원장.md` 30행 · 선행 계획서 299행 — 손대지 않음) · `poetry run black .` 84개 변경 없음 · `poetry run python validate_project.py` → Ruff 통과 · PyRight 통과 · Pytest passed=603, failed=0, skipped=0
  - **이 계획서에만 남는 것**(사용자가 「목록만」으로 정한 것): 1회차 C(⑩ `Tokens.all_total` 데드 코드 · ⑪ 조회 명령의 `--no-root` 위험 · ⑫ 「5번 칸 비용은 막지 않고 센다」 설계 재검토 · ⑬ 개수 표기 · OPERATIONS 분량) · 2회차 R2-8(흩어진 「예산」 서술). 이 계획서를 지우면 함께 사라진다

---

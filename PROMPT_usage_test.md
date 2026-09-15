# 낮 실테스트 — 회차 하나가 5시간 한도의 몇 %인가

> **쓰는 법**: 새 세션에서 이 문서 하나만 가리키고 「이대로 해 줘」라고 하면 됩니다.
> 그 세션은 **관찰자**이고, 아래 절차대로 값을 읽고 **조용히 기다리다가** 결과를 정리합니다.

## 🔴 0. 이 문서는 «일회용»입니다

이 저장소는 **「진행 상태 문서와 인계 문서를 두지 않는다」**가 규칙입니다(루트 `CLAUDE.md`).
이 파일은 그 규칙의 예외가 아니라 **스스로 사라지는 임시 문서**로서만 허용됩니다.

- **9절의 조치까지 끝내면 이 파일을 지웁니다.** 남겨 두면 다음 세션이 끝난 테스트를 또 준비합니다
- 자리가 `docs/` 가 아니라 **저장소 루트**인 것도 그래서입니다 — `docs/` 는 문서 지도(`docs/INDEX.md`)에
  등록 의무가 있고, 몇 시간 뒤 사라질 파일을 거기 넣으면 **지도를 넣었다 빼는 churn** 이 생깁니다.
  등록 의무는 `docs/` 하나에만 걸려 있습니다(`tests/test_index.py` 로 확인)

---

## 1. 무엇을 재려는 건가 (배경)

이 파이프라인은 **남는 구독 토큰**으로 돕니다. 그런데 한 회차가 몇 장의 근거 문서를 낼지 정하는
값은 **달러 환산값**(`--cycle-budget-usd`)이고, **5시간 사용 한도와는 아무 연결이 없습니다.**

🔴 **그래서 지금 아무도 이 질문에 답할 수 없습니다 — 「근거 문서 한 장이 5시간 창의 몇 %인가」.**
모르면 두 방향으로 다 틀립니다.

| 한 장이 창의 15% 라면 | 한 장이 창의 40% 라면 |
| --- | --- |
| 새벽 설정($10 · 약 2장)은 **창의 70%를 그냥 버립니다** — 프로젝트 목적과 정면으로 어긋납니다 | 2장에 **80%를 먹어** 사용자 본인 작업이 낮에 막힙니다 |

**이번 테스트가 그 숫자를 한 번 얻는 자리입니다.** 한 번만 얻으면 그 뒤로는 러너가 자기 토큰으로
계산해 **모든 회차의 로그에** 적습니다 — 아무도 없는 새벽 회차까지 포함해서.

### 🔴 왜 «사람이 옆에서» 재야 하나 — 파이프라인은 못 잽니다

사용률은 `~/.claude.json` 의 `cachedUsageUtilization.utilization.five_hour` 에 백분율로 있습니다.
그런데 **그 캐시는 대화 세션이 돌 때만 갱신됩니다.** 실측으로 셋을 확인했습니다.

| 어디서 읽으려 해도 | 왜 안 되나 |
| --- | --- |
| 컨테이너 안 | 에이전트 HOME(`~/.research-lab-agent-home/.claude.json`)에 **그 키가 없습니다** — 헤드리스 호출은 이 캐시를 만들지 않습니다 |
| `docker/run.sh` (호스트 셸) | 새벽에는 대화 세션이 없어 **지난 창의 값이 그대로** 남아 있습니다. 읽으면 **틀린 숫자가 맞는 것처럼** 기록됩니다 |
| `claude` CLI · 응답 JSON | 사용량 명령이 없고 응답에 한도·잔량 필드가 없습니다 |

**그래서 이 세션이 유일한 관찰자입니다.**

---

## 2. 이미 준비된 것 (건드리지 마세요)

| 항목 | 값 |
| --- | --- |
| 발사 | **launchd · 오늘 12:00 정각** (`~/Library/LaunchAgents/local.research-lab.cycle.plist`) |
| 회차 인자 | `--cycle-budget-usd 1` |
| 단계 상한 | 넘기지 않음 → 기본 **$2** (새벽과 동일) |
| 원래 값 | **01:00 · `--cycle-budget-usd 10`** — 9절에서 되돌립니다 |

🔴 **`--cycle-budget-usd 1` 은 «금액 제약이 아닙니다».** 첫 실행 폴더는 그 값과 무관하게
**한 번 끝까지** 돌고, 판정은 그 «뒤»에 「한 장 더 시작할까」로만 걸립니다. 지금 한 장의 중앙값이
$4.5735(표본 1건)이라 임계가 $2.287 이고, **그 미만의 아무 값이나 결과가 같습니다 — 한 장에서 멈춤.**
즉 `1` 은 **「한 장」이라는 뜻**입니다.

🔴 **회차 실행에 이 세션이 관여하지 않습니다.** launchd 가 부르고, 컨테이너 «안»의 새 헤드리스
에이전트가 돕니다. **새벽 01:00 과 경로가 글자 하나 같습니다** — 다른 것은 시각과 장수뿐입니다.
**절대로 `docker/run.sh` 를 손으로 부르지 마세요** — 그러면 「무인 실행」이 아니게 되고,
예약 회차와 겹치면 **잠금이 그 경계를 못 막아** 둘이 같은 폴더를 번갈아 씁니다.

---

## 3. 지금 «바로» 할 일 — 실행 전 사용률을 읽는다

```bash
python3 -c "
import json, pathlib, datetime, zoneinfo
KST = zoneinfo.ZoneInfo('Asia/Seoul')
cu = json.loads(pathlib.Path.home().joinpath('.claude.json').read_text())['cachedUsageUtilization']
fetched = datetime.datetime.fromtimestamp(cu['fetchedAtMs'] / 1000, KST)
now = datetime.datetime.now(KST)
fh = cu['utilization']['five_hour']
print('캐시 갱신:', fetched.strftime('%Y-%m-%d %H:%M:%S'))
print('지금     :', now.strftime('%Y-%m-%d %H:%M:%S'))
print('신선도   :', round((now - fetched).total_seconds()), '초 전')
print('five_hour utilization:', fh['utilization'], '%')
print('resets_at:', fh['resets_at'])
"
```

**세 가지를 판정합니다.**

1. 🔴 **그 값이 «이번 창»의 것인가** — 아래 「신선도 함정」을 반드시 먼저 읽으세요
2. 🔴 **`resets_at` 이 회차 예상 종료(약 12:25)보다 «뒤»인가** — 리셋이 회차를 가로지르면
   **Δ 가 음수로 나오면서도 에러가 안 납니다.** 가로지르면 **측정을 중단하고 사용자에게 알립니다**
3. **그 `utilization` 값을 before 로 적어 둡니다** (숫자를 그대로 — 눈으로 읽어 다시 타이핑하지 말고
   출력을 복사합니다)

### 🔴 신선도 함정 — 캐시는 «상시 갱신이 아닙니다»

**[실측 2026-09-15]** 갱신 시각이 **09:44:10 → 10:15:56 → 10:27:16** 이었습니다 —
간격이 **32분 · 11분**으로 **일정하지 않습니다.** 턴을 돌 때마다 갱신되는 것도 아닙니다.

🔴 **그래서 「몇 초 전인가」로 판정할 수 없습니다.** 간격이 불규칙하니 임계값을 정할 수 없고,
정해도 그 값이 다음 날 틀립니다. **아래 판정식으로 봅니다.**

🔴 **그래서 11:58 에 읽은 값이 «11:00 리셋 전»의 것일 수 있습니다.** 그러면 그 값은
**지난 창의 사용률**이고, before 로 쓰면 Δ 가 통째로 거짓이 되는데 **에러는 나지 않습니다.**

**판정은 「몇 초 전인가」가 아니라 «같은 창인가»로 합니다.**

🔴 **그런데 「창 시작 = resets_at − 5시간」으로 비교하면 안 됩니다.** `resets_at` 도 **캐시 안의
값이라 같이 낡습니다** — 낡은 기록으로 계산한 창 시작과 그 기록의 갱신 시각을 비교하면
**언제나 통과합니다.** 검사가 자기 자신을 검사하는 꼴입니다.

```
쓸 수 있다  ⇔  resets_at 이 «지금보다 미래»다
```

**창이 이미 리셋됐는데 캐시가 안 갱신됐다면 `resets_at` 이 과거로 남습니다** — 그것이 신호입니다.

```bash
python3 -c "
import json, pathlib, time, datetime, zoneinfo
KST = zoneinfo.ZoneInfo('Asia/Seoul')
path = pathlib.Path.home() / '.claude.json'
for _ in range(60):
    cu = json.loads(path.read_text())['cachedUsageUtilization']
    fetched = datetime.datetime.fromtimestamp(cu['fetchedAtMs'] / 1000, KST)
    fh = cu['utilization']['five_hour']
    resets = datetime.datetime.fromisoformat(fh['resets_at']).astimezone(KST)
    now = datetime.datetime.now(KST)
    if resets > now:
        print('[쓸 수 있음] utilization =', fh['utilization'], '%')
        print('  캐시 갱신 :', fetched.strftime('%H:%M:%S'), '/ 지금', now.strftime('%H:%M:%S'))
        print('  이 창    :', (resets - datetime.timedelta(hours=5)).strftime('%H:%M:%S'), '~', resets.strftime('%H:%M:%S'))
        raise SystemExit
    print('[아직] resets_at', resets.strftime('%H:%M:%S'), '이 이미 지났습니다 — 낡은 창의 값입니다')
    time.sleep(60)
print('[못 얻음] 60분 동안 이번 창의 값이 캐시에 안 들어왔습니다 — 아래 «before 를 못 얻은 경우» 를 보세요')
"
```

#### before 를 못 얻은 경우 — 측정을 버리지 않습니다

**창이 11:00 에 리셋되므로 12:00 회차는 «거의 빈 창»에서 시작합니다.** 그래서 before 가 없어도
**after 하나로 상한을 말할 수 있습니다.**

> **`utilization_after` 는 「이 회차 몫 + 그 창에서 사람·관찰자가 쓴 몫」입니다.**
> 즉 **회차 몫의 상한**입니다. before 를 못 얻었으면 **Δ 대신 그 상한을 적고,
> 「상한이며 회차 몫은 이보다 작다」를 반드시 함께 적습니다.** 값을 버리는 것보다 낫고,
> **상한이라는 사실을 적지 않는 것**이 유일한 사고입니다.

---

## 4. 그다음 — «조용히» 기다린다

아래를 **백그라운드로** 띄우고 그때까지 아무것도 하지 않습니다. 완주하면 하네스가 깨웁니다.

```bash
python3 -c "
import json, pathlib, time, datetime, zoneinfo
KST = zoneinfo.ZoneInfo('Asia/Seoul')
today = datetime.datetime.now(KST).strftime('%Y-%m-%d')
p = pathlib.Path('runs/cycles.jsonl')
for _ in range(150):
    if p.is_file():
        for line in p.read_bytes().decode('utf-8', 'replace').splitlines():
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get('event') == 'finished' and e.get('ts', '') >= today + 'T12:00':
                print('[완주]', json.dumps(e, ensure_ascii=False))
                raise SystemExit
    time.sleep(30)
print('[시간초과] 75분 동안 12시 이후의 종료 줄이 없습니다 — 7절을 보세요')
"
```

🔴 **회차가 도는 동안 턴을 쓰지 마세요.** 이 세션의 사용량도 **같은 창**을 먹으므로,
말을 섞을수록 Δ 에 섞이는 몫이 커집니다.

---

## 5. 완주 뒤 — 실행 «후» 사용률을 읽고 Δ 를 구한다

3절의 명령을 **그대로 한 번 더** 돌립니다. 🔴 **여기서도 같은 함정이 걸립니다** —
캐시가 약 30분 주기로 갱신되므로 **회차가 끝난 «직후»의 값이 아직 안 들어와 있을 수 있습니다.**

**판정은 「캐시 갱신 시각 ≥ 회차 종료 시각」입니다.** 회차 종료 시각은 `runs/cycles.jsonl` 종료
줄의 `ts` 입니다. 조건을 만족할 때까지 3절의 대기 명령을 `window_start` 대신
**그 종료 시각**으로 바꿔 돌립니다.

```
Δ = after − before      (단위: 창의 %)
```

**before 가 없으면** 5절 위의 「상한」으로 적습니다 — `Δ` 자리에 `after (상한)` 을 씁니다.

### 🔴 Δ 에 섞인 오차를 «반드시» 함께 적습니다

이 세션이 3절·5절에 쓴 양도 같은 창에 들어갑니다. 그래서 **Δ 는 회차 몫보다 큽니다.**

> **이 오차의 방향이 «안전한 쪽»입니다.** Δ 가 부풀면 역산한 창의 크기가 작아지고,
> 그러면 이후 회차의 % 가 **실제보다 크게** 계산됩니다 — 사용자가 **과소계산을 원하지 않는다**고
> 명시했으므로 이 방향이 맞습니다. 그래도 **그 사실을 기록에 적습니다.**

---

## 6. 무엇을 확인하나 (완주한 경우)

| 볼 것 | 어디 |
| --- | --- |
| 회차 시작·종료 · 종료 코드 · 장수 · 멈춘 이유 · 토큰 성분 · `tokens_limit_total` | `runs/cycles.jsonl` 의 **마지막 두 줄** |
| 「왜 한 장에서 멈췄나」 — 남은 예산 · 한 장 중앙값 · **표본 수** | `runs/<실행폴더>/decisions.jsonl` 의 예산 판정 줄 |
| 🔴 **계측이 살아 있나** — 토큰 성분 넷이 **0 이 아닌지** | 같은 두 곳 |
| 예약 실행이 화면에 찍은 것 | `~/Library/Logs/research-lab/cycle.out.log` · `cycle.err.log` |
| 🔴 **근거 문서를 «눈으로» 읽기** | `dossier/` 의 새 문서 — 특히 **11번 칸**(미검증)에 판정 못 한 주소가 사람이 읽는 모양으로 실렸는지 |

🔴 **「테스트가 초록이니 됐다」로 넘기지 마세요.** 이 저장소는 **테스트 404개가 통과하는데 문서에
파이썬 목록 표기가 그대로 실린** 일을 겪었습니다. **제품은 사람이 읽는 문서**이므로 한 장 열어 읽습니다.

---

## 7. 결과별 조치

| 회차 로그의 모양 | 뜻 | 무엇을 하나 |
| --- | --- | --- |
| **시작 + 종료(코드 0) · `produced` 1** | 정상 완주 | 8절로 — 보정값을 산정 |
| **종료 코드 2** | **한도 소진 — 정상입니다.** 넘어가서 과금되지 않습니다 | Δ 는 못 얻습니다(창이 소진). 그 사실만 기록하고 8절은 건너뜁니다. 🔴 **다만 이때 「소진 시점의 누적 토큰」이 분모의 하한**이므로 그 값을 기록해 두면 다음에 쓸 재료가 됩니다 |
| **종료 코드 1** | 미완성 | **다음 회차가 이어받습니다.** 실패 원문(`decisions.jsonl`)을 읽고 원인만 기록 |
| **종료 코드 3 · 4** | 🔴 인증·과금 거부 / 자격증명 발견 | **사람이 손대야 합니다.** 즉시 사용자에게 알립니다 |
| **시작만 있고 종료가 없다** | **중단** (강제 종료·컨테이너 죽음·예외) | `cycle.err.log` 에 추적이 있는지 · `docker info` 가 되는지 |
| **12시 이후 줄이 아예 없다** | **발사조차 안 됐다** | **트리거 쪽**입니다 — `launchctl print gui/$(id -u)/local.research-lab.cycle` · `cycle.err.log` · `brew services list` (엔진) |

---

## 8. 보정값 산정 (정상 완주한 경우만)

```
창 한 개의 토큰 수 ≈ tokens_limit_total ÷ (Δ ÷ 100)
```

🔴 **Δ 대신 「상한」을 얻은 경우에도 같은 식을 씁니다.** 상한을 넣으면 창이 실제보다 **작게**
나오고, 그러면 이후 회차의 % 가 **실제보다 크게** 계산됩니다 — **과소계산을 피하는 방향**이라
안전한 쪽입니다. **다만 「상한으로 산정했다」를 `measured_on` 옆에 반드시 적습니다.**

- `tokens_limit_total` 은 `runs/cycles.jsonl` 종료 줄에 **이미 합계로 적혀 있습니다.**
  🔴 **성분 넷을 손으로 더하지 마세요** — 이 값은 영구 분모가 되므로 한 자리만 틀려도 이후 모든 비율이 틀립니다
- 넣을 자리는 `src/research_lab/runner/usage.py` 의 `CALIBRATION` 이고,
  **`tokens_per_window` 와 «잰 날짜»를 함께** 적습니다 (한도 정책이 바뀌면 값이 조용히 틀립니다)

🔴 **이것은 소스 변경이라 계획서 규약에 걸립니다.** `usage.py` 를 바로 고치지 말고
**숫자를 사용자에게 먼저 보여 승인받으세요.** 루트 `CLAUDE.md` 의 「계획서 선행」이 걸린 자리입니다.

**그다음 기록할 곳** (문서만 고치는 것은 계획서 없이 가능합니다)

- `docs/DESIGN.md` **§11.9** — before · after · Δ · 오차 사실 · 회차의 비용/토큰/장수를 **실측으로**
- `docs/DESIGN.md` **§10.1 M** — 「5시간 한도의 분모가 비어 있다」 항목. 채웠으면 **머리의 표와
  본문 제목을 둘 다** 갱신합니다 (표만 고치면 다음 세션이 어긋난 것을 읽습니다)

---

## 🔴 9. 반드시 되돌릴 것 — 예약을 01:00 · $10 으로

`~/Library/LaunchAgents/local.research-lab.cycle.plist` 에서 **두 곳**을 고칩니다.

| 지금 | 되돌릴 값 |
| --- | --- |
| `--cycle-budget-usd 1` | **`--cycle-budget-usd 10`** |
| `<key>Hour</key><integer>12</integer>` | **`<integer>1</integer>`** |

그리고 **임시 주석(`[임시 2026-09-15] 낮 실테스트용 …`)을 지운 뒤** 다시 올립니다 —
고치기만 하면 이미 올라간 정의가 그대로 돕니다.

```bash
plutil -lint ~/Library/LaunchAgents/local.research-lab.cycle.plist
launchctl bootout gui/$(id -u)/local.research-lab.cycle
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.research-lab.cycle.plist
launchctl print gui/$(id -u)/local.research-lab.cycle | grep -E 'state = |runs'
```

**되돌린 것을 확인한 뒤 이 파일을 지웁니다** (0절).

---

## 10. 하지 않는 것

| 하지 않는다 | 왜 |
| --- | --- |
| **`docker/run.sh` 를 손으로 부르기** | 「무인 실행」이 아니게 되고, 예약 회차와 겹치면 **잠금이 경계를 못 막아** 둘이 같은 폴더를 씁니다 |
| **`runs/cycles.jsonl` 에 직접 줄을 쓰기** | 그 파일은 **러너만 씁니다**(계층 계약). 손으로 끼운 줄이 섞이면 원자료인지 아닌지 갈리지 않습니다 |
| **git 명령** | 사용자가 직접 합니다 (전역 규칙) |
| **낡은 캐시 값을 before/after 로 쓰기** | Δ 가 통째로 거짓이 되고 **에러는 나지 않습니다** |
| **`usage.py` 를 승인 없이 고치기** | 소스 변경은 계획서 선행이 규약입니다 |
| **회차가 도는 동안 수다** | 같은 창을 먹어 Δ 의 오차가 커집니다 |

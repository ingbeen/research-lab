# 운용 — 트리거를 붙이고, 기계를 옮긴다

> 이 문서는 **그 기계의 OS 설정**을 다룹니다. 저장소의 실행 명령어와 그 옵션의 뜻은
> [COMMANDS.md](COMMANDS.md) 가 단일 SoT 이며 여기에 복제하지 않습니다.
>
> **등록과 설정은 사람이 직접 합니다.** 아래 명령은 제가 대신 실행하지 않고,
> 무엇이 이 기계에 설치·등록되는지를 쓰는 사람이 통제합니다. 등록된 뒤의
> **읽기 전용 확인**만 함께 봅니다.

---

## 1. 운용기는 mac 입니다 (2026-09-14 결정)

| 후보 | 붙이는 것 |
| --- | --- |
| **mac (채택)** | `launchd` + `pmset` 절전 해제 + `caffeinate` |
| WSL | Windows 작업 스케줄러의 「절전 모드 해제」 옵션 + `wsl.exe -- docker run …` |

**근거**: 파이프라인을 지은 뒤 세 단계가 전부 mac 에서 돌았고, 원래 설계도 「최종 운용은
mac 한 대」였습니다. 컨테이너로 싸 둔 덕에 **옮길 때 바뀌는 것이 트리거뿐**이라는 전제는
그대로이며, 그 전제를 실제로 쓰는 자리가 아래 7절입니다.

---

## 2. 착수 전 확인 — 읽기 전용

셋 다 **없으면 회차가 시작 자체를 거부**하거나 조용히 안 돕니다.

```bash
# ① 무인 실행용 장기 토큰이 있는가. 없으면 'claude setup-token' 으로 한 번만 발급한다
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && echo "토큰 있음" || echo "토큰 없음"

# ② API 키가 «없어야» 한다. 있으면 구독 대신 API 로 과금된다
[ -n "${ANTHROPIC_API_KEY+x}" ] && echo "[위험] API 키가 설정돼 있다" || echo "API 키 없음 (정상)"

# ③ 컨테이너 런타임이 떠 있는가
docker info >/dev/null 2>&1 && echo "도커 정상" || echo "도커가 안 떠 있다"
```

🔴 **③ 이 이 기계의 약한 고리입니다.** 도커 엔진이 VM 위에 있어서, **재부팅하면 사람이
다시 띄우기 전까지 예약 회차가 매번 실패합니다.** 종료 코드로는 그냥 실패로 보일 뿐
「도커가 안 떠 있다」로는 안 보이므로, 재부팅 뒤에는 이 확인을 한 번 돌립니다.
**[미검증] 이 기계에서 엔진이 로그인 시 자동으로 뜨는지는 아직 안 쟀습니다.**

---

## 3. 트리거 등록 — 사용자가 실행합니다

예약 시각은 **매일 01:00 (KST)** 입니다. 근거는 사용 한도가 「첫 프롬프트부터」 5시간
창으로 돌기 때문이고, 낮에 직접 쓰는 시간대와 겹치지 않는 쪽이 유리합니다.

### 3.1 작업 정의 파일을 만든다

`~/Library/LaunchAgents/local.research-lab.cycle.plist` 로 저장합니다.
**저장소 «밖»입니다** — 이 저장소는 PUBLIC 이고, 아래 파일에는 토큰이 들어갑니다.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>local.research-lab.cycle</string>

  <key>ProgramArguments</key>
  <array>
    <!-- caffeinate 로 감싼다. 회차가 길어질 수 있어 도는 중에 다시 잠들면 안 된다 -->
    <string>/usr/bin/caffeinate</string>
    <string>-i</string>
    <string>/Users/사용자이름/Workspace/research-lab/docker/run.sh</string>
    <string>--cycle-budget-usd</string>
    <string>10</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>1</integer>
    <key>Minute</key><integer>0</integer>
  </dict>

  <key>EnvironmentVariables</key>
  <dict>
    <!-- launchd 는 로그인 셸의 환경을 «물려받지 않는다». 넘길 것을 여기 적어야 한다 -->
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>CLAUDE_CODE_OAUTH_TOKEN</key>
    <string>발급받은-토큰</string>
  </dict>

  <key>StandardOutPath</key>
  <string>/Users/사용자이름/Library/Logs/research-lab/cycle.out.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/사용자이름/Library/Logs/research-lab/cycle.err.log</string>
</dict>
</plist>
```

🔴 **여기서 조용히 틀어지는 자리가 셋입니다.**

| 자리 | 안 하면 |
| --- | --- |
| **`PATH` 를 적는다** | launchd 의 기본 경로에는 `docker` 가 없습니다. 회차가 「명령을 못 찾음」으로 끝나는데, **로그를 안 보면 그냥 안 돈 것처럼 보입니다** |
| **`--cycle-budget-usd` 를 «명시»한다** | 기본값에 기대면 나중에 그 기본값을 고치는 날 **예약 회차의 동작이 조용히 달라집니다** |
| **`ANTHROPIC_API_KEY` 를 «안» 적는다** | 적으면 그 순간 구독 대신 API 로 과금됩니다. launchd 가 환경을 안 물려받는 것이 여기서는 **안전판**이니 그대로 둡니다 |

**토큰이 이 파일에 들어가므로 권한을 좁힙니다.**

```bash
mkdir -p ~/Library/Logs/research-lab
chmod 600 ~/Library/LaunchAgents/local.research-lab.cycle.plist
```

### 3.2 등록한다

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.research-lab.cycle.plist
```

### 3.3 잠든 기계를 깨운다

`launchd` 는 **잠든 동안 시각이 지나가면 그 회차를 못 돕니다.** 예약 시각보다 조금 앞서
기계를 깨웁니다.

```bash
sudo pmset repeat wakeorpoweron MTWRFSU 00:55:00
```

> **[미검증] 「절전 해제가 실제로 이 기계를 깨우는가」는 아직 안 쟀습니다.**
> 설계가 처음부터 재기로 하고 미뤄 둔 항목이며, **추론으로 넘기면 안 되는 자리**입니다 —
> 이 저장소는 권한 비트를 추론했다가 틀린 적이 있습니다. 첫 예약 회차가 그 답입니다.

---

## 4. 등록 뒤 확인 — 읽기 전용

```bash
# 등록됐나
launchctl print gui/$(id -u)/local.research-lab.cycle | head -20

# 다음 절전 해제 예약
pmset -g sched

# 지난 회차가 어떻게 끝났나
tail -40 ~/Library/Logs/research-lab/cycle.err.log
```

---

## 5. 결과를 어디서 보나

| 무엇 | 어디 |
| --- | --- |
| **그 회차가 어떻게 끝났나** | 위 로그의 마지막 줄과 **종료 코드** — 값의 뜻은 [COMMANDS.md](COMMANDS.md) 가 SoT 입니다 |
| **무엇을 읽고 어떻게 판단했나** | `runs/<실행폴더>/decisions.jsonl` |
| **왜 한 장에서 멈췄나** | 같은 파일의 예산 판정 줄 — 남은 예산 · 한 장의 중앙값 · **표본 수**가 함께 적힙니다 |
| **제품** | `dossier/` 아래 근거 문서 |
| **다음에 팔 후보** | `ledger/원장.md` |

🔴 **사람이 손대야 하는 종료 코드는 둘입니다** — 인증·과금 거부와 자격증명 발견.
나머지는 다음 회차가 이어받습니다. **한도 소진은 정상입니다** — 넘어가서 과금되지 않습니다.

---

## 6. 🔴 기계가 «안 막는» 것 — 손으로 돌리기 전에 본다

**예약된 회차가 도는 동안 호스트에서 직접 회차를 돌리면 막히지 않습니다.**

동시 실행을 막는 잠금은 커널이 쥐고 있어 프로세스가 어떻게 죽든 풀립니다. 그 성질이
「컨테이너가 죽으면 파이프라인이 무인 상태로 정지」하던 버그를 고쳤지만, 대신
**그 잠금은 컨테이너와 호스트 사이를 넘지 못합니다.** 컨테이너끼리는 정상으로 막힙니다.

겹치면 **둘이 같은 실행 폴더와 같은 후보 목록을 번갈아 쓰고, 한쪽의 갱신이 예외도 로그도
없이 사라집니다.**

**확인 수단은 있습니다 — 잠금이 아니라 컨테이너 목록입니다.**

```bash
docker ps
```

운용 경로가 컨테이너 하나이므로, **목록에 이 프로젝트의 컨테이너가 없으면 예약 회차가
지금 돌고 있지 않다는 뜻**입니다. 손으로 돌리기 전에 이것만 봅니다.

> **이미지 이름으로 거르지 않는 편이 안전합니다.** 실행 스크립트가 이미지 이름을 환경변수로
> 덮어쓸 수 있어서, 이름을 박아 거르면 **덮어쓴 날 조용히 「안 돌고 있음」으로 보입니다.**

> **왜 코드로 안 막았나**: 시각 기준 신호는 「죽인 뒤 5분 만에 재실행」과 「5분째 정상
> 실행 중」을 구별하지 못해 이미 한 번 기각된 수단이고, 되살리면 **고쳤던 정지 버그가
> 그 길로 돌아옵니다.** 러너가 컨테이너 목록을 직접 보게 하면 **컨테이너 «안»에서는 그
> 명령이 없어 운용 경로에서 되레 깨집니다.** 그래서 못 막는 자리를 여기 적는 쪽을 택했습니다.

---

## 7. 다른 기계로 옮길 때 — 바뀌는 것과 안 바뀌는 것

| 안 바뀐다 | 왜 |
| --- | --- |
| 저장소 · 컨테이너 이미지 정의 · 의존성 잠금 | 베이스 이미지가 여러 아키텍처를 다 가지고 있습니다 |
| 컨테이너 «안» 경로 | 고정돼 있고 호스트 경로는 바깥에서 주입합니다 |
| 실행 사용자 지정 | 파일 공유 계층이 사용자 번호를 호스트 사용자로 옮겨 줘서, 번호가 달라도 그대로 둡니다 |
| 산출물이 생기는 자리 | 저장소 폴더를 그대로 물려 쓰므로 컨테이너 안에 상태가 남지 않습니다 |

| 바뀐다 | 무엇을 한다 |
| --- | --- |
| **트리거** | 이 문서 3절을 그 기계의 방식으로 다시 합니다 (WSL 이면 Windows 작업 스케줄러 + 「절전 모드 해제」) |
| **절전 해제** | 기계마다 수단이 다르고, **답도 다릅니다 — 그 기계에서 다시 재야 합니다** |
| 에이전트의 홈 폴더 | 저장소 밖 호스트 폴더라 기계를 따라오지 않습니다. 잃는 것은 없습니다 — 되짚을 기록은 저장소 안에 쌓입니다 |
| 토큰 | 그 기계에서 새로 발급합니다 |

**옮긴 뒤 첫 할 일은 품질 검증 한 번입니다** — 명령은 [COMMANDS.md](COMMANDS.md) 에 있습니다.
WSL 에서 돌리면 **잠금이 그 파일 시스템에서 표준대로 도는지**라는 남은 [미검증] 항목도
함께 닫힙니다. 저장소를 Windows 드라이브가 아니라 리눅스 파일 시스템에 두는 것이 전제입니다.

---

## 8. 멈추거나 고칠 때

```bash
# 잠시 끈다
launchctl bootout gui/$(id -u)/local.research-lab.cycle

# 절전 해제 예약을 지운다
sudo pmset repeat cancel
```

**작업 정의 파일을 고친 뒤에는 `bootout` → `bootstrap` 순으로 다시 올립니다.**
고치기만 하면 이미 올라간 정의가 그대로 돕니다.

> 🔴 **진입점 파일 이름이 바뀌면 컨테이너 이미지를 다시 빌드해야 합니다.**
> 소스는 호스트 폴더를 그대로 물려 쓰므로 평소에는 빌드가 필요 없는데, **진입점만
> 이미지에 구워져 있어서** 안 빌드하면 「그런 파일이 없다」로 회차가 죽습니다.
> 빌드 명령은 [COMMANDS.md](COMMANDS.md) 에 있습니다.

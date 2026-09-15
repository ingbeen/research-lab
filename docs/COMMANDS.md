# research-lab 실행 명령어 레퍼런스

> 이 파일은 research-lab 실행 명령어의 **단일 SoT(Source of Truth)** 입니다.
> `README.md` · `CLAUDE.md` 등 다른 문서에는 실행 명령어를 기재하지 않으며, 필요 시 이 문서를 참조합니다.
> 설치처럼 한 번만 쓰는 일회성 명령어는 기재하지 않습니다. **평상시 반복 실행하는 명령어만** 관리합니다.

---

## 품질 검증

```bash
# 전체 검증 (Ruff + PyRight + Pytest)
poetry run python validate_project.py

# 개별 실행
poetry run python validate_project.py --only-lint
poetry run python validate_project.py --only-pyright
poetry run python validate_project.py --only-tests

# 커버리지 포함 테스트
poetry run python validate_project.py --cov

# 포맷 자동 적용 (마지막 Phase에서만)
poetry run black .
```

> **`failed=0 skipped=0` 이 통과 기준입니다.** 이 둘만 보면 됩니다.
>
> **`passed` 의 절대값을 기준선으로 삼지 않습니다.** 코드를 지우면 테스트도 함께 줄어드는 것이
> 정상인데, 숫자를 문서에 박아 두면 **정상 상태가 고장으로 읽힙니다.** 판단이 필요하면
> **직전 실행과 비교**하세요. 지운 코드 없이 `passed` 가 줄었다면 그때가 신호입니다.

> 검증이 **세 항목 모두 실패**하면서 `Command not found` 가 보이면 코드 문제가 아니라
> 실행 환경 문제입니다. `poetry env info --path` 가 이 저장소의 `.venv` 를 가리키는지 확인하세요.
>
> **다른 저장소에서 이 저장소의 검증을 부를 때는 `env -u VIRTUAL_ENV` 를 붙입니다.**
> 세션을 시작한 저장소의 가상환경이 셸에 남아 있어, 안 붙이면 엉뚱한 venv 를 써서
> `ModuleNotFoundError` 가 나고 **「패키지가 없다」로 오진합니다.**
>
> ```bash
> cd ~/workspace/research-lab && env -u VIRTUAL_ENV poetry run python validate_project.py
> ```

---

## 회차 실행

### 컨테이너로 (운용 방식)

```bash
# 이미지 빌드 (Dockerfile 이나 의존성이 바뀔 때만)
docker build -t research-lab:latest .

# 회차 하나를 돈다 (예산이 남는 한 근거 문서를 여러 장 낸다)
./docker/run.sh

# 이 회차에 쓸 예산을 바꿔서
./docker/run.sh --cycle-budget-usd 4.0

# 단계 하나의 폭주 감지 상한을 바꿔서
./docker/run.sh --budget-usd 1.0

# 끊긴 회차를 이어받는다 (실행 폴더를 지정하면 그 자리에서 이어진다)
./docker/run.sh --run-dir runs/20260913_0100
```

### 🔴 예산 플래그가 «둘»이고 뜻이 다릅니다

이름이 닮아서, 무인 실행에서 잘못 주면 **에러 없이 다른 동작을 합니다.**

| 플래그 | 무엇을 막나 | 성질 |
| --- | --- | --- |
| `--budget-usd` | **한 «단계»**가 정상보다 훨씬 많이 쓰는 것 | **하드 상한** — 넘으면 그 단계를 중단합니다 |
| `--cycle-budget-usd` | **한 «회차»**가 근거 문서를 몇 장까지 낼지 | 🔴 **상한이 아니라 «시작 판정»입니다** — 「이만큼도 안 남았으면 다음 장을 시작하지 않는다」이지 도는 중에 끊지 않습니다. **그래서 마지막 한 장이 이 값을 넘길 수 있고 그것이 정상입니다** |

> **둘 다 과금 방지 장치가 아닙니다.** 과금은 구독 토큰만 넘기고 API 키를 거부하는 쪽이 막습니다.
>
> **「한 장이 얼마인가」는 지난 회차들의 로그에서 그때그때 계산합니다** — 누적 파일을 두지
> 않습니다. 표본이 없으면 「0이 든다」가 아니라 **「모른다」로 보고 다음 장을 시작하지
> 않습니다.** 그 판정과 표본 수는 그 회차의 결정 로그에 남습니다.

> 🔴 **진입점 «파일명»이 바뀌면 이미지를 반드시 다시 빌드합니다.** `ENTRYPOINT` 가 이미지에
> 구워져 있어, 안 빌드하면 `can't open file '/work/scripts/...': No such file or directory` 로
> 회차가 죽습니다. **소스는 bind mount 라 평소에는 빌드가 필요 없어서** 더 놓치기 쉽습니다 —
> 「코드를 고쳤는데 왜 옛날 걸 찾지」로 읽히고, 실행 로그만 봐서는 원인이 안 드러납니다.
> `[실측] 2026-09-14` 실행 단위 개명 뒤 실제로 여기 걸렸습니다.
>
> **`CLAUDE_CODE_OAUTH_TOKEN` 이 환경에 있어야 합니다.** 없으면 스크립트가 시작을 거부합니다.
> 발급은 호스트에서 `claude setup-token` 으로 한 번만 합니다.
>
> **`ANTHROPIC_API_KEY` 가 설정돼 있으면 시작을 거부합니다** — 빈 문자열이어도 마찬가지입니다.
> 이 프로젝트는 구독 토큰만 쓰며, 그 변수가 있으면 구독 대신 API 로 과금됩니다.

### 호스트에서 직접 (개발·디버깅용)

```bash
poetry run python scripts/run_cycle.py --budget-usd 0.5
```

### 종료 코드

무인 실행에서 **사람이 받는 신호가 이것뿐**이라 갈래마다 값이 다릅니다.

| 코드 | 뜻 | 무엇을 해야 하나 |
| --- | --- | --- |
| `0` | 완주 | 없음 |
| `1` | 미완성 (그 외 실패) | 없음. **다음 회차가 이어받습니다** |
| `1` + stderr 에 `[막힘]` | 같은 단계가 **3회차 연속** 막혀 그 실행 폴더를 접었습니다 | 🔴 **원인을 고쳐야 합니다.** 후보가 원장에 `- [!]` 로 남으므로, 고친 뒤 `- [ ]` 로 바꾸고 사유 줄을 지우면 다시 팝니다. 안 고치면 또 같은 자리에서 막힙니다 |
| `2` | 한도 소진 | 없음. **정상입니다** — 넘어가서 과금되지 않습니다 |
| `3` | 인증·과금 거부 | 🔴 **사람이 손대야 합니다.** 토큰 만료·정책 변경·API 키 혼입 |
| `4` | 자격증명 발견 | 🔴 **산출물에 자격증명이 들어갔습니다.** 이 저장소는 PUBLIC 입니다 |

🔴 **종료 코드는 «끝난» 회차의 신호입니다.** 끊긴 회차는 종료 코드를 내지 못하므로
아래로 봅니다.

### 중단된 회차 조회

`runs/cycles.jsonl` 에 회차마다 **시작 한 줄 · 종료 한 줄**이 남습니다.
**시작만 있고 종료가 없는 회차가 「중단」**입니다 — 강제 종료·컨테이너 죽음·전원 차단은
끝을 적지 못한 채 끝나기 때문입니다.

```bash
poetry run python -c "
import sys; sys.path.insert(0,'src')
from research_lab.runner import cycle_log
from research_lab.common_constants import RUNS_DIR
print(cycle_log.unfinished_ids(RUNS_DIR) or '중단된 회차 없음')
"
```

**[주의] 지금 도는 중인 회차도 여기 나옵니다.** 그 구별은 `docker ps` 로 합니다 —
자세한 것은 [OPERATIONS.md](OPERATIONS.md) 5.1 에 있습니다.

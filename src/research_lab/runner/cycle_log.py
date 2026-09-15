"""회차의 «생애»를 남긴다 — 시작과 종료, 그리고 그 짝으로 읽는 「중단」.

`decision_log` 와 자리가 다르다. 그쪽은 **실행 폴더**의 과정을 적고, 이쪽은 **회차** 자체를
적는다 — 한 회차가 폴더를 여럿 만들 수 있으므로(계층 계약 §8) 회차의 시작·종료를 어느 한
폴더에 적으면 그 폴더가 그 회차의 전부인 것처럼 읽힌다.

[중요] **이 파일이 있어야 「중단됐다」와 「아예 안 돌았다」가 구별된다.** 강제 종료·컨테이너
죽음·전원 차단은 모두 **끝을 적지 못한 채** 끝나므로, 죽는 프로세스에게 기록을 기대할 수
없다. 중단은 **「시작은 있는데 끝이 없다」**로 판정할 수밖에 없고, 그러려면 시작이 미리
적혀 있어야 한다. 회차는 주로 새벽에 돌기 때문에 이 구별이 없으면 아침에 되짚을 것이 없다.

[중요] **적을 수 있는 것을 이름과 타입으로 고정한다.** `decision_log.record` 처럼 아무 값이나
받는 통로를 두지 않는 이유는, 이 파일이 **자격증명 스캔 범위 «밖»**이기 때문이다 —
회차마다 덧붙는 파일을 스캔에 넣으면 한 번 걸린 뒤 이후 모든 회차가 실패하고, 무인 실행에는
그것을 치울 사람이 없다(그 이유로 스캔 범위를 좁힌 선례가 있다). 그래서 막는 것이 검사가
아니라 **모양**이어야 한다. 이 저장소는 PUBLIC 이다.

[주의] 경로는 **이름만** 적는다. 절대경로를 적으면 호스트의 사용자 폴더가 그대로 공개 이력에
남는다. 이름만으로도 그 폴더를 찾을 수 있다.
"""

import uuid
from pathlib import Path
from typing import Any, Final

from research_lab.common_constants import CYCLE_LOG_FILENAME
from research_lab.runner import jsonl, usage

EVENT_STARTED: Final = "started"
EVENT_FINISHED: Final = "finished"

KEY_CYCLE_ID: Final = "cycle_id"


def new_cycle_id() -> str:
    """회차를 식별하는 값을 만든다.

    [중요] 시각을 쓰지 않는다. 같은 «분»에 두 회차가 시작할 수 있다 — 전부 건너뛴 회차는
    비용 0 에 몇 초면 끝난다. 시각으로 짝지으면 그때 **시작 둘과 종료 하나가 섞여
    중단 판정이 틀린다.** 실행 폴더 이름 충돌을 순번으로 푼 것과 같은 축이다.
    """
    return str(uuid.uuid4())


def started(
    runs_dir: Path,
    *,
    cycle_id: str,
    cycle_dossiers: int,
    step_budget_usd: float,
    ledger_name: str,
    run_dir_name: str | None,
) -> None:
    """회차가 시작했다고 적는다 — **어떤 일보다 먼저.**

    Args:
        runs_dir: 실행 폴더들이 쌓이는 뿌리
        cycle_id: 이 회차의 식별값
        cycle_dossiers: 이 회차에 요청된 근거 문서 장수 (반복의 상한이기도 하다)
        step_budget_usd: 한 단계에 건 폭주 감지 상한 (달러 — CLI 플래그의 단위다)
        ledger_name: 쓴 원장 파일의 **이름**
        run_dir_name: 사람이 지정한 실행 폴더의 **이름**. 지정이 없으면 None

    [중요] 과금 가드보다는 «뒤»에 부른다. 가드는 한 줄이라도 돌기 전에 막는 것이라,
    그 앞에 적으면 **돌지도 않은 회차가 「시작했다」로 남고** 짝이 없으니 중단으로 읽힌다.

    [주의] 2026-09-15 이전의 줄에는 이 자리에 `cycle_budget_usd`(달러)가 들어 있다.
    덧붙이기 전용 파일이라 **과거 줄을 고치지 않으므로** 읽는 쪽이 둘 다 만날 수 있다.
    """
    _append(
        runs_dir,
        {
            "event": EVENT_STARTED,
            KEY_CYCLE_ID: cycle_id,
            "cycle_dossiers": cycle_dossiers,
            "step_budget_usd": step_budget_usd,
            "ledger": ledger_name,
            "run_dir_arg": run_dir_name,
        },
    )


def finished(
    runs_dir: Path,
    *,
    cycle_id: str,
    exit_code: int,
    produced: int,
    spent_usd: float,
    stop_reason: str,
    last_run_dir_name: str,
    tokens: usage.Tokens | None,
) -> None:
    """회차가 끝났다고 적는다 — **어느 경로로 끝나든.**

    Args:
        runs_dir: 실행 폴더들이 쌓이는 뿌리
        cycle_id: 시작에 적은 것과 «같은» 값. 이것으로 짝이 지어진다
        exit_code: 그 회차의 종료 코드. **무인 실행에서 사람이 받는 신호가 이것뿐**인데
            지금까지 화면에만 나갔고, 그 화면 기록은 저장소 밖이라 기계를 옮기면 따라오지 않는다
        produced: 낸 근거 문서의 장수
        spent_usd: 그 회차가 쓴 돈
        stop_reason: 루프가 멈춘 이유
        last_run_dir_name: 마지막 실행 폴더의 **이름**
        tokens: 그 회차가 쓴 토큰 성분. 모르면 None

    [주의] 예외가 빠져나가 프로세스가 죽으면 이 줄이 안 적힌다. 그것이 «맞다» —
    그 상태는 실제로 중단이고, 그렇게 읽히는 것이 이 모듈의 목적이다.
    """
    entry: dict[str, Any] = {
        "event": EVENT_FINISHED,
        KEY_CYCLE_ID: cycle_id,
        "exit_code": exit_code,
        "produced": produced,
        "spent_usd": spent_usd,
        "stop_reason": stop_reason,
        "last_run_dir": last_run_dir_name,
    }
    if tokens is not None:
        entry.update(tokens.as_log_fields())
        # [중요] 보정값을 «한 번» 읽어 비율과 날짜에 같이 쓴다. 따로 읽으면 한쪽만 갈려
        # **비율은 비었는데 날짜만 찍히는** 줄이 나온다
        calibration = usage.calibrated()
        share = usage.window_share_percent(tokens, calibration=calibration)
        # [중요] 보정의 «분자»를 함께 적는다. 없으면 사람이 성분을 손으로 더해야 하고
        # **눈으로 읽어 다시 타이핑한 값은 근거물이 아니다.**
        #
        # [주의] 2026-09-15 이전의 줄에는 이 자리에 `tokens_limit_total`(네 성분의 합)이
        # 들어 있다. 그때는 캐시 읽기도 한도를 먹는다고 보았고 **그 가정이 틀렸다** —
        # 실측은 `docs/DESIGN.md` 에 있다. 열쇠 이름을 바꾸는 것은 **같은 이름에 다른 뜻을
        # 담지 않기** 위해서다. 덧붙이기 전용 파일이라 과거 줄은 고치지 않는다
        entry["tokens_new_total"] = tokens.new_total
        entry["window_share_percent"] = share
        entry["window_share_per_dossier_percent"] = usage.per_dossier_percent(share, produced=produced)
        entry["limit_calibrated_on"] = calibration.measured_on if calibration is not None else None

    _append(runs_dir, entry)


def read(runs_dir: Path) -> list[dict[str, Any]]:
    """회차 기록을 적힌 순서대로 읽는다.

    Args:
        runs_dir: 실행 폴더들이 쌓이는 뿌리

    Returns:
        읽히는 줄만. 파일이 없으면 빈 목록. **깨진 줄은 건너뛴다** — 이 파일은 회차마다
        덧붙여지므로 한 줄이 반쯤 쓰이다 끊길 수 있고, 여기서 터지면
        **멀쩡한 회차가 시작하자마자 죽는다.** 잘린 글자까지 견디는 것은 `jsonl.read` 가 맡는다
    """
    return jsonl.read(runs_dir / CYCLE_LOG_FILENAME)


def unfinished_ids(runs_dir: Path) -> list[str]:
    """시작만 있고 끝이 없는 회차의 식별값 — 적힌 순서대로.

    Args:
        runs_dir: 실행 폴더들이 쌓이는 뿌리

    Returns:
        짝이 없는 시작의 식별값. **기록이 하나도 없으면 빈 목록이다** —
        「아예 안 돌았다」는 중단이 아니고, 그것을 중단으로 읽으면 봐야 할 곳
        (트리거 쪽)이 아니라 엉뚱한 곳(컨테이너·에이전트)을 들여다보게 된다

    [주의] **지금 도는 중인 회차도 여기 들어온다.** 그 구별은 이 파일 밖에 있다 —
    도는 컨테이너 목록을 보면 된다. 지난 회차를 볼 때만 「중단」으로 읽는다
    """
    started_ids: list[str] = []
    finished_ids: set[str] = set()

    for entry in read(runs_dir):
        cycle_id = entry.get(KEY_CYCLE_ID)
        if not isinstance(cycle_id, str):
            continue
        if entry.get("event") == EVENT_STARTED:
            started_ids.append(cycle_id)
        elif entry.get("event") == EVENT_FINISHED:
            finished_ids.add(cycle_id)

    return [cycle_id for cycle_id in started_ids if cycle_id not in finished_ids]


def _append(runs_dir: Path, entry: dict[str, Any]) -> None:
    """한 줄 덧붙인다. 다시 쓰지 않는다 — 다시 쓰면 앞 회차들이 사라지고 예외도 안 난다."""
    jsonl.append(runs_dir / CYCLE_LOG_FILENAME, entry)

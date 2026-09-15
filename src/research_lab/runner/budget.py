"""회차가 «쓴 돈»을 센다 — 판정하지 않고 세기만 한다.

[중요] **비용은 기록이지 판정 재료가 아니다.** 한 회차가 몇 장을 낼지는 장수로 지시하며,
여기서 나온 값은 회차 로그와 화면 요약에 실릴 뿐 루프를 멈추지 않는다.

[중요] **누적 파일로 저장하지 않는다.** 「한 장이 얼마였나」를 물으면 그때 로그를 훑어
계산한다 — 누적 집계는 한 번 틀어지면 틀어졌다는 사실을 아무도 모른다.
"""

from pathlib import Path
from typing import Any, Final

from research_lab.runner import decision_log

KEY_COST_USD: Final = "cost_usd"

# 돈을 적을 때의 자릿수. 한 호출의 바닥값이 $0.0951 이라 그보다 잘게 봐야 의미가 있다
COST_DIGITS: Final = 4


def cost_of(run_dir: Path) -> float:
    """그 실행 폴더에 «지금까지» 기록된 비용의 합.

    러너가 스스로 적은 값을 쓴다. 컨테이너 HOME 의 세션 로그에 기대면 기계를 옮기는
    순간 과거가 사라진다.

    Args:
        run_dir: 실행 폴더

    Returns:
        기록된 비용의 합. 읽을 수 없는 값은 빼고 더한다 — **검사기가 죽어서 파이프라인을
        멈추게 해서는 안 된다.** 결정 로그는 회차마다 덧붙여지는 파일이라 한 줄이 반쯤
        쓰이다 끊길 수 있고, 사람이 손으로 고칠 수도 있다

    [중요] 이 값은 그 폴더의 «생애 총합»이다. 한 회차가 쓴 몫을 알려면 **차분**으로 봐야
    한다 — 이어받은 폴더에는 지난 회차의 줄이 남아 있어, 합을 그대로 쓰면 지난 회차의
    소비까지 이번 것으로 세고 **그 어긋남은 아무 에러도 내지 않는다.**
    """
    return _cost_from(decision_log.read(run_dir))


def _cost_from(entries: list[dict[str, Any]]) -> float:
    """읽어 둔 결정 로그에서 비용 합을 구한다."""
    total = 0.0
    for entry in entries:
        if entry.get("event") != decision_log.EVENT_COST:
            continue
        spent = entry.get(KEY_COST_USD)
        # [주의] `bool` 을 걸러낸다. 파이썬에서 `True` 는 `int` 라 그냥 두면 1달러로 더해진다
        if isinstance(spent, int | float) and not isinstance(spent, bool):
            total += float(spent)
    return total

"""측정 설계 초안(10번 칸)이 «그대로 잴 수 있는 형태»인지 검사한다.

이 칸에는 반드시 들어갈 자리가 있고, 자리마다 **안 적으면 생기는 일**이 있다(아래 표).
그래서 자리를 줄이지 않는다.

| 자리 | 안 적으면 |
| --- | --- |
| 미래 참조가 없음 | 판정 시점에 알 수 없는 정보로 신호를 정의해 **못 잴 것을 재게 된다** |
| 실제로 살 수 있는 상품 | 지수로 잰 성적은 **집행할 수 없는 성적**이다 |
| 진입·보유 격자 | 한 값만 재면 그게 **가장 좋은 값이라서 고른 것인지** 구별되지 않는다 |
| 기준선 | 주식은 장기 상승해서 아무 날에나 사도 오른 비율이 절반을 넘는다. **기준선 없는 비율은 사람을 속인다** |
| 방향을 미리 정하지 않음 | 「내린다」도 유효한 신호다. 먼저 정하면 **반대쪽 발견을 통째로 놓친다** |
| 예상 표본 수 | 표본이 적으면 **소수점 차이로 우열을 가리게 된다** |

[중요] 이 칸이 채워지면 **사전등록**이 공짜로 따라온다 — 재기 «전»에 측정 방법이 문서에
박히므로 결과를 보고 기준을 고치는 일이 구조적으로 막힌다.

[중요] 격자가 «한 값»이면 사유를 요구한다. 막기만 하면 달력 규칙 후보에서 억지 격자를
지어내게 되므로, 반증 게이트의 「0건이면 사유」와 같은 모양으로 푼다.
"""

from collections.abc import Mapping
from typing import Any, Final

from research_lab.gate.filled import is_filled

KEY_SINGLE_VALUE_REASON: Final = "single_value_reason"

# 문장으로 받는 자리. 괄호 안은 사유에 실을 사람이 읽는 이름이다
TEXT_FIELDS: Final = (
    ("instrument", "대상 — 실제로 살 수 있는 상품인가 (없으면 그 사실과 이유)"),
    ("no_lookahead", "미래 참조가 없음 — 판정 시점에 아는 값만 쓰는가"),
    ("baseline", "기준선 — 무엇과 견주는가"),
    ("direction", "방향 — 위·아래를 미리 정하지 않았는가"),
    ("expected_samples", "예상 표본 수"),
)

# 여러 값을 받는 자리.
#
# [중요] 격자가 **둘**인 이유는 진입 시점과 보유 기간이 서로 다른 축이기 때문이다.
# 하나로 합치면 「12월 20일에 사서 20일 보유」와 「12월 26일에 사서 60일 보유」를
# 구별해 훑을 수 없다
GRID_FIELDS: Final = (
    ("entry_grid", "진입 시점 격자"),
    ("holding_grid", "보유 기간 격자"),
)

# 격자로 인정하는 «서로 다른» 값의 최소 개수.
#
# 정성 표현 게이트가 파라미터 후보값에 요구하는 수와 같다 — 둘 다 「한 값을 고르지 않고
# 축만 정한다」는 같은 규율이라 수가 갈리면 읽는 사람이 이유를 찾게 된다
MIN_GRID_VALUES: Final = 2


def shortfall_reason(payload: Mapping[str, Any]) -> str | None:
    """10번 칸의 자리가 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    Args:
        payload: 측정 설계 단계가 낸 산출물. 모양이 어긋나 있어도 된다

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    for key, label in TEXT_FIELDS:
        if not is_filled(payload.get(key)):
            return f"10번 칸의 「{label}」(`{key}`)가 비어 있습니다. " f"물을 것이 없으면 «「해당 없음」과 그 이유»를 적으세요 — 빈 채로 두는 것과 다릅니다."

    excused = is_filled(payload.get(KEY_SINGLE_VALUE_REASON))

    for key, label in GRID_FIELDS:
        grid = payload.get(key)
        if not isinstance(grid, list) or not grid:
            # [중요] 문자열도 여기서 막는다. 비어 있지 않으니 「적혀 있다」로 읽히는 데다
            # 파이썬에서는 순회까지 되어 **예외 없이 글자 수만큼 세어진다**
            return f"10번 칸의 「{label}」(`{key}`)가 비었거나 목록이 아닙니다. 진입과 보유를 **여러 값으로** 훑어야 합니다."

        usable = _distinct(grid)
        if usable == 0:
            # [중요] 사유가 있어도 여기는 못 비켜 간다. 사유는 「값이 «하나»뿐이다」를 해명하는
            # 것이지 **「값이 없다」를 해명하는 것이 아니다.** 빈 문자열만 든 목록이 통과하면
            # 근거 문서의 10번 칸이 「적히지 않았습니다」인 채로 완성본으로 나간다
            return f"10번 칸의 「{label}」(`{key}`)에 쓸 수 있는 값이 하나도 없습니다. 사유를 적어도 «값이 없는 것»은 통과하지 않습니다."

        if usable < MIN_GRID_VALUES and not excused:
            return (
                f"10번 칸의 「{label}」(`{key}`)가 서로 다른 값 {MIN_GRID_VALUES}개에 못 미칩니다. "
                f"한 값만 재면 그것이 «가장 좋은 값이라서 고른 것인지» 구별되지 않습니다. "
                f"값이 정말 하나뿐이면 `{KEY_SINGLE_VALUE_REASON}` 에 왜 하나뿐인지 적으세요."
            )

    return None


def distinct_size(grid: Any) -> int:
    """격자에 든 «서로 다른» 값의 수를 센다 — 계측용이다.

    이 값이 로그에 있어야 나중에 「격자를 한 값으로 낸 후보가 몇이었나」를 셀 수 있다.

    Args:
        grid: 격자. 무엇이든 들어올 수 있다

    Returns:
        서로 다른 값의 수. 목록이 아니면 0
    """
    return _distinct(grid) if isinstance(grid, list) else 0


def _distinct(grid: list[Any]) -> int:
    """같은 값을 여러 번 적은 것은 «한 값»으로 센다.

    [중요] 안 그러면 값 하나를 복붙해 게이트를 통과한다. 검색어 게이트가
    「같은 말을 표기만 바꿔 여러 번 적은 것은 갈아 끼운 것이 아니다」로 세는 것과 같은 축이다.

    비교는 **문자열로** 한다 — 에이전트가 `20` 과 `"20"` 을 섞어 내는 일이 흔한데,
    그 둘은 같은 값이고 타입으로 가르면 복붙이 통과한다.

    [중요] 그래도 `None` 은 «문자열로 만들기 전에» 뺀다. `str(None)` 은 `"None"` 이라는
    내용 있는 문자열이라, 안 빼면 **`null` 을 채워 격자 수를 부풀릴 수 있다** — 이 함수가
    막으려던 복붙과 같은 일이 열쇠만 바꿔 일어난다. 그리고 `[null, null]` 이 1 로 세어지면
    「쓸 수 있는 값이 하나도 없다」 갈래가 **한 번도 돌지 않는다.**
    비었다는 판정은 `filled.is_filled` 한 곳이 한다 — `None` 뿐 아니라 `[]`·`{}` 도 걸러야 하는데
    ( `str([])` 는 `"[]"` 라 비어 있지 않다), 판정이 두 벌이면 **게이트가 「값이 있다」로 읽은
    것을 조립부는 「적히지 않았습니다」로 렌더한다.**
    """
    return len({str(item).strip() for item in grid if is_filled(item)})

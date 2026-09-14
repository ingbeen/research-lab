"""한 줄 주장의 정성 표현이 «해명»됐는지 검사한다.

[중요] **이 사전은 「기각 목록」이 아니라 «파라미터 해명을 요구하는» 목록이다.**

「짧은 기간」과 「옥석을 가려」는 성질이 다르다.

| 갈래 | 예 | 왜 갈리나 |
| --- | --- | --- |
| 축은 있고 값이 비었다 | 짧은 기간 · 단기 · 크게 상회 · 전저점 대비 | 값을 채우면 재는 절차가 확정된다 |
| 축 자체가 없다 | 옥석을 가려 · 유망한 것 중에 | 무엇을 채울지조차 없다 |
| 판정 시점에 모르는 값 | «미래» 저점 · 고점 | 미래 참조라 측정이 성립하지 않는다 |

앞의 것은 **격자로 스윕하면 재진다.** 설계의 채워 본 예시도 진입·청산을 격자로 두고 있어,
범위를 기각 사유로 삼으면 그 관용과 정면으로 어긋난다. 뒤의 둘은 파라미터를 낼 수 없어
자연히 걸린다 — **가르는 것은 사전이 아니라 「파라미터를 낼 수 있는가」다.**

그래서 사전에 걸려도 버리지 않고 **축과 후보값을 내라고 요구한다.** 오탐의 대가가
거의 0 이라 사전을 넉넉히 키워도 좋은 후보가 죽지 않는다.

[중요] 게이트는 **적혔는가만** 본다. 그 축이 옳은지 · 그 값이 판정 시점에 관측 가능한지는
판정하지 않는다 — 판정하려 들면 게이트가 또 하나의 판단자가 된다.

[주의] 못 막는 것 둘을 알고 쓴다 — ① 사전에 없는 정성 표현 ② 「미래 저점」을 「전저점」인
척 포장한 격자. 둘 다 나중에 사람이 보는 자리다.
"""

from typing import Any, Final

# 값이 비어 있다는 «표시»가 되는 말.
#
# 기각 목록이 아니므로 넉넉히 담는다 — 잴 수 있는 표현(「단기」)과 못 재는 표현(「옥석」)이
# 한 사전에 함께 있는 것이 정상이다. 둘을 가르는 것은 사전이 아니라 파라미터다
QUALITATIVE_TERMS: Final = (
    # 크기 — 얼마가 「크게」인가
    "크게",
    "큰 폭",
    "대폭",
    "급등",
    "급락",
    "상당",
    "충분",
    # 기간 — 며칠인가
    "짧은",
    "단기",
    "중기",
    "장기",
    "며칠",
    "수일",
    "수주",
    "수개월",
    "당분간",
    "직후",
    # 가격 수준 — 어느 시점의 무엇과 견주나. 「전저점」이면 재지고 「미래 저점」이면 못 잰다
    "저점",
    "고점",
    "저가",
    "저평가",
    "고평가",
    "고배당",
    "근접",
    # 판정자가 없는 말 — 규칙이 아니라 사람을 부르는 말인데, 무인 실행에 사람은 없다
    "옥석",
    "유망",
    "우량",
    "괜찮",
    # 주체가 없는 예측 — 누가 언제 무엇을 보고 예상하는지가 없다
    "예상되는",
    "전망되는",
    "기대되는",
)

# 한 축이 «격자»로 인정되려면 필요한 서로 다른 숫자 후보값의 수.
#
# 둘인 이유는 하나면 격자가 아니라 **임의로 고른 값 하나**이기 때문이다.
# 그 값이 곧 결론을 만들고, 그건 조사가 아니라 창작이다
MIN_DISTINCT_CANDIDATES: Final = 2


def triggered_terms(claim: str) -> tuple[str, ...]:
    """한 줄 주장에 든 정성 표현을 찾는다.

    Args:
        claim: 후보의 한 줄 주장

    Returns:
        걸린 표현들. 없으면 빈 튜플
    """
    lowered = claim.casefold()
    return tuple(term for term in QUALITATIVE_TERMS if term.casefold() in lowered)


def shortfall_reason(claim: str, parameters: Any) -> str | None:
    """해명이 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    사유를 «문자열로» 돌리는 것은 원장의 기각 줄에 그대로 적기 위해서다.
    「거부됨」만 남으면 다음에 같은 후보가 나왔을 때 왜 버렸는지 알 수 없어 **또 판다.**

    [중요] **어떤 입력에도 예외를 올리지 않는다.** 에이전트가 낸 값이라 목록 자리에
    문자열이 오거나 항목 자리에 숫자가 오는 일이 흔하다. 검사기가 죽으면 그 회차가
    통째로 끝난다.

    Args:
        claim: 후보의 한 줄 주장
        parameters: 에이전트가 낸 파라미터 축들. 모양이 어긋나 있어도 된다

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    terms = triggered_terms(claim)
    if not terms:
        return None

    if _usable_axes(parameters):
        return None

    return (
        f"한 줄 주장에 값이 비어 있는 표현이 있습니다: {list(terms)}. "
        f"그 표현마다 «무엇을 얼마로 바꿀 수 있는지»를 파라미터 축으로 적고, "
        f"축마다 서로 다른 숫자 후보값을 {MIN_DISTINCT_CANDIDATES}개 이상 주세요 "
        f"(예: 보유 기간 · 거래일 · [5, 20, 60]). "
        f"축을 못 정하겠다면 그 후보는 잴 수 없습니다 — 임의로 값을 채우면 "
        f"어떤 값을 넣느냐가 결론을 만듭니다."
    )


def _usable_axes(parameters: Any) -> int:
    """격자로 쓸 수 있는 축이 몇 개인지 센다."""
    if not isinstance(parameters, list):
        return 0
    return sum(1 for item in parameters if _is_usable_axis(item))


def _is_usable_axis(item: Any) -> bool:
    """축 하나가 이름과 «격자»를 갖췄는지 본다."""
    if not isinstance(item, dict):
        return False

    if not str(item.get("name", "")).strip():
        # 이름이 없으면 무슨 축인지 모른 채 숫자만 남는다. 그 격자는 나중에 못 읽는다
        return False

    candidates = item.get("candidates")
    if not isinstance(candidates, list):
        return False

    # [중요] `bool` 은 `int` 의 하위형이라 그냥 세면 `True`/`False` 가 숫자로 통과한다.
    # 그리고 같은 값을 여러 번 적은 것은 격자가 «아니다» — 숫자만 채우면 통과하는
    # 게이트는 게이트가 아니라는 점에서 검색어 게이트와 같은 자리다
    numbers = {float(value) for value in candidates if isinstance(value, int | float) and not isinstance(value, bool)}
    return len(numbers) >= MIN_DISTINCT_CANDIDATES

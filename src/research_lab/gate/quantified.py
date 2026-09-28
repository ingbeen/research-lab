"""한 줄 주장의 정성 표현이 «해명»됐는지 검사한다.

[중요] **이 사전은 「기각 목록」이 아니라 «파라미터 해명을 요구하는» 목록이다.**

「짧은 기간」과 「옥석을 가려」는 성질이 다르다.

| 갈래 | 예 | 왜 갈리나 |
| --- | --- | --- |
| 축은 있고 값이 비었다 | 짧은 기간 · 단기 · 크게 상회 · 전저점 대비 | 값을 채우면 재는 절차가 확정된다 |
| 축 자체가 없다 | 옥석을 가려 · 유망한 것 중에 | 무엇을 채울지조차 없다 |
| 판정 시점에 모르는 값 | «미래» 저점 · 고점 | 미래 참조라 측정이 성립하지 않는다 |
| 주체가 없는 예측 | 편입이 «예상되는» | 누가 언제 무엇을 보고 예상하는지가 없어 정보 집합이 정의되지 않는다 |

앞의 것은 **격자로 스윕하면 재진다.** 설계의 채워 본 예시도 진입·청산을 격자로 두고 있어,
범위를 기각 사유로 삼으면 그 관용과 정면으로 어긋난다. 뒤의 셋은 그 표현만 있으면 파라미터를
낼 수 없어 자연히 걸린다 — **가르는 것은 사전이 아니라 「파라미터를 낼 수 있는가」다.**

그래서 사전에 걸려도 버리지 않고 **축과 후보값을 내라고 요구한다.** 오탐의 대가는 축 한 줄이라
사전을 넉넉히 키워도 좋은 후보가 죽지 않는다. 다만 수집은 걸린 표현 «마다» 한 줄을 요구하므로,
낱말 안에 우연히 든 조각(「상장기업」의 「장기」)은 판정 전에 가린다(`INCIDENTAL_COMPOUNDS`).

[중요] 게이트는 **적혔는가만** 본다. 그 축이 옳은지 · 그 값이 판정 시점에 관측 가능한지는
판정하지 않는다 — 판정하려 들면 게이트가 또 하나의 판단자가 된다.

[중요] **판정이 두 갈래다 — 수집은 표현 «마다» 축을, 탐색은 축 «하나 이상»을 요구한다**
(`each_term`). 하나로 두면 「옥석을 가려 … 전저점 대비」가 전저점 축만으로 지나가, 축 자체가
없는 표현이 해명 없이 근거 문서까지 간다. 그렇다고 탐색에도 표현마다 요구하면 안 된다 —
탐색 에이전트는 이 사전을 모르므로 사전에 든 줄 모르는 말(「직후」)에 축을 안 내고, 기각은
다시 안 파므로 **멀쩡한 후보가 영구히 닫힌다.** 수집 지시문은 걸린 표현을 글자 그대로 짚어
주므로 그 자리에서 요구한다.

[중요] 축이 표현을 «푸는지»는 축의 `term`(그 축이 푸는 표현) **또는 이름**에 그 표현이 들어
있는지로 본다. 이름만으로 맞추지 않는 것은 축 이름에 표현이 안 들어가는 것이 정상이기
때문이다(「크게 상회」→ 「서프라이즈 하한」). 이름도 보는 것은 `term` 을 빠뜨렸지만 이름에 그
말이 든 축(「단기 보유 기간」)까지 기각하지 않기 위해서다.

[주의] 못 막는 것 셋을 알고 쓴다 — ① 사전에 없는 정성 표현 ② 「미래 저점」을 「전저점」인
척 포장한 격자 ③ 한 축의 `term` 에 표현을 몰아 적어 그 축이 풀지 않는 표현까지 푼 것으로 적은 것
(한 축이 여러 표현을 함께 푸는 정당한 경우와 글자로는 갈리지 않는다). 셋 다 나중에 사람이 보는 자리다.
"""

from typing import Any, Final

from research_lab.gate.filled import is_filled

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

# 사전의 말이 «우연히 든» 흔한 낱말 — 판정 전에 가린다.
#
# [중요] 사전은 글자 그대로 찾으므로 낱말 안의 조각도 문다(「상장기업」의 「장기」 · 「매수일」의
# 「수일」 · 「매수주문」의 「수주」). 탐색에서는 축 하나면 통과해 대가가 없지만, **수집은 걸린 표현
# 마다 축을 요구하고 그 기각은 다시 안 판다** — 가리지 않으면 값이 다 정해진 후보가 없는 표현
# 때문에 영구히 닫힌다. 낱말 앞머리로만 찾는 길은 버렸다 — 「전저점」의 「저점」 · 「최고점」의
# 「고점」처럼 낱말 안에 든 «진짜» 표현을 놓친다
INCIDENTAL_COMPOUNDS: Final = ("상장기", "매수일", "매수주")

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
    for compound in INCIDENTAL_COMPOUNDS:
        lowered = lowered.replace(compound, " ")
    return tuple(term for term in QUALITATIVE_TERMS if term.casefold() in lowered)


def shortfall_reason(claim: str, parameters: Any, *, each_term: bool) -> str | None:
    """해명이 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    사유를 «문자열로» 돌리는 것은 원장의 기각 줄에 그대로 적기 위해서다.
    「거부됨」만 남으면 다음에 같은 후보가 나왔을 때 왜 버렸는지 알 수 없어 **또 판다.**

    [중요] **어떤 입력에도 예외를 올리지 않는다.** 에이전트가 낸 값이라 목록 자리에
    문자열이 오거나 항목 자리에 숫자가 오는 일이 흔하다. 검사기가 죽으면 그 회차가
    통째로 끝난다.

    Args:
        claim: 후보의 한 줄 주장
        parameters: 에이전트가 낸 파라미터 축들. 모양이 어긋나 있어도 된다
        each_term: 걸린 표현 «마다» 축을 요구할지(수집), 축 하나 이상이면 될지(탐색).
            **기본값을 두지 않는다** — 두 판정은 기각의 무게가 달라 부르는 쪽이 골라야 한다

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    terms = triggered_terms(claim)
    if not terms:
        return None

    axes = _usable_axes(parameters)
    if each_term:
        uncovered = [term for term in terms if not any(_answers(axis, term) for axis in axes)]
        return _uncovered_reason(uncovered) if uncovered else None

    if axes:
        return None

    return (
        f"한 줄 주장에 값이 비어 있는 표현이 있습니다: {list(terms)}. "
        f"그 표현마다 «무엇을 얼마로 바꿀 수 있는지»를 파라미터 축으로 적고, "
        f"축마다 서로 다른 숫자 후보값을 {MIN_DISTINCT_CANDIDATES}개 이상 주세요 "
        f"(예: 보유 기간 · 거래일 · [5, 20, 60]). "
        f"축을 못 정하겠다면 그 후보는 잴 수 없습니다 — 임의로 값을 채우면 "
        f"어떤 값을 넣느냐가 결론을 만듭니다."
    )


def _uncovered_reason(uncovered: list[str]) -> str:
    """표현마다의 판정에서 풀지 못한 표현을 짚는 사유.

    [중요] **풀지 못한 표현만** 짚는다. 풀린 표현까지 늘어놓으면 무엇을 고칠지가 흐려지고,
    이 사유는 원장의 기각 줄에 그대로 남아 사람이 판정을 뒤집을 때 근거가 된다.
    """
    named = " · ".join(f"「{term}」" for term in uncovered)
    return (
        f"한 줄 주장의 값이 비어 있는 표현 중 축으로 풀지 못한 것이 있습니다: {named}. "
        f"표현마다 그 표현을 `term` 에 그대로 적은 축을 내고, 축마다 서로 다른 숫자 후보값을 "
        f"{MIN_DISTINCT_CANDIDATES}개 이상 주세요 "
        f"(예: 「단기」 → 이름 「보유 기간」 · 단위 거래일 · 후보값 [5, 20, 60] · term 「단기」). "
        f"축을 못 정하겠다면 그 후보는 잴 수 없습니다 — 임의로 값을 채우면 "
        f"어떤 값을 넣느냐가 결론을 만듭니다."
    )


def _usable_axes(parameters: Any) -> list[dict[str, Any]]:
    """격자로 쓸 수 있는 축들."""
    if not isinstance(parameters, list):
        return []
    return [item for item in parameters if _is_usable_axis(item)]


def _answers(axis: dict[str, Any], term: str) -> bool:
    """그 축이 그 표현을 푸나 — `term` 이나 이름 «하나하나»에 그 표현이 들어 있나.

    [주의] 이어 붙여 한 문자열로 보지 않는다. `term` 「큰」과 이름 「폭 하한」을 이으면 「큰 폭」이
    생겨, 아무도 적지 않은 표현이 풀린 것으로 읽힌다.
    """
    folded = _squeezed(term)
    return any(folded in _squeezed(written) for written in _strings(axis.get("term")) + _strings(axis.get("name")))


def _squeezed(text: str) -> str:
    """띄어쓰기를 빼고 대소문자를 접은 꼴 — 「큰 폭」과 「큰폭」을 같게 본다.

    [중요] 수집의 기각은 다시 안 판다. 띄어쓰기 하나로 표현을 못 푼 것으로 읽으면 잴 수 있는
    후보가 영구히 닫힌다.
    """
    return "".join(text.split()).casefold()


def _strings(value: Any) -> list[str]:
    """문자열이거나 문자열 목록인 값에서 문자열만 꺼낸다. 나머지 모양은 «안 적힌 것»이다."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _is_usable_axis(item: Any) -> bool:
    """축 하나가 이름과 «격자»를 갖췄는지 본다."""
    if not isinstance(item, dict):
        return False

    # [중요] 기본값 `""` 로는 «값이 null 인 경우»를 못 막는다 — 그때는 기본값이 안 쓰이고
    # `str(None)` = `"None"` 이 되어 **이름이 적힌 것으로 읽힌다.** 빈 값만 담은 목록·절(`[""]`)도
    # 같은 모양이라, 판정은 게이트들이 함께 쓰는 `is_filled` 가 한다
    name = item.get("name")
    if not is_filled(name):
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

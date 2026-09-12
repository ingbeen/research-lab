"""정성 표현 게이트의 계약을 고정한다.

[중요] **이 사전은 「기각 목록」이 아니라 «파라미터 해명을 요구하는» 목록이다.**

「짧은 기간」과 「옥석을 가려」는 성질이 다르다. 앞의 것은 **축이 있고 값만 비어 있어서**
격자로 스윕하면 재지고, 뒤의 것은 **축 자체가 없어서** 무엇을 채울지조차 없다.
파라미터는 값이 빌 때 채우는 것이지 «무슨 값인지 모를 때»는 못 채운다 — 그래서 둘이 갈린다.

걸리면 버리는 것이 아니라 **그 표현에 대응하는 파라미터 축과 후보값을 내라**고 요구한다.
그래서 **오탐의 대가가 거의 0 이고**, 사전을 넉넉히 키워도 좋은 후보가 죽지 않는다.

[중요] 게이트는 **적혔는가만** 본다. 그 축이 옳은지 · 그 값이 판정 시점에 관측 가능한지는
판정하지 않는다 — 판정하려 들면 게이트가 또 하나의 판단자가 된다.
"""

from research_lab.gate import quantified


def test_claim_without_qualitative_terms_passes_without_parameters() -> None:
    """
    목적: 값이 이미 다 정해진 후보는 파라미터 없이 통과하는 계약을 고정한다.

    「11월~4월 보유」처럼 달력만 보면 정해지는 후보는 채울 축이 없다. 그런 후보에까지
    파라미터를 요구하면 **에이전트가 없는 축을 지어낸다.**

    Given: 정성 표현이 없는 한 줄 주장과 빈 파라미터
    When: 검사한다
    Then: 사유가 없다
    """
    claim = "11월 첫 거래일에 사서 4월 마지막 거래일에 판다"

    assert quantified.shortfall_reason(claim, []) is None


def test_qualitative_term_without_parameters_is_blocked() -> None:
    """
    목적: 정성 표현이 있는데 파라미터가 없으면 막는 계약을 고정한다.

    Given: 「짧은 기간」이 든 한 줄 주장과 빈 파라미터
    When: 검사한다
    Then: 사유가 나온다
    """
    claim = "3인 이상 임원이 짧은 기간 내 동시에 자사주를 매수한 종목을 산다"

    assert quantified.shortfall_reason(claim, []) is not None


def test_qualitative_term_with_a_parameter_grid_passes() -> None:
    """
    목적: 해명된 정성 표현이 «기각되지 않는» 계약을 고정한다.

    이것이 이 게이트의 핵심이다. 「짧은 기간」은 못 잴 후보의 표시가 아니라
    **격자로 받아야 할 축**이다. 설계의 채워 본 예시도 진입·청산을 격자로 두고 있다.

    Given: 「짧은 기간」이 든 주장과 그 축을 채운 파라미터
    When: 검사한다
    Then: 사유가 없다
    """
    claim = "3인 이상 임원이 짧은 기간 내 동시에 자사주를 매수한 종목을 산다"
    parameters = [{"name": "동시 매수 판정 창", "unit": "거래일", "candidates": [5, 10, 20]}]

    assert quantified.shortfall_reason(claim, parameters) is None


def test_single_candidate_value_is_blocked() -> None:
    """
    목적: 후보값을 «하나만» 채운 것이 해명으로 인정되지 않는 계약을 고정한다.

    값 하나를 임의로 고르면 **어떤 값을 넣느냐가 결론을 만든다.** 격자가 그것을 막는
    이유가 여기 있다 — 값을 고르지 않고 축만 정하기 때문이다.

    Given: 후보값이 하나뿐인 파라미터
    When: 검사한다
    Then: 막힌다
    """
    claim = "실적이 크게 상회한 종목을 산다"
    parameters = [{"name": "서프라이즈 하한", "unit": "%", "candidates": [10]}]

    assert quantified.shortfall_reason(claim, parameters) is not None


def test_repeated_candidate_values_do_not_count_as_a_grid() -> None:
    """
    목적: 같은 값을 여러 번 적은 것이 격자로 세어지지 않는 계약을 고정한다.

    숫자만 채우면 통과하는 게이트는 게이트가 아니다 — 검색어 게이트와 같은 자리다.

    Given: 같은 값이 반복된 후보값
    When: 검사한다
    Then: 막힌다
    """
    claim = "실적이 크게 상회한 종목을 산다"
    parameters = [{"name": "서프라이즈 하한", "unit": "%", "candidates": [10, 10, 10]}]

    assert quantified.shortfall_reason(claim, parameters) is not None


def test_axis_that_cannot_be_numbered_is_blocked() -> None:
    """
    목적: **축 자체가 없는** 표현이 격자를 흉내 내도 막히는 계약을 고정한다.

    「옥석을 가려」는 규칙이 아니라 사람을 부르는 말인데, **무인 실행에 사람은 없다.**
    숫자 후보값을 요구하는 것이 이 갈래를 거르는 장치다.

    Given: 「옥석」이 든 주장과 숫자가 아닌 후보값
    When: 검사한다
    Then: 막힌다
    """
    claim = "상장 후 큰 폭 하락한 종목 중 옥석을 가려 매수한다"
    parameters = [{"name": "옥석 기준", "candidates": ["좋은 것", "괜찮은 것"]}]

    assert quantified.shortfall_reason(claim, parameters) is not None


def test_parameter_without_a_name_does_not_count() -> None:
    """
    목적: 이름 없는 파라미터가 해명으로 세어지지 않는 계약을 고정한다.

    이름이 없으면 **무슨 축인지 모른 채 숫자만 남는다.** 그 격자는 나중에 못 읽는다.

    Given: 이름이 빈 파라미터
    When: 검사한다
    Then: 막힌다
    """
    claim = "단기 보유한다"
    parameters = [{"name": "  ", "candidates": [5, 20]}]

    assert quantified.shortfall_reason(claim, parameters) is not None


def test_malformed_parameters_do_not_crash_the_gate() -> None:
    """
    목적: 모양이 어긋난 입력에 게이트가 «죽지 않는» 계약을 고정한다.

    검사기가 죽어서 파이프라인을 멈추게 해서는 안 된다. 판정을 «못 하는 것»과
    «실패로 판정하는 것»은 다르고, 여기서는 후자로 떨어지는 것이 맞다 —
    해명이 안 된 것은 사실이기 때문이다.

    Given: 목록 자리에 문자열이, 항목 자리에 숫자가 온 입력
    When: 검사한다
    Then: 예외 없이 사유가 나온다
    """
    claim = "단기 보유한다"

    assert quantified.shortfall_reason(claim, "파라미터") is not None
    assert quantified.shortfall_reason(claim, [1, "둘", None]) is not None


def test_reason_names_what_was_triggered() -> None:
    """
    목적: 막을 때 «무엇이 왜 걸렸는지»를 함께 돌려주는 계약을 고정한다.

    「거부됨」만 돌려주면 다음 밤이 같은 시도를 반복한다. 이 사유는 원장의 기각 줄에
    그대로 적혀 **다음에 같은 후보를 또 파지 않게** 한다.

    Given: 「저점」이 든 주장
    When: 검사한다
    Then: 걸린 표현이 사유에 들어 있다
    """
    reason = quantified.shortfall_reason("신주 상장 이후 저점에서 재매수한다", [])

    assert reason is not None
    assert "저점" in reason


def test_dictionary_covers_both_measurable_and_unmeasurable_phrases() -> None:
    """
    목적: 사전이 «해명 요구» 목록이라 넉넉히 담긴다는 계약을 고정한다.

    걸려도 기각이 아니라 해명 요구라 **오탐의 대가가 거의 0 이다.** 그래서 잴 수 있는
    표현(「단기」)과 못 재는 표현(「옥석」)을 한 사전에 함께 둔다 — 둘을 가르는 것은
    사전이 아니라 **파라미터를 낼 수 있는가**이기 때문이다.

    Given: 사전
    When: 두 갈래의 대표 표현을 찾는다
    Then: 둘 다 들어 있다
    """
    terms = set(quantified.QUALITATIVE_TERMS)

    assert {"단기", "짧은"} & terms, "값이 빈 축을 가리키는 표현이 사전에 없습니다"
    assert {"옥석", "저점"} & terms, "축이 없거나 판정 시점에 모르는 표현이 사전에 없습니다"

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

import pytest

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
    parameters = [{"name": "동시 매수 판정 창", "term": "짧은 기간", "unit": "거래일", "candidates": [5, 10, 20]}]

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
    parameters = [{"name": "서프라이즈 하한", "term": "크게", "unit": "%", "candidates": [10]}]

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
    parameters = [{"name": "서프라이즈 하한", "term": "크게", "unit": "%", "candidates": [10, 10, 10]}]

    assert quantified.shortfall_reason(claim, parameters) is not None


def test_an_integer_and_the_same_float_are_one_candidate() -> None:
    """
    목적: 값이 같은 정수와 실수(`5` · `5.0`)를 후보 «하나»로 세는 계약을 고정한다.

    따로 세면 같은 값을 두 번 적은 축이 격자로 통과한다 — 같은 값 반복을 막는 계약과 같은 자리다.

    Given: 5 와 5.0 만 든 후보값
    When: 검사한다
    Then: 막힌다
    """
    parameters = [{"name": "보유 기간", "term": "단기", "unit": "거래일", "candidates": [5, 5.0]}]

    assert quantified.shortfall_reason("단기 보유한다", parameters) is not None


def test_an_integer_beyond_the_float_range_counts_as_a_candidate() -> None:
    """
    목적: [중요] 실수로 못 옮기는 큰 정수 후보값에도 게이트가 «죽지 않고» 숫자 후보로 세는 계약을 고정한다.

    JSON 은 자릿수 제한 없는 정수를 그대로 넘긴다. 게이트가 죽으면 그 단계가 「그 외」 실패로 재시도되고,
    못 읽은 것으로 치면 숫자 후보가 모자라 **첫 답에서 영구 기각**된다. 숫자는 숫자로 센다 —
    값이 말이 되는지는 게이트가 보지 않는다.

    Given: 후보값에 실수 범위를 넘는 정수가 든 축 · 실수로 바꾸면 같아지는 서로 다른 큰 정수 둘
    When: 검사한다
    Then: 예외 없이 격자로 세어져 통과한다 — 서로 다른 수는 서로 다른 후보다
    """
    for candidates in ([10**400, 5], [10**20, 10**20 + 1]):
        parameters = [{"name": "보유 기간", "term": "단기", "unit": "거래일", "candidates": candidates}]

        assert quantified.shortfall_reason("단기 보유한다", parameters) is None, candidates


def test_a_quoted_number_counts_as_a_candidate() -> None:
    """
    목적: [중요] 숫자 하나로 읽히는 글자를 숫자 후보로 세는 계약을 고정한다.

    에이전트는 `5` 와 `"5"` 를 섞어 낸다. 못 세면 잴 수 있는 후보가 첫 답에서 **영구 기각**된다.
    같은 수를 표기만 바꿔 적은 것은 한 후보이고, 단위가 붙은 글자는 숫자 후보가 아니다.

    Given: 따옴표 숫자 둘 · 같은 수를 글자와 숫자로 적은 것 · 단위가 붙은 글자 둘
    When: 검사한다
    Then: 첫째만 통과한다
    """
    claim = "단기 보유한다"

    def axis(candidates: list[object]) -> list[dict[str, object]]:
        return [{"name": "보유 기간", "term": "단기", "unit": "거래일", "candidates": candidates}]

    assert quantified.shortfall_reason(claim, axis(["5", "20"])) is None
    assert quantified.shortfall_reason(claim, axis(["5", 5])) is not None
    assert quantified.shortfall_reason(claim, axis(["5%", "20%"])) is not None


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
    # 큰 폭은 성한 축으로 풀어 둔다 — 그래야 막히는 이유가 «옥석 축의 격자»뿐이다
    parameters = [
        {"name": "하락 폭 하한", "term": "큰 폭", "unit": "%", "candidates": [30, 50]},
        {"name": "옥석 기준", "term": "옥석", "candidates": ["좋은 것", "괜찮은 것"]},
    ]

    reason = quantified.shortfall_reason(claim, parameters)

    assert reason is not None
    assert "「옥석」" in reason and "「큰 폭」" not in reason


def test_parameter_without_a_name_does_not_count() -> None:
    """
    목적: 이름 없는 파라미터가 해명으로 세어지지 않는 계약을 고정한다.

    이름이 없으면 **무슨 축인지 모른 채 숫자만 남는다.** 그 격자는 나중에 못 읽는다.

    Given: 이름이 빈 파라미터
    When: 검사한다
    Then: 막힌다
    """
    claim = "단기 보유한다"
    parameters = [{"name": "  ", "term": "단기", "candidates": [5, 20]}]

    assert quantified.shortfall_reason(claim, parameters) is not None


def test_a_name_holding_only_empty_values_does_not_count() -> None:
    """
    목적: 빈 값만 담은 목록·절 이름도 «이름 없음»으로 보는 계약을 고정한다.

    `str([""])` 는 `"['']"` 라 비어 있지 않아, 안 파고들면 이름 없는 축이 해명으로 세어진다.
    탐색과 수집에는 응답 모양을 강제하는 스키마가 없다.

    Given: 이름 자리에 빈 값만 든 목록 · 절 · 겹친 목록이 온 파라미터
    When: 검사한다
    Then: 모두 막힌다
    """
    for hollow in ([""], {"k": ""}, [[]]):
        parameters = [{"name": hollow, "term": "단기", "unit": "거래일", "candidates": [5, 20]}]

        assert quantified.shortfall_reason("단기 보유한다", parameters) is not None, hollow


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

    「거부됨」만 돌려주면 다음 회차가 같은 시도를 반복한다. 이 사유는 원장의 기각 줄에
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


# --------------------------------------------------------------------------
# 표현 «마다» 축 — 수집이 쓰는 엄격한 판정
# --------------------------------------------------------------------------

SPAC_CLAIM = "코스닥 스팩 합병 상장 종목 중 상장 후 큰 폭 하락한 종목에서 옥석을 가려 저점 매수한다"


def _axis(name: str, *, term: object = None, candidates: list[object] | None = None) -> dict[str, object]:
    """게이트를 통과하는 격자를 가진 축. `term` 을 주면 그 칸을 단다."""
    axis: dict[str, object] = {"name": name, "unit": "거래일", "candidates": candidates or [20, 60]}
    if term is not None:
        axis["term"] = term
    return axis


def test_an_expression_left_without_its_own_axis_is_named() -> None:
    """
    목적: [중요] 한 표현에만 축을 낸 주장이 «남은 표현을 짚여» 막히는 계약을 고정한다.

    예전 판정은 쓸 만한 축이 «하나라도» 있으면 통과였다. 그래서 「옥석을 가려 … 저점」이
    전저점 축 하나로 지나갔고, **축 자체가 없는 표현(옥석)이 해명 없이** 근거 문서까지 갔다.

    Given: 「큰 폭 · 옥석 · 저점」이 든 주장에 큰 폭 · 저점 축만 있다
    When: 엄격하게 검사한다
    Then: 막히고, 사유가 «옥석»을 짚는다
    """
    parameters = [_axis("하락 폭 하한", term="큰 폭"), _axis("전저점 산정 일수", term="전저점 대비")]

    reason = quantified.shortfall_reason(SPAC_CLAIM, parameters)

    assert reason is not None
    assert "「옥석」" in reason
    assert "「저점」" not in reason and "「큰 폭」" not in reason, "풀린 표현까지 짚으면 무엇을 고칠지 흐려진다"


def test_every_expression_with_its_axis_passes() -> None:
    """
    목적: 표현마다 축이 있으면 통과하는 계약을 고정한다.

    Given: 세 표현에 각자의 축
    When: 엄격하게 검사한다
    Then: 사유가 없다
    """
    parameters = [
        _axis("하락 폭 하한", term="큰 폭"),
        _axis("옥석 판정 — 합병 대상 시가총액 순위 상한", term="옥석"),
        _axis("전저점 산정 일수", term="저점"),
    ]

    assert quantified.shortfall_reason(SPAC_CLAIM, parameters) is None


def test_an_axis_name_holding_the_expression_counts() -> None:
    """
    목적: `term` 을 안 적어도 «축 이름에 그 표현이 들어 있으면» 푼 것으로 보는 계약을 고정한다.

    `term` 은 이번에 새로 생긴 칸이다. 이름에 이미 그 말을 담은 축(「단기 보유 기간」)까지
    기각하면 **멀쩡한 후보가 영구 기각된다** — 기각은 다시 안 판다.

    Given: 「단기」가 든 주장과 이름에 「단기」가 든 축(`term` 없음)
    When: 엄격하게 검사한다
    Then: 사유가 없다
    """
    assert quantified.shortfall_reason("공시 다음날 사서 단기 보유한다", [_axis("단기 보유 기간")]) is None


def test_one_axis_may_answer_several_expressions() -> None:
    """
    목적: 한 축이 `term` 에 표현 여럿을 담아 «함께» 풀 수 있는 계약을 고정한다.

    「큰 폭 하락」과 「저점」이 같은 축(하락률)으로 풀리는 주장이 있다. 표현마다 따로 축을
    요구하면 **같은 축을 두 번 적게 만들 뿐** 재는 절차는 달라지지 않는다.

    Given: 세 표현 · `term` 이 목록인 축 하나와 옥석 축 하나
    When: 엄격하게 검사한다
    Then: 사유가 없다
    """
    parameters = [_axis("하락률 하한", term=["큰 폭", "저점"]), _axis("옥석 판정 기준", term="옥석")]

    assert quantified.shortfall_reason(SPAC_CLAIM, parameters) is None


def test_an_unusable_axis_does_not_answer_its_expression() -> None:
    """
    목적: 격자가 안 되는 축은 `term` 을 달아도 «푼 것이 아닌» 계약을 고정한다.

    값 하나를 임의로 고른 축으로 표현을 «풀었다»고 치면 **어떤 값을 넣느냐가 결론을 만든다.**

    Given: 「단기」가 든 주장과 후보값이 하나뿐인 축(`term` 은 단기)
    When: 엄격하게 검사한다
    Then: 막힌다
    """
    parameters = [_axis("보유 기간", term="단기", candidates=[20])]

    assert quantified.shortfall_reason("단기 보유한다", parameters) is not None


def test_an_expression_is_not_assembled_across_term_and_name() -> None:
    """
    목적: `term` 과 이름을 «이어 붙여» 표현을 찾지 않는 계약을 고정한다.

    이어 붙이면 `term` 「큰」과 이름 「폭 하한」이 「큰 폭」이 되어, 아무도 적지 않은 표현이
    풀린 것으로 읽힌다.

    Given: 「큰 폭」이 든 주장과 `term` 「큰」 · 이름 「폭 하한」인 축
    When: 엄격하게 검사한다
    Then: 막힌다
    """
    parameters = [_axis("폭 하한", term="큰")]

    assert quantified.shortfall_reason("상장 후 큰 폭 하락한 종목을 산다", parameters) is not None


def test_a_spacing_variant_of_the_expression_still_counts() -> None:
    """
    목적: 표현의 «띄어쓰기»만 다른 `term` 도 그 표현을 푼 것으로 보는 계약을 고정한다.

    수집의 기각은 다시 안 판다. 「큰 폭」을 「큰폭」으로 적은 축을 못 푼 것으로 읽으면
    잴 수 있는 후보가 띄어쓰기 하나로 영구히 닫힌다.

    Given: 「큰 폭」이 든 주장과 `term` 「큰폭」인 축
    When: 엄격하게 검사한다
    Then: 사유가 없다
    """
    parameters = [_axis("상승 하한", term="큰폭")]

    assert quantified.shortfall_reason("큰 폭 상승 후 매수한다", parameters) is None


@pytest.mark.parametrize(
    "claim",
    [
        "코스닥 상장기업을 공시 다음 거래일 시가에 매수해 5거래일 보유한다",
        "매수일로부터 20거래일 보유한다",
        "외국인 순매수주문이 몰린 종목을 다음 거래일 시가에 산다",
    ],
)
def test_a_word_that_merely_contains_a_dictionary_entry_is_not_flagged(claim: str) -> None:
    """
    목적: [중요] 흔한 낱말 «안에 우연히 든» 사전 글자를 표현으로 보지 않는 계약을 고정한다.

    수집은 걸린 표현마다 축을 요구하고 그 기각은 다시 안 판다. 「상장기업」의 「장기」 · 「매수일」의
    「수일」 · 「매수주문」의 「수주」를 표현으로 보면 값이 다 정해진 후보가 없는 표현 때문에
    영구히 닫힌다.

    Given: 사전 글자를 낱말 안에만 품은, 값이 다 정해진 주장
    When: 표현을 찾고 엄격하게 검사한다
    Then: 걸린 표현이 없고 사유도 없다
    """
    assert quantified.triggered_terms(claim) == ()
    assert quantified.shortfall_reason(claim, []) is None


# --------------------------------------------------------------------------
# 「값이 정해진 말」 선언 — 사전 오탐의 탈출구
#
# 사전은 글자 그대로 찾으므로 이미 정의된 이름·값의 일부도 문다. 그 표현에 축만 요구하면
# 에이전트는 가짜 축을 지어내거나 빈 목록을 내 영구 기각된다 — 기각은 다시 안 판다.
# --------------------------------------------------------------------------

# 실제 원장에 있는 주장. 원장 16개에 사전을 돌려 나온 유일한 오탐이다 [실측 2026-09-28]
NEAR_HIGH_CLAIM = "직전 52주 신고가 대비 현재가 비율(근접도) 상위 30% 종목을 매수하고 하위 30%를 매도해 6~12개월 보유한다"
NEAR_HIGH_REASON = "근접도는 현재가를 직전 52주 신고가로 나눈 비율의 이름이다 — 주장이 상위 30% 로 값을 정했다"


def _declared(term: object, why: object = NEAR_HIGH_REASON) -> dict[str, object]:
    """「값이 정해진 말」 선언 하나."""
    return {"term": term, "why": why}


def test_a_declaration_answers_its_expression() -> None:
    """
    목적: [중요] 이미 정의된 이름의 일부로 걸린 표현을 «선언»으로 풀 수 있는 계약을 고정한다.

    Given: 「근접도」가 든 실제 원장 주장 · 축 없음 · 「근접」 선언
    When: 엄격하게 검사한다
    Then: 사유가 없다
    """
    assert quantified.shortfall_reason(NEAR_HIGH_CLAIM, [], fixed_terms=[_declared("근접")]) is None


@pytest.mark.parametrize("why", ["", "   ", None, [""]])
def test_a_declaration_without_a_reason_answers_nothing(why: object) -> None:
    """
    목적: 이유가 빈 선언은 «안 적힌 것»인 계약을 고정한다.

    이유가 없으면 11번 칸에서 사람이 그 선언이 맞는지 가를 재료가 없다. 게이트는 이유의
    내용은 보지 않지만 «적혔는가»는 본다.

    Given: 이유가 비었거나 빈 값만 담은 「근접」 선언
    When: 엄격하게 검사한다
    Then: 막히고, 사유가 「근접」을 짚는다
    """
    reason = quantified.shortfall_reason(NEAR_HIGH_CLAIM, [], fixed_terms=[_declared("근접", why)])

    assert reason is not None
    assert "「근접」" in reason


def test_a_declaration_answers_only_its_own_expression() -> None:
    """
    목적: 선언이 «자기 표현만» 푸는 계약을 고정한다.

    선언 하나로 다른 표현까지 풀리면 「옥석」처럼 축 자체가 없는 표현이 해명 없이 지나간다.

    Given: 「큰 폭 · 옥석 · 저점」이 든 주장에 큰 폭 축과 저점 선언
    When: 엄격하게 검사한다
    Then: 막히고, 사유가 옥석만 짚는다
    """
    reason = quantified.shortfall_reason(SPAC_CLAIM, [_axis("하락 폭 하한", term="큰 폭")], fixed_terms=[_declared("저점")])

    assert reason is not None
    assert "「옥석」" in reason
    assert "「저점」" not in reason and "「큰 폭」" not in reason


@pytest.mark.parametrize("term", ["옥석을 가려 장기채", "옥석을 가려 장기채 ETF 를 매수한다"])
def test_a_declared_phrase_holding_several_expressions_answers_none(term: str) -> None:
    """
    목적: [중요] 선언의 글자 하나에 걸린 표현이 «둘 이상» 들면 어느 것도 풀지 않는 계약을 고정한다.

    축과 달리 선언은 격자가 필요 없다. 긴 구절이나 주장 통째를 선언으로 적어 여러 표현이 한 줄로
    풀리면, 「옥석」처럼 축 자체가 없는 표현이 해명 없이 지나간다 — 판정을 비켜 가는 길이다.
    선언은 «정의된 말 하나»를 가리키는 자리다.

    Given: 「옥석 · 장기」가 든 주장과, 둘을 한 글자열에 담은 선언
    When: 엄격하게 검사한다
    Then: 막히고, 사유가 둘 다 짚는다
    """
    reason = quantified.shortfall_reason("옥석을 가려 장기채 ETF 를 매수한다", [], fixed_terms=[_declared(term)])

    assert reason is not None
    assert "「옥석」" in reason and "「장기」" in reason


@pytest.mark.parametrize("term", [["장기", "저가"], ["저가", "장기"]])
def test_one_declaration_may_name_several_expressions(term: object) -> None:
    """
    목적: 선언의 `term` 이 «목록»이어도 그 표현들을 푸는 계약을 고정한다 — 축의 `term` 과 같은 모양이다.

    Given: 「장기 · 저가」가 둘 다 정의된 이름의 일부로 걸린 주장과 둘을 담은 선언 하나
    When: 엄격하게 검사한다
    Then: 사유가 없다
    """
    claim = "전일 저가를 종가가 하향 돌파하면 미국 장기채 ETF 를 다음 날 시가에 매수한다"

    assert quantified.triggered_terms(claim) == ("장기", "저가")
    assert quantified.shortfall_reason(claim, [], fixed_terms=[_declared(term)]) is None


def test_a_spacing_variant_in_a_declaration_still_counts() -> None:
    """
    목적: 선언의 표현이 띄어쓰기만 달라도 푸는 계약을 고정한다 — 축과 «같은 대조 규칙»이다.

    규칙이 둘로 갈리면 같은 글자가 축에서는 풀리고 선언에서는 안 풀려, 기각은 다시 안 파므로
    그 차이 하나로 후보가 영구히 닫힌다.

    Given: 「큰 폭」이 든 주장과 `term` 「큰폭」인 선언
    When: 엄격하게 검사한다
    Then: 사유가 없다
    """
    assert quantified.shortfall_reason("큰 폭 상승 후 매수한다", [], fixed_terms=[_declared("큰폭")]) is None


@pytest.mark.parametrize(
    "fixed_terms",
    [
        "근접",
        3,
        {"term": "근접", "why": NEAR_HIGH_REASON},
        [3, None, "근접"],
        [{"term": 3, "why": NEAR_HIGH_REASON}],
        [{"why": NEAR_HIGH_REASON}],
    ],
)
def test_a_malformed_declaration_answers_nothing_and_does_not_crash(fixed_terms: object) -> None:
    """
    목적: 모양이 어긋난 선언이 «예외 없이» 못 푼 것으로 읽히는 계약을 고정한다.

    에이전트가 낸 값이라 목록 자리에 문자열이 오는 일이 흔하다. 검사기가 죽으면 그 회차가
    통째로 끝나고, 모양이 틀린 것을 푼 것으로 읽으면 이유 없는 통과가 된다. 축(`params`)과 같은 관용이다.

    Given: 목록이 아니거나 · 항목이 사전이 아니거나 · `term` 이 없거나 문자열이 아닌 선언
    When: 엄격하게 검사한다
    Then: 예외 없이 막힌다
    """
    assert quantified.shortfall_reason(NEAR_HIGH_CLAIM, [], fixed_terms=fixed_terms) is not None


def test_the_strict_reason_offers_the_declaration() -> None:
    """
    목적: 엄격 판정의 사유가 «선언의 길»도 말하는 계약을 고정한다.

    이 사유는 원장의 기각 줄에 그대로 남아, 사람이 판정을 뒤집을 때 근거가 된다.
    축의 길만 적혀 있으면 오탐으로 기각된 후보를 가를 실마리가 없다.

    Given: 「근접도」 주장 · 축도 선언도 없음
    When: 엄격하게 검사한다
    Then: 사유가 `fixed_terms` 를 말한다
    """
    reason = quantified.shortfall_reason(NEAR_HIGH_CLAIM, [], fixed_terms=None)

    assert reason is not None
    assert "fixed_terms" in reason
    assert "한 줄에 표현 하나" in reason, "원장의 기각 줄을 읽는 사람이 한 줄에 둘을 담아 기각된 것을 가를 수 있어야 한다"


@pytest.mark.parametrize(
    ("claim", "term"),
    [
        (NEAR_HIGH_CLAIM, "근접"),
        ("미국 장기채 ETF 를 매월 마지막 거래일에 매수해 다음 달 첫 거래일에 매도한다", "장기"),
        ("KOSPI200 단기채권 ETF 를 FOMC 발표 2거래일 전 종가에 매수한다", "단기"),
        ("전일 저가를 종가가 하향 돌파하면 다음 날 시가에 매수한다", "저가"),
        ("당일 고가와 저가의 중간값 위에서 마감하면 다음 날 시가에 매수한다", "저가"),
    ],
)
def test_a_defined_word_caught_by_the_dictionary_passes_only_with_a_declaration(claim: str, term: str) -> None:
    """
    목적: [중요] 값이 다 정해진 주장이 사전 오탐에 걸려도 «선언이 있으면» 통과하는 계약을 고정한다.

    첫 줄은 실제 원장의 오탐이고 나머지는 합성 예시다(지표 이름 · 상품 이름 · 시가·고가·저가·종가).
    낱말 안 조각 가림 목록으로는 「전일 저가」처럼 문맥으로만 갈리는 것을 못 가린다.

    Given: 사전이 무는 정의된 말이 든 주장
    When: 선언 없이 · 선언과 함께 엄격하게 검사한다
    Then: 사전은 그 말을 걸고, 선언 없이는 막히고 선언이 있으면 통과한다
    """
    assert quantified.triggered_terms(claim) == (term,)
    assert quantified.shortfall_reason(claim, [], fixed_terms=None) is not None
    assert quantified.shortfall_reason(claim, [], fixed_terms=[_declared(term)]) is None

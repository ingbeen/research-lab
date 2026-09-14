"""측정 설계 초안(10번 칸)이 «잴 수 있는 형태»인지 보는 계약을 고정한다.

설계 §5.2 가 이 칸에 반드시 들어갈 여섯 자리를 이미 못박아 두었고, 각 자리마다
**안 적으면 생기는 일**까지 적어 두었다. 그래서 자리를 줄이지 않는다.

[중요] 이 칸이 채워지면 **사전등록**이 공짜로 따라온다 — 재기 «전»에 측정 방법이 문서에
박히므로 결과를 보고 기준을 고치는 일이 구조적으로 막힌다. 자리가 비면 그 효과가 통째로 없다.

[중요] 격자는 **한 값이 아니라 여러 값**이다. 한 값만 재면 그게 **가장 좋은 값이라서
고른 것인지** 구별되지 않는다. 다만 막기만 하면 달력 규칙 후보에서 억지 격자를 만들게
되므로, **한 값이면 사유를 요구**한다 — 반증 게이트의 「0건이면 사유」와 같은 모양이다.
"""

from typing import Any

from research_lab.gate import measurement


def _filled(**overrides: Any) -> dict[str, Any]:
    """게이트를 통과하는 산출물."""
    payload: dict[str, Any] = {
        "claim": "소형주는 1월에 더 오른다. 12월 말에 사서 1월 말에 판다",
        "instrument": "코스닥150 을 추종하는 국내 상장 ETF. 지수가 아니라 실제로 살 수 있는 상품이다",
        "no_lookahead": "진입·청산이 달력만 보면 정해지므로 판정 시점에 모르는 값이 들어가지 않는다",
        "entry_grid": ["12월 20일", "12월 23일", "12월 26일", "12월 30일"],
        "holding_grid": [20, 40, 60],
        "baseline": "같은 보유 기간을 아무 날에나 시작했을 때의 전체 평균",
        "direction": "위·아래를 미리 정하지 않는다. 내린다도 유효한 신호다",
        "expected_samples": "연 1회 x 20년 = 20건",
        "unverified": ["2000년 이전 코스닥 데이터 품질"],
    }
    payload.update(overrides)
    return payload


def test_a_filled_payload_passes() -> None:
    """
    목적: 여섯 자리가 다 찬 산출물이 통과하는 계약을 고정한다.

    Given: 설계 §5.2 의 자리를 모두 채운 산출물
    When: 검사한다
    Then: 사유가 없다
    """
    assert measurement.shortfall_reason(_filled()) is None


def test_each_required_slot_is_demanded() -> None:
    """
    목적: 여섯 자리가 «하나도 빠짐없이» 요구되는 계약을 고정한다.

    자리를 하나 줄이면 그 물음을 안 묻게 되고, 안 묻힌 칸은 조용히 비어 나간다.
    - 미래 참조를 안 물으면 **못 잴 것을 재게 된다**
    - 기준선을 안 물으면 **비율이 사람을 속인다** (주식은 장기 상승해서 아무 날에나
      사도 오른 비율이 절반을 넘는다)
    - 방향을 미리 정하면 **반대쪽 발견을 통째로 놓친다**
    - 표본 수를 안 물으면 **소수점 차이로 우열을 가리게 된다**

    Given: 자리 하나씩을 비운 산출물들
    When: 검사한다
    Then: 그때마다 그 자리를 가리키는 사유가 돌아온다
    """
    for key in ("instrument", "no_lookahead", "baseline", "direction", "expected_samples"):
        reason = measurement.shortfall_reason(_filled(**{key: "  "}))

        assert reason is not None, key
        assert key in reason


def test_an_empty_grid_is_a_shortfall() -> None:
    """
    목적: 격자가 비면 막는 계약을 고정한다.

    Given: 진입 격자가 빈 산출물
    When: 검사한다
    Then: 그 자리를 가리키는 사유가 돌아온다
    """
    reason = measurement.shortfall_reason(_filled(entry_grid=[]))

    assert reason is not None
    assert "entry_grid" in reason


def test_a_single_value_grid_needs_a_reason() -> None:
    """
    목적: [중요] 격자가 한 값이면 «사유»를 요구하는 계약을 고정한다.

    한 값만 재면 그게 **가장 좋은 값이라서 고른 것인지** 구별되지 않는다(설계 §5.2).
    그래도 막기만 하지 않는 이유는, 달력 규칙 후보처럼 값이 하나뿐인 경우가 실제로 있고
    그때 요구하면 **억지 격자를 지어내게** 되기 때문이다.

    Given: 진입 격자가 한 값뿐이고 사유가 없는 산출물
    When: 검사한다
    Then: 사유가 돌아온다
    """
    reason = measurement.shortfall_reason(_filled(entry_grid=["12월 20일"]))

    assert reason is not None
    assert "entry_grid" in reason


def test_a_single_value_grid_passes_with_a_reason() -> None:
    """
    목적: 한 값이어도 «왜 하나뿐인지»를 적으면 통과하는 계약을 고정한다.

    Given: 한 값짜리 격자와 그 사유
    When: 검사한다
    Then: 통과한다
    """
    payload = _filled(
        entry_grid=["11월 첫 거래일"],
        single_value_reason="진입일이 달력 규칙으로 하나뿐이다. 대신 보유 기간을 격자로 훑는다",
    )

    assert measurement.shortfall_reason(payload) is None


def test_repeated_values_do_not_count_as_a_grid() -> None:
    """
    목적: 같은 값을 여러 번 적은 것이 «격자로 세어지지 않는» 계약을 고정한다.

    검색어 게이트가 「같은 말을 표기만 바꿔 여러 번 적은 것은 갈아 끼운 것이 아니다」로
    세는 것과 같은 축이다. 안 그러면 값 하나를 복붙해 게이트를 통과한다.

    Given: 같은 값이 세 번 든 격자
    When: 검사한다
    Then: 한 값짜리와 같게 사유를 요구한다
    """
    reason = measurement.shortfall_reason(_filled(holding_grid=[20, 20, 20]))

    assert reason is not None
    assert "holding_grid" in reason


def test_a_grid_that_is_not_a_list_is_a_shortfall() -> None:
    """
    목적: 격자 자리에 목록이 아닌 값이 오면 막는 계약을 고정한다.

    문자열은 «비어 있지 않아서» 「적혀 있다」로 읽히고, 파이썬에서는 순회까지 되어
    **예외 없이 글자 수만큼 세어진다.**

    Given: 격자가 문자열인 산출물
    When: 검사한다
    Then: 사유가 돌아온다
    """
    reason = measurement.shortfall_reason(_filled(holding_grid="20일에서 60일"))

    assert reason is not None
    assert "holding_grid" in reason


def test_any_shape_is_survivable() -> None:
    """
    목적: [중요] 어떤 입력에도 «예외를 올리지 않는» 계약을 고정한다 (계층 계약 §5).

    Given: 모양이 어긋난 값들
    When: 검사한다
    Then: 예외 없이 사유가 돌아온다
    """
    for broken in ({}, {"entry_grid": None}, {"instrument": []}, {"holding_grid": {"a": 1}}):
        assert measurement.shortfall_reason(broken) is not None


def test_a_grid_with_no_usable_values_never_passes() -> None:
    """
    목적: [중요] 사유가 있어도 «값이 없는» 격자는 통과하지 않는 계약을 고정한다.

    사유는 「값이 «하나»뿐이다」를 해명하는 것이지 **「값이 없다」를 해명하는 것이 아니다.**
    둘을 같은 길로 묶으면 빈 문자열만 든 목록이 통과하고, 근거 문서의 10번 칸이
    **「적히지 않았습니다」인 채로 완성본으로 나간다** — 칸이 빈 문서가 제품이 되는 것이라
    이 저장소가 가장 막고 싶어 하는 모양이다.

    Given: 빈 문자열만 든 격자와, 채워진 사유
    When: 검사한다
    Then: 사유가 있어도 막힌다
    """
    payload = _filled(entry_grid=["", "   "], single_value_reason="달력 규칙이라 값이 하나뿐이다")

    reason = measurement.shortfall_reason(payload)

    assert reason is not None
    assert "entry_grid" in reason

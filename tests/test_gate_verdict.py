"""판정(2번 칸)이 «판정 · 이유 · 적용한 기준»을 모두 담았는지 보는 계약을 고정한다.

[중요] **「적용한 기준」을 「이유」와 다른 자리로 받는다.** 한 칸이면
「원칙 12 에 걸린다」로 적혀도 게이트가 못 본다. 이 산출물은 저장소 밖으로 나가므로
**번호는 그 자리에서 죽고**, 받는 쪽은 「왜 보류지?」에 답을 얻지 못한 채 종이만 쥔다.
자리를 갈라 두면 안 물을 수가 없다 — 11칸 구조가 자유 서술을 버린 것과 같은 이유이고,
**자립성이라는 1순위 제약을 기계가 건드릴 수 있는 유일한 지점**이다.

[중요] 판정이 «맞는지»는 보지 않는다. 보려 들면 게이트가 또 하나의 판단자가 된다.
「기각」도 「보류」도 정상 결과이며, 회차마다 「잴 가치 있음」이 나오면 그게 고장이다.
"""

from typing import Any

from research_lab.gate import verdict


def _filled(**overrides: Any) -> dict[str, Any]:
    """게이트를 통과하는 산출물."""
    payload: dict[str, Any] = {
        "claim": "소형주는 1월에 더 오른다. 12월 말에 사서 1월 말에 판다",
        "verdict": "보류",
        "reason": "경제적 근거는 있으나 표본이 연 1회 x 20년 = 20건이라 시기를 둘로 쪼개면 칸당 10건이다",
        "criteria": "칸당 10건 미만이면 우연과 구별되지 않으므로 「어느 시기가 만든 값인가」를 물을 수 없다",
        "unverified_extra": ["국내 절세 매도 유인의 실제 크기"],
    }
    payload.update(overrides)
    return payload


def test_a_filled_payload_passes() -> None:
    """
    목적: 셋이 다 찬 산출물이 통과하는 계약을 고정한다.

    Given: 판정·이유·기준이 모두 적힌 산출물
    When: 검사한다
    Then: 사유가 없다
    """
    assert verdict.shortfall_reason(_filled()) is None


def test_every_promised_verdict_passes() -> None:
    """
    목적: 약속된 세 값이 «모두» 통과하는 계약을 고정한다.

    「기각」이 막히면 에이전트가 기각을 피하게 되고, 그것은 이 파이프라인의 가치를
    정면으로 깎는다 — 여기의 가치는 찾는 것보다 **가짜를 그 전에 걸러내는 것**이다.

    Given: 세 판정값
    When: 각각 검사한다
    Then: 전부 통과한다
    """
    for value in verdict.VERDICT_VALUES:
        assert verdict.shortfall_reason(_filled(verdict=value)) is None, value


def test_an_unpromised_verdict_is_a_shortfall() -> None:
    """
    목적: 약속 밖의 판정값을 막는 계약을 고정한다.

    이 값은 기계가 읽어 「판정이 어떻게 갈렸나」를 세는 자리다. 자유 문자열이면
    셀 수 없고, 못 센다는 사실은 아무 에러도 내지 않는다.

    Given: 「조건부 채택」이라 적은 산출물
    When: 검사한다
    Then: 약속된 값들을 알려주는 사유가 돌아온다
    """
    reason = verdict.shortfall_reason(_filled(verdict="조건부 채택"))

    assert reason is not None
    assert "보류" in reason


def test_a_missing_reason_is_a_shortfall() -> None:
    """
    목적: 이유 없는 판정을 막는 계약을 고정한다.

    설계 §2 가 2번 칸을 「판정 **+ 반드시 이유**」로 적어 둔 자리다.

    Given: 이유가 빈 산출물
    When: 검사한다
    Then: 사유가 돌아온다
    """
    reason = verdict.shortfall_reason(_filled(reason="  "))

    assert reason is not None
    assert "reason" in reason


def test_a_missing_criteria_is_a_shortfall() -> None:
    """
    목적: [중요] «적용한 기준 자체»가 없으면 막는 계약을 고정한다.

    이것이 이 게이트의 핵심이다. 이유만 있고 기준이 없으면 「원칙 12 에 걸린다」로
    적힌 문서와 구별되지 않고, 그 문서는 **저장소 밖에서 판단 불가능한 종이**가 된다.

    Given: 이유는 있고 기준이 빈 산출물
    When: 검사한다
    Then: 사유가 돌아온다
    """
    reason = verdict.shortfall_reason(_filled(criteria=""))

    assert reason is not None
    assert "criteria" in reason


def test_any_shape_is_survivable() -> None:
    """
    목적: [중요] 어떤 입력에도 «예외를 올리지 않는» 계약을 고정한다 (계층 계약 §5).

    Given: 모양이 어긋난 값들
    When: 검사한다
    Then: 예외 없이 사유가 돌아온다
    """
    for broken in ({}, {"verdict": None}, {"verdict": ["보류"], "reason": 3, "criteria": {}}):
        assert verdict.shortfall_reason(broken) is not None

"""연간 가동일 게이트의 계약을 고정한다.

연간 매매 횟수도 적고 보유기간도 짧은 후보는 수익을 기대하기 어렵다 — 한 해의 대부분 돈이 쉬기
때문이다. 그래서 «돈이 일하는 거래일»(연간 독립 진입 시점 × 보유 거래일)이 문턱에 못 미치면
탐색 단계에서 기각한다.

[중요] 값을 못 읽는 것은 «미달»이 아니다. 기각된 후보는 사람이 손대기 전까지 다시 안 파지므로,
판정을 못 하면 거르지 않는다.
"""

import math

import pytest

from research_lab.gate import activity


def test_active_days_is_the_product() -> None:
    """
    목적: 가동일이 «독립 진입 시점 × 보유 거래일»인 계약을 고정한다.

    Given: 연 12회 · 4거래일
    When: 가동일을 구한다
    Then: 48 이다
    """
    assert activity.active_days(12, 4) == 48


def test_fractional_estimates_are_read() -> None:
    """
    목적: 소수 어림도 읽는 계약을 고정한다.

    「2년에 한 번」은 연 0.5회다. 정수만 받으면 그런 후보가 「판정 못 함」으로 새어 나간다.

    Given: 연 0.5회 · 120거래일
    When: 가동일을 구한다
    Then: 60 이다
    """
    assert activity.active_days(0.5, 120) == 60


def test_enough_active_days_pass() -> None:
    """
    목적: 가동일이 넉넉한 후보는 막지 않는 계약을 고정한다.

    Given: 연 4회 · 60거래일 (가동일 240)
    When: 검사한다
    Then: 사유가 없다
    """
    assert activity.shortfall_reason(4, 60, "분기 실적 시즌마다 한 번 · 석 달 보유") is None


def test_the_threshold_itself_passes() -> None:
    """
    목적: 문턱과 «같은» 가동일은 통과하는 계약을 고정한다.

    Given: 가동일이 정확히 문턱인 어림
    When: 검사한다
    Then: 사유가 없다
    """
    assert activity.shortfall_reason(1, activity.MIN_ACTIVE_DAYS_PER_YEAR, "근거") is None


def test_too_few_active_days_are_rejected() -> None:
    """
    목적: 드물고 짧은 후보를 막는 계약을 고정한다.

    Given: 연 12회 · 4거래일 (가동일 48)
    When: 검사한다
    Then: 사유가 나온다
    """
    assert activity.shortfall_reason(12, 4, "매월 옵션 만기주 · 나흘 보유") is not None


def test_reason_carries_the_estimates_and_the_threshold() -> None:
    """
    목적: 사유만 보고 「어림이 틀렸나」를 가를 수 있게 하는 계약을 고정한다.

    사유는 원장에 그대로 실린다. 사람이 판정을 뒤집을 근거가 이것뿐이다.

    Given: 연 12회 · 4거래일과 그 근거
    When: 검사한다
    Then: 두 어림값 · 곱 · 문턱 · 근거가 사유에 들어 있다
    """
    reason = activity.shortfall_reason(12, 4, "매월 옵션 만기주 · 나흘 보유")

    assert reason is not None
    for fragment in (
        "12회",
        "보유 4거래일",
        "= 48거래일",
        f"{activity.MIN_ACTIVE_DAYS_PER_YEAR}거래일에 못 미칩니다",
        "매월 옵션 만기주 · 나흘 보유",
    ):
        assert fragment in reason


def test_missing_basis_is_said_out_loud() -> None:
    """
    목적: 근거가 없어도 막되, 근거가 없었다는 사실을 사유에 남기는 계약을 고정한다.

    Given: 근거 없이 낸 미달 어림 — 러너가 꺼낸 근거가 빈 글자다
    When: 검사한다
    Then: 사유가 나오고, 근거가 없었다고 적혀 있다
    """
    reason = activity.shortfall_reason(12, 4, "")

    assert reason is not None
    assert "적지 않았습니다" in reason


def test_a_basis_that_is_not_text_is_not_written_out() -> None:
    """
    목적: 글자가 아닌 근거를 받으면 «적지 않음»으로 보고 파이썬 표기를 사유에 싣지 않는 계약을 고정한다.

    근거를 펴는 것은 러너의 일이다(`payload.as_text`). 날것 값을 넘기는 호출자가 생겨도
    `['매월 한 번']` 같은 표기가 공개 원장에 실리면 안 된다.

    Given: 목록 · null 근거
    When: 검사한다
    Then: 사유에 근거가 없었다고 적히고 목록 표기가 없다
    """
    for basis in (["매월 한 번"], None):
        reason = activity.shortfall_reason(12, 4, basis)

        assert reason is not None, basis
        assert "적지 않았습니다" in reason
        assert "['" not in reason


@pytest.mark.parametrize(
    ("entries", "holding"),
    [
        ("4~5", 60),
        (4, "12회"),
        ("", 60),
        ("nan", 60),
        (True, 60),
        (4, True),
        (None, 60),
        (4, None),
        (-1, 60),
        (math.inf, 60),
        (4, math.nan),
        ([4], 60),
        (10**400, 4),
        (4, 10**400),
    ],
)
def test_unreadable_estimates_are_not_judged(entries: object, holding: object) -> None:
    """
    목적: [중요] 어림을 못 읽으면 «거르지 않는» 계약을 고정한다.

    판정을 못 한 것을 미달로 접으면 멀쩡한 후보가 영구 기각된다. 참/거짓은 파이썬에서 정수라
    그냥 두면 1 로 곱해진다. 숫자 하나가 아닌 글자(범위 · 단위가 붙은 말)는 읽지 않는다 — 어느
    끝을 쓸지가 게이트의 판단이 된다. JSON 은 자릿수 제한 없는 정수를 넘기므로 실수로 못 옮기는
    정수도 예외 없이 「판정 못 함」이다.

    Given: 숫자 하나로 읽을 수 없거나 0 이상의 유한한 수가 아닌 어림
    When: 가동일을 구하고 검사한다
    Then: 가동일이 없고, 사유도 없다
    """
    assert activity.active_days(entries, holding) is None
    assert activity.shortfall_reason(entries, holding, "근거") is None


def test_quoted_numbers_are_read() -> None:
    """
    목적: [중요] 따옴표 안의 숫자 하나를 숫자로 읽는 계약을 고정한다.

    에이전트는 `12` 와 `"12"` 를 섞어 낸다. 못 읽으면 그 후보가 판정 없이 통과해 기준이 꺼진다.

    Given: 따옴표로 감싼 12 와 앞뒤에 공백이 붙은 5
    When: 가동일을 구하고 검사한다
    Then: 60 으로 읽히고, 따옴표 없는 같은 숫자와 판정 · 사유가 같다 — 문턱 값에 기대지 않는다
    """
    assert activity.active_days("12", " 5 ") == 60
    assert activity.shortfall_reason("12", " 5 ", "근거") == activity.shortfall_reason(12, 5, "근거")


@pytest.mark.parametrize(
    ("entries", "holding", "days", "rejected"),
    [
        (4, 0, 4, True),  # 분기마다 당일 청산 — 드물고 짧다
        ("12", "0", 12, True),
        (4, -0.0, 4, True),
        (252, 0, 252, False),  # 매일 당일 청산 — 짧아도 매일 돈이 돈다
        (100, 0.5, 100, False),  # 반나절 보유도 그날 하루는 돈이 묶인다
        (50, 0.5, 50, True),
    ],
)
def test_same_day_holding_counts_as_one_day(entries: object, holding: object, days: float, rejected: bool) -> None:
    """
    목적: [중요] 보유 1 미만(당일 청산)을 «하루»로 세는 계약을 고정한다.

    0 을 그대로 곱하면 매일 도는 당일 청산까지 가동일 0 으로 영구 기각된다. 판정 못 함으로 흘리면
    드문 당일 청산이 게이트를 비켜 간다. 같은 날 사고 팔아도 그날 하루는 돈이 묶인다 — 0 과 1 사이도 같다.

    Given: 보유를 0 또는 1 미만으로 어림한 후보
    When: 가동일을 구하고 검사한다
    Then: 보유를 하루로 센 곱이 나오고, 드문 것만 걸린다
    """
    assert activity.active_days(entries, holding) == days
    assert (activity.shortfall_reason(entries, holding, "근거") is not None) is rejected


def test_the_reason_shows_the_holding_it_counted() -> None:
    """
    목적: 사유가 에이전트가 쓴 보유와 «곱한 값»을 함께 보여 주는 계약을 고정한다.

    보유를 하루로 올려 곱해 놓고 쓴 값만 찍으면 「0 × 4 = 4」처럼 스스로 모순인 줄이 되고, 곱한 값만
    찍으면 에이전트가 0.5 를 썼는지 사유만 보고는 알 수 없다. 사람이 판정을 뒤집을 근거가 이 사유뿐이다.

    Given: 연 4회 · 보유 0 (부호가 음인 0 포함), 연 50회 · 보유 0.5
    When: 검사한다
    Then: 쓴 보유 · 올려 센 보유 · 곱이 함께 찍히고 「-0」이 없다
    """
    for holding in (0, -0.0):
        reason = activity.shortfall_reason(4, holding, "근거")

        assert reason is not None
        assert "보유 0거래일(1거래일로 올려 셈) = 4거래일" in reason
        assert "-0" not in reason

    reason = activity.shortfall_reason(50, 0.5, "근거")

    assert reason is not None
    assert "보유 0.5거래일(1거래일로 올려 셈) = 50거래일" in reason


@pytest.mark.parametrize(("entries", "holding"), [(0, 60), (0, 2520), ("0", 60), (-0.0, 60)])
def test_zero_entries_cannot_be_judged(entries: object, holding: object) -> None:
    """
    목적: [중요] 연횟수 0 을 «판정 못 함»으로 두는 계약을 고정한다.

    연 0회는 「모름」과도 「한 번 사서 계속 든다」와도 구별되지 않는다. 곱하면 상시 보유(0 × 2520)가
    가동일 0 으로 영구 기각된다. 드문 후보는 지시문이 0.5 같은 소수로 받는다.

    Given: 연횟수를 0 으로 어림한 후보
    When: 가동일을 구하고 검사한다
    Then: 가동일이 없고, 사유도 없다
    """
    assert activity.active_days(entries, holding) is None
    assert activity.shortfall_reason(entries, holding, "근거") is None


@pytest.mark.parametrize(
    ("entries", "holding", "rejected"),
    [
        (12, 5, True),  # 옵션 만기주 — 매월 한 번 · 범위 4 ~ 5거래일의 긴 쪽
        (1, 66, True),  # 연말 배당락 — 연 1회 · 범위 6 ~ 66거래일의 긴 쪽
        (1, 125, False),  # Sell in May — 연 1회 · 약 6개월
    ],
)
def test_the_threshold_splits_the_known_cases(entries: int, holding: int, rejected: bool) -> None:
    """
    목적: 문턱이 기존 후보의 «긴 쪽 어림»을 사람이 정한 대로 가르는 계약을 고정한다.

    지시문은 범위의 긴 쪽을 쓰게 한다. 그 어림에서도 드물고 짧은 대표 사례(옵션 만기주 ·
    연말 배당락)는 걸리고, 드물어도 오래 드는 사례(Sell in May)는 통과해야 한다 — 문턱을 이
    둘 사이에 둔 것이 사용자 결정이다(2026-09-29).

    Given: 기존 후보의 긴 쪽 어림
    When: 검사한다
    Then: 대표 사례만 걸린다
    """
    assert (activity.shortfall_reason(entries, holding, "근거") is not None) is rejected

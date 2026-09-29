"""게이트들이 함께 쓰는 「숫자로 읽히나」 판정의 계약을 고정한다.

정성 표현 게이트(축의 후보값)와 측정 설계 게이트(격자)가 「같은 값인가」를 이 판정 하나로 본다.
뜻이 갈리면 한 게이트는 두 값으로, 다른 게이트는 한 값으로 세어 같은 격자의 판정이 갈린다.
"""

import json

import pytest

from research_lab.gate.numbers import as_number


@pytest.mark.parametrize(("value", "expected"), [(5, 5), (5.0, 5.0), (-10, -10), (0, 0)])
def test_numbers_are_read_as_they_are(value: object, expected: float) -> None:
    """
    목적: 정수와 실수는 «그대로» 수로 읽는 계약을 고정한다.

    Given: 정수 · 실수 · 음수 · 0
    When: 읽는다
    Then: 같은 수가 돌아온다
    """
    assert as_number(value) == expected


def test_an_integer_beyond_the_float_range_stays_an_integer() -> None:
    """
    목적: [중요] 실수 범위를 넘는 정수도 예외 없이 «수»로 돌려주는 계약을 고정한다.

    JSON 은 자릿수 제한 없는 정수를 그대로 넘긴다. 실수로 바꾸면 예외가 오르고, 못 읽은 것으로 치면
    정성 표현 게이트에서 숫자 후보가 모자라 영구 기각된다.

    Given: 401자리 정수
    When: 읽는다
    Then: 그 정수 그대로다
    """
    assert as_number(10**400) == 10**400


@pytest.mark.parametrize(("value", "expected"), [("5", 5.0), (" 20 ", 20.0), ("-10", -10.0), ("0.5", 0.5)])
def test_a_quoted_single_number_is_read(value: str, expected: float) -> None:
    """
    목적: [중요] 숫자 하나로 읽히는 글자를 수로 읽는 계약을 고정한다.

    에이전트는 `5` 와 `"5"` 를 섞어 낸다. 못 읽으면 정성 표현 게이트가 그 축을 격자로 안 세어 영구 기각한다.

    Given: 따옴표 안의 숫자 하나 (공백 · 음수 · 소수 포함)
    When: 읽는다
    Then: 그 실수다
    """
    assert as_number(value) == expected


@pytest.mark.parametrize("value", ["5%", "20거래일", "1~3", "", "  ", "nan", "inf", "-inf", "1e400", "다섯"])
def test_text_that_is_not_one_finite_number_is_not_read(value: str) -> None:
    """
    목적: 숫자 하나가 아니거나 유한하지 않은 글자는 «수가 아니다»로 보는 계약을 고정한다.

    단위 · 범위가 붙은 글자를 풀어 읽기 시작하면 어느 끝을 쓸지가 게이트의 판단이 된다.
    유한하지 않은 글자를 버리는 이유 — `float("nan")` 은 부를 때마다 다른 객체라 집합에서 겹쳐지지 않아
    `["nan", "nan"]` 이 두 값으로 세어진다.

    Given: 단위 · 범위 · 빈 글자 · 비유한 값 · 한글 수사
    When: 읽는다
    Then: None 이다
    """
    assert as_number(value) is None


@pytest.mark.parametrize("value", [True, False, None, [5], {"n": 5}])
def test_other_shapes_are_not_numbers(value: object) -> None:
    """
    목적: 참/거짓과 목록 · 사전 · null 은 수가 아닌 계약을 고정한다.

    파이썬에서 `True` 는 `int` 라 그냥 두면 1 로 읽힌다.

    Given: 참/거짓 · null · 목록 · 사전
    When: 읽는다
    Then: None 이다
    """
    assert as_number(value) is None


def test_json_non_finite_numbers_stay_as_they_are() -> None:
    """
    목적: JSON 의 NaN · Infinity 는 지금처럼 수로 두는 계약을 고정한다.

    JSON 파싱은 NaN 을 한 객체로 돌려주므로 `[NaN, NaN]` 은 집합에서 한 값이다 — 글자 「nan」과 달리 겹쳐진다.

    Given: JSON 으로 읽은 NaN 두 개와 Infinity
    When: 읽는다
    Then: 받은 객체 그대로이고, NaN 두 개는 집합에서 하나다
    """
    first, second, infinite = json.loads("[NaN, NaN, Infinity]")

    assert as_number(first) is first
    assert as_number(infinite) == float("inf")
    assert len({as_number(first), as_number(second)}) == 1

"""게이트들이 함께 쓰는 「그 자리가 채워졌나」 판정의 계약을 고정한다.

게이트들이 이 판정 하나를 쓴다. 여기서 뜻이 갈리면 게이트는 「적혔다」로 읽고
조립부는 「적히지 않았습니다」로 찍는 어긋남이 **쓰는 곳 전부에서 한꺼번에** 생긴다.
"""

from typing import Any

from research_lab.gate.filled import is_filled


def test_values_with_content_are_filled() -> None:
    """
    목적: 내용이 조금이라도 있으면 «채워졌다»로 보는 계약을 고정한다.

    내용의 질은 보지 않는다 — 「해당 없음」 한 줄도, 숫자 0 도 채운 것이다.

    Given: 문장 · 숫자 0 · 빈 값 사이에 든 문장
    When: 판정한다
    Then: 전부 채워졌다
    """
    for value in ("해당 없음 — 위험 보상 구조가 아니다", 0, ["", "국내 ETF 일봉"], {"국내": "", "미국": "3배"}):
        assert is_filled(value), value


def test_containers_holding_only_empty_values_are_not_filled() -> None:
    """
    목적: [중요] 빈 값만 담은 목록·절을 «비었다»로 보는 계약을 고정한다.

    `str([""])` 는 `"['']"` 라 비어 있지 않다. 안 파고들면 게이트와 조립부의 판정이 갈린다.

    Given: None · 공백 · 빈 목록 · 빈 값만 든 목록과 절 · 겹친 빈 목록
    When: 판정한다
    Then: 전부 비었다
    """
    for value in (None, "   ", [], {}, [""], {"k": ""}, [[]], [None, {"k": [" "]}]):
        assert not is_filled(value), value


def test_deeply_nested_values_do_not_raise() -> None:
    """
    목적: [중요] 아무리 깊게 중첩돼도 «예외를 올리지 않는» 계약을 고정한다.

    에이전트가 낸 값이라 깊이를 보장할 수 없다. 게이트가 죽으면 고칠 수 있었던 것까지
    그 회차를 끝낸다 — 판정을 못 하는 것과 실패로 판정하는 것은 다르다.

    Given: 파이썬 재귀 한도보다 깊게 겹친 목록 (맨 안쪽이 빈 값인 것과 문장인 것)
    When: 판정한다
    Then: 예외 없이 각각 비었다 · 채워졌다
    """
    hollow: Any = ""
    written: Any = "맨 안쪽의 문장"
    for _ in range(5_000):
        hollow = [hollow]
        written = [written]

    assert not is_filled(hollow)
    assert is_filled(written)

"""계보 게이트의 계약을 고정한다.

**웹에서 합의는 근거가 아니다.** 여러 곳이 같은 말을 하는 가장 흔한 이유는 서로 베꼈기
때문이고, 그렇게 만들어진 합의는 「여러 소스에서 확인됨」이라는 라벨을 달고 온다.
계보표는 그 라벨을 벗겨 **「세 곳에서 확인」이 아니라 「한 원본 · 복제 두 곳」**으로 적게 한다.

[중요] 게이트가 보는 것은 둘뿐이다 — 독립 소스 «수»가 적혔나, 그리고 모았던 출처가
**하나도 빠지지 않고** 계보표에 들어갔나. 어느 것이 진짜 원본인지는 판정하지 않는다.

[중요] **검색어 하한을 걸지 않는다.** 계보는 이미 모은 출처를 보는 일이라 하한을 걸면
억지 검색을 유발한다 — 게이트가 규율을 만드는 것이 아니라 규율을 흉내 내게 만드는 자리다.
"""

from research_lab.gate import lineage


def _group(origin: str, copies: list[str]) -> dict[str, object]:
    """원본 하나와 그 복제들로 계보 한 덩어리를 만든다."""
    return {
        "origin": {"url": origin},
        "copies": [{"url": url} for url in copies],
        "why": "같은 숫자와 같은 예시가 반복된다",
    }


def test_complete_lineage_passes() -> None:
    """
    목적: 모았던 출처를 모두 다룬 계보표가 통과하는 계약을 고정한다.

    Given: 두 출처를 원본·복제로 묶고 독립 소스 수를 적은 계보표
    When: 검사한다
    Then: 사유가 없다
    """
    payload = {
        "groups": [_group("https://example.com/원본", ["https://example.com/복제"])],
        "independent_source_count": 1,
    }

    reason = lineage.shortfall_reason(payload, source_urls=["https://example.com/원본", "https://example.com/복제"])

    assert reason is None


def test_missing_independent_source_count_is_blocked() -> None:
    """
    목적: 「복제를 뺀 진짜 소스 수」가 없으면 막는 계약을 고정한다.

    그 숫자가 이 단계의 산출물이다. 없으면 계보표는 출처를 나열한 표일 뿐이다.

    Given: 독립 소스 수가 없는 계보표
    When: 검사한다
    Then: 사유가 나온다
    """
    payload = {"groups": [_group("https://example.com/원본", [])]}

    assert lineage.shortfall_reason(payload, source_urls=["https://example.com/원본"]) is not None


def test_dropped_source_is_blocked() -> None:
    """
    목적: 모았던 출처가 계보표에서 «빠지면» 막는 계약을 고정한다.

    출처를 빠뜨리고 「독립 세 곳」이라 적으면 그 숫자가 통째로 틀린다. 그리고 이 고장은
    **에러를 내지 않는다** — 표는 그럴듯하게 완성된 것처럼 보인다.

    Given: 두 출처 중 하나만 다룬 계보표
    When: 검사한다
    Then: 빠진 URL 이 사유에 들어 있다
    """
    payload = {"groups": [_group("https://example.com/원본", [])], "independent_source_count": 1}

    reason = lineage.shortfall_reason(payload, source_urls=["https://example.com/원본", "https://example.com/빠뜨린"])

    assert reason is not None
    assert "빠뜨린" in reason


def test_url_comparison_is_normalized() -> None:
    """
    목적: 표기 차이가 «빠진 출처»로 읽히지 않는 계약을 고정한다.

    [중요] 정규화하지 않으면 끝 슬래시 하나, 호스트 대소문자 하나 때문에 같은 URL 이
    다르게 보여 **에러 없이 매 회차 막힌다.** 원인이 게이트 자신이라 로그만 봐서는
    무엇이 어긋났는지 드러나지 않는다.

    Given: 끝 슬래시와 호스트 대소문자만 다른 같은 URL
    When: 검사한다
    Then: 같은 것으로 보아 통과한다
    """
    payload = {"groups": [_group("https://Example.com/원본/", [])], "independent_source_count": 1}

    assert lineage.shortfall_reason(payload, source_urls=["https://example.com/원본"]) is None


def test_query_string_is_not_thrown_away() -> None:
    """
    목적: 질의 문자열만 다른 URL 이 «같은 것으로» 뭉개지지 않는 계약을 고정한다.

    [중요] 정규화가 지나치면 반대쪽으로 터진다 — `...?id=1` 과 `...?id=2` 가 같아 보이면
    **빠진 출처가 「다뤄진 것」으로 통과한다.** 이 게이트가 잡으려던 바로 그 고장이다.

    Given: 질의 문자열만 다른 두 출처 중 하나만 다룬 계보표
    When: 검사한다
    Then: 빠진 쪽이 잡힌다
    """
    payload = {"groups": [_group("https://example.com/a?id=1", [])], "independent_source_count": 1}

    reason = lineage.shortfall_reason(payload, source_urls=["https://example.com/a?id=1", "https://example.com/a?id=2"])

    assert reason is not None
    assert "id=2" in reason


def test_sources_without_a_url_are_not_required() -> None:
    """
    목적: URL 이 없는 출처를 대조 대상에서 «빼는» 계약을 고정한다.

    링크를 못 찾은 것은 「미검증」으로 적는 것이 규율이다. 그런 출처까지 계보에
    넣으라고 요구하면, 넣을 것이 없어 **에이전트가 URL 을 지어낸다.**

    Given: URL 이 빈 출처가 섞인 입력
    When: 검사한다
    Then: 통과한다
    """
    payload = {"groups": [_group("https://example.com/원본", [])], "independent_source_count": 1}

    assert lineage.shortfall_reason(payload, source_urls=["https://example.com/원본", "", "   "]) is None


def test_no_sources_at_all_passes() -> None:
    """
    목적: 모은 출처가 하나도 없는 회차를 막지 «않는» 계약을 고정한다.

    찬성 근거 0건 · 반증 0건은 「실체 없음」이라는 정상 결과다. 그 회차의 계보표가
    비는 것은 당연하고, 막으면 **정상 결과가 실패로 보고된다.**

    Given: 출처가 없는 입력과 독립 소스 수 0
    When: 검사한다
    Then: 통과한다
    """
    assert lineage.shortfall_reason({"groups": [], "independent_source_count": 0}, source_urls=[]) is None


def test_malformed_payload_does_not_crash_the_gate() -> None:
    """
    목적: 모양이 어긋난 입력에 게이트가 «죽지 않는» 계약을 고정한다.

    검사기가 죽어서 파이프라인을 멈추게 해서는 안 된다.

    Given: 계보 자리에 문자열이, 소스 수 자리에 문자열이 온 입력
    When: 검사한다
    Then: 예외 없이 사유가 나온다
    """
    payload = {"groups": "한 덩어리", "independent_source_count": "셋"}

    assert lineage.shortfall_reason(payload, source_urls=["https://example.com/원본"]) is not None

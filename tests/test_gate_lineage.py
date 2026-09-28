"""계보 게이트의 계약을 고정한다.

**웹에서 합의는 근거가 아니다.** 여러 곳이 같은 말을 하는 가장 흔한 이유는 서로 베꼈기
때문이고, 그렇게 만들어진 합의는 「여러 소스에서 확인됨」이라는 라벨을 달고 온다.
계보표는 그 라벨을 벗겨 **「세 곳에서 확인」이 아니라 「한 원본 · 복제 두 곳」**으로 적게 한다.

[중요] 게이트가 보는 것은 하나뿐이다 — 모았던 출처가 **하나도 빠지지 않고** 계보표에
들어갔나. 어느 것이 진짜 원본인지는 판정하지 않는다. 독립 소스 «수»는 에이전트가 적지 않고
러너가 덩어리 수로 센다.

[중요] **검색어 하한을 걸지 않는다.** 계보는 이미 모은 출처를 보는 일이라 하한을 걸면
억지 검색을 유발한다 — 게이트가 규율을 만드는 것이 아니라 규율을 흉내 내게 만드는 자리다.
"""

from research_lab.gate import lineage
from research_lab.runner import payload as payload_helpers


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


def test_the_gate_does_not_ask_for_the_independent_source_count() -> None:
    """
    목적: 게이트가 「복제를 뺀 진짜 소스 수」를 «요구하지 않는» 계약을 고정한다.

    정의상 자기 혼자인 덩어리가 독립 1 이라 그 수는 덩어리 수와 같다. 에이전트에게 적게 하면
    틀려도 에러가 없으므로 러너가 센다 — 게이트가 요구하면 러너가 세는 값과 두 벌이 된다.

    Given: 출처를 모두 다뤘고 독립 소스 수는 안 적은 계보표
    When: 검사한다
    Then: 사유가 없다
    """
    payload = {"groups": [_group("https://example.com/원본", [])]}

    assert lineage.shortfall_reason(payload, source_urls=["https://example.com/원본"]) is None


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


# --------------------------------------------------------------------------
# 한 원본은 한 덩어리에만 — 독립 소스 수가 부풀지 않게
# --------------------------------------------------------------------------

ORIGIN = "https://example.com/원논문"
MIRROR = "https://mirror.example/원논문.pdf"
DIGEST = "https://blog.example/두-논문-정리"
OTHER = "https://example.com/다른-논문"


def test_an_origin_in_two_groups_is_blocked() -> None:
    """
    목적: [중요] 한 원본이 «두 덩어리의 원본»이면 막는 계약을 고정한다.

    독립 소스 수는 주소가 있는 덩어리 수다. 같은 원본이 두 덩어리로 나뉘면 **그 수가 하나
    부풀고, 6번 칸 맨 앞의 숫자가 틀린 채 나간다** — 표는 그럴듯해 보여 에러가 없다.

    Given: 같은 원본(표기만 다름)을 원본으로 둔 덩어리 둘
    When: 검사한다
    Then: 막히고, 사유가 그 주소를 짚는다
    """
    payload = {"groups": [_group(ORIGIN, [MIRROR]), _group("https://EXAMPLE.com/원논문/", [])]}

    reason = lineage.shortfall_reason(payload, source_urls=[ORIGIN, MIRROR])

    assert reason is not None
    assert "원논문" in reason


def test_an_origin_that_reappears_as_a_copy_is_blocked() -> None:
    """
    목적: 원본이 «다른 덩어리의 복제»로 또 나오면 막는 계약을 고정한다.

    「A 는 B 를 베꼈다」와 「A 는 독립 원본이다」가 한 표에 함께 있으면, A 의 덩어리는
    B 에 합쳐져야 하는데 **따로 세어진다.**

    Given: 한 덩어리의 원본이 다른 덩어리의 복제로도 적힌 표
    When: 검사한다
    Then: 막힌다
    """
    payload = {"groups": [_group(ORIGIN, [MIRROR]), _group(OTHER, [ORIGIN])]}

    assert lineage.shortfall_reason(payload, source_urls=[ORIGIN, MIRROR, OTHER]) is not None


def test_a_digest_copying_two_origins_may_sit_in_both_groups() -> None:
    """
    목적: 두 원본을 모은 글이 «두 덩어리의 복제»로 나오는 것은 통과하는 계약을 고정한다.

    모음 글은 서로 독립인 두 원본을 함께 옮긴다. 두 덩어리에 다 적어도 **덩어리 수는
    그대로라** 독립 소스 수가 부풀지 않는다 — 막으면 정당한 표를 지어낸 것처럼 몬다.

    Given: 원본이 다른 두 덩어리가 같은 모음 글을 복제로 든다
    When: 검사한다
    Then: 사유가 없다
    """
    payload = {"groups": [_group(ORIGIN, [DIGEST]), _group(OTHER, [DIGEST])]}

    assert lineage.shortfall_reason(payload, source_urls=[ORIGIN, OTHER, DIGEST]) is None


def test_an_origin_listed_again_in_its_own_group_passes() -> None:
    """
    목적: 원본이 «제 덩어리의 복제»로 또 적힌 것은 통과하는 계약을 고정한다.

    한 덩어리 안의 중복은 덩어리 수를 바꾸지 않는다. 막으면 수가 옳은 표를 오탐으로 막는다.

    Given: 원본이 제 덩어리의 복제 목록에도 있다
    When: 검사한다
    Then: 사유가 없다
    """
    payload = {"groups": [_group(ORIGIN, [ORIGIN, MIRROR])]}

    assert lineage.shortfall_reason(payload, source_urls=[ORIGIN, MIRROR]) is None


def test_a_dropped_source_and_a_repeated_origin_are_named_together() -> None:
    """
    목적: 빠진 출처와 원본 중복을 «한 사유에 함께» 돌려주는 계약을 고정한다.

    한 번에 하나씩 알리면 걸린 자리 수만큼 회차가 들고, 세 번이면 후보가 걷힌다.

    Given: 출처 하나가 빠졌고 원본 하나가 두 덩어리에 든 표
    When: 검사한다
    Then: 사유에 빠진 주소와 중복된 원본이 둘 다 있다
    """
    payload = {"groups": [_group(ORIGIN, []), _group(ORIGIN, [])]}

    reason = lineage.shortfall_reason(payload, source_urls=[ORIGIN, OTHER])

    assert reason is not None
    assert "다른-논문" in reason
    assert "원논문" in reason


def test_normalizing_never_raises() -> None:
    """
    목적: 대조용 정규화가 «어떤 입력에도» 예외를 올리지 않는 계약을 고정한다.

    이 함수는 게이트와 근거 문서 조립이 함께 쓴다. 쪼갤 수 없는 호스트(대괄호가 든 꼴) 하나로
    여기서 터지면 비용을 다 치른 단계가 마지막에 깨진다.

    Given: 대괄호가 든 호스트
    When: 정규화한다
    Then: 예외 없이 값이 나온다
    """
    assert lineage.normalize_url("https://[x]/a")


def test_a_hash_route_keeps_two_articles_apart() -> None:
    """
    목적: 해시로 페이지를 가르는 주소는 «서로 다른 글»로 남기는 계약을 고정한다.

    조각을 통째로 버리면 `#/글/101` 과 `#/글/202` 가 한 주소가 되어, 둘을 각자 원본으로 적은
    옳은 표가 「한 원본이 두 덩어리에」로 막힌다. 문서 안의 절을 가리키는 조각은 여전히 버린다.

    Given: 해시 경로만 다른 두 주소 · 절 조각만 다른 두 주소
    When: 정규화한다
    Then: 앞의 둘은 다르고, 뒤의 둘은 같다
    """
    assert lineage.normalize_url("https://site.example/#/article/101") != lineage.normalize_url(
        "https://site.example/#/article/202"
    )
    assert lineage.normalize_url("https://site.example/a#1") == lineage.normalize_url("https://site.example/a#2")


def test_only_a_string_is_an_address() -> None:
    """
    목적: 주소 자리에 «문자열»만 주소로 보는 계약을 고정한다 — 러너와 같은 열쇠다.

    목록이 든 주소 자리를 게이트는 파이썬 표기로, 러너는 편 문자열로 읽으면 열쇠가 갈려 게이트는
    「빠졌다」, 러너는 「이미 모았다」로 읽는다 — 그 단계는 매 회차 같은 자리에서 막힌다.

    Given: 원본의 주소 자리에 목록이 든 표와, 그것을 모은 출처로 세지 않은 러너
    When: 검사한다
    Then: 사유가 없다
    """
    source = {"url": ["https://a.example/x"]}
    payload = {"groups": [{"origin": source, "copies": []}]}

    assert payload_helpers.url_of(source) == ""
    assert lineage.shortfall_reason(payload, source_urls=[payload_helpers.url_of(source)]) is None

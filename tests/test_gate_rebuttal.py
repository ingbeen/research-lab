"""반증 게이트의 계약을 고정한다 — «행위»를 검사하고 «결과»를 검사하지 않는다.

두 문서가 부딪히는 자리였다. 로드맵은 「반증 칸 비면 실패」라 적었고, 설계 §5.5 A 는
「절의 존재만 본다 · 빈 경우에도 「없음」이라 적을 길이 남아야 한다」고 적었다.

**행위를 검사하는 쪽으로 정했다.** 반증 칸이 있고 반증 검색어가 충분하면 통과하며,
반증이 0건이면 「없음」과 「왜 못 찾았나」를 적게 하고 그대로 통과시킨다.

[중요] 결과가 0건인 것을 실패로 만드는 순간 에이전트에게 **반증을 「지어낼」 압력**이 생긴다.
이 저장소는 백테스트를 하지 않아 부풀릴 점수가 없고, 그래서 **유일하게 남는 위조 위험이
「없는 출처」**다. 게이트가 그 압력을 만들면 안 된다.
"""

from research_lab.gate import rebuttal


def test_rebuttals_found_pass() -> None:
    """
    목적: 반증을 찾아 온 회차가 막히지 않는 계약을 고정한다.

    Given: 반증 하나가 든 산출물
    When: 검사한다
    Then: 사유가 없다
    """
    payload = {"rebuttals": [{"title": "재현 실패", "url": "https://example.com/a", "kind": "primary"}]}

    assert rebuttal.shortfall_reason(payload) is None


def test_no_rebuttal_with_a_reason_passes() -> None:
    """
    목적: 「없음」도 정상 결과로 다루는 계약을 고정한다.

    못 찾은 것과 아니라고 확인한 것은 다르다. 0건을 실패로 만들면 다음부터
    **에이전트가 반증을 지어낸다** — 이 범위에서 유일하게 남는 위조 위험이 그것이다.

    Given: 반증 0건이지만 못 찾은 사유가 적힌 산출물
    When: 검사한다
    Then: 사유가 없다
    """
    payload = {"rebuttals": [], "not_found_reason": "한국어·영어로 여섯 번 던졌으나 반대 주장을 찾지 못했다"}

    assert rebuttal.shortfall_reason(payload) is None


def test_missing_rebuttal_field_is_blocked() -> None:
    """
    목적: 반증 «칸» 자체가 없으면 막는 계약을 고정한다.

    이것이 게이트 1차의 본체다. 칸이 없다는 것은 그 단계가 **아예 묻지 않았다**는 뜻이다.

    Given: 반증 칸이 없는 산출물
    When: 검사한다
    Then: 사유가 나온다
    """
    assert rebuttal.shortfall_reason({"queries": ["ㄱ", "ㄴ", "ㄷ"]}) is not None


def test_empty_rebuttals_without_a_reason_are_blocked() -> None:
    """
    목적: 0건인데 «왜 못 찾았는지»가 없으면 막는 계약을 고정한다.

    「없음」이라 적을 길은 남기되, **적기는 해야 한다.** 빈 목록만 돌려주는 것은
    「찾아봤는데 없었다」와 「안 찾았다」가 구별되지 않는다.

    Given: 반증 0건이고 사유가 빈 산출물
    When: 검사한다
    Then: 사유가 나온다
    """
    assert rebuttal.shortfall_reason({"rebuttals": [], "not_found_reason": "   "}) is not None


def test_rebuttals_in_a_wrong_shape_are_blocked() -> None:
    """
    목적: 목록 자리에 다른 것이 와도 «통과되지 않는» 계약을 고정한다.

    목록 대신 문자열을 내놓는 것은 흔한 어긋남이고, 문자열은 비어 있지 않으므로
    「0건이 아니다」로 읽혀 조용히 통과할 수 있다.

    Given: 반증 칸이 문자열인 산출물
    When: 검사한다
    Then: 막힌다
    """
    assert rebuttal.shortfall_reason({"rebuttals": "없음"}) is not None


def test_gate_does_not_judge_the_quality_of_rebuttals() -> None:
    """
    목적: 게이트가 반증의 «질»을 판정하지 «않는» 계약을 고정한다.

    판정하려 들면 게이트가 또 하나의 판단자가 된다 — 설계 §5.5 A 가 훅에서 그대로
    가져온 결정이다. 내용이 부실한지는 나중에 사람이 본다.

    Given: 내용이 빈약한 반증 하나
    When: 검사한다
    Then: 통과한다
    """
    payload = {"rebuttals": [{"title": "", "url": "", "says": ""}]}

    assert rebuttal.shortfall_reason(payload) is None


def test_malformed_payload_does_not_crash_the_gate() -> None:
    """
    목적: 모양이 어긋난 입력에 게이트가 «죽지 않는» 계약을 고정한다.

    검사기가 죽어서 파이프라인을 멈추게 해서는 안 된다.

    Given: 빈 매핑
    When: 검사한다
    Then: 예외 없이 사유가 나온다
    """
    assert rebuttal.shortfall_reason({}) is not None

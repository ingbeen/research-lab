"""메커니즘 산출물이 3·9번 칸의 «자리»를 채웠는지 보는 계약을 고정한다.

3번 칸(왜 우위가 있을 수 있나)과 9번 칸(왜 사라졌을 수 있나)은 한 쌍이다 —
「우위가 있었나」와 「그 우위가 아직 살아 있나」이기 때문이다. 자유 서술로 두면
**찾은 것만 쓰고 안 찾은 것은 언급조차 안 한다.** 그래서 설계가 각 칸에 적어 둔 갈래를
하나씩 자리로 요구한다.

[중요] **「해당 없음」이라 적을 길을 남긴다.** 그 길이 없으면 게이트가 에이전트에게
**없는 사실을 채워 넣을 압력**을 만든다 — 반증 게이트가 「0건 = 실패」를 고르지 않은 것과
같은 축이다.

[중요] 설명의 «질»은 판정하지 않는다. 판정하려 들면 게이트가 또 하나의 판단자가 된다.
"""

from typing import Any

from research_lab.gate import mechanism


def _filled(**overrides: Any) -> dict[str, Any]:
    """게이트를 통과하는 산출물."""
    payload: dict[str, Any] = {
        "claim": "소형주는 1월에 더 오른다. 12월 말에 사서 1월 말에 판다",
        "edge": {
            "risk_premium": "해당 없음 — 위험을 더 지는 구조가 아니다",
            "behavioral": "연말 절세 매도 뒤 되사기와 기관 윈도드레싱이 1월 초 매수를 만든다",
            "structural": "1월에 신규 자금이 유입되는 연금·펀드 구조가 있다",
        },
        "decay": {
            "post_publication": "1976년 논문으로 널리 알려져 선반영됐을 수 있다",
            "regulatory": "한국은 양도세 구조가 달라 절세 매도 유인 자체가 작다",
            "market_structure": "패시브 비중이 커지며 연말 개별 매도 압력이 옅어졌다",
        },
        "queries": ["january effect decay", "1월 효과 소멸"],
        "sources": [{"title": "원논문", "url": "https://example.com/jan"}],
        "unverified": ["국내 절세 매도 유인의 실제 크기"],
    }
    payload.update(overrides)
    return payload


def test_a_filled_payload_passes() -> None:
    """
    목적: 자리가 다 찬 산출물이 통과하는 계약을 고정한다.

    Given: 3·9번 칸의 자리가 모두 채워진 산출물
    When: 검사한다
    Then: 사유가 없다
    """
    assert mechanism.shortfall_reason(_filled()) is None


def test_not_applicable_is_a_pass() -> None:
    """
    목적: [중요] 「해당 없음」으로 채운 자리가 통과하는 계약을 고정한다.

    그 길이 없으면 게이트가 **없는 사실을 채워 넣을 압력**을 만든다. 이 저장소에서
    유일하게 남는 위조 위험이 「없는 출처」이고, 게이트가 그 압력을 만들면 안 된다.

    Given: 세 자리가 모두 「해당 없음」과 그 이유인 산출물
    When: 검사한다
    Then: 통과한다
    """
    payload = _filled(
        edge={
            "risk_premium": "해당 없음 — 위험 보상 구조가 아니다",
            "behavioral": "해당 없음 — 알려진 편향과 연결되지 않는다",
            "structural": "해당 없음 — 제도나 미시구조에서 나오는 것이 아니다",
        }
    )

    assert mechanism.shortfall_reason(payload) is None


def test_a_missing_edge_slot_is_a_shortfall() -> None:
    """
    목적: 3번 칸의 한 자리가 비면 막는 계약을 고정한다.

    Given: 행동 편향 자리가 빈 산출물
    When: 검사한다
    Then: 그 자리를 가리키는 사유가 돌아온다
    """
    payload = _filled()
    payload["edge"]["behavioral"] = "   "

    reason = mechanism.shortfall_reason(payload)

    assert reason is not None
    assert "behavioral" in reason


def test_a_missing_decay_slot_is_a_shortfall() -> None:
    """
    목적: 9번 칸의 한 자리가 비면 막는 계약을 고정한다.

    9번 칸이 통째로 빠지는 것이 이 파이프라인에서 가장 흔한 누락이다 —
    찬성 근거를 모으다 보면 「아직 되나」를 안 묻게 된다.

    Given: 발표 후 소멸 자리가 빈 산출물
    When: 검사한다
    Then: 그 자리를 가리키는 사유가 돌아온다
    """
    payload = _filled()
    payload["decay"]["post_publication"] = ""

    reason = mechanism.shortfall_reason(payload)

    assert reason is not None
    assert "post_publication" in reason


def test_a_missing_section_is_a_shortfall() -> None:
    """
    목적: 절이 통째로 없거나 절이 아니면 막는 계약을 고정한다.

    목록이나 문자열이 와도 여기서 막는다 — 그런 값은 «비어 있지 않아서»
    「적혀 있다」로 읽혀 조용히 통과할 수 있다.

    Given: 9번 칸이 문자열인 산출물
    When: 검사한다
    Then: 사유가 돌아온다
    """
    reason = mechanism.shortfall_reason(_filled(decay="아직 유효하다"))

    assert reason is not None
    assert "decay" in reason


def test_any_shape_is_survivable() -> None:
    """
    목적: [중요] 어떤 입력에도 «예외를 올리지 않는» 계약을 고정한다 (계층 계약 §5).

    에이전트가 낸 값이라 목록 자리에 문자열이 오는 일이 흔한데, 검사기가 죽으면
    고칠 수 있었던 것까지 그 회차를 끝낸다.

    Given: 모양이 어긋난 값들
    When: 검사한다
    Then: 예외 없이 사유가 돌아온다
    """
    for broken in ({}, {"edge": None, "decay": 3}, {"edge": [], "decay": []}):
        assert mechanism.shortfall_reason(broken) is not None

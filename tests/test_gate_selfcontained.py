"""근거 문서가 «저장소 밖에서도 읽히는지»를 보는 계약을 고정한다.

이 저장소의 1순위 제약은 **「dossier 는 다른 문서를 한 장도 열지 않고 판단할 수 있어야
한다」**이다. 그런데 그 제약을 지키는 장치가 러너의 «고정 문구»에만 걸려 있었고,
**에이전트가 쓴 산문은 아무도 안 봤다.**

[실측 2026-09-15] 실제로 나간 근거 문서의 **2번 칸(판정)**이 「이 스킬이 예로 든 …과
사실상 같은 모양이다」로 판정 근거를 댔다. 받는 쪽에는 그 스킬이 없으므로
**링크가 깨지는 게 아니라 판정 이유가 통째로 해석 불가**가 된다.

[중요] 이 게이트는 **사전 매칭만** 한다. 「자립적으로 잘 썼나」를 재지 않는다 —
재려고 들면 게이트가 또 하나의 판단자가 된다. 보는 것은 「가리키는 말이 적혔나」뿐이다.

[중요] **오탐의 대가가 누락의 대가보다 훨씬 작다.** 걸리면 그 회차가 미완성이 되고
다음 회차가 다시 쓴다. 놓치면 **판단 불가능한 문서가 저장소 밖으로 나가고 되돌릴 수 없다.**
"""

from typing import Any

from research_lab.gate import selfcontained


def test_a_clean_document_passes() -> None:
    """
    목적: 가리키는 말이 없는 문서가 통과하는 계약을 고정한다.

    Given: 기준 자체를 그 자리에 적은 칸들
    When: 검사한다
    Then: 사유가 없다
    """
    sections = {
        "2. 판정": "보류 — 표본이 20건이라 시기를 둘로 쪼개면 칸당 10건이다. 칸당 10건 미만이면 우연과 구별되지 않는다",
        "4. 데이터 실현가능성": "일봉만 필요하다. 국내 ETF 일봉은 pykrx 로 받을 수 있다",
    }

    assert selfcontained.shortfall_reason(sections) is None


def test_pointing_at_a_document_that_does_not_travel_is_a_shortfall() -> None:
    """
    목적: 함께 가지 않는 문서를 가리키면 막는 계약을 고정한다.

    Given: 판정 칸이 「이 스킬이 예로 든」으로 근거를 댄 문서
    When: 검사한다
    Then: 걸린 표현과 그 칸을 «둘 다» 가리키는 사유가 돌아온다
    """
    sections = {"2. 판정": "보류 — 이는 이 스킬이 예로 든 「신호가 연 1회」와 사실상 같은 모양이다"}

    reason = selfcontained.shortfall_reason(sections)

    assert reason is not None
    assert "이 스킬" in reason
    assert "2. 판정" in reason


def test_the_reason_says_what_to_write_instead() -> None:
    """
    목적: 「거부됨」만 돌려주지 않는 계약을 고정한다.

    무엇이 왜 걸렸는지가 함께 돌아와야 다음 회차가 같은 문장을 다시 쓰지 않는다.
    이 저장소는 「모델용 맥락을 안 담으면 같은 편집을 재시도한다」를 이미 겪었다.

    Given: 가리키는 말이 든 문서
    When: 검사한다
    Then: 대신 무엇을 적어야 하는지가 사유에 들어 있다
    """
    reason = selfcontained.shortfall_reason({"9. 왜 사라졌을 수 있나": "이 스킬에서 준 국내 반증을 보라"})

    assert reason is not None
    assert "기준 자체" in reason


def test_every_seeded_term_is_caught() -> None:
    """
    목적: 씨앗 사전의 표현이 «하나도 빠짐없이» 걸리는 계약을 고정한다.

    사전에 넣어 두고 안 보는 항목이 생기면 **그 표현만 조용히 통과한다** —
    이 계획서가 고치고 있는 고장과 정확히 같은 모양이다.

    Given: 사전의 각 표현이 하나씩 든 칸
    When: 검사한다
    Then: 그때마다 막힌다
    """
    for term in selfcontained.POINTER_TERMS:
        reason = selfcontained.shortfall_reason({"2. 판정": f"보류 — {term} 를 보라"})

        assert reason is not None, term


def test_terms_are_reported_in_a_fixed_order() -> None:
    """
    목적: 걸린 표현을 «정의된 순서»로 돌려주는 계약을 고정한다.

    회차마다 순서가 달라지면 로그를 대조할 수 없다. 검색어 게이트·비용어 스캐너가
    같은 이유로 정의된 순서를 쓴다.

    Given: 사전의 표현 둘이 정의 순서와 «반대로» 적힌 칸
    When: 걸린 표현을 센다
    Then: 정의된 순서로 돌아온다
    """
    first, second = selfcontained.POINTER_TERMS[0], selfcontained.POINTER_TERMS[1]

    found = selfcontained.pointers_in(f"{second} 그리고 {first}")

    assert found == (first, second)


def test_no_input_raises() -> None:
    """
    목적: 어떤 입력에도 예외를 올리지 않는 계약을 고정한다.

    계층 계약 §5 — 에이전트가 낸 값이라 목록 자리에 문자열이 오는 일이 흔한데,
    검사기가 죽으면 고칠 수 있었던 것까지 그 회차를 끝낸다.

    Given: 모양이 어긋난 입력들
    When: 검사한다
    Then: 터지지 않는다
    """
    broken: list[Any] = [{}, {"2. 판정": None}, {"2. 판정": 12}, {"2. 판정": ["이 스킬"]}, {None: "이 스킬"}]

    for payload in broken:
        selfcontained.shortfall_reason(payload)


def test_a_null_section_is_not_the_text_none() -> None:
    """
    목적: `null` 인 칸을 `"None"` 이라는 본문으로 읽지 않는 계약을 고정한다.

    §12 가 못박은 것과 같은 자리다 — `str(None)` 은 내용이 있는 문자열이라
    「비었나」를 보는 가드를 전부 통과한다.

    Given: 본문이 `null` 인 칸
    When: 걸린 표현을 센다
    Then: 아무것도 안 걸린다
    """
    assert selfcontained.pointers_in(None) == ()


def test_legitimate_prose_is_not_caught() -> None:
    """
    목적: [중요] 멀쩡한 문장이 걸리지 «않는» 계약을 고정한다.

    [탈락 2026-09-15] 사전에 `§` · `원칙 ` · `앞서 말한` · `위에서 본` 을 넣었다가 뺐다.
    아래 셋이 전부 걸렸고 **셋 다 자립을 깨지 않는 문장**이었다. 특히 `§355` 는
    **분할 상장 후보의 세법 조항**이라, 이 저장소가 실제로 파는 주제에서 곧바로 터진다.

    [중요] **오탐의 대가를 「다음 회차가 다시 쓴다」로 계산했던 것이 틀렸다.** 품질 실패는
    회차 안에서 재시도되지 않고 사유가 지시문으로 되먹여지지도 않으므로, 계통 오탐은
    매 회차 반복되고 **세 번이면 그 후보가 원장에서 걷힌다.**

    Given: 밖을 가리키지 않는 문장들
    When: 가리키는 말을 센다
    Then: 하나도 안 걸린다
    """
    for text in (
        "미국 세법 §355 상 적격 분할이면 비과세다",
        "회계 원칙 (GAAP) 상 인식 시점이 다르다",
        "앞서 말한 2024년 개정 시행령이 자사주 배정을 금지했다",
        "위에서 본 표의 두 번째 줄이 그 경우다",
        "이 문서는 분할 상장 후보를 다룬다",
    ):
        assert selfcontained.pointers_in(text) == (), text


def test_every_offending_section_is_reported_at_once() -> None:
    """
    목적: 걸린 자리를 «전부» 한 번에 돌려주는 계약을 고정한다.

    한 번에 하나씩 알리면 걸린 자리 수만큼 회차가 들고, 세 번이면 후보가 걷힌다.
    모아 돌려주는 비용은 0 이다.

    Given: 두 칸이 각각 다른 표현으로 밖을 가리키는 문서
    When: 검사한다
    Then: 두 칸이 «둘 다» 사유에 들어 있다
    """
    reason = selfcontained.shortfall_reason({"2. 판정": "이 스킬이 예로 든 것과 같다", "9. 왜 사라졌을 수 있나": "그 저장소의 기록을 보라"})

    assert reason is not None
    assert "2. 판정" in reason
    assert "9. 왜 사라졌을 수 있나" in reason

"""과금 가드가 `ANTHROPIC_API_KEY` 를 보면 시작을 거부하는 계약을 고정한다.

이 프로젝트의 전제는 「남는 구독 토큰만 쓴다」이고, 과금 경로는 셋뿐인데 전부 인증 문제다.
그중 하나가 이 환경변수다 — 설정돼 있으면 구독 인증을 가로채 API 과금으로 넘어간다.

[중요] 가드는 러너의 «가장 앞»에서 돈다. 한 줄이라도 돈 뒤에 막으면 이미 과금된 뒤다.
"""

import pytest

from research_lab.agent import billing_guard


def test_configured_key_is_rejected() -> None:
    """
    목적: 키가 있으면 시작조차 못 하게 하는 계약을 고정한다.

    Given: `ANTHROPIC_API_KEY` 가 들어 있는 환경
    When: 과금 가드를 부른다
    Then: 예외가 오른다
    """
    with pytest.raises(billing_guard.BillingGuardError):
        billing_guard.assert_subscription_only({"ANTHROPIC_API_KEY": "sk-ant-api03-예시값"})


def test_empty_string_key_is_also_rejected() -> None:
    """
    목적: 「설정했는데 비어 있다」가 통과하지 않는 계약을 고정한다.

    존재 여부와 값의 유무를 구별하지 않으면, 키를 지우려다 빈 값으로 덮은 상태가 조용히 통과한다.
    그 상태의 «의도»를 기계가 알 수 없으므로 안전한 쪽으로 떨어뜨린다 —
    거부는 시작 시점에 시끄럽게 실패하지만, 통과는 조용히 과금된다.

    Given: `ANTHROPIC_API_KEY` 가 빈 문자열인 환경
    When: 과금 가드를 부른다
    Then: 예외가 오른다
    """
    with pytest.raises(billing_guard.BillingGuardError):
        billing_guard.assert_subscription_only({"ANTHROPIC_API_KEY": ""})


def test_absent_key_passes() -> None:
    """
    목적: 정상 환경에서 가드가 길을 막지 않는 계약을 고정한다.

    Given: `ANTHROPIC_API_KEY` 가 없고 구독 토큰만 있는 환경
    When: 과금 가드를 부른다
    Then: 아무 일도 일어나지 않는다
    """
    billing_guard.assert_subscription_only({"CLAUDE_CODE_OAUTH_TOKEN": "토큰-예시값"})


def test_error_message_names_the_variable() -> None:
    """
    목적: 사람이 읽고 조치할 수 있는 메시지를 내는 계약을 고정한다.

    무인 실행에서 이 예외는 로그에만 남는다. 변수 이름이 메시지에 없으면
    나중에 로그를 보고도 무엇을 지워야 하는지 알 수 없다.

    Given: 키가 설정된 환경
    When: 가드가 예외를 올린다
    Then: 메시지에 변수 이름이 들어 있다
    """
    with pytest.raises(billing_guard.BillingGuardError) as raised:
        billing_guard.assert_subscription_only({"ANTHROPIC_API_KEY": "sk-ant-api03-예시값"})

    assert "ANTHROPIC_API_KEY" in str(raised.value)

"""멈춘 단계부터 이어받는 계약을 고정한다.

밤은 「한 세션을 길게 돌리고 resume 에 목숨을 거는」 구조가 아니다. 단계마다 짧게 부르고
**산출물을 파일로 인계**하므로, 어디서 끊겨도 그 단계부터 다시 시작한다.
`--resume` 은 보험이지 뼈대가 아니다.

[중요] 끝난 단계를 다시 도는 것은 「안전한 재시도」가 아니라 «토큰 낭비»다.
밤 예산이 유한하므로 이어받기가 실제로 건너뛰어야 한다.
"""

import pytest

from research_lab.runner import steps


def test_first_night_starts_at_the_first_step() -> None:
    """
    목적: 상태가 없으면 처음부터 시작하는 계약을 고정한다.

    Given: 아직 아무 단계도 끝내지 않은 상태
    When: 다음에 할 단계를 묻는다
    Then: 첫 단계가 돌아온다
    """
    assert steps.next_step(completed=[]) == steps.STEPS[0]


def test_resumes_after_the_completed_step() -> None:
    """
    목적: 끝난 단계를 건너뛰고 그 «다음»부터 이어받는 계약을 고정한다.

    Given: 첫 단계만 끝난 상태
    When: 다음에 할 단계를 묻는다
    Then: 두 번째 단계가 돌아온다
    """
    assert steps.next_step(completed=[steps.STEPS[0]]) == steps.STEPS[1]


def test_returns_none_when_every_step_is_done() -> None:
    """
    목적: 다 끝난 밤을 「할 일 없음」으로 다루는 계약을 고정한다.

    None 이 아니라 마지막 단계를 돌려주면 **완성된 산출물 위에 다시 쓴다.**

    Given: 모든 단계가 끝난 상태
    When: 다음에 할 단계를 묻는다
    Then: None 이 돌아온다
    """
    assert steps.next_step(completed=list(steps.STEPS)) is None


def test_completed_order_does_not_matter() -> None:
    """
    목적: 기록 순서가 아니라 «정의된 순서»로 판정하는 계약을 고정한다.

    끝난 단계 목록은 실패·재시도로 순서가 뒤섞일 수 있다. 그 목록의 마지막 원소를 보고
    다음을 정하면 **엉뚱한 단계로 건너뛴다.**

    Given: 끝난 단계가 정의된 순서와 다르게 기록된 상태
    When: 다음에 할 단계를 묻는다
    Then: 정의된 순서 기준으로 아직 안 한 첫 단계가 돌아온다
    """
    assert steps.next_step(completed=list(reversed(steps.STEPS))) is None


def test_unknown_step_in_state_is_rejected() -> None:
    """
    목적: 모르는 단계 이름이 «조용히» 무시되지 않는 계약을 고정한다.

    단계 이름을 바꾸면 예전 상태 파일에 옛 이름이 남는다. 그걸 무시하면
    **끝난 단계를 처음부터 다시 돈다** — 예외도 없이 예산만 두 배로 쓴다.

    Given: 정의에 없는 단계 이름이 든 상태
    When: 다음에 할 단계를 묻는다
    Then: 예외가 오른다
    """
    with pytest.raises(steps.UnknownStepError):
        steps.next_step(completed=["옛날에_있던_단계"])


def test_step_names_are_stable_identifiers() -> None:
    """
    목적: 단계 이름이 상태 파일에 남는 «식별자»임을 고정한다.

    이 이름은 파일에 기록돼 다음 밤이 읽는다. 표시용 문구가 아니므로 영문 식별자로 두고,
    바꿀 때는 예전 상태를 어떻게 다룰지 함께 정해야 한다.

    Given: 정의된 단계 목록
    When: 이름을 본다
    Then: 중복이 없고 비어 있지 않다
    """
    assert len(set(steps.STEPS)) == len(steps.STEPS)
    assert all(name.isascii() and name for name in steps.STEPS)

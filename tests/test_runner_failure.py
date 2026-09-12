"""실패를 셋으로 가르는 계약과, 모르는 실패가 안전한 쪽으로 떨어지는 계약을 고정한다.

셋으로 가르는 이유는 **대응이 다르기 때문**이다.

- **한도 소진** — 재시도해봐야 또 막힌다. 깨끗이 끝내고 다음 밤이 이어받는다
- **인증·과금 거부** — 재시도가 의미 없다. 사람에게 알린다. 다른 갈래와 섞이면
  **며칠 조용히 안 도는 상태**가 된다
- **그 외** — 상한까지 재시도한다

[중요] 한도 소진과 인증 거부의 «실제 메시지 모양»은 아직 모른다(일부러 만들 수 없다).
그래서 이 테스트는 **특정 문구를 사실로 박지 않는다.** 대신 분류표가 판정을 이끈다는 것과,
**표에 없는 실패가 「그 외」로 떨어지고 원문이 보존된다**는 것을 고정한다.
처음 한도에 부딪히는 날 그 원문이 표를 가르치는 재료가 된다.
"""

import pytest

from research_lab.runner import failures


def test_unknown_failure_falls_through_to_other() -> None:
    """
    목적: 분류에 실패한 실패가 「그 외」로 떨어지는 계약을 고정한다.

    이것이 이 모듈의 핵심이다. 분류기를 완벽하게 만드는 대신 **모를 때 안전한 쪽으로
    떨어지게** 만든다. 안전한 쪽이 「그 외」인 이유는, 상한이 걸린 재시도라 폭주하지 않으면서
    일시적 장애는 실제로 복구되기 때문이다.

    Given: 어느 분류에도 안 걸리는 실패 원문
    When: 분류한다
    Then: 「그 외」로 판정된다
    """
    assert failures.classify("도무지 알 수 없는 실패 원문").kind is failures.FailureKind.OTHER


def test_raw_text_is_preserved_verbatim() -> None:
    """
    목적: 원문이 «통째로» 보존되는 계약을 고정한다.

    원문이 안 남아 있는 것이 사고이지, 미리 모르는 것 자체는 사고가 아니다.
    처음 한도에 부딪히는 날 이 원문이 없으면 그 답을 영영 못 얻는다.

    Given: 여러 줄짜리 실패 원문
    When: 분류한다
    Then: 원문이 자르거나 다듬지 않은 채 그대로 들어 있다
    """
    raw = "첫 줄\n둘째 줄  \n\t셋째 줄"

    assert failures.classify(raw).raw == raw


def test_classifier_never_raises_on_odd_input() -> None:
    """
    목적: 분류기가 죽어서 파이프라인을 멈추지 않는 계약을 고정한다.

    검사기가 판정을 «못 하는 것»과 «실패로 판정하는 것»은 다르다.
    분류기가 예외를 올리면 그 밤이 통째로 끝난다 — 고칠 수 있었던 실패까지 함께.

    Given: 빈 문자열과 제어문자가 섞인 원문
    When: 분류한다
    Then: 예외 없이 판정이 돌아온다
    """
    for raw in ("", "\x00\x1b[31m", " " * 1000):
        assert failures.classify(raw).kind in tuple(failures.FailureKind)


@pytest.mark.parametrize("kind", [failures.FailureKind.LIMIT, failures.FailureKind.AUTH, failures.FailureKind.BUDGET])
def test_table_drives_classification(kind: failures.FailureKind) -> None:
    """
    목적: 판정이 «분류표»에서 나오는 계약을 고정한다.

    문구를 코드 곳곳에 흩으면 새 모양을 배웠을 때 어디를 고쳐야 하는지 알 수 없다.
    표 하나가 SoT 여야 한 줄 추가로 가르칠 수 있다.

    Given: 분류표에 등록된 문구
    When: 그 문구가 든 원문을 분류한다
    Then: 표가 말하는 갈래로 판정된다
    """
    for pattern in failures.patterns_for(kind):
        assert failures.classify(f"앞말 {pattern} 뒷말").kind is kind


def test_limit_is_not_retried() -> None:
    """
    목적: 한도 소진을 재시도하지 않는 계약을 고정한다.

    해봐야 또 막히고, 그 사이 남은 예산을 태운다.

    Given: 한도 소진 갈래
    When: 재시도해도 되는지 묻는다
    Then: 아니다
    """
    assert failures.should_retry(failures.FailureKind.LIMIT) is False


def test_auth_is_not_retried() -> None:
    """
    목적: 인증·과금 거부를 재시도하지 않는 계약을 고정한다.

    토큰이 만료됐거나 정책이 바뀐 상태에서 재시도는 의미가 없다.
    다른 갈래와 섞이면 **며칠 조용히 안 도는 상태**가 된다.

    Given: 인증·과금 거부 갈래
    When: 재시도해도 되는지 묻는다
    Then: 아니다
    """
    assert failures.should_retry(failures.FailureKind.AUTH) is False


def test_other_is_retried() -> None:
    """
    목적: 「그 외」만 재시도 대상인 계약을 고정한다.

    Given: 그 외 갈래
    When: 재시도해도 되는지 묻는다
    Then: 그렇다
    """
    assert failures.should_retry(failures.FailureKind.OTHER) is True


def test_retry_limit_exists_and_is_finite() -> None:
    """
    목적: 재시도에 «상한»이 있는 계약을 고정한다.

    상한이 없으면 밤새 같은 실패를 반복하며 토큰을 태운다. 아침에 보면
    **예산은 다 썼고 산출물은 0장**이고, 그런 밤은 「실패」가 아니라 「아무 일 없음」처럼 보여
    며칠 지나서야 알아챈다.

    Given: 재시도 상한 설정
    When: 값을 본다
    Then: 유한한 양수다
    """
    assert isinstance(failures.MAX_RETRIES, int)
    assert 0 < failures.MAX_RETRIES < 100


def test_budget_exhaustion_is_not_retried() -> None:
    """
    목적: 러너가 건 예산 상한에 걸린 것을 «다시 부르지 않는» 계약을 고정한다.

    [실측 2026-09-12] `--max-budget-usd 0.01` 로 돌렸더니 「그 외」로 분류돼
    **3번 재시도됐고, 시도마다 상한의 세 배를 태웠다.** 예산 소진은 다시 불러도
    같은 자리에 서므로 재시도가 순 낭비다.

    Given: 예산 소진 갈래
    When: 재시도해도 되는지 묻는다
    Then: 아니다
    """
    assert failures.should_retry(failures.FailureKind.BUDGET) is False


def test_measured_budget_exhaustion_classifies_as_budget() -> None:
    """
    목적: 실측된 예산 소진 응답이 「예산」 갈래로 갈리는 계약을 고정한다.

    Given: 실측된 예산 소진 원문의 특징 필드
    When: 분류한다
    Then: 예산 갈래다
    """
    measured = '{"terminal_reason":"budget_exhausted","subtype":"error_max_budget_usd",'
    measured += '"errors":["Reached maximum budget ($0.01)"],"is_error":true}'

    assert failures.classify(measured).kind is failures.FailureKind.BUDGET


def test_budget_is_not_confused_with_the_subscription_limit() -> None:
    """
    목적: «우리가 건» 상한과 «구독» 한도를 갈라 두는 계약을 고정한다.

    구독 한도는 기다리면 풀리고 그 밤은 정상 종료다. 예산 상한은 **사람이 값을 올리기
    전에는 안 풀린다** — 둘을 같은 갈래로 두면 「정상입니다」로 보고되면서 매일 밤 멈춘다.

    Given: 두 갈래
    When: 견준다
    Then: 서로 다르다
    """
    assert failures.FailureKind.BUDGET is not failures.FailureKind.LIMIT

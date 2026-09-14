"""실패를 셋으로 가른다.

가르는 이유는 **대응이 다르기 때문**이다 — 한도는 기다리고, 인증은 사람을 부르고,
그 외만 재시도한다. 셋을 섞으면 인증 실패가 재시도에 묻혀 **며칠 조용히 안 도는 상태**가 된다.

[중요] 한도 소진과 인증 거부의 «실제 메시지 모양»은 아직 모른다. 일부러 만들 수 없기 때문이다.
그래서 이 모듈의 설계는 「분류기를 완벽하게 만든다」가 아니라 **「모를 때 안전한 쪽으로
떨어지게 만든다」**이다. 처음 한도에 부딪히는 날 로그에 남은 원문이 표를 가르치는 재료가 된다.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class FailureKind(StrEnum):
    """실패의 갈래."""

    LIMIT = "limit"
    AUTH = "auth"
    # 러너가 건 폭주 감지 상한에 걸렸다. **구독 한도(LIMIT)와 다르다** —
    # 이건 우리가 스스로 건 것이라 사람이 값을 올리기 전에는 몇 번을 불러도 같은 자리에 선다
    BUDGET = "budget"
    # 게이트가 막은 것 — 산출물이 규율에 못 미쳤다. 「그 외」와 갈라 두는 이유는
    # **재시도해도 달라질 게 없어서**다. 기다리면 풀리는 고장이 아니라 결과의 질이 문제다
    QUALITY = "quality"
    OTHER = "other"


@dataclass(frozen=True)
class Failure:
    """분류 결과와 그 근거가 된 원문."""

    kind: FailureKind
    raw: str


# 갈래별 탐지 문구. 소문자로 적고 대소문자를 무시해 맞춘다.
#
# [주의] 아래 문구는 **아직 실측되지 않은 추정**이다. 처음 한도·인증 실패에 부딪히는 날
# 로그의 원문을 보고 이 표에 한 줄을 더하는 것이 이 모듈을 가르치는 방법이다.
# 표에 없는 실패는 「그 외」로 떨어지므로, 추정이 틀려도 파이프라인은 폭주하지 않는다.
#
# 문구는 갈래끼리 겹치지 않게 둔다 — 한쪽의 문구가 다른 쪽 문구의 부분 문자열이면
# 판정이 «먼저 보는 쪽»에 따라 달라져 표를 읽어서는 결과를 알 수 없다
PATTERNS: Final[dict[FailureKind, tuple[str, ...]]] = {
    FailureKind.AUTH: (
        # [실측 2026-09-12] 컨테이너에서 잘못된 토큰으로 부른 응답의 `result` 가
        # "Invalid auth token - Fix external auth token - ..." 였다.
        # **아래 추정 문구 중 어느 것도 여기 걸리지 않아** 「그 외」로 떨어져 3번 재시도됐다 —
        # 설계가 「②를 ①·③과 섞으면 며칠 조용히 안 도는 상태가 된다」고 경고한 그 모양이다.
        # 처음 부딪힌 실패가 표를 가르친 첫 사례다
        "invalid auth token",
        "fix external auth token",
        # 아래는 아직 [미검증] 추정이다
        "invalid api key",
        "authentication_error",
        "unauthorized",
        "oauth token has expired",
        "credit balance is too low",
    ),
    FailureKind.LIMIT: (
        # [실측 2026-09-12] 실제로 부딪힌 문구다 —
        # "You've hit your session limit - resets 4:40pm (Asia/Seoul)"
        # 아래 추정 문구 중 어느 것도 안 걸려 「그 외」로 떨어졌고, 30초씩 쉬며 두 번 더 불렀다.
        # 다행히 거부는 비용 0 이었지만, 설계가 「한도는 재시도하지 않는다 — 해봐야 또 막힌다」고
        # 정한 바로 그 자리를 지나쳤다. **일부러 만들 수 없다던 모양을 이렇게 얻었다**
        "hit your session limit",
        "session limit",
        # 아래는 아직 [미검증] 추정이다
        "usage limit reached",
        "rate_limit_error",
        "weekly limit",
        "5-hour limit",
    ),
    FailureKind.BUDGET: (
        # [실측 2026-09-12] `--max-budget-usd 0.01` 로 돌려 받은 응답의 필드다.
        # 처음에는 「그 외」로 떨어져 **3번 재시도됐고, 시도마다 상한의 세 배를 태웠다** —
        # 예산 소진은 다시 불러도 같은 결과라 재시도가 순 낭비다
        "error_max_budget_usd",
        "budget_exhausted",
        "reached maximum budget",
    ),
}

# 「그 외」를 몇 번까지 다시 해보나.
#
# [중요] 상한이 없으면 한 회차 내내 같은 실패를 반복하며 토큰을 태운다. 나중에 보면 예산은 다 썼고
# 산출물은 0장인데, 그런 회차는 「실패」가 아니라 「아무 일 없음」처럼 보여 며칠 지나서야 알아챈다
MAX_RETRIES: Final = 3

# 표를 보는 순서. **인증을 먼저 본다.**
#
# 한 원문에 두 갈래의 문구가 같이 들어 있을 때 무엇으로 판정할지의 문제다.
# 인증을 한도로 잘못 보면 「기다리면 풀린다」로 처리돼 **며칠 조용히 안 도는 상태**가 되지만,
# 한도를 인증으로 잘못 보면 사람을 한 번 헛부를 뿐이다. 손해가 작은 쪽으로 기운다
LOOKUP_ORDER: Final = (FailureKind.AUTH, FailureKind.BUDGET, FailureKind.LIMIT)


def patterns_for(kind: FailureKind) -> tuple[str, ...]:
    """그 갈래의 탐지 문구를 돌려준다.

    Args:
        kind: 실패의 갈래

    Returns:
        탐지 문구들. 「그 외」는 표가 없으므로 빈 튜플
    """
    return PATTERNS.get(kind, ())


def classify(raw: str) -> Failure:
    """실패 원문을 갈래로 나눈다.

    [중요] **어떤 입력에도 예외를 올리지 않는다.** 검사기가 판정을 «못 하는 것»과
    «실패로 판정하는 것»은 다르다. 분류기가 죽으면 고칠 수 있었던 실패까지 함께
    그 회차를 끝낸다.

    Args:
        raw: 실패 원문. 비어 있거나 제어문자가 섞여 있어도 된다

    Returns:
        갈래와 **자르거나 다듬지 않은 원문**. 원문이 안 남으면 처음 한도에 부딪히는 날
        그 답을 영영 못 얻는다
    """
    haystack = raw.casefold()
    for kind in LOOKUP_ORDER:
        if any(pattern in haystack for pattern in PATTERNS[kind]):
            return Failure(kind=kind, raw=raw)
    return Failure(kind=FailureKind.OTHER, raw=raw)


def should_retry(kind: FailureKind) -> bool:
    """그 갈래를 다시 해봐도 되는지 답한다.

    Args:
        kind: 실패의 갈래

    Returns:
        「그 외」만 True. 한도는 해봐야 또 막히고, 인증은 사람이 고치기 전엔 안 풀린다
    """
    return kind is FailureKind.OTHER

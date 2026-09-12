"""구독 토큰 말고 다른 것으로 돌지 못하게 막는다.

이 프로젝트의 전제는 「남는 구독 토큰만 쓴다」이고, 과금 경로는 셋뿐인데 **전부 인증 문제**다.
그중 코드로 막을 수 있는 것이 이 환경변수다 — 설정돼 있으면 구독 인증을 가로채
API 과금으로 넘어간다.

[중요] `--max-budget-usd` 는 이 일을 하지 못한다. 그 플래그는 **API 달러 지출의 상한**이고
구독 인증에는 달러 지출 자체가 없다. 과금을 막는 레버는 **인증**이지 예산이 아니다.
"""

from collections.abc import Mapping
from typing import Final

# 있으면 구독 인증을 가로채는 변수
FORBIDDEN_ENV_VAR: Final = "ANTHROPIC_API_KEY"


class BillingGuardError(RuntimeError):
    """구독 외 과금 경로가 열려 있을 때."""


def assert_subscription_only(env: Mapping[str, str]) -> None:
    """구독 인증만 쓸 수 있는 환경인지 확인한다.

    러너의 **가장 앞**에서 부른다. 한 줄이라도 돈 뒤에 막으면 이미 과금된 뒤다.

    Args:
        env: 검사할 환경변수. `os.environ` 을 직접 읽지 않고 받는 이유는
            컨테이너에 넘길 환경을 «넘기기 전에» 검사할 수 있어야 하기 때문이다

    Raises:
        BillingGuardError: 금지된 변수가 있을 때. **빈 문자열도 거부한다** —
            존재와 값의 유무를 구별하지 않으면 「지우려다 빈 값으로 덮은」 상태가
            조용히 통과한다. 그 상태의 의도를 기계는 알 수 없으므로 안전한 쪽으로 떨어뜨린다.
            거부는 시작 시점에 시끄럽게 실패하지만, 통과는 조용히 과금된다
    """
    if FORBIDDEN_ENV_VAR not in env:
        return

    raise BillingGuardError(
        f"{FORBIDDEN_ENV_VAR} 가 설정돼 있어 시작할 수 없습니다. "
        f"이 프로젝트는 구독 토큰(CLAUDE_CODE_OAUTH_TOKEN)만 씁니다. "
        f"그 변수가 있으면 구독 대신 API 로 과금됩니다. "
        f"값이 비어 있어도 마찬가지로 거부합니다 — 지우려면 변수 자체를 unset 하세요."
    )

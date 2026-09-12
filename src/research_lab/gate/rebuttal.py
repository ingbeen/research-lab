"""반증 산출물이 규율을 지켰는지 검사한다 — «행위»를 보고 «결과»를 보지 않는다.

두 규정이 부딪히는 자리였다. 로드맵은 「반증 칸 비면 실패」라 적었고, 설계의 게이트 원형은
「절의 존재만 본다 · 빈 경우에도 「없음」이라 적을 길이 남아야 한다」고 적었다.

**행위를 검사하는 쪽으로 정했다.** 반증 칸이 있으면 통과하고, 0건이면 「왜 못 찾았나」를
요구한다. 반증 «검색어»의 하한은 검색어 게이트가 따로 본다.

[중요] 결과가 0건인 것을 실패로 만드는 순간 에이전트에게 **반증을 「지어낼」 압력**이 생긴다.
이 저장소는 백테스트를 하지 않아 부풀릴 점수가 없고, 그래서 **유일하게 남는 위조 위험이
「없는 출처」**다. 게이트가 그 압력을 만들면 안 된다. 반증 0건은 수집의 「찬성 근거 0건」과
같은 «실체 없음»이라는 정상 결과다.

[중요] 반증의 «질»은 판정하지 않는다. 판정하려 들면 게이트가 또 하나의 판단자가 된다.
"""

from collections.abc import Mapping
from typing import Any, Final

KEY_REBUTTALS: Final = "rebuttals"
KEY_NOT_FOUND_REASON: Final = "not_found_reason"


def shortfall_reason(payload: Mapping[str, Any]) -> str | None:
    """반증 규율이 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    사유를 «문자열로» 돌리는 것은 실패 원문에 그대로 실어 보내기 위해서다.
    「게이트에 걸렸다」만 남으면 다음 밤이 무엇을 고쳐야 하는지 모른다.

    Args:
        payload: 반증 단계가 낸 산출물. 모양이 어긋나 있어도 된다

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    rebuttals: Any = payload.get(KEY_REBUTTALS)

    if not isinstance(rebuttals, list):
        # 칸이 아예 없다는 것은 그 단계가 **묻지도 않았다**는 뜻이다.
        # 목록이 아닌 값(문자열 등)은 비어 있지 않으므로 「0건이 아니다」로 읽혀
        # 조용히 통과할 수 있어 여기서 함께 막는다
        return (
            f"반증 칸(`{KEY_REBUTTALS}`)이 없거나 목록이 아닙니다. "
            f"반증을 못 찾았어도 빈 목록으로 두고 `{KEY_NOT_FOUND_REASON}` 에 "
            f"«무엇을 어떻게 찾았는데 왜 없었는지»를 적으세요 — 「없음」도 정상 결과입니다."
        )

    if rebuttals:
        return None

    if not str(payload.get(KEY_NOT_FOUND_REASON, "")).strip():
        return (
            f"반증이 0건인데 «왜 못 찾았는지»(`{KEY_NOT_FOUND_REASON}`)가 비어 있습니다. "
            f"0건 자체는 정상 결과이지만, 적어 두지 않으면 "
            f"「찾아봤는데 없었다」와 「안 찾았다」가 구별되지 않습니다."
        )

    return None

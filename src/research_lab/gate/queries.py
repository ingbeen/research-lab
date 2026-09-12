"""검색어를 충분히 갈아 끼웠는지 검사한다.

**한 번 검색하고 멈추면 처음 걸린 것에 갇힌다.** 한국어와 영어는 결과 집합이 거의 겹치지 않고,
첫 검색이 알려준 «진짜 용어»로 다시 던져야 제대로 된 것이 나온다.
검색어를 하나만 던진 밤은 **조사한 것처럼 보이지만 조사가 아니다.**

[중요] 이 검사가 없으면 그런 밤도 「완주」로 끝난다. 루트 `CLAUDE.md` 가
「프롬프트로 지시한 규율은 형식적으로만 지켜진다 — 러너가 검사한다」고 못박은 자리다.
"""

from collections.abc import Sequence
from typing import Final

# 최소 검색어 수. 루트 `CLAUDE.md` 「리서치의 규율」이 정한 값이다.
#
# 셋인 이유는 「한국어 · 영어 · 첫 검색이 알려준 진짜 용어」가 최소 한 바퀴이기 때문이다.
# 둘이면 언어만 바꾸고 용어는 그대로일 수 있다
MIN_QUERIES: Final = 3


def shortfall_reason(queries: Sequence[str]) -> str | None:
    """검색어가 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    사유를 «문자열로» 돌리는 것은 실패 원문에 그대로 실어 보내기 위해서다.
    「게이트에 걸렸다」만 남으면 다음 밤이 무엇을 고쳐야 하는지 모른다 —
    게이트가 미완성을 돌려줄 때는 **무엇이 왜 모자랐는지를 함께** 돌려줘야 한다.

    Args:
        queries: 그 단계가 실제로 던진 검색어들

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    # 같은 말을 여러 번 적은 것은 «갈아 끼운 것»이 아니다.
    # 앞뒤 공백과 대소문자만 다른 것도 같은 검색어로 본다
    distinct = {query.strip().casefold() for query in queries if query.strip()}

    if len(distinct) >= MIN_QUERIES:
        return None

    return (
        f"검색어가 {len(distinct)}개뿐입니다 (최소 {MIN_QUERIES}개). "
        f"한 번 검색하고 멈추면 처음 걸린 것에 갇힙니다 — "
        f"한국어와 영어를 모두 돌리고, 첫 검색이 알려준 용어로 다시 던지세요. "
        f"던진 것: {sorted(distinct)}"
    )

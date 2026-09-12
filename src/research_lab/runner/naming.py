"""후보 이름을 파일명으로 바꾼다.

경로를 만드는 곳은 이 모듈 하나다. 에이전트가 낸 한 줄 주장이 그대로 파일명이 되므로
사람이 고른 이름과 달리 무엇이 들어올지 모른다.
"""

from typing import Final

# 파일명이 쓸 수 있는 최대 바이트.
#
# [중요] 문자 수가 아니라 «바이트»다. 파일시스템의 한도가 바이트이고, 한글은 UTF-8 에서
# 한 자가 3바이트라 글자 수로 자르면 한글 이름만 한도를 넘겨 저장이 실패한다.
# 흔한 한도인 255 에서 넉넉히 물러선 값이다 — 앞에 날짜가, 뒤에 `_찬성근거.json` 같은
# 꼬리가 더 붙기 때문이다
MAX_SLUG_BYTES: Final = 120

# 파일명에 남기는 문자. 나머지는 아래 규칙에 따라 밑줄로 바꾸거나 떨어뜨린다.
# 하이픈을 남기는 이유는 미국 후보가 `Post-Earnings ...` 처럼 들어오기 때문이다
KEPT_PUNCTUATION: Final = "-_"

# 밑줄로 «바꾸는» 문자. 떨어뜨리면 단어가 붙어 버리는 것들이다.
# 마침표가 여기 있는 이유는 둘이다 — `3.5배` 가 `35배` 로 바뀌면 뜻이 달라지고,
# 떨어뜨리기만 하면 `../..` 이 붙어 상위 경로 조각이 남는다
REPLACED_WITH_SEPARATOR: Final = "."

SEPARATOR: Final = "_"


class UnusableNameError(ValueError):
    """남는 문자가 없어 파일명을 만들 수 없을 때."""


def slug(claim: str) -> str:
    """후보의 한 줄 주장에서 파일명을 만든다.

    Args:
        claim: 에이전트가 낸 후보 문구

    Returns:
        경로 구분자가 없고 공백이 없는 파일명 조각

    Raises:
        UnusableNameError: 남는 문자가 하나도 없을 때. 빈 문자열을 돌려주면 산출물이
            확장자만 가진 파일로 저장되고 다음 후보가 그것을 덮어쓴다
    """
    kept: list[str] = []
    for char in claim:
        if char.isalnum() or char in KEPT_PUNCTUATION:
            kept.append(char)
        elif char.isspace() or char in REPLACED_WITH_SEPARATOR:
            kept.append(SEPARATOR)
        # 그 밖(따옴표·괄호·경로 구분자 등)은 떨어뜨린다

    made = _collapse(kept)
    made = _truncate_on_character_boundary(made)
    # 자르고 나면 끝에 구분자가 남을 수 있다
    made = made.strip(SEPARATOR)

    if not made:
        raise UnusableNameError(f"파일명으로 쓸 수 있는 문자가 없습니다: {claim!r}")

    return made


def _collapse(chars: list[str]) -> str:
    """이어진 구분자를 하나로 줄이고 앞뒤의 것을 떼어 낸다.

    문자를 떨어뜨리고 나면 구분자가 여러 개 남는다. 그대로 두면 읽기 어렵고,
    **같은 후보가 표기 차이만으로 다른 파일명을 얻는다.**
    """
    collapsed: list[str] = []
    for char in chars:
        if char == SEPARATOR and (not collapsed or collapsed[-1] == SEPARATOR):
            continue
        collapsed.append(char)
    return "".join(collapsed).strip(SEPARATOR)


def _truncate_on_character_boundary(made: str) -> str:
    """바이트 한도에 맞춰 자르되 문자 중간에서 자르지 않는다.

    바이트로 잘라 놓고 디코딩하면 깨진 바이트가 남아 파일명이 이상해지거나 저장이 실패한다.
    그래서 자를 위치를 «문자» 단위로 뒤에서부터 줄인다.
    """
    if len(made.encode("utf-8")) <= MAX_SLUG_BYTES:
        return made

    cut = made
    while cut and len(cut.encode("utf-8")) > MAX_SLUG_BYTES:
        cut = cut[:-1]
    return cut

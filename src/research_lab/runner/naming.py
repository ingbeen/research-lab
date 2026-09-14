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

# 짧은 식별자가 쓸 수 있는 최대 길이.
#
# 폴더명을 짧게 만드는 것이 이 식별자의 존재 이유이므로 한 줄 주장의 한도보다 훨씬 짧다.
# 여기서 잘려도 뜻이 안 상하는 이유는 식별자가 «이름»이지 «설명»이 아니기 때문이다
MAX_IDENTIFIER_LENGTH: Final = 40

IDENTIFIER_SEPARATOR: Final = "-"

# 식별자에서 구분자로 «바꾸는» 문자. 나머지 비영숫자는 떨어뜨린다.
# 하이픈 자신이 여기 있는 것은 「바꿔도 자기 자신」이라 한 갈래로 처리되기 때문이다 —
# 빠뜨리면 `pead-us` 가 `peadus` 로 뭉개진다
IDENTIFIER_REPLACED: Final = "._-"


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

    made = _collapse(kept, SEPARATOR)
    made = _truncate_on_character_boundary(made)
    # 자르고 나면 끝에 구분자가 남을 수 있다
    made = made.strip(SEPARATOR)

    if not made:
        raise UnusableNameError(f"파일명으로 쓸 수 있는 문자가 없습니다: {claim!r}")

    return made


def identifier_slug(raw: str) -> str:
    """에이전트가 낸 짧은 식별자를 경로에 쓸 수 있는 형태로 다듬는다.

    [중요] 식별자도 «에이전트가 내고 사람이 손으로 고치는» 값이라 한 줄 주장과 똑같이
    정규화를 타야 한다. 여기를 건너뛰면 `../` 한 조각이 그대로 폴더명이 되어
    **산출물이 그 회차의 폴더 밖에 쓰인다.**

    영숫자를 ASCII 로 한정하는 이유는 원장의 줄 형식이 이 문자 집합으로 식별자를
    알아보기 때문이다 — 그 밖의 글자가 섞이면 그 줄은 「식별자 없는 줄」로 읽힌다.

    Args:
        raw: 다듬기 전 식별자

    Returns:
        소문자 영숫자와 하이픈으로만 된 이름

    Raises:
        UnusableNameError: 남는 문자가 하나도 없을 때
    """
    kept: list[str] = []
    for char in raw.lower():
        if char.isascii() and char.isalnum():
            kept.append(char)
        elif char.isspace() or char in IDENTIFIER_REPLACED:
            kept.append(IDENTIFIER_SEPARATOR)
        # 그 밖(경로 구분자·따옴표·한글 등)은 떨어뜨린다

    made = _collapse(kept, IDENTIFIER_SEPARATOR)[:MAX_IDENTIFIER_LENGTH].strip(IDENTIFIER_SEPARATOR)

    if not made:
        raise UnusableNameError(f"식별자로 쓸 수 있는 문자가 없습니다: {raw!r}")

    return made


def folder_name(claim: str, identifier: str | None) -> str:
    """그 후보의 산출물이 쌓일 폴더 이름을 정한다.

    식별자가 있으면 그것을 쓴다. 한 줄 주장 전체를 폴더명으로 쓰면 한도에서 잘리고
    **잘린 자리가 문장 중간이라 무슨 후보인지 이름만으로 안 드러난다.**
    주장은 파일 «안»에 이미 있으므로 폴더명이 그것을 반복할 이유가 없다.

    Args:
        claim: 후보의 한 줄 주장
        identifier: 그 후보의 짧은 식별자. 예전에 담긴 후보에는 없다

    Returns:
        폴더 이름

    Raises:
        UnusableNameError: 식별자도 주장도 쓸 수 있는 문자가 없을 때
    """
    if identifier and identifier.strip():
        try:
            return identifier_slug(identifier)
        except UnusableNameError:
            # [중요] 식별자 하나 때문에 그 후보를 «못 파게» 만들지 않는다.
            # 사람이 상태 파일이나 원장을 손으로 고쳐 한글 식별자를 넣는 일이 있을 수 있는데,
            # 여기서 터뜨리면 반증·계보가 파일을 쓰기 직전에 죽어 상한까지 헛돈다.
            # 한 줄 주장에서 만든 긴 이름이 «이름이 없는 것»보다 낫다
            pass
    return slug(claim)


def _collapse(chars: list[str], separator: str) -> str:
    """이어진 구분자를 하나로 줄이고 앞뒤의 것을 떼어 낸다.

    문자를 떨어뜨리고 나면 구분자가 여러 개 남는다. 그대로 두면 읽기 어렵고,
    **같은 후보가 표기 차이만으로 다른 파일명을 얻는다.**
    """
    collapsed: list[str] = []
    for char in chars:
        if char == separator and (not collapsed or collapsed[-1] == separator):
            continue
        collapsed.append(char)
    return "".join(collapsed).strip(separator)


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

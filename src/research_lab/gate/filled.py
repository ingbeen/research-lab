"""게이트들이 함께 쓰는 「그 자리가 채워졌나」 판정.

[중요] **판정을 한 곳에만 둔다.** 게이트마다 따로 두면 한 벌만 고쳐질 때 같은 이름이
서로 다른 뜻이 되어, 한 게이트는 `[""]` 를 「채워짐」으로 통과시키고 조립부는 같은 값을
「적히지 않았습니다」로 찍는다 — 그 어긋남은 에러를 내지 않는다.
"""

from typing import Any


def is_filled(value: Any) -> bool:
    """그 자리가 «채워졌나».

    [주의] 답의 «내용»은 보지 않는다. 숫자 하나만 적어도, 「해당 없음」 한 줄만 적어도
    채운 것이다 — 여기서 내용이나 모양을 따지기 시작하면 게이트가 또 하나의 판단자가 된다.

    [중요] 담긴 것이 «빈» 컨테이너도 빈 것으로 본다. `str([""])` 는 `"['']"` 라
    비어 있지 않으므로, 안 파고들면 **게이트는 「값이 있다」로 읽고 조립부는
    「적히지 않았습니다」로 렌더한다** — 그 어긋남은 에러를 내지 않고,
    빈 칸이 든 문서가 완성본으로 나간다.

    [중요] 파이썬 재귀로 파고들지 않는다. 에이전트가 낸 값이라 깊이를 보장할 수 없고,
    게이트는 어떤 입력에도 예외를 올리지 않아야 한다.
    """
    pending: list[Any] = [value]
    while pending:
        current = pending.pop()
        if current is None:
            continue
        if isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, list | tuple | set):
            pending.extend(current)
        elif str(current).strip():
            return True
    return False

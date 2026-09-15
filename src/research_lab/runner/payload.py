"""에이전트가 낸 JSON 에서 «목록»을 안전하게 꺼낸다.

[중요] 이 가드가 없으면 **문자열이 글자 단위로 잘린다.** 에이전트가 목록 대신 문자열
하나를 내놓는 것은 흔한 어긋남인데, 파이썬에서 문자열은 순회 가능해서 **예외가 나지 않는다.**

두 자리에서 각각 다르게 터진다.

| 자리 | 무슨 일이 나나 |
| --- | --- |
| 후보 목록 | `"없음"` 이 후보 `'없'` 과 `'음'` 둘로 원장에 담긴다. 원장은 append-only 이고 **중복 방지의 전부**라 그 쓰레기가 이후 회차마다 호출을 한 번씩 잡아먹는다 |
| 검색어 목록 | `"1월 효과"` 가 글자 다섯으로 세어져 **검색어 게이트를 통과한다.** 한 번도 안 갈아 끼운 회차가 「조사한 회차」로 기록된다 |

네 단계가 같은 모양의 JSON 을 받으므로 꺼내는 곳도 하나여야 한다 — 한 곳만 가드가 빠지면
그 단계에서만 조용히 통과한다.
"""

from typing import Any


def as_text(value: Any) -> str:
    """문자열이어야 하는 값을 «없음»과 구별해 꺼낸다.

    [중요] `str(value)` 를 바로 쓰지 않는다. JSON 의 `null` 은 파이썬에서 `None` 이 되고
    `str(None)` 은 **`"None"` 이라는 «내용이 있는» 문자열**이다 — 비었는지 보는 검사를
    전부 통과하고 그대로 문서·파일명·판정에 실린다.

    [중요] **`dict.get(key, "")` 의 기본값으로는 못 막는다.** 열쇠가 «있고» 값이 `null` 이면
    기본값이 아예 안 쓰이기 때문이다. 이 고장이 실제로 세 자리에 있었다 — 반증 사유가
    문서에 `None` 으로 실리고, 반증 게이트가 그 `None` 을 「사유가 적혔다」로 읽어
    **통과시키고**, 후보 식별자가 `None` 이 되어 문서 파일명이 `..._None.md` 가 됐다.

    Args:
        value: 에이전트가 낸 값. 무엇이든 들어올 수 있다

    Returns:
        앞뒤 공백을 턴 문자열. 값이 없으면 빈 문자열
    """
    return "" if value is None else str(value).strip()


def as_list(value: Any) -> list[Any]:
    """목록이어야 하는 값을 목록으로만 받는다.

    Args:
        value: 에이전트가 낸 값. 무엇이든 들어올 수 있다

    Returns:
        목록이면 그대로, 아니면 빈 목록
    """
    return value if isinstance(value, list) else []


def as_strings(value: Any) -> list[str]:
    """문자열 목록이어야 하는 값을 추려 받는다.

    Args:
        value: 에이전트가 낸 값. 무엇이든 들어올 수 있다

    Returns:
        비어 있지 않은 문자열들. 목록이 아니면 빈 목록
    """
    return [str(item) for item in as_list(value) if str(item).strip()]


def urls_in(sources: Any) -> set[str]:
    """출처 목록에서 비어 있지 않은 URL 을 모은다.

    찬성 근거 · 반증 · 계보가 모두 같은 모양(`{"url": ...}`)의 출처를 다루므로
    꺼내는 곳도 하나여야 한다. 세 곳에 흩어지면 한 곳만 가드가 빠져도
    **그 단계에서만 조용히 빈 집합이 되고**, 그 결과 계보 게이트가 통과해 버린다.

    Args:
        sources: 출처 목록. 무엇이든 들어올 수 있다

    Returns:
        비어 있지 않은 URL 들
    """
    found = {as_text(item.get("url")) for item in as_list(sources) if isinstance(item, dict)}
    return {url for url in found if url}

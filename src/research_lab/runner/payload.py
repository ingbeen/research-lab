"""에이전트가 낸 JSON 에서 «목록»을 안전하게 꺼낸다.

[중요] 이 가드가 없으면 **문자열이 글자 단위로 잘린다.** 에이전트가 목록 대신 문자열
하나를 내놓는 것은 흔한 어긋남인데, 파이썬에서 문자열은 순회 가능해서 **예외가 나지 않는다.**

두 자리에서 각각 다르게 터진다.

| 자리 | 무슨 일이 나나 |
| --- | --- |
| 후보 목록 | `"없음"` 이 후보 `'없'` 과 `'음'` 둘로 원장에 담긴다. 원장은 append-only 이고 **중복 방지의 전부**라 그 쓰레기가 이후 회차마다 호출을 한 번씩 잡아먹는다 |
| 검색어 목록 | `"1월 효과"` 가 글자 다섯으로 세어져 **검색어 게이트를 통과한다.** 한 번도 안 갈아 끼운 회차가 「조사한 회차」로 기록된다 |

여러 단계가 같은 모양의 JSON 을 받으므로 꺼내는 곳도 하나여야 한다 — 한 곳만 가드가 빠지면
그 단계에서만 조용히 통과한다.
"""

from typing import Any


def as_text(value: Any) -> str:
    """문자열이어야 하는 값을 «없음»과 구별해, 사람이 읽는 한 줄로 꺼낸다.

    [중요] `str(value)` 를 바로 쓰지 않는다. JSON 의 `null` 은 파이썬에서 `None` 이 되고
    `str(None)` 은 **`"None"` 이라는 «내용이 있는» 문자열**이다 — 비었는지 보는 검사를
    전부 통과하고 그대로 문서·파일명·판정에 실린다.

    [중요] **`dict.get(key, "")` 의 기본값으로는 못 막는다.** 열쇠가 «있고» 값이 `null` 이면
    기본값이 아예 안 쓰이기 때문이다. 이 고장이 실제로 세 자리에 있었다 — 반증 사유가
    문서에 `None` 으로 실리고, 반증 게이트가 그 `None` 을 「사유가 적혔다」로 읽어
    **통과시키고**, 후보 식별자가 `None` 이 되어 문서 파일명이 `..._None.md` 가 됐다.

    [중요] **목록 · 사전도 `str()` 로 찍지 않는다.** 그러면 `['국내 ETF 일봉']` 처럼 파이썬
    표기가 그대로 실리고, 이 함수의 결과는 파일을 거쳐 **저장소 밖으로 나가는 근거 문서**가
    된다. 펴는 일을 조립부에만 두면 조립부를 안 지나는 자리(반증 러너가 「못 찾은 이유」를
    저장하는 자리)에서 표기가 파일에 박히고, 이미 문자열이 된 표기는 조립부가 못 편다.
    **펴는 곳이 하나면 한 자리만 새는 일이 구조적으로 없다.**

    [중요] **한 겹만 펴면 안 된다.** 날짜 «구간»이 목록의 목록으로, 데이터 목록이 사전의 목록으로
    오는 것이 정상이다. 한 겹만 펴면 안쪽이 `str()` 을 타서 막으려던 표기가 그대로 나온다.

    Args:
        value: 에이전트가 낸 값. 무엇이든 들어올 수 있다

    Returns:
        앞뒤 공백을 턴 문자열. 값이 없으면 빈 문자열. 목록은 ` · ` 로, 사전은 `열쇠: 값` 으로
        잇고 빈 항목은 뺀다. **빈 값을 표기하지 않는 것은** 부르는 자리마다 그 표기가 달라서다 —
        근거 문서의 절은 「적히지 않았습니다」, 표 한 칸은 `-`
    """
    if value is None:
        return ""
    if isinstance(value, list | tuple):
        return " · ".join(text for text in (as_text(item) for item in value) if text)
    if isinstance(value, dict):
        pairs = ((key, as_text(item)) for key, item in value.items())
        return " · ".join(f"{key}: {text}" for key, text in pairs if text)
    return str(value).strip()


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

    [중요] **문자열이 아닌 항목은 버린다.** `str(item)` 으로 감싸면 JSON 의 `null` 이
    `"None"` 으로, 중첩 목록이 `"['a', 'b']"` 라는 파이썬 표기로 살아남는다 —
    이 함수의 결과는 **근거 문서의 줄이 되어 저장소 밖으로 나가므로**, 그 두 문자열은
    사람이 읽는 자리에 그대로 실린다. 「비었나」를 보는 검사는 둘 다 통과시킨다.
    """
    return [item.strip() for item in as_list(value) if isinstance(item, str) and item.strip()]


def url_of(source: Any) -> str:
    """출처 하나의 주소. 주소 자리가 «문자열»일 때만 주소로 본다 — 아니면 빈 문자열.

    [중요] `as_text` 로 펴지 않는다. 목록이 든 주소 자리를 펴서 주소로 삼으면, 같은 자리를
    문자열만 주소로 보는 계보 게이트와 **열쇠가 갈려** 게이트는 「빠졌다」, 러너는 「이미 모은
    주소」로 읽는다 — 그 단계는 매 회차 같은 자리에서 막힌다. 주소가 아닌 모양의 값은 근거 문서
    본문에 펴서 실리고, 거기서 본문 주소로 찔린다.
    """
    if not isinstance(source, dict):
        return ""
    raw = source.get("url")
    return raw.strip() if isinstance(raw, str) else ""


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
    return {url for url in (url_of(item) for item in as_list(sources)) if url}

"""계보표가 «모았던 출처를 빠짐없이» 다뤘는지 검사한다.

**웹에서 합의는 근거가 아니다.** 여러 곳이 같은 말을 하는 가장 흔한 이유는 서로 베꼈기
때문이고, 그렇게 만들어진 합의는 「여러 소스에서 확인됨」이라는 라벨을 달고 온다.
계보표는 그 라벨을 벗겨 **「세 곳에서 확인」이 아니라 「한 원본 · 복제 두 곳」**으로 적게 한다.

[중요] 보는 것은 둘뿐이다 — **복제를 뺀 진짜 소스 수**가 적혔나, 그리고 모았던 출처가
**하나도 빠지지 않고** 계보표에 들어갔나. 어느 것이 진짜 원본인지는 판정하지 않는다.
출처를 빠뜨리고 「독립 세 곳」이라 적으면 그 숫자가 통째로 틀리는데, **그 고장은
에러를 내지 않는다** — 표는 그럴듯하게 완성된 것처럼 보인다.

[중요] **검색어 하한을 걸지 않는다.** 계보는 이미 모은 출처를 보는 일이라 하한을 걸면
억지 검색을 유발한다 — 게이트가 규율을 만드는 대신 규율을 «흉내 내게» 만드는 자리다.
"""

from collections.abc import Iterable, Mapping
from typing import Any, Final
from urllib.parse import urlsplit

KEY_GROUPS: Final = "groups"
KEY_INDEPENDENT_SOURCE_COUNT: Final = "independent_source_count"

# 사유에 실을 빠진 URL 의 최대 개수. 전부 실으면 실패 원문이 통째로 URL 목록이 된다
MAX_LISTED_MISSING: Final = 5


def normalize_url(raw: str) -> str:
    """대조에 쓸 형태로 URL 을 다듬는다.

    [중요] 정규화하지 않으면 끝 슬래시 하나, 호스트 대소문자 하나 때문에 같은 URL 이
    다르게 보여 **에러 없이 매 회차 막힌다.** 원인이 게이트 자신이라 로그만 봐서는
    무엇이 어긋났는지 드러나지 않는다.

    스킴(`http`/`https`)을 빼는 것은 같은 글이 두 스킴으로 인용되는 일이 흔해서다.
    조각(`#절`)을 빼는 것도 같은 이유다 — 같은 문서의 다른 자리를 가리킬 뿐이다.

    [중요] **호스트만 소문자로 내린다.** 경로는 대소문자를 가리는 서버가 있어 내리면 안 되고,
    무엇보다 **두 갈래가 서로 다르게 내리면 같은 URL 이 다른 열쇠가 된다** —
    정규화가 막으려던 고장을 정규화가 만드는 셈이다.

    Args:
        raw: 다듬기 전 URL

    Returns:
        대조용 형태. 빈 값이면 빈 문자열
    """
    text = raw.strip()
    if not text:
        return ""

    # 스킴이 없으면 `urlsplit` 이 호스트를 경로로 읽는다. 대조용이므로 임시 스킴을 붙여
    # 두 갈래가 «같은 방식»으로 쪼개지게 만든다
    split = urlsplit(text if "//" in text else f"//{text}", scheme="https")

    host = split.netloc.casefold()
    path = split.path.rstrip("/")
    # [중요] 질의 문자열을 «버리지 않는다». 버리면 `...?id=1` 과 `...?id=2` 가 같아 보여
    # **빠진 출처가 「다뤄진 것」으로 통과한다** — 게이트가 잡으려던 바로 그 고장이다
    query = f"?{split.query}" if split.query else ""
    return f"{host}{path}{query}"


def shortfall_reason(payload: Mapping[str, Any], *, source_urls: Iterable[str]) -> str | None:
    """계보표가 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    Args:
        payload: 계보 단계가 낸 산출물. 모양이 어긋나 있어도 된다
        source_urls: 찬성·반증이 모았던 URL 전부. 빈 값은 대조에서 빠진다 —
            링크를 못 찾은 것은 「미검증」으로 가는 것이 규율이라, 그런 출처까지
            계보에 넣으라고 요구하면 **에이전트가 URL 을 지어낸다**

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    count: Any = payload.get(KEY_INDEPENDENT_SOURCE_COUNT)
    if not isinstance(count, int) or isinstance(count, bool):
        return (
            f"복제를 뺀 진짜 소스 수(`{KEY_INDEPENDENT_SOURCE_COUNT}`)가 없거나 정수가 아닙니다. "
            f"그 숫자가 이 단계의 산출물입니다 — 없으면 계보표는 출처를 나열한 표일 뿐입니다."
        )

    expected = {normalize_url(url): url for url in source_urls if normalize_url(url)}
    covered = _covered(payload.get(KEY_GROUPS))

    missing = [original for key, original in expected.items() if key not in covered]
    if not missing:
        return None

    listed = missing[:MAX_LISTED_MISSING]
    tail = f" 외 {len(missing) - len(listed)}건" if len(missing) > len(listed) else ""
    return (
        f"모았던 출처가 계보표에서 빠졌습니다: {listed}{tail}. "
        f"찬성·반증이 연 URL 은 «전부» 원본이나 복제 중 한 자리에 놓여야 합니다 — "
        f"빠뜨린 채 독립 소스 수를 적으면 그 숫자가 틀리고, 그 고장은 에러를 내지 않습니다."
    )


def _covered(groups: Any) -> set[str]:
    """계보표가 다룬 URL 을 모은다."""
    if not isinstance(groups, list):
        return set()

    found: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        found |= _urls_of(group.get("origin"))
        copies = group.get("copies")
        if isinstance(copies, list):
            for copy in copies:
                found |= _urls_of(copy)
    return found


def _urls_of(source: Any) -> set[str]:
    """출처 하나에서 대조용 URL 을 꺼낸다."""
    if not isinstance(source, dict):
        return set()
    normalized = normalize_url(str(source.get("url", "")))
    return {normalized} if normalized else set()

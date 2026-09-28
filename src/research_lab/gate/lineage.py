"""계보표가 «모았던 출처를 빠짐없이» 다뤘는지 검사한다.

**웹에서 합의는 근거가 아니다.** 여러 곳이 같은 말을 하는 가장 흔한 이유는 서로 베꼈기
때문이고, 그렇게 만들어진 합의는 「여러 소스에서 확인됨」이라는 라벨을 달고 온다.
계보표는 그 라벨을 벗겨 **「세 곳에서 확인」이 아니라 「한 원본 · 복제 두 곳」**으로 적게 한다.

[중요] 보는 것은 둘이다 — 모았던 출처가 **하나도 빠지지 않고** 계보표에 들어갔나, 그리고
**한 원본이 두 덩어리에 들어가지 않았나.** 복제를 뺀 진짜 소스 수는 보지 않는다 — 정의상
주소가 있는 덩어리 수와 같아 러너가 센다. 그래서 출처를 빠뜨리거나 한 원본을 두 덩어리로
나누면 그 수가 통째로 틀리는데, **그 고장은 에러를 내지 않는다** — 표는 그럴듯하게 완성된 것처럼
보인다.

[중요] 어느 것이 진짜 원본인지 · 덩어리를 옳게 나눴는지는 **판정하지 않는다** — 판정하면 게이트가
또 하나의 판단자가 된다. 원본 중복은 판단이 아니라 **표 자체의 모순**이다(「A 는 원본이다」와
「A 는 저 덩어리의 복제다」가 한 표에 함께 있다). 복제가 두 덩어리에 나오는 것은 막지 않는다 —
두 원본을 모은 글이 그 모양이고, 덩어리 수가 그대로라 소스 수가 부풀지 않는다.
막는 대신 러너가 덜 세는 길은 버렸다 — 6번 칸에 덩어리 다섯을 보여 주며 「독립 4」라 적는 식으로
**표와 수가 어긋나고**, 읽는 사람은 어느 쪽이 맞는지 가를 수 없다.

[중요] **검색어 하한을 걸지 않는다.** 계보는 이미 모은 출처를 보는 일이라 하한을 걸면
억지 검색을 유발한다 — 게이트가 규율을 만드는 대신 규율을 «흉내 내게» 만드는 자리다.
"""

from collections.abc import Iterable, Mapping
from typing import Any, Final
from urllib.parse import urlsplit

KEY_GROUPS: Final = "groups"

# 사유에 실을 빠진 URL 의 최대 개수. 전부 실으면 실패 원문이 통째로 URL 목록이 된다
MAX_LISTED_MISSING: Final = 5

# 경로처럼 쓰이는 조각의 머리 — 해시로 페이지를 가르는 사이트의 글 주소다
ROUTE_FRAGMENT_PREFIXES: Final = ("/", "!/")


def normalize_url(raw: str) -> str:
    """대조에 쓸 형태로 URL 을 다듬는다.

    [중요] 정규화하지 않으면 끝 슬래시 하나, 호스트 대소문자 하나 때문에 같은 URL 이
    다르게 보여 **에러 없이 매 회차 막힌다.** 원인이 게이트 자신이라 로그만 봐서는
    무엇이 어긋났는지 드러나지 않는다.

    스킴(`http`/`https`)을 빼는 것은 같은 글이 두 스킴으로 인용되는 일이 흔해서다.
    조각(`#절`)을 빼는 것도 같은 이유다 — 같은 문서의 다른 자리를 가리킬 뿐이다.
    [중요] 단 **경로처럼 쓰이는 조각**(`#/글/101` · `#!/글/101`)은 남긴다. 해시로 페이지를 가르는
    사이트에서는 그것이 곧 다른 글이라, 빼면 **서로 다른 두 글이 한 주소로 합쳐져** 계보 지시문에서
    한쪽이 사라지고, 둘을 각자 원본으로 적은 옳은 표가 「한 원본이 두 덩어리에」로 막힌다.

    [중요] **어떤 입력에도 예외를 올리지 않는다.** 주소로 쪼갤 수 없는 글자(대괄호가 든 호스트 등)면
    적힌 글자를 그대로 열쇠로 쓴다 — 같은 글자끼리는 여전히 같게 맞춰진다. 이 함수는 게이트와
    근거 문서 조립이 함께 쓰므로, 여기서 터지면 비용을 다 치른 단계가 마지막에 깨진다.

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
    try:
        split = urlsplit(text if "//" in text else f"//{text}", scheme="https")
    except ValueError:
        return text

    host = split.netloc.casefold()
    path = split.path.rstrip("/")
    # [중요] 질의 문자열을 «버리지 않는다». 버리면 `...?id=1` 과 `...?id=2` 가 같아 보여
    # **빠진 출처가 「다뤄진 것」으로 통과한다** — 게이트가 잡으려던 바로 그 고장이다
    query = f"?{split.query}" if split.query else ""
    route = f"#{split.fragment}" if split.fragment.startswith(ROUTE_FRAGMENT_PREFIXES) else ""
    return f"{host}{path}{query}{route}"


def shortfall_reason(payload: Mapping[str, Any], *, source_urls: Iterable[str]) -> str | None:
    """계보표가 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    Args:
        payload: 계보 단계가 낸 산출물. 모양이 어긋나 있어도 된다
        source_urls: 찬성·반증이 모았던 URL 전부. 빈 값은 대조에서 빠진다 —
            링크를 못 찾은 것은 「미검증」으로 가는 것이 규율이라, 그런 출처까지
            계보에 넣으라고 요구하면 **에이전트가 URL 을 지어낸다**

    Returns:
        모자랄 때의 사유, 충분하면 None

    [탈락 2026-09-15] 여기에 **「계보가 복제라 적은 주소를 앞 단계가 1차 출처로 셌나」**를
    더하려다 걷어냈다. 두 값이 **직교하는 축**이라 애초에 모순이 아니다 —
    `kind` 는 「1차 연구인가 2차 서술인가」이고 원본/복제는 「최초 발행인가 재게시인가」라,
    **원논문의 미러는 1차이면서 복제**다. 실측으로 계보 산출물 다섯 중 **셋이 막혔고**
    (NBER 워킹페이퍼 · 학술지의 원논문 페이지 · 원논문 PDF 미러) 셋 다 정당한 경우였다.
    품질 실패는 회차 안에서 재시도되지 않으므로 그 오탐은 회차를 통째로 태우고,
    세 번이면 **후보가 원장에서 걷힌다.**
    """
    expected = {normalize_url(url): url for url in source_urls if normalize_url(url)}
    groups = payload.get(KEY_GROUPS)
    covered = _covered(groups)

    missing = [original for key, original in expected.items() if key not in covered]
    repeated = _repeated_origins(groups)

    # [중요] 둘을 «한 사유에» 함께 싣는다. 품질 실패는 회차 안에서 재시도되지 않으므로,
    # 하나씩 알리면 걸린 자리 수만큼 회차가 들고 세 번이면 후보가 걷힌다
    problems: list[str] = []
    if missing:
        problems.append(
            f"모았던 출처가 계보표에서 빠졌습니다: {_listed(missing)}. "
            f"찬성·반증이 연 URL 은 «전부» 원본이나 복제 중 한 자리에 놓여야 합니다 — "
            f"빠뜨리면 덩어리로 세는 독립 소스 수가 틀리고, 그 고장은 에러를 내지 않습니다."
        )
    if repeated:
        problems.append(
            f"한 원본이 두 덩어리에 들어 있습니다: {_listed(repeated)}. "
            f"원본은 한 덩어리에만 둡니다 — 다른 덩어리의 원본이나 복제로 또 적으면 독립 소스 수가 "
            f"그만큼 부풀고, 그 고장은 에러를 내지 않습니다. 다른 글을 베낀 것이면 그 덩어리의 복제로 옮기세요."
        )
    return " ".join(problems) or None


def _listed(urls: list[str]) -> str:
    """사유에 실을 주소 목록 — 앞의 몇 개와 나머지 건수. 전부 실으면 사유가 통째로 URL 목록이 된다."""
    listed = urls[:MAX_LISTED_MISSING]
    tail = f" 외 {len(urls) - len(listed)}건" if len(urls) > len(listed) else ""
    return f"{listed}{tail}"


def _covered(groups: Any) -> set[str]:
    """계보표가 다룬 URL 을 모은다."""
    return {key for _, key, _ in _placements(groups)}


def _repeated_origins(groups: Any) -> list[str]:
    """다른 덩어리에도 나오는 원본 주소 — 처음 적힌 글자로, 처음 나온 순서대로 한 번씩.

    원본이 «제 덩어리의 복제»로 또 적힌 것은 세지 않는다. 한 덩어리 안의 중복은 덩어리 수를
    바꾸지 않아 소스 수가 부풀지 않는다 — 막으면 수가 옳은 표를 오탐으로 막는다.
    """
    placed = _placements(groups)
    groups_of: dict[str, set[int]] = {}
    for index, key, _ in placed:
        groups_of.setdefault(key, set()).add(index)

    repeated: dict[str, str] = {}
    for index, key, original in _origins(groups):
        if groups_of[key] - {index}:
            repeated.setdefault(key, original)
    return list(repeated.values())


def _origins(groups: Any) -> list[tuple[int, str, str]]:
    """덩어리마다의 원본 — (덩어리 자리, 대조용 열쇠, 적힌 글자)."""
    if not isinstance(groups, list):
        return []
    found: list[tuple[int, str, str]] = []
    for index, group in enumerate(groups):
        keyed = _keyed(group.get("origin")) if isinstance(group, dict) else None
        if keyed is not None:
            found.append((index, *keyed))
    return found


def _placements(groups: Any) -> list[tuple[int, str, str]]:
    """계보표에 놓인 모든 주소 — 원본과 복제를 가리지 않고 (덩어리 자리, 대조용 열쇠, 적힌 글자)."""
    placed = _origins(groups)
    if not isinstance(groups, list):
        return placed
    for index, group in enumerate(groups):
        copies = group.get("copies") if isinstance(group, dict) else None
        for copy in copies if isinstance(copies, list) else []:
            keyed = _keyed(copy)
            if keyed is not None:
                placed.append((index, *keyed))
    return placed


def _keyed(source: Any) -> tuple[str, str] | None:
    """출처 하나에서 (대조용 열쇠, 적힌 글자)를 꺼낸다. 주소가 없으면 None."""
    if not isinstance(source, dict):
        return None
    # [중요] **문자열만 주소로 본다.** `str()` 로 감싸면 `null` 이 `"None"` 이라는 가짜 주소가 되어
    # **빠뜨린 출처가 「덮였다」로 읽히고**, 목록은 파이썬 표기가 되어 러너(문자열만 주소로 본다)와
    # 열쇠가 갈린다 — 그러면 게이트는 「빠졌다」, 러너는 「이미 모았다」로 읽어 매 회차 같은 자리에서 막힌다
    raw = source.get("url")
    written = raw.strip() if isinstance(raw, str) else ""
    normalized = normalize_url(written)
    return (normalized, written) if normalized else None

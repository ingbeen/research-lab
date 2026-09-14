"""산출물에 실린 URL 이 실제로 있는지 확인한다 — 지어낸 출처를 막는다.

이 저장소는 백테스트를 하지 않아 부풀릴 점수가 없다. 그래서 **유일하게 남는 위조 위험이
「없는 출처」**이고, 그것은 **읽어서는 구별되지 않는다.** 사람이 판단할 일이 아니라
기계가 막을 일이다.

[중요] 「죽음」은 **404·410 뿐**이다. 403·429·5xx·타임아웃·DNS 실패는 「판정 못 함」으로
통과시킨다. 학술지·뉴스 사이트는 봇을 막으므로 차단을 죽음으로 보면 **멀쩡한 출처가 든
회차가 매번 죽는다** — 판정을 «못 하는 것»과 «실패로 판정하는 것»은 다르다.

[주의] 그래서 남는 구멍이 하나 있다 — **도메인 자체가 가짜인 URL 은 DNS 실패로 떨어져
통과한다.** 실제 위조는 대개 「진짜 도메인 + 가짜 경로」 모양이라 404 로 잡히지만,
DNS 실패를 죽음으로 보면 **네트워크가 한 번 끊긴 회차가 통째로 죽는다.** 그래서 판정 못 한
사유를 `tally` 가 회차마다 남긴다. 분포가 쌓이면 그때 이 가정을 다시 본다 —
`failures.PATTERNS` 를 원문으로 가르치는 것과 같은 방식이다.

[중요] 네트워크를 찌르는 쪽을 **주입으로 받는다.** 게이트는 「값을 받아 사유를 돌려준다」는
계층 계약을 지키고, 테스트는 네트워크 없이 결정적으로 돈다.
"""

import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final
from urllib.parse import quote, urlsplit, urlunsplit


class Liveness(StrEnum):
    """URL 하나의 판정."""

    ALIVE = "alive"
    DEAD = "dead"
    # 찔러 봤지만 «가를 수 없었다». 차단·과부하·타임아웃·이름 해석 실패가 여기 온다.
    # 죽음과 갈라 두는 이유는 **대응이 다르기 때문**이다 — 죽음은 그 회차를 막고, 이건 통과시킨다
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Probe:
    """URL 하나를 찔러 본 결과."""

    liveness: Liveness
    # 왜 그렇게 판정했나 — 「메서드 + 상태코드」이거나 「메서드 + 예외 이름」이다.
    # 이 문자열이 쌓여야 위 [주의] 의 가정을 나중에 다시 볼 수 있다
    detail: str
    # HTTP 응답이 있었다면 그 상태코드. 아예 못 닿았으면 None
    status: int | None = None


# 찌르는 쪽. 주입으로 받으므로 이 모듈은 네트워크에 묶이지 않는다
Prober = Callable[[str], Probe]

# 「그 자리에 문서가 없다」. 이 둘만 죽음으로 본다
DEAD_STATUS_CODES: Final = frozenset({404, 410})

# 실제로 열어 볼 스킴. **이 목록에 없으면 아예 요청하지 않는다.**
#
# [중요] `urllib` 은 `file://` 도 연다. 에이전트가 낸 값을 그대로 넘기면
# 「그 경로가 이 기계에 있느냐」가 판정 결과로 드러나고, 그 결과는 결정 로그를 타고
# **git 에 올라가 공개된다**(`runs/` 를 포함하기로 한 결정). 컨테이너 안에서 내부 주소를
# 두드리게 만드는 길이기도 하다. 이 게이트에 필요한 것은 웹 출처뿐이라 잃는 것이 없다
ALLOWED_SCHEMES: Final = frozenset({"http", "https"})

# HEAD 를 거부하는 서버가 쓰는 상태코드. 거부를 그대로 「판정 못 함」으로 두면
# 그런 사이트의 URL 은 **영영 검사되지 않으므로** GET 으로 한 번 더 묻는다
METHOD_REFUSED_STATUS_CODES: Final = frozenset({405, 501})

# 한 URL 을 기다리는 시간. 한 회차의 출처가 [실측 2026-09-12] 12건이었고 단계 하나가
# 172~273초 걸리므로, 최악(전부 타임아웃)이어도 회차 전체에서 무시할 수 있는 몫이다
PROBE_TIMEOUT_SECONDS: Final = 10.0

# 자기를 밝히는 UA 를 쓴다. 브라우저를 흉내 내지 않는다 —
# 차단당하면 「판정 못 함」이 되어 게이트가 약해질 뿐, 회차가 죽지는 않는다
USER_AGENT: Final = "research-lab-url-check/1.0"

# 사유에 실을 죽은 URL 의 최대 개수. 전부 실으면 실패 원문이 통째로 URL 목록이 된다
MAX_LISTED_DEAD: Final = 5

KEY_UNKNOWN_DETAILS: Final = "unknown_details"

# 판정 못 한 «주소» 자체가 실리는 자리.
#
# [중요] 사유(`HEAD 403`)만 남기면 **어느 주소가 확인 안 됐는지 알 수 없다.** 그러면
# 근거 문서를 받는 쪽은 표에 적힌 주소 중 무엇이 실제로 열렸고 무엇이 안 열렸는지
# **읽어서 구별할 방법이 없다.** 봇 차단은 두 표본 연속 21% 로 나왔고, 게이트를 세게
# 만드는 대신(그러면 멀쩡한 출처가 든 회차가 매번 죽는다) 사람이 볼 자리를 만드는 쪽이다
KEY_UNKNOWN_URLS: Final = "unknown_urls"

# 퍼센트 인코딩에서 «건드리지 않을» 글자.
#
# [중요] `%` 가 들어 있는 것이 핵심이다. 빼면 이미 인코딩된 URL 이 **다시** 인코딩되어
# `%20` 이 `%2520` 이 되고, **멀쩡한 URL 이 404 로 돌아와 게이트가 거짓 양성을 낸다** —
# 지어낸 출처를 잡으려던 검사가 진짜 출처를 지어낸 것으로 몰아붙이는 셈이다
SAFE_PATH_CHARS: Final = "/%:@!$&'()*+,;=~"
SAFE_QUERY_CHARS: Final = "/%:@!$&'()*+,;=?~"


def liveness_for_status(status: int) -> Liveness:
    """HTTP 상태코드 하나를 판정으로 옮긴다.

    Args:
        status: 응답의 상태코드

    Returns:
        404·410 은 죽음, 2xx·3xx 는 살아 있음, **나머지는 전부 판정 못 함**
    """
    if status in DEAD_STATUS_CODES:
        return Liveness.DEAD
    if 200 <= status < 400:
        return Liveness.ALIVE
    return Liveness.UNKNOWN


def probe_url(url: str) -> Probe:
    """URL 하나를 실제로 찔러 본다 — 기본 prober.

    Args:
        url: 찔러 볼 URL

    Returns:
        판정과 그 근거. **어떤 이유로 실패해도 예외를 올리지 않는다**
    """
    probed = _request(url, method="HEAD")
    if probed.status in METHOD_REFUSED_STATUS_CODES:
        return _request(url, method="GET")
    return probed


def probe_all(urls: Iterable[object], *, probe: Prober) -> dict[str, Probe]:
    """URL 들을 한 번씩 찔러 본다.

    Args:
        urls: 산출물에서 꺼낸 URL 들. 모양이 어긋난 값이 섞여 있어도 된다
        probe: 하나를 찔러 보는 쪽

    Returns:
        URL 마다의 판정. 빈 값과 문자열이 아닌 값은 빠지고, 같은 URL 은 한 번만 찌른다

    [중요] **찌르는 쪽이 예외를 던져도 여기서 막는다.** 검사기가 죽어서 파이프라인을
    멈추게 해서는 안 되고, 「판정을 못 한 것」이 「죽음」으로 바뀌어서도 안 된다.
    """
    probed: dict[str, Probe] = {}
    for raw in urls:
        # 빈 URL 은 찌르지 않는다. 링크를 못 찾은 것은 「미검증」으로 가는 것이 규율인데,
        # 그런 출처까지 실재를 요구하면 **에이전트가 URL 을 지어낸다**
        url = raw.strip() if isinstance(raw, str) else ""
        if not url or url in probed:
            continue
        try:
            probed[url] = probe(url)
        except Exception as unexpected:
            probed[url] = Probe(liveness=Liveness.UNKNOWN, detail=type(unexpected).__name__)
    return probed


def shortfall_reason(probed: Mapping[str, Probe]) -> str | None:
    """죽은 URL 이 있으면 그 사유를, 없으면 None 을 돌려준다.

    Args:
        probed: `probe_all` 의 결과

    Returns:
        막을 때의 사유, 통과면 None. **사유에 어느 URL 이 죽었는지를 싣는다** —
        「거부됨」만 돌려주면 다음 회차가 무엇을 고쳐야 하는지 모른다
    """
    dead = sorted(url for url, result in probed.items() if result.liveness is Liveness.DEAD)
    if not dead:
        return None

    listed = dead[:MAX_LISTED_DEAD]
    tail = f" 외 {len(dead) - len(listed)}건" if len(dead) > len(listed) else ""
    return (
        f"실재하지 않는 URL 이 {len(dead)}건 있습니다: {listed}{tail}. "
        f"**실제로 연 URL 만** 적어야 합니다 — 링크를 못 찾았으면 URL 을 비우고 "
        f"`unverified` 에 적으세요. 지어낸 출처는 사람이 읽어서는 구별되지 않습니다."
    )


def tally(probed: Mapping[str, Probe]) -> dict[str, Any]:
    """그 회차의 판정 분포를 센다 — 결정 로그에 그대로 실린다.

    「404·410 만 죽음으로 본다」는 **가정**이고, 그것을 나중에 다시 보려면 무엇이 얼마나
    판정 못 됐는지가 쌓여 있어야 한다. 판정 못 한 «사유»까지 남기는 이유가 그것이다.

    Args:
        probed: `probe_all` 의 결과

    Returns:
        판정별 개수와, 판정 못 한 사유들 (중복을 걷어내고 정렬한 것),
        그리고 **판정 못 한 주소들**. 주소를 사유와 «따로» 싣는 이유는 사유만으로는
        어느 출처가 확인 안 됐는지 되짚을 수 없기 때문이다 — 그 목록이 근거 문서의
        미검증 칸으로 간다. 정렬하는 것은 로그가 회차마다 같은 순서여야 견줄 수 있어서다
    """
    counted = Counter(result.liveness for result in probed.values())
    return {
        Liveness.ALIVE.value: counted[Liveness.ALIVE],
        Liveness.DEAD.value: counted[Liveness.DEAD],
        Liveness.UNKNOWN.value: counted[Liveness.UNKNOWN],
        KEY_UNKNOWN_DETAILS: sorted(
            {result.detail for result in probed.values() if result.liveness is Liveness.UNKNOWN}
        ),
        KEY_UNKNOWN_URLS: sorted(url for url, result in probed.items() if result.liveness is Liveness.UNKNOWN),
    }


def to_ascii_url(url: str) -> str:
    """URL 을 실제로 요청할 수 있는 ASCII 형태로 옮긴다.

    [중요] 이것이 없으면 **한글이 든 URL 은 하나도 검사되지 않는다.** `urllib` 은
    ASCII 가 아닌 글자를 그대로 보내지 못해 `UnicodeEncodeError` 를 내고, 그것은
    「판정 못 함」으로 떨어져 **조용히 통과한다** — 지어낸 한글 URL 을 영영 못 잡는다는 뜻이다.
    국내 매매법을 다루는 저장소라 한글 URL 은 드문 입력이 아니다. [실측 2026-09-14]

    조각(`#절`)은 버린다. 서버로 보내지는 값이 아니고, 붙여 보내면 거부하는 서버가 있다.

    Args:
        url: 산출물에 적힌 URL

    Returns:
        요청에 쓸 ASCII URL. 호스트를 옮길 수 없으면 원본 호스트를 그대로 둔다 —
        그러면 아래에서 「판정 못 함」이 되며, 그것이 죽음으로 모는 것보다 안전하다
    """
    split = urlsplit(url)

    host = split.netloc
    if not host.isascii():
        try:
            host = host.encode("idna").decode("ascii")
        except (UnicodeError, ValueError):
            pass

    return urlunsplit(
        (
            split.scheme,
            host,
            quote(split.path, safe=SAFE_PATH_CHARS),
            quote(split.query, safe=SAFE_QUERY_CHARS),
            "",
        )
    )


def _request(url: str, *, method: str) -> Probe:
    """한 번 요청해 보고 판정으로 옮긴다.

    [중요] **어떤 예외도 밖으로 내보내지 않는다.** 못 닿은 것은 「판정 못 함」이지 죽음이
    아니고, 그 구분이 이 모듈의 전부다.
    """
    try:
        target = to_ascii_url(url)
        if urlsplit(target).scheme not in ALLOWED_SCHEMES:
            # 스킴을 안 적었거나(에이전트가 흔히 그런다) 웹이 아닌 것을 적었다.
            # 「판정 못 함」이지 죽음이 아니다 — 못 여는 것과 없는 것은 다르다
            return Probe(liveness=Liveness.UNKNOWN, detail=f"{method} unsupported-scheme")

        # [중요] `Request` 를 만드는 것도 try 안이다. 스킴이 이상하면 «생성자»가
        # `ValueError` 를 올리므로, 밖에 두면 이 함수가 예외를 흘려보낸다 —
        # 「어떤 예외도 밖으로 내보내지 않는다」는 약속이 거기서 깨진다
        request = urllib.request.Request(target, method=method, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
            status = int(response.status)
    except urllib.error.HTTPError as error:
        status = int(error.code)
        # 4xx·5xx 는 예외로 온다. 소켓이 열린 채로 오므로 닫아 준다.
        # [중요] 닫다 나는 오류는 삼킨다 — 이 줄은 `except` 안이라 여기서 예외가 나면
        # 그대로 밖으로 나가고, 「어떤 예외도 내보내지 않는다」는 약속이 깨진다
        with suppress(Exception):
            error.close()
    except Exception as unexpected:
        # 이름 해석 실패·타임아웃·연결 거부·잘못된 URL 이 여기 온다.
        # 예외 «이름»만 남긴다 — 메시지에는 호스트가 통째로 들어와 로그가 길어진다
        return Probe(liveness=Liveness.UNKNOWN, detail=f"{method} {type(unexpected).__name__}")

    return Probe(liveness=liveness_for_status(status), detail=f"{method} {status}", status=status)

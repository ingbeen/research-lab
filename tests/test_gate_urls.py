"""URL 실재 게이트의 계약을 고정한다 — 지어낸 출처를 기계가 잡는다.

백테스트가 없어 부풀릴 점수가 없는 대신, **존재하지 않는 논문·URL 을 그럴듯하게 지어내는
것**이 이 저장소에 유일하게 남은 위조 위험이다(설계 §6). 그리고 **읽어서는 구별되지 않는다** —
사람이 판단할 일이 아니라 기계가 막을 일이다.

[중요] 「죽음」은 **404·410 뿐**이다. 403·429·5xx·타임아웃·DNS 실패는 **판정 못 함**으로
통과시킨다. 학술지·뉴스 사이트는 봇을 막으므로 그것을 죽음으로 보면 **멀쩡한 밤이 죽는다** —
판정을 «못 하는 것»과 «실패로 판정하는 것»은 다르다는 계층 계약 그대로다.

[중요] 네트워크를 찌르는 쪽을 **주입**으로 받는다. 그래서 이 파일은 네트워크 없이 돌고,
무엇이 들어오면 무엇으로 판정하는지가 테스트에 그대로 적힌다.
"""

import urllib.error
import urllib.request
from typing import Any

import pytest

from research_lab.gate import urls


def _probe_of(table: dict[str, urls.Probe]):
    """표에 적힌 대로 답하는 prober. 표에 없으면 살아 있다고 본다."""

    def probe(url: str) -> urls.Probe:
        return table.get(url, urls.Probe(liveness=urls.Liveness.ALIVE, detail="200", status=200))

    return probe


def _dead(status: int = 404) -> urls.Probe:
    return urls.Probe(liveness=urls.Liveness.DEAD, detail=str(status), status=status)


def _unknown(detail: str = "403") -> urls.Probe:
    return urls.Probe(liveness=urls.Liveness.UNKNOWN, detail=detail, status=None)


# --------------------------------------------------------------------------
# 상태코드 판정 — 「무엇을 죽음으로 보나」
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status", [404, 410])
def test_missing_resource_is_dead(status: int) -> None:
    """
    목적: 「그 자리에 문서가 없다」만 죽음으로 보는 계약을 고정한다.

    지어낸 URL 은 대개 **진짜 도메인 + 가짜 경로**(`arxiv.org/abs/없는번호`) 모양이라
    여기서 잡힌다.

    Given: 404 또는 410
    When: 판정한다
    Then: 죽음이다
    """
    assert urls.liveness_for_status(status) is urls.Liveness.DEAD


@pytest.mark.parametrize("status", [200, 204, 301, 302])
def test_reachable_resource_is_alive(status: int) -> None:
    """
    목적: 닿는 URL 을 살아 있는 것으로 보는 계약을 고정한다.

    Given: 2xx·3xx
    When: 판정한다
    Then: 살아 있다
    """
    assert urls.liveness_for_status(status) is urls.Liveness.ALIVE


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503])
def test_blocked_or_broken_server_is_not_judged(status: int) -> None:
    """
    목적: [중요] **차단·과부하를 죽음으로 «보지 않는» 계약**을 고정한다.

    이 게이트에서 가장 비싼 오판이다. 학술지·뉴스 사이트는 봇을 막으므로 403 을 죽음으로
    보면 **멀쩡한 출처가 든 밤이 매번 죽는다.** 게이트가 약해지는 것보다 낫다 —
    약해지면 사람이 아침에 보지만, 밤이 죽으면 아무것도 안 나온다.

    Given: 401·403·429·5xx
    When: 판정한다
    Then: 판정 못 함이다
    """
    assert urls.liveness_for_status(status) is urls.Liveness.UNKNOWN


# --------------------------------------------------------------------------
# 게이트 — 「무엇을 막나」
# --------------------------------------------------------------------------


def test_all_alive_passes() -> None:
    """
    목적: 전부 살아 있는 산출물이 막히지 않는 계약을 고정한다.

    Given: 살아 있는 URL 둘
    When: 찔러 보고 검사한다
    Then: 사유가 없다
    """
    probed = urls.probe_all(["https://example.com/a", "https://example.com/b"], probe=_probe_of({}))

    assert urls.shortfall_reason(probed) is None


def test_dead_url_blocks_the_step() -> None:
    """
    목적: 죽은 URL 이 **하나라도** 있으면 막는 계약을 고정한다.

    설계 §6 이 「죽은 URL 이 하나라도 있으면 그 밤을 미완성으로 만든다」고 정했다.
    비율로 봐주면 지어낸 출처 하나가 진짜 아홉에 묻힌다.

    Given: 살아 있는 URL 하나와 죽은 URL 하나
    When: 검사한다
    Then: 사유가 나온다
    """
    probed = urls.probe_all(
        ["https://example.com/a", "https://example.com/없음"],
        probe=_probe_of({"https://example.com/없음": _dead()}),
    )

    assert urls.shortfall_reason(probed) is not None


def test_reason_names_the_dead_url() -> None:
    """
    목적: 「거부됨」만 돌려주지 «않는» 계약을 고정한다 (계층 계약 §5).

    무엇이 왜 모자랐는지를 함께 돌려야 다음 밤이 헛돌지 않는다. 사유는 실패 원문에
    그대로 실려 결정 로그에 남는다.

    Given: 죽은 URL 하나
    When: 검사한다
    Then: 사유에 그 URL 이 들어 있다
    """
    dead_url = "https://example.com/지어낸-논문"
    probed = urls.probe_all([dead_url], probe=_probe_of({dead_url: _dead()}))

    reason = urls.shortfall_reason(probed)

    assert reason is not None
    assert dead_url in reason


def test_unknown_does_not_block() -> None:
    """
    목적: [중요] 판정 못 한 URL 이 밤을 «죽이지 않는» 계약을 고정한다.

    위 상태코드 판정과 짝이다. 여기가 뚫리면 봇 차단 한 번에 밤이 통째로 미완성이 된다.

    Given: 전부 판정 못 한 URL 들
    When: 검사한다
    Then: 사유가 없다
    """
    probed = urls.probe_all(
        ["https://example.com/a", "https://example.com/b"],
        probe=_probe_of({"https://example.com/a": _unknown(), "https://example.com/b": _unknown("timeout")}),
    )

    assert urls.shortfall_reason(probed) is None


def test_no_urls_pass() -> None:
    """
    목적: URL 이 하나도 없는 산출물을 막지 «않는» 계약을 고정한다.

    「찬성 근거 0건」·「반증 0건」은 실체 없음이라는 **정상 결과**다. 여기서 막으면
    게이트가 에이전트에게 출처를 지어낼 압력을 만든다 — 이 게이트가 막으려는 바로 그것이다.

    Given: 빈 URL 목록
    When: 검사한다
    Then: 사유가 없다
    """
    assert urls.shortfall_reason(urls.probe_all([], probe=_probe_of({}))) is None


def test_listed_dead_urls_are_capped() -> None:
    """
    목적: 사유에 싣는 URL 수에 상한이 있는 계약을 고정한다.

    전부 실으면 실패 원문이 통째로 URL 목록이 된다 — 계보 게이트가 같은 이유로
    상한을 두고 있다.

    Given: 상한보다 많은 죽은 URL
    When: 검사한다
    Then: 사유가 나오고, 전체 건수가 함께 적힌다
    """
    dead_urls = [f"https://example.com/{index}" for index in range(urls.MAX_LISTED_DEAD + 3)]
    probed = urls.probe_all(dead_urls, probe=_probe_of({url: _dead() for url in dead_urls}))

    reason = urls.shortfall_reason(probed)

    assert reason is not None
    assert str(len(dead_urls)) in reason


# --------------------------------------------------------------------------
# 찔러 보기 — 어떤 입력에도 죽지 않는다
# --------------------------------------------------------------------------


def test_probe_failure_is_not_treated_as_dead() -> None:
    """
    목적: [중요] 찌르는 쪽이 **예외를 던져도** 게이트가 죽지도, 죽음으로 판정하지도 않는 계약을 고정한다.

    검사기가 죽어서 파이프라인을 멈추게 해서는 안 되고, 「판정을 못 한 것」을
    「실패로 판정하는 것」으로 바꿔서도 안 된다.

    Given: 항상 예외를 던지는 prober
    When: 찔러 보고 검사한다
    Then: 예외 없이 판정 못 함이 되고, 막히지 않는다
    """

    def exploding(url: str) -> urls.Probe:
        raise RuntimeError(f"찌르다 터졌다: {url}")

    probed = urls.probe_all(["https://example.com/a"], probe=exploding)

    assert probed["https://example.com/a"].liveness is urls.Liveness.UNKNOWN
    assert urls.shortfall_reason(probed) is None


def test_blank_urls_are_not_probed() -> None:
    """
    목적: 빈 URL 을 찌르지 «않는» 계약을 고정한다.

    링크를 못 찾은 것은 「미검증」으로 가는 것이 규율이다. 그런 출처까지 실재를 요구하면
    **에이전트가 URL 을 지어낸다** — 계보 게이트가 빈 URL 을 대조에서 빼는 것과 같은 이유다.

    Given: 빈 문자열과 공백만 든 목록
    When: 찔러 본다
    Then: 아무것도 안 찔렀고 막히지 않는다
    """
    probed = urls.probe_all(["", "   "], probe=_probe_of({}))

    assert probed == {}
    assert urls.shortfall_reason(probed) is None


def test_same_url_is_probed_once() -> None:
    """
    목적: 같은 URL 을 두 번 찌르지 않는 계약을 고정한다.

    찬성과 반증이 같은 논문을 인용하는 일은 정상이고, 실제로 [실측 2026-09-12] 밤에서
    겹침이 2건 있었다. 두 번 찌르면 시간만 늘어난다.

    Given: 같은 URL 이 두 번 든 목록
    When: 찔러 본다
    Then: 한 번만 찔렀다
    """
    calls: list[str] = []

    def counting(url: str) -> urls.Probe:
        calls.append(url)
        return urls.Probe(liveness=urls.Liveness.ALIVE, detail="200", status=200)

    urls.probe_all(["https://example.com/a", "https://example.com/a"], probe=counting)

    assert calls == ["https://example.com/a"]


def test_non_string_urls_do_not_crash() -> None:
    """
    목적: URL 자리에 문자열이 아닌 값이 와도 게이트가 죽지 «않는» 계약을 고정한다.

    에이전트가 낸 값이라 모양이 어긋나는 것은 흔하다. 검사기가 죽으면 고칠 수 있었던
    것까지 그 밤을 끝낸다.

    Given: None 과 숫자가 섞인 목록
    When: 찔러 보고 검사한다
    Then: 예외가 나지 않는다
    """
    probed = urls.probe_all([None, 3, "https://example.com/a"], probe=_probe_of({}))  # type: ignore[list-item]

    assert urls.shortfall_reason(probed) is None


# --------------------------------------------------------------------------
# 계측 — 「404·410만 죽음」 가정을 다시 볼 재료
# --------------------------------------------------------------------------


def test_tally_counts_every_verdict() -> None:
    """
    목적: 밤마다 판정 분포가 남는 계약을 고정한다.

    「404·410 만 죽음으로 본다」는 **가정**이고, 남는 구멍은 가짜 도메인이 DNS 실패로
    통과하는 것이다. 그 가정을 나중에 다시 보려면 **무엇이 얼마나 판정 못 됐는지**가
    쌓여 있어야 한다 — `failures.PATTERNS` 를 원문으로 가르치는 것과 같은 방식이다.

    Given: 살아 있음·죽음·판정 못 함이 하나씩
    When: 센다
    Then: 셋이 각각 세어지고, 판정 못 한 사유가 남는다
    """
    probed = urls.probe_all(
        ["https://example.com/a", "https://example.com/b", "https://example.com/c"],
        probe=_probe_of({"https://example.com/b": _dead(), "https://example.com/c": _unknown("gaierror")}),
    )

    counted = urls.tally(probed)

    assert counted["alive"] == 1
    assert counted["dead"] == 1
    assert counted["unknown"] == 1
    assert counted["unknown_details"] == ["gaierror"]


# --------------------------------------------------------------------------
# ASCII 로 옮기기 — 한글 URL 이 «조용히» 빠져나가지 않게 한다
# --------------------------------------------------------------------------


def test_non_ascii_path_is_percent_encoded() -> None:
    """
    목적: [중요] 한글이 든 경로를 실제로 «요청할 수 있는» 형태로 옮기는 계약을 고정한다.

    [실측 2026-09-14] 이것이 없을 때 한글 URL 은 `UnicodeEncodeError` 를 내고
    「판정 못 함」으로 떨어져 **조용히 통과했다.** 국내 매매법을 다루는 저장소라
    한글 URL 은 드문 입력이 아니고, 그 말은 **지어낸 한글 URL 을 영영 못 잡는다**는 뜻이다.

    Given: 경로에 한글이 든 URL
    When: 옮긴다
    Then: 전부 ASCII 가 된다
    """
    moved = urls.to_ascii_url("https://ko.wikipedia.org/wiki/1월_효과")

    assert moved.isascii()
    assert moved.startswith("https://ko.wikipedia.org/wiki/")


def test_non_ascii_host_is_encoded() -> None:
    """
    목적: 한글 도메인을 옮기는 계약을 고정한다.

    Given: 호스트에 한글이 든 URL
    When: 옮긴다
    Then: 전부 ASCII 가 된다
    """
    assert urls.to_ascii_url("https://한글도메인.example/문서").isascii()


def test_already_encoded_url_is_not_encoded_twice() -> None:
    """
    목적: [중요] 이미 인코딩된 URL 을 «다시» 인코딩하지 않는 계약을 고정한다.

    다시 인코딩하면 `%20` 이 `%2520` 이 되어 **멀쩡한 URL 이 404 로 돌아온다.**
    지어낸 출처를 잡으려던 게이트가 진짜 출처를 지어낸 것으로 몰아붙이게 되고,
    그 오판은 밤을 미완성으로 만든다.

    Given: 이미 퍼센트 인코딩된 URL
    When: 옮긴다
    Then: 그대로다
    """
    encoded = "https://example.com/a%20b?q=x%2By"

    assert urls.to_ascii_url(encoded) == encoded


def test_fragment_is_dropped() -> None:
    """
    목적: 조각(`#절`)을 빼고 요청하는 계약을 고정한다.

    서버로 보내지는 값이 아니고, 붙여 보내면 거부하는 서버가 있다.

    Given: 조각이 붙은 URL
    When: 옮긴다
    Then: 조각이 빠진다
    """
    assert urls.to_ascii_url("https://example.com/a#3절") == "https://example.com/a"


# --------------------------------------------------------------------------
# 진짜 요청 경로 — 네트워크 없이 «urlopen 만» 갈아 끼워 덮는다
#
# [중요] 위 테스트들은 전부 주입된 prober 를 쓰므로 진짜 `urllib` 을 한 번도 안 지난다.
# 그 구멍에 실제로 결함이 숨어 있었다 — 스킴 없는 URL 에서 `Request` 생성자가
# 예외를 올려 「어떤 예외도 내보내지 않는다」는 약속이 깨져 있었다. [실측 2026-09-14]
# --------------------------------------------------------------------------


class _FakeResponse:
    """`urlopen` 이 돌려주는 것 중 이 모듈이 «실제로 보는» 것만 흉내 낸다."""

    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> bool:
        return False


@pytest.mark.real_prober
def test_head_refusal_falls_back_to_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: HEAD 를 거부하는 서버에 GET 으로 한 번 더 묻는 계약을 고정한다.

    거부를 그대로 「판정 못 함」으로 두면 **그런 사이트의 URL 은 영영 검사되지 않는다.**

    Given: HEAD 에 405 를 내고 GET 에 200 을 내는 서버
    When: 찔러 본다
    Then: 둘 다 보냈고 살아 있음으로 판정된다
    """
    seen: list[str] = []

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        seen.append(request.get_method())
        if request.get_method() == "HEAD":
            raise urllib.error.HTTPError(request.full_url, 405, "Method Not Allowed", {}, None)  # type: ignore[arg-type]
        return _FakeResponse(200)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probed = urls.probe_url("https://example.com/a")

    assert seen == ["HEAD", "GET"]
    assert probed.liveness is urls.Liveness.ALIVE


@pytest.mark.real_prober
def test_http_error_becomes_a_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 4xx 가 «예외»로 오는 것을 판정으로 옮기는 계약을 고정한다.

    `urllib` 은 404 를 값이 아니라 예외로 준다. 이 변환을 빠뜨리면 **죽은 URL 이
    「판정 못 함」으로 떨어져 통째로 통과한다.**

    Given: 404 를 내는 서버
    When: 찔러 본다
    Then: 죽음으로 판정되고, 닫기 실패가 밖으로 새지 않는다
    """

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probed = urls.probe_url("https://example.com/없음")

    assert probed.liveness is urls.Liveness.DEAD
    assert probed.status == 404


@pytest.mark.real_prober
def test_url_without_a_scheme_does_not_raise() -> None:
    """
    목적: [중요] 스킴 없는 URL 에 «예외를 올리지 않는» 계약을 고정한다.

    에이전트가 `example.com/논문` 처럼 스킴을 빼고 적는 것은 흔한 모양이다.
    `Request` 생성자가 여기서 `ValueError` 를 올리는데, 그것이 밖으로 새면
    **검사기가 죽어서 그 밤이 통째로 끝난다.**

    Given: 스킴이 없는 URL
    When: 찔러 본다
    Then: 예외 없이 판정 못 함이 된다
    """
    probed = urls.probe_url("example.com/논문")

    assert probed.liveness is urls.Liveness.UNKNOWN


@pytest.mark.real_prober
@pytest.mark.parametrize("url", ["file:///etc/hosts", "ftp://example.com/a"])
def test_non_web_schemes_are_never_opened(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] 웹이 아닌 스킴을 **아예 열지 않는** 계약을 고정한다.

    `urllib` 은 `file://` 도 연다. 에이전트가 낸 값을 그대로 넘기면 「그 경로가 이 기계에
    있느냐」가 판정으로 드러나고, 그 결과는 결정 로그를 타고 **git 에 올라가 공개된다** —
    이 저장소는 PUBLIC 이고 `runs/` 를 포함하기로 했다. 컨테이너 안에서 내부 주소를
    두드리게 만드는 길이기도 하다.

    Given: 웹이 아닌 스킴의 URL
    When: 찔러 본다
    Then: 아무것도 열지 않고 판정 못 함이 된다
    """

    def must_not_be_called(request: Any, timeout: float | None = None) -> _FakeResponse:
        raise AssertionError(f"열면 안 되는 것을 열었습니다: {request}")

    monkeypatch.setattr(urllib.request, "urlopen", must_not_be_called)

    assert urls.probe_url(url).liveness is urls.Liveness.UNKNOWN

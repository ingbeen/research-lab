"""URL 실재 게이트의 계약을 고정한다 — 지어낸 출처를 기계가 잡는다.

백테스트가 없어 부풀릴 점수가 없는 대신, **존재하지 않는 논문·URL 을 그럴듯하게 지어내는
것**이 이 저장소에 유일하게 남은 위조 위험이다. 그리고 **읽어서는 구별되지 않는다** —
사람이 판단할 일이 아니라 기계가 막을 일이다.

[중요] 「죽음」은 **404·410 뿐**이다. 403·429·5xx·타임아웃·DNS 실패는 **판정 못 함**으로
통과시킨다. 학술지·뉴스 사이트는 봇을 막으므로 그것을 죽음으로 보면 **멀쩡한 회차가 죽는다** —
판정을 «못 하는 것»과 «실패로 판정하는 것»은 다르다는 계층 계약 그대로다.

[중요] 네트워크를 찌르는 쪽을 **주입**으로 받는다. 그래서 이 파일은 네트워크 없이 돌고,
무엇이 들어오면 무엇으로 판정하는지가 테스트에 그대로 적힌다.
"""

import email.message
import socket
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
    보면 **멀쩡한 출처가 든 회차가 매번 죽는다.** 게이트가 약해지는 것보다 낫다 —
    약해지면 사람이 나중에 보지만, 회차가 죽으면 아무것도 안 나온다.

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

    무엇이 왜 모자랐는지를 함께 돌려야 다음 회차가 헛돌지 않는다. 사유는 실패 원문에
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
    목적: [중요] 판정 못 한 URL 이 회차를 «죽이지 않는» 계약을 고정한다.

    위 상태코드 판정과 짝이다. 여기가 뚫리면 봇 차단 한 번에 회차가 통째로 미완성이 된다.

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

    찬성과 반증이 같은 논문을 인용하는 일은 정상이고, 실제로 [실측 2026-09-12] 회차에서
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
    것까지 그 회차를 끝낸다.

    Given: None 과 숫자가 섞인 목록
    When: 찔러 보고 검사한다
    Then: 예외가 나지 않는다
    """
    probed = urls.probe_all([None, 3, "https://example.com/a"], probe=_probe_of({}))

    assert urls.shortfall_reason(probed) is None


# --------------------------------------------------------------------------
# 계측 — 「404·410만 죽음」 가정을 다시 볼 재료
# --------------------------------------------------------------------------


def test_tally_counts_every_verdict() -> None:
    """
    목적: 회차마다 판정 분포가 남는 계약을 고정한다.

    「무엇을 죽음으로 보나」는 **가정**이다. 그 가정을 나중에 다시 보려면 **무엇이 얼마나
    판정 못 됐는지**가 쌓여 있어야 한다 — `failures.PATTERNS` 를 원문으로 가르치는 것과
    같은 방식이다.

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
    그 오판은 회차를 미완성으로 만든다.

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
            raise urllib.error.HTTPError(request.full_url, 405, "Method Not Allowed", email.message.Message(), None)
        return _FakeResponse(200)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probed = urls.probe_url("https://example.com/a")

    assert seen == ["HEAD", "GET"]
    assert probed.liveness is urls.Liveness.ALIVE


@pytest.mark.real_prober
def test_head_404_is_confirmed_with_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] HEAD 의 404 를 «GET 으로 확인한 뒤에» 판정하는 계약을 고정한다.

    국내 언론사가 널리 쓰는 `articleView.html` CMS 는 **HEAD 에 404 를 주면서 GET 에는
    200 을 준다** [실측 2026-09-16]. 확인 없이 확정하면 살아 있는 1차 출처가
    「지어낸 것」으로 몰리고, **그 한 건이 회차를 통째로 끝낸다** — 실제로 두 회차가
    그렇게 죽었고 그때까지 잡힌 죽음은 전부 이 오탐이었다.

    Given: HEAD 에 404 를 내고 GET 에 200 을 내는 서버
    When: 찔러 본다
    Then: 둘 다 보냈고 살아 있음으로 판정된다
    """
    seen: list[str] = []

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        seen.append(request.get_method())
        if request.get_method() == "HEAD":
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", email.message.Message(), None)
        return _FakeResponse(200)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probed = urls.probe_url("https://news.example/news/articleView.html?idxno=1")

    assert seen == ["HEAD", "GET"]
    assert probed.liveness is urls.Liveness.ALIVE


@pytest.mark.real_prober
def test_head_404_stays_dead_when_get_agrees(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 진짜로 없는 문서는 **여전히 죽음**임을 고정한다.

    GET 확인을 붙이는 것이 게이트를 무르게 만들어서는 안 된다. 지어낸 출처를 막는 것이
    이 검사의 존재 이유이고, 백테스트가 없는 이 저장소에 **남는 위조 위험이 그것뿐**이다.

    Given: HEAD 와 GET 이 모두 404 를 내는 서버
    When: 찔러 본다
    Then: 죽음으로 판정되고 상태코드가 남는다
    """

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", email.message.Message(), None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probed = urls.probe_url("https://example.com/정말-없음")

    assert probed.liveness is urls.Liveness.DEAD
    assert probed.status == 404


@pytest.mark.real_prober
def test_head_404_becomes_unknown_when_get_cannot_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 확인하러 간 GET 이 «대답을 못 하면» 죽음으로 확정하지 않는 계약을 고정한다.

    HEAD 는 404 였는데 GET 이 타임아웃·차단으로 막히면 **가른 것이 없다.** 그때 죽음으로
    떨어뜨리면 네트워크가 나쁜 회차가 멀쩡한 출처를 지어낸 것으로 만든다 —
    판정을 «못 하는 것»과 «실패로 판정하는 것»은 다르다.

    Given: HEAD 에 404 를 내고 GET 에서 끊기는 서버
    When: 찔러 본다
    Then: 판정 못 함이 된다
    """

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        if request.get_method() == "HEAD":
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", email.message.Message(), None)
        raise TimeoutError("끊김")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probed = urls.probe_url("https://example.com/못-가른다")

    assert probed.liveness is urls.Liveness.UNKNOWN


@pytest.mark.real_prober
def test_the_head_verdict_survives_in_the_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 확인을 거친 판정의 사유에 **HEAD 쪽도 남는** 계약을 고정한다.

    [중요] HEAD 를 버리면 「HEAD 는 404 였는데 GET 이 막혔다」가 「HEAD 가 아무 말도
    안 했다」와 구별되지 않는다. 그러면 **이 왕복을 넣게 만든 오탐을 로그에서 다시 잴 수
    없다** — 그 실측 자체가 HEAD 와 GET 의 «불일치»가 보였기에 가능했고,
    판정 못 한 사유의 분포가 그 가정을 다시 볼 유일한 재료다.

    Given: HEAD 에 404 를 내고 GET 에서 막히는 서버
    When: 찔러 본다
    Then: 사유에 두 메서드의 답이 함께 남는다
    """

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        if request.get_method() == "HEAD":
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", email.message.Message(), None)
        raise TimeoutError("끊김")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probed = urls.probe_url("https://example.com/못-가른다")

    assert "404" in probed.detail
    assert "TimeoutError" in probed.detail


@pytest.mark.real_prober
def test_a_living_url_is_asked_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] 살아 있는 URL 에 GET 을 «덧붙이지 않는» 계약을 고정한다.

    이 게이트는 한 회차가 내는 모든 출처를 지난다. 확인 요청이 모든 URL 에 붙으면
    **트래픽이 통째로 두 배가 되고** 남의 서버를 그만큼 더 두드린다.
    확인은 죽음 후보에만 붙어야 한다.

    Given: HEAD 에 200 을 내는 서버
    When: 찔러 본다
    Then: HEAD 한 번으로 끝난다
    """
    seen: list[str] = []

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        seen.append(request.get_method())
        return _FakeResponse(200)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert urls.probe_url("https://example.com/멀쩡").liveness is urls.Liveness.ALIVE
    assert seen == ["HEAD"]


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
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", email.message.Message(), None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probed = urls.probe_url("https://example.com/없음")

    assert probed.liveness is urls.Liveness.DEAD
    assert probed.status == 404


def _network(*, target_errno: int, control_reachable: bool, asked: list[str]) -> Any:
    """인용된 주소는 그 `errno` 로 이름 해석에 실패하고, 대조 주소는 닿거나 못 닿는 `urlopen`.

    못 닿는 대조는 «끊긴 네트워크의 mac» 모양이다 — 대조 이름이 캐시에서 풀려도 실제 요청은 못 나간다.
    """

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        if request.full_url == urls.CONTROL_URL:
            asked.append("control")
            if control_reachable:
                return _FakeResponse(200)
        raise urllib.error.URLError(socket.gaierror(target_errno, "name resolution failed"))

    return fake_urlopen


def _lookup(*, host_missing: bool, asked: list[str]) -> Any:
    """인용된 호스트를 다시 물을 때의 답을 흉내 낸다. 무엇을 물었는지 `asked` 에 남긴다."""

    def fake_getaddrinfo(host: str, *_: Any, **__: Any) -> list[Any]:
        asked.append(host)
        if host_missing:
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))]

    return fake_getaddrinfo


@pytest.mark.real_prober
def test_a_domain_that_does_not_exist_is_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] **이름이 없는 도메인**을 죽음으로 보는 계약을 고정한다.

    지어낸 출처가 「진짜 도메인 + 가짜 경로」면 404 로 잡히지만, **도메인까지 지어내면**
    이름 해석에서 떨어져 「판정 못 함」으로 통과해 왔다. 그런데 이름 해석 실패를 통째로
    죽음으로 보면 **네트워크가 한 번 끊긴 회차가 통째로 죽는다.** 그래서 「그런 이름이 없다」는
    답이고, 인용된 호스트를 다시 물어도 없고, 대조 주소에 실제로 닿을 때만 죽음이다.

    Given: 「그런 이름 없음」으로 실패하는 요청 · 다시 물어도 없는 호스트 · 닿는 대조 주소
    When: 찔러 본다
    Then: 죽음이고, 사유에서 이름 없는 도메인임이 보인다
    """
    asked: list[str] = []
    monkeypatch.setattr(
        urllib.request, "urlopen", _network(target_errno=socket.EAI_NONAME, control_reachable=True, asked=asked)
    )
    monkeypatch.setattr(socket, "getaddrinfo", _lookup(host_missing=True, asked=asked))

    probed = urls.probe_url("https://no-such-journal.example/paper")

    assert probed.liveness is urls.Liveness.DEAD
    assert "NXDOMAIN" in probed.detail


@pytest.mark.real_prober
def test_a_missing_name_is_not_judged_when_the_control_cannot_be_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] 대조 주소에 «실제로» 못 닿으면 판정 못 함으로 떨어지는 계약을 고정한다.

    끊긴 네트워크의 mac 은 캐시에 없는 이름마다 「그런 이름 없음」을 낸다. 대조를 이름 해석으로
    하면 자주 묻는 대조 이름은 캐시에서 풀려 **멀쩡한 출처가 지어낸 것으로 몰린다.** 그래서 대조는
    실제 요청으로 한다 — 모를 때는 안전한 쪽으로 떨어진다.

    Given: 「그런 이름 없음」으로 실패하는 요청 · 다시 물어도 없는 호스트 · 못 닿는 대조 주소
    When: 찔러 본다
    Then: 판정 못 함이다
    """
    asked: list[str] = []
    monkeypatch.setattr(
        urllib.request, "urlopen", _network(target_errno=socket.EAI_NONAME, control_reachable=False, asked=asked)
    )
    monkeypatch.setattr(socket, "getaddrinfo", _lookup(host_missing=True, asked=asked))

    assert urls.probe_url("https://no-such-journal.example/paper").liveness is urls.Liveness.UNKNOWN


@pytest.mark.real_prober
def test_a_missing_name_on_a_redirect_is_not_charged_to_the_cited_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] 넘겨받은(redirect) «다음 자리»의 이름이 없을 때 인용된 주소를 죽음으로 몰지 않는 계약을 고정한다.

    `urllib` 은 넘겨주기를 따라간다. DOI 나 짧은 주소가 없어진 출판사 도메인으로 넘겨 주면
    「그런 이름 없음」이 오는데, **인용된 식별자는 실재한다** — 지어낸 것으로 몰면 안 된다.

    Given: 「그런 이름 없음」으로 실패하는 요청과, 다시 물으면 풀리는 인용된 호스트
    When: 찔러 본다
    Then: 판정 못 함이고, 대조를 묻지 않았다
    """
    asked: list[str] = []
    monkeypatch.setattr(
        urllib.request, "urlopen", _network(target_errno=socket.EAI_NONAME, control_reachable=True, asked=asked)
    )
    monkeypatch.setattr(socket, "getaddrinfo", _lookup(host_missing=False, asked=asked))

    probed = urls.probe_url("https://doi.example/10.1000/xyz")

    assert probed.liveness is urls.Liveness.UNKNOWN
    assert "control" not in asked


@pytest.mark.real_prober
def test_a_temporary_name_failure_is_not_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 「일시적 실패」는 다시 묻지도 대조하지도 않고 판정 못 함인 계약을 고정한다.

    일시적 실패는 «이름이 없다»는 답이 아니라 **답을 못 받았다**는 뜻이다.

    Given: 일시적 실패로 끝나는 이름 해석
    When: 찔러 본다
    Then: 판정 못 함이고, 호스트도 대조도 묻지 않았다
    """
    asked: list[str] = []
    monkeypatch.setattr(
        urllib.request, "urlopen", _network(target_errno=socket.EAI_AGAIN, control_reachable=True, asked=asked)
    )
    monkeypatch.setattr(socket, "getaddrinfo", _lookup(host_missing=True, asked=asked))

    assert urls.probe_url("https://example.org/a").liveness is urls.Liveness.UNKNOWN
    assert asked == []


@pytest.mark.real_prober
def test_a_refused_connection_is_not_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 이름 해석이 아닌 연결 실패는 판정 못 함인 계약을 고정한다.

    Given: 연결이 거부되는 요청
    When: 찔러 본다
    Then: 판정 못 함이다
    """

    def fake_urlopen(request: Any, timeout: float | None = None) -> _FakeResponse:
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert urls.probe_url("https://example.org/a").liveness is urls.Liveness.UNKNOWN


@pytest.mark.real_prober
def test_url_without_a_scheme_does_not_raise() -> None:
    """
    목적: [중요] 스킴 없는 URL 에 «예외를 올리지 않는» 계약을 고정한다.

    에이전트가 `example.com/논문` 처럼 스킴을 빼고 적는 것은 흔한 모양이다.
    `Request` 생성자가 여기서 `ValueError` 를 올리는데, 그것이 밖으로 새면
    **검사기가 죽어서 그 회차가 통째로 끝난다.**

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


def test_tally_names_the_unjudged_urls() -> None:
    """
    목적: 판정 못 한 «주소»가 사유와 «함께» 남는 계약을 고정한다.

    [중요] 사유(`HEAD 403`)만 남기면 **어느 주소가 확인 안 됐는지 알 수 없다.**
    그러면 근거 문서를 받는 쪽은 표에 적힌 주소들 중 무엇이 실제로 열렸고 무엇이
    안 열렸는지 **읽어서 구별할 방법이 없다** — 봇 차단은 두 표본 연속 21% 로 나왔고,
    게이트를 세게 만드는 대신 사람이 볼 자리를 만드는 쪽이 이 저장소의 선택이다.

    Given: 살아 있음 하나와 판정 못 함 둘
    When: 센다
    Then: 판정 못 한 주소가 «정렬돼» 남는다
    """
    probed = urls.probe_all(
        ["https://example.com/열림", "https://ssrn.example/막힘", "https://gone.example/이름없음"],
        probe=_probe_of(
            {
                "https://ssrn.example/막힘": _unknown("HEAD 403"),
                "https://gone.example/이름없음": _unknown("HEAD URLError"),
            }
        ),
    )

    counted = urls.tally(probed)

    assert counted[urls.KEY_UNKNOWN_URLS] == [
        "https://gone.example/이름없음",
        "https://ssrn.example/막힘",
    ], "로그가 회차마다 같은 순서여야 나중에 견줄 수 있다"
    assert "https://example.com/열림" not in counted[urls.KEY_UNKNOWN_URLS]


def test_tally_names_no_urls_when_everything_was_judged() -> None:
    """
    목적: 전부 판정된 회차에서는 «빈 목록»이 나오는 계약을 고정한다.

    없는 사실을 채워 넣지 않는다 — 이 값이 그대로 근거 문서의 11번 칸으로 가므로,
    여기서 새면 **확인된 주소가 「확인 못 했다」로 적힌다.**

    Given: 전부 살아 있는 주소들
    When: 센다
    Then: 판정 못 한 주소가 없다
    """
    probed = urls.probe_all(["https://example.com/a", "https://example.com/b"], probe=_probe_of({}))

    assert urls.tally(probed)[urls.KEY_UNKNOWN_URLS] == []


def test_tally_names_the_dead_urls() -> None:
    """
    목적: 죽은 «주소»도 판정 분포와 함께 남는 계약을 고정한다.

    출처 칸의 죽음은 그 단계를 막으며 사유에 주소가 실리지만, 근거 문서 «본문»의 주소는
    막지 않고 표시만 한다. 그 자리에는 실패 줄이 없어서, 분포에 주소가 없으면
    **무엇이 죽었는지가 어디에도 안 남는다.**

    Given: 살아 있음 하나와 죽음 둘
    When: 센다
    Then: 죽은 주소가 «정렬돼» 남는다
    """
    probed = urls.probe_all(
        ["https://example.com/열림", "https://example.com/z", "https://example.com/b"],
        probe=_probe_of({"https://example.com/z": _dead(), "https://example.com/b": _dead(410)}),
    )

    assert urls.tally(probed)[urls.KEY_DEAD_URLS] == ["https://example.com/b", "https://example.com/z"]


# --------------------------------------------------------------------------
# 본문에서 주소 뽑기 — 출처 칸 밖의 주소도 찌르기 위해
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "근거는 NBER 워킹페이퍼(https://www.nber.org/papers/w1234)에 있다. 또 https://example.com/a.",
            ["https://www.nber.org/papers/w1234", "https://example.com/a"],
        ),
        (
            "「https://example.com/q?x=1」 과 'http://example.org/b' 를 보라",
            ["https://example.com/q?x=1", "http://example.org/b"],
        ),
        ("[표본] https://example.com/list; 이어서 https://example.com/list", ["https://example.com/list"]),
    ],
)
def test_urls_are_picked_out_of_prose(text: str, expected: list[str]) -> None:
    """
    목적: 산문 속 주소를 «감싼 글자와 끝 문장부호 없이» 뽑는 계약을 고정한다.

    괄호 · 낫표 · 따옴표 · 끝의 마침표가 주소에 붙어 나오면 **멀쩡한 주소가 없는 문서로**
    찔리고, 그 판정이 근거 문서에 「없었다」로 실린다.

    Given: 괄호 · 낫표 · 따옴표 · 문장부호에 둘러싸인 주소, 같은 주소 두 번
    When: 뽑는다
    Then: 주소만, 나온 순서대로, 한 번씩
    """
    assert urls.urls_in_text(text) == expected


def test_a_korean_path_is_not_cut() -> None:
    """
    목적: 한글 경로를 가진 주소를 «자르지 않는» 계약을 고정한다.

    국내 매매법을 다루는 저장소라 한글 경로 주소는 드문 입력이 아니다. 한글에서 끊으면
    `…/w/` 만 남아 **엉뚱한 문서를 찌른다.**

    Given: 한글 경로 주소가 든 문장
    When: 뽑는다
    Then: 경로 전체가 나온다
    """
    assert urls.urls_in_text("나무위키 https://namu.wiki/w/1월_효과 참고") == ["https://namu.wiki/w/1월_효과"]


@pytest.mark.parametrize("value", [None, 3, ["https://example.com/a"], {"url": "https://example.com/a"}])
def test_non_text_yields_no_urls(value: Any) -> None:
    """
    목적: 문자열이 아닌 값에 «예외 없이» 빈 목록을 내는 계약을 고정한다.

    검사기가 죽으면 고칠 수 있었던 것까지 그 회차를 끝낸다.

    Given: 문자열이 아닌 값
    When: 뽑는다
    Then: 빈 목록
    """
    assert urls.urls_in_text(value) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("출처는 https://www.krx.co.kr：참고", ["https://www.krx.co.kr"]),
        ("https://example.com？", ["https://example.com"]),
        ("공시는 https://www.krx.co.kr에서 받는다", ["https://www.krx.co.kr"]),
        ("**https://example.com/a** 를 보라", ["https://example.com/a"]),
        ("DOI https://doi.org/10.1016/0304-405X(93)90023-5 참고", ["https://doi.org/10.1016/0304-405X(93)90023-5"]),
        (
            "(https://en.wikipedia.org/wiki/Momentum_(finance))에 있다",
            ["https://en.wikipedia.org/wiki/Momentum_(finance)"],
        ),
        ("https://[x]/a", []),
    ],
)
def test_awkward_neighbours_do_not_break_extraction(text: str, expected: list[str]) -> None:
    """
    목적: [중요] 주소에 붙은 «이상한 이웃»이 예외도 거짓 주소도 만들지 않는 계약을 고정한다.

    - 호스트 뒤 전각 부호는 `urlsplit` 이 예외로 거부한다 — 뽑기가 터지면 판정 단계가 비용을
      치른 뒤 깨지고, 매 회차 같은 자리에서 되풀이돼 후보가 걷힌다
    - 호스트에 붙은 한글은 조사다 — 그대로 두면 없는 도메인이 되어 멀쩡한 주소를 두고
      「열리지 않는다」가 적힌다
    - 괄호는 짝으로 가른다 — 괄호에서 끊으면 DOI 같은 출처가 잘린 채 다시 찔린다

    Given: 전각 부호 · 붙은 조사 · 마크다운 강조 · 괄호 짝 · 쪼갤 수 없는 호스트
    When: 뽑는다
    Then: 예외 없이 주소만 나온다
    """
    assert urls.urls_in_text(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://한국은행.kr/stat 도", ["https://한국은행.kr/stat"]),
        ("https://example.한국/a 참고", ["https://example.한국/a"]),
        ("https://x.com/a… 그리고", ["https://x.com/a"]),
    ],
)
def test_korean_domains_survive_and_trailing_marks_are_dropped(text: str, expected: list[str]) -> None:
    """
    목적: 한글 도메인은 «그대로», 끝의 말줄임 · 줄표는 «떼고» 뽑는 계약을 고정한다.

    호스트에 붙은 한글을 조사로 보고 자르되, 한글로 시작하는 호스트나 한글 최상위 도메인까지
    자르면 주소가 통째로 사라져 **찔리지도 표시되지도 않은 채** 문서에 남는다.

    Given: 한글 호스트 · 한글 최상위 도메인 · 말줄임이 붙은 주소
    When: 뽑는다
    Then: 도메인은 온전하고 끝 부호는 빠진다
    """
    assert urls.urls_in_text(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("“https://example.com/report”를 보라", ["https://example.com/report"]),
        ("《https://example.com/b》 참고", ["https://example.com/b"]),
        ("HTTPS://Example.com/A 참고", ["HTTPS://Example.com/A"]),
        ("https://www.kb증권.com/research/1 참고", ["https://www.kb증권.com/research/1"]),
    ],
)
def test_typographic_marks_and_mixed_hosts_are_handled(text: str, expected: list[str]) -> None:
    """
    목적: 굽은 따옴표 · 겹화살괄호에서 끊고, 대문자 스킴을 뽑고, 한글이 섞인 호스트를 자르지 않는 계약을 고정한다.

    굽은 따옴표가 붙은 채 뽑히면 멀쩡한 주소가 「열리지 않는다」로 적히고, 대문자 스킴을 놓치면
    그 주소는 찔리지 않은 채 확인된 것처럼 남는다. 한글이 섞인 호스트(`kb증권.com`)를 조사로 보고
    자르면 없는 주소가 찔린다.

    Given: 굽은 따옴표 · 겹화살괄호 · 대문자 스킴 · 한글이 섞인 호스트
    When: 뽑는다
    Then: 주소만 온전히 나온다
    """
    assert urls.urls_in_text(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("_https://x.com/a_ 참고", ["https://x.com/a"]),
        ("~~https://x.com/a~~ 는 옛 주소", ["https://x.com/a"]),
        ("| https://x.com/a\\|b | 다음 칸", ["https://x.com/a"]),
        ("https://en.wikipedia.org/wiki/Foo_ 참고", ["https://en.wikipedia.org/wiki/Foo_"]),
    ],
)
def test_markdown_around_a_url_is_not_part_of_it(text: str, expected: list[str]) -> None:
    """
    목적: 주소를 감싼 마크다운(강조 · 취소선 · 표의 이스케이프)을 주소에 넣지 않는 계약을 고정한다.

    붙은 채 뽑히면 다른 경로로 찔려 멀쩡한 주소가 「열리지 않는다」로 적힌다. 다만 앞에 짝이 없는
    끝 밑줄은 떼지 않는다 — 밑줄로 끝나는 주소가 있다.

    Given: 밑줄 강조 · 취소선 · 이스케이프한 세로선 · 밑줄로 끝나는 주소
    When: 뽑는다
    Then: 마크다운 없이 주소만 나온다
    """
    assert urls.urls_in_text(text) == expected

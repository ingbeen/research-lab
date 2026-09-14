"""테스트가 «진짜 네트워크»를 쓰지 않게 만들고, 판정을 바꿔 끼울 자리를 하나로 둔다.

URL 실재 게이트가 수집·반증에 붙으면서, 그 단계를 도는 테스트가 산출물에 적힌 URL 을
실제로 찌를 수 있게 됐다. 그대로 두면 넷이 한꺼번에 나빠진다 —
① 오프라인에서 테스트가 깨지고 ② 남의 서버를 두드리고 ③ 느려지고
④ **결과가 그날 네트워크에 따라 달라져** 초록과 빨강이 코드와 무관해진다.

[중요] 각 테스트 파일이 알아서 막게 두지 않는다. 한 곳만 빠져도 **그 파일만 조용히
네트워크를 쓰고**, 그 사실은 오프라인에 가기 전까지 드러나지 않는다. 그래서 여기서 한 번 막는다.
"""

from collections.abc import Callable, Iterable, Mapping

import pytest

from research_lab.gate import urls as url_gate


def _alive(url: str) -> url_gate.Probe:
    """찔러 봤더니 살아 있었다."""
    return url_gate.Probe(liveness=url_gate.Liveness.ALIVE, detail="HEAD 200", status=200)


@pytest.fixture(autouse=True)
def _no_real_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """찌르는 쪽을 「전부 살아 있음」으로 바꾼다 — 아무 테스트도 밖으로 나가지 못한다.

    `real_prober` 표시가 붙은 테스트만 비켜 간다. **진짜 요청 경로에도 계약이 있고**
    (스킴 거르기·HEAD 거부 시 GET·4xx 를 판정으로 옮기기), 그것을 검사하려면 이 함수를
    실제로 지나야 한다. 그 테스트는 `urlopen` 을 직접 갈아 끼워 밖으로 나가지 않는 것을
    스스로 책임진다.
    """
    if request.node.get_closest_marker("real_prober") is not None:
        return
    monkeypatch.setattr(url_gate, "probe_url", _alive)


@pytest.fixture
def probing(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """URL 판정을 원하는 대로 바꿔 끼우고, 무엇을 찔렀는지 돌려준다.

    테스트마다 prober 를 손으로 흉내 내면 `Probe` 모양이 바뀔 때 그 수만큼 고쳐야 하고,
    **빠뜨린 곳은 「계약이 깨졌다」가 아니라 알쏭달쏭한 타입 오류로 터진다.**

    쓰는 법::

        probed = probing(dead={"https://example.com/없음"})
        ...
        assert probed == [...]        # 무엇을 찔렀나
    """
    calls: list[str] = []

    def install(*, dead: Iterable[str] = (), unknown: Mapping[str, str] | None = None) -> list[str]:
        dead_urls = set(dead)
        unknown_urls = dict(unknown or {})

        def probe(url: str) -> url_gate.Probe:
            calls.append(url)
            if url in dead_urls:
                return url_gate.Probe(liveness=url_gate.Liveness.DEAD, detail="HEAD 404", status=404)
            if url in unknown_urls:
                return url_gate.Probe(liveness=url_gate.Liveness.UNKNOWN, detail=unknown_urls[url])
            return _alive(url)

        monkeypatch.setattr(url_gate, "probe_url", probe)
        return calls

    return install

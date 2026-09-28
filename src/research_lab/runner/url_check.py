"""모은 출처의 URL 이 실제로 있는지 확인하고, 그 판정을 부르는 쪽에 돌려준다.

URL 을 내는 다섯 단계가 **똑같은 일을 한다** — 자기가 모은 출처를 찌르고, 판정 분포를
남기고, 죽은 것이 있으면 사유를 만든다. 두 벌로 흩어지면 한 곳만 고쳐질 때 **그 단계에서만
계측이 어긋나고, 어긋났다는 사실이 드러나지 않는다** — 단계마다 같은 값을 적는 일을
`decision_log.record_cost` 한 곳에 모은 것과 같은 이유다.

[중요] **막는 «방식»은 단계마다 다르다.** 수집은 그 회차의 후보를 «고르는» 자리라
죽은 주소를 짚어 다시 묻고 후보를 바꿀 수 있지만, 나머지 넷은 후보가 이미 박혀 있어
막고 다음 회차에 넘기는 것이 전부다. 그래서 여기가 둘로 갈린다 — **판정하고 사유를
돌려주는 쪽**(`check_sources`)과 **그 사유로 단계를 막는 쪽**(`assert_sources_exist`).
찌르고 기록하는 일은 여전히 한 곳이다.

[중요] 이 검사는 **네트워크를 쓴다.** 그래서 값싼 게이트(검색어·정성 표현·반증 규율)가
모두 통과한 «뒤»에 부른다. 어차피 막힐 단계에서 URL 을 찌르는 것은 순 낭비다.

[중요] 근거 문서 «본문»의 주소는 **막지 않고** 찌른다(`check_body_urls`). 본문에서 주소를
뽑는 일은 틀릴 수 있어(한글이 붙은 꼴 · 괄호가 든 주소), 그것으로 막으면 **거짓 죽음이 같은
자리에서 반복되고 세 번이면 멀쩡한 후보가 걷힌다.** 대신 판정 못 한 것과 죽은 것을 근거
문서의 미검증 칸에 싣는다 — 머리말의 「거기 없는 주소는 확인된 것」이 본문 주소에서도 참이 된다.
찌르고 남기는 일은 출처 칸과 같은 한 곳(`_probe_and_record`)이다.
"""

from pathlib import Path
from typing import Any, Final

from research_lab.gate import urls as url_gate
from research_lab.runner import decision_log
from research_lab.runner import payload as payload_helpers
from research_lab.runner.steps import StepQualityFailed

GATE_NAME: Final = "urls"

# 본문 검사의 기록을 출처 칸의 것과 가르는 표시. 같은 단계 이름 · 같은 게이트 이름으로
# 남으므로, 이것이 없으면 로그만 보고는 무엇을 찌른 줄인지 모른다
SCOPE_BODY: Final = "body"


def check_sources(run_dir: Path, step: str, sources: Any, *, what: str) -> str | None:
    """출처의 URL 을 찔러 보고 판정 분포를 남긴 뒤, 막아야 하면 그 사유를 돌려준다.

    **출처 칸을 판정하는 곳은 여기 하나다**(찌르고 남기는 일은 `_probe_and_record`).
    부르는 쪽이 둘(막고 끝내는 단계와 다시 물어보는 단계)이라 갈라 두면 한쪽만 고쳐질 때
    **그 단계에서만 계측이 어긋나고, 어긋났다는 사실이 드러나지 않는다.**

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 부르는 단계 이름. 결정 로그에 그대로 적힌다
        sources: `{"url": ...}` 모양의 출처 목록. 모양이 어긋나 있어도 된다
        what: 사유 앞에 붙일 말 (예: 「수집 출처」)

    Returns:
        막아야 하면 그 사유, 통과면 None. **사유에는 실재하지 않는 URL 이 이름으로
        실린다** — 그래야 부르는 쪽이 그것을 그대로 다음 지시문에 넣어 무엇이 문제였는지
        짚을 수 있다. 「거부됨」만 돌려주면 다음 시도가 같은 것을 다시 낸다
    """
    # 정렬해서 넘기는 것은 로그를 회차마다 같은 순서로 남기기 위해서다.
    # `urls_in` 이 집합을 돌려주므로 그대로 쓰면 순서가 실행마다 달라진다
    probed = _probe_and_record(run_dir, step, sorted(payload_helpers.urls_in(sources)))

    shortfall = url_gate.shortfall_reason(probed)
    if shortfall is None:
        return None

    decision_log.record(run_dir, step, decision_log.EVENT_FAILED, gate=GATE_NAME, reason=shortfall)
    return f"{what}가 실재하지 않습니다 — {shortfall}"


def assert_sources_exist(run_dir: Path, step: str, sources: Any, *, what: str) -> None:
    """출처의 URL 을 찔러 보고, 실재하지 않는 것이 있으면 그 단계를 막는다.

    다시 물어볼 길이 없는 단계(반증·계보·실현가능성·메커니즘)가 쓴다. 그 단계들은
    **그 회차의 후보가 이미 박혀 있어** 후보를 바꿀 수 없으므로, 막고 다음 회차에
    넘기는 것이 할 수 있는 전부다.

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 부르는 단계 이름. 결정 로그에 그대로 적힌다
        sources: `{"url": ...}` 모양의 출처 목록. 모양이 어긋나 있어도 된다
        what: 실패 원문 앞에 붙일 말 (예: 「반증 출처」)

    Raises:
        StepQualityFailed: 실재하지 않는 URL 이 있을 때
    """
    reason = check_sources(run_dir, step, sources, what=what)
    if reason is not None:
        raise StepQualityFailed(reason)


def check_body_urls(run_dir: Path, step: str, urls: list[str]) -> list[str]:
    """근거 문서 본문의 주소를 찔러 보고 남긴 뒤, 살아 있음이 확인 안 된 것을 돌려준다 — **막지 않는다.**

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 부르는 단계 이름. 결정 로그에 그대로 적힌다
        urls: 본문에서 뽑은 주소들. 출처 칸이 이미 찌른 주소는 부르는 쪽이 빼고 넘긴다

    Returns:
        죽은 것과 판정 못 한 것, 받은 순서대로. [중요] **둘을 가르지 않고** 돌려준다 — 뽑기를 거친
        주소는 «죽었다»가 곧 «그 자리에 문서가 없다»가 아니다(조사가 섞여 뽑히면 멀쩡한 주소도
        죽는다). 그래서 근거 문서는 둘을 한 문구로 싣고, 이 기록은 출처 칸의 판정 못 한 주소 목록과
        섞이지 않게 `scope` 로 갈린다
    """
    probed = _probe_and_record(run_dir, step, urls, scope=SCOPE_BODY)
    return [url for url, result in probed.items() if result.liveness is not url_gate.Liveness.ALIVE]


def _probe_and_record(run_dir: Path, step: str, urls: list[str], **extra: Any) -> dict[str, url_gate.Probe]:
    """찌르고 판정 분포를 남긴다 — **찌르고 남기는 곳은 여기 하나다.**

    막혀서 끝나도 무엇을 찔렀고 무엇을 판정 못 했는지는 남아야 한다 — 그래서 판정 «앞»에서
    적는다. 판정 못 한 사유의 분포가 「무엇을 죽음으로 보나」는 가정을 다시 볼 재료다.
    """
    probed = url_gate.probe_all(urls, probe=url_gate.probe_url)
    decision_log.record(run_dir, step, decision_log.EVENT_READ, gate=GATE_NAME, **extra, **url_gate.tally(probed))
    return probed

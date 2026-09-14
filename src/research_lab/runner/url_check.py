"""모은 출처의 URL 이 실제로 있는지 확인하고, 없으면 그 단계를 막는다.

수집과 반증이 **똑같은 일을 한다** — 자기가 모은 출처를 찌르고, 판정 분포를 남기고,
죽은 것이 있으면 막는다. 두 벌로 흩어지면 한 곳만 고쳐질 때 **그 단계에서만 계측이
어긋나고, 어긋났다는 사실이 드러나지 않는다** — 네 단계가 같은 값을 적는 일을
`decision_log.record_cost` 한 곳에 모은 것과 같은 이유다.

[중요] 이 검사는 **네트워크를 쓴다.** 그래서 값싼 게이트(검색어·정성 표현·반증 규율)가
모두 통과한 «뒤»에 부른다. 어차피 막힐 단계에서 URL 을 찌르는 것은 순 낭비다.
"""

from pathlib import Path
from typing import Any, Final

from research_lab.gate import urls as url_gate
from research_lab.runner import decision_log
from research_lab.runner import payload as payload_helpers
from research_lab.runner.steps import StepQualityFailed

GATE_NAME: Final = "urls"


def assert_sources_exist(run_dir: Path, step: str, sources: Any, *, what: str) -> None:
    """출처의 URL 을 찔러 보고, 실재하지 않는 것이 있으면 막는다.

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 부르는 단계 이름. 결정 로그에 그대로 적힌다
        sources: `{"url": ...}` 모양의 출처 목록. 모양이 어긋나 있어도 된다
        what: 실패 원문 앞에 붙일 말 (예: 「수집 출처」)

    Raises:
        StepQualityFailed: 실재하지 않는 URL 이 있을 때
    """
    # 정렬해서 넘기는 것은 로그를 회차마다 같은 순서로 남기기 위해서다.
    # `urls_in` 이 집합을 돌려주므로 그대로 쓰면 순서가 실행마다 달라진다
    probed = url_gate.probe_all(sorted(payload_helpers.urls_in(sources)), probe=url_gate.probe_url)

    # 막혀서 끝나도 무엇을 찔렀고 무엇을 판정 못 했는지는 남아야 한다 — 게이트 «앞»에서 적는다.
    # 판정 못 한 사유의 분포가 「404·410 만 죽음으로 본다」는 가정을 다시 볼 재료다
    decision_log.record(run_dir, step, decision_log.EVENT_READ, gate=GATE_NAME, **url_gate.tally(probed))

    shortfall = url_gate.shortfall_reason(probed)
    if shortfall is not None:
        decision_log.record(run_dir, step, decision_log.EVENT_FAILED, gate=GATE_NAME, reason=shortfall)
        raise StepQualityFailed(f"{what}가 실재하지 않습니다 — {shortfall}")

"""앞선 시도가 품질 게이트에 막혔으면 그 사유를 «다음 시도의 지시문»에 싣는 계약을 고정한다.

품질 실패는 회차 안에서 재시도되지 않는다 — 기다려서 풀리는 고장이 아니다. 그런데 사유가
다음 시도에 안 실리면 **에이전트는 무엇이 막혔는지 모른 채 같은 표현 · 같은 주소를 다시 내고**,
같은 자리에서 세 번 막히면 멀쩡한 후보가 원장에서 걷힌다. 자립성 사전의 오탐(외부 카탈로그를
말한 정상 문장)이 그렇게 «고칠 수 있는데 못 고치는» 실패가 되던 자리다.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from research_lab.agent.invoke import AgentResult
from research_lab.gate import selfcontained
from research_lab.runner import (
    decision_log,
    feasibility,
    lineage,
    measurement,
    mechanism,
    previous_failure,
    rebut,
    steps,
    verdict,
)
from research_lab.runner.failures import FailureKind

REASON = "반증 산출물: 「카탈로그에」 — 가리키는 대신 기준 자체를 적으세요"


class _Stop(Exception):
    """지시문만 받아 두고 그 단계를 여기서 끝내게 하는 표시."""


def _record_quality_failure(run_dir: Path, step: str, raw: str) -> None:
    """에이전트가 답을 냈는데(비용 줄) 품질 게이트에 막힌 시도를 흉내 낸다."""
    decision_log.record(run_dir, step, decision_log.EVENT_COST, cost_usd=0.1, tokens=10, elapsed_seconds=1.0)
    decision_log.record(
        run_dir,
        step,
        decision_log.EVENT_FAILED,
        kind=FailureKind.QUALITY.value,
        attempt=1,
        max_retries=3,
        raw=raw,
    )


# 후보가 박힌 단계를 «이름으로» 부르는 자리. 단계를 더하면서 여기 안 더하면 아래 테스트가
# `KeyError` 로 빨강이 된다 — 새 단계가 되먹임을 비켜 가는 것을 그 자리에서 잡는다
RUNNERS: dict[str, Callable[[Any, Callable[[str], AgentResult]], None]] = {
    "rebut": lambda ready, ask: rebut.run(ready.run_dir, ask),
    "lineage": lambda ready, ask: lineage.run(ready.run_dir, ask),
    "feasibility": lambda ready, ask: feasibility.run(ready.run_dir, ask),
    "mechanism": lambda ready, ask: mechanism.run(ready.run_dir, ask),
    "measurement": lambda ready, ask: measurement.run(ready.run_dir, ask),
    "verdict": lambda ready, ask: verdict.run(ready.run_dir, ready.ledger_path, ask, dossier_dir=ready.dossier_dir),
}


def test_the_reason_is_appended_when_there_is_one(tmp_path: Path) -> None:
    """
    목적: 직전 품질 실패가 있으면 그 사유가 지시문 «끝»에 붙는 계약을 고정한다.

    Given: 그 단계의 품질 실패 기록
    When: 지시문에 붙인다
    Then: 원래 지시문 뒤에 그 사유가 있다
    """
    _record_quality_failure(tmp_path, "mechanism", REASON)

    prompt = previous_failure.with_previous_failure("원래 지시문", tmp_path, "mechanism")

    assert prompt.startswith("원래 지시문")
    assert REASON in prompt


def test_the_prompt_is_untouched_without_a_failure(tmp_path: Path) -> None:
    """
    목적: 품질 실패가 없으면 지시문을 «그대로» 두는 계약을 고정한다.

    처음 도는 단계에 「앞선 시도가 막혔다」가 붙으면 에이전트는 없는 잘못을 고치려 든다.

    Given: 품질 실패가 없는 실행 폴더
    When: 지시문에 붙인다
    Then: 원래 지시문 그대로다
    """
    assert previous_failure.with_previous_failure("원래 지시문", tmp_path, "mechanism") == "원래 지시문"


@pytest.mark.parametrize("step", steps.CANDIDATE_STEPS)
def test_every_step_with_a_pinned_candidate_carries_the_reason(step: str, prepared: Any) -> None:
    """
    목적: [중요] 후보가 박힌 «모든» 단계가 직전 품질 실패 사유를 담아 에이전트를 부르는 계약을 고정한다.

    한 단계만 빠지면 **그 단계의 오탐만 계속 같은 자리에서 반복되고**, 나머지가 멀쩡하니
    그 한 곳을 놓친다. 단계 목록에서 직접 돌리므로 단계를 더하면 이 테스트가 따라온다.

    Given: 앞 단계가 다 끝난 후보 폴더와 그 단계의 품질 실패 기록
    When: 그 단계를 돈다
    Then: 에이전트가 받은 지시문에 그 사유가 있다
    """
    ready = prepared()
    _record_quality_failure(ready.run_dir, step, REASON)
    seen: list[str] = []

    def ask(prompt: str) -> AgentResult:
        seen.append(prompt)
        raise _Stop

    with pytest.raises(_Stop):
        RUNNERS[step](ready, ask)

    assert REASON in seen[0]


def test_the_appended_words_pass_the_gate_they_serve() -> None:
    """
    목적: 붙이는 문구 «자체»가 자립성 게이트를 통과하는 계약을 고정한다.

    금지하는 표현을 지시문이 쓰면 그것은 지시가 아니라 **예시**가 된다 — 에이전트는
    프롬프트에서 받은 말을 제 답에 되돌려 쓴다.

    Given: 붙이는 문구
    When: 산출물에 거는 것과 같은 게이트에 넣는다
    Then: 걸리는 것이 없다
    """
    assert selfcontained.shortfall_reason({"SUFFIX": previous_failure.SUFFIX}) is None

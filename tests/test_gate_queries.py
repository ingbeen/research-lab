"""검색어 수 게이트의 계약을 고정한다.

**한 번 검색하고 멈추면 처음 걸린 것에 갇힌다.** 한국어와 영어는 결과 집합이 거의 겹치지 않고,
첫 검색이 알려준 «진짜 용어»로 다시 던져야 제대로 된 것이 나온다.
검색어를 하나만 던진 밤은 **조사한 것처럼 보이지만 조사가 아니다.**

[중요] 이 검사가 없으면 그런 밤도 「완주」로 끝난다 — 루트 `CLAUDE.md` 가
「프롬프트로 지시한 규율은 형식적으로만 지켜진다」고 못박은 자리다.
"""

import json
from pathlib import Path

import pytest

from research_lab.agent.invoke import AgentResult
from research_lab.gate import queries as query_gate
from research_lab.runner import collect, decision_log, failures, ledger, night, steps


def _answer(payload: object, *, cost: float | None = 0.5, tokens: int | None = 100) -> AgentResult:
    """에이전트가 그 JSON 을 돌려줬다고 치는 응답."""
    text = json.dumps(payload, ensure_ascii=False)
    return AgentResult(text=text, raw=text, cost_usd=cost, tokens=tokens, elapsed_seconds=1.0, session_id="세션")


def test_enough_queries_pass() -> None:
    """
    목적: 규율을 지킨 밤이 막히지 않는 계약을 고정한다.

    Given: 서로 다른 검색어 셋
    When: 검사한다
    Then: 사유가 없다
    """
    assert query_gate.shortfall_reason(["1월 효과", "january effect", "소형주 계절성"]) is None


def test_too_few_queries_are_blocked() -> None:
    """
    목적: 검색어가 모자라면 막는 계약을 고정한다.

    Given: 검색어 하나
    When: 검사한다
    Then: 사유가 나온다
    """
    assert query_gate.shortfall_reason(["1월 효과"]) is not None


def test_repeating_the_same_query_does_not_count() -> None:
    """
    목적: 같은 말을 여러 번 적은 것이 «갈아 끼운 것»으로 세어지지 않는 계약을 고정한다.

    숫자만 채우면 통과하는 게이트는 게이트가 아니다. 앞뒤 공백과 대소문자만 다른 것도
    같은 검색어로 본다.

    Given: 표기만 다른 같은 검색어 셋
    When: 검사한다
    Then: 막힌다
    """
    assert query_gate.shortfall_reason(["january effect", "January Effect", "  january effect  "]) is not None


def test_reason_says_what_to_do() -> None:
    """
    목적: 막을 때 «무엇이 왜 모자랐는지»를 함께 돌려주는 계약을 고정한다.

    「거부됨」만 돌려주면 다음 밤이 같은 시도를 반복한다.

    Given: 검색어 하나
    When: 검사한다
    Then: 개수와 기준, 그리고 던진 것이 사유에 들어 있다
    """
    reason = query_gate.shortfall_reason(["1월 효과"])

    assert reason is not None
    assert str(query_gate.MIN_QUERIES) in reason
    assert "1월 효과" in reason


def test_gate_failure_is_not_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 게이트가 막은 것을 «그 밤에 다시 부르지 않는» 계약을 고정한다.

    검색어 부족은 네트워크 끊김처럼 기다리면 풀리는 고장이 아니다. 「그 외」로 두면
    상한(3번)만큼 **full 예산으로 에이전트를 세 번 더 부르고도** 같은 자리에 설 공산이 크다.

    Given: 매번 게이트에 걸리는 단계
    When: 밤을 돈다
    Then: 한 번만 부르고, 「질」 갈래로 끝난다
    """
    monkeypatch.setattr(night, "sleep", lambda _: None)
    attempts: list[str] = []

    def blocked(step: str, _: Path) -> None:
        attempts.append(step)
        raise steps.StepQualityFailed("검색어 부족")

    result = night.run_night(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=blocked)

    assert len(attempts) == 1
    assert result.failure is not None
    assert result.failure.kind is failures.FailureKind.QUALITY


def test_blocked_candidate_stays_undug(tmp_path: Path) -> None:
    """
    목적: 게이트에 막힌 후보가 「안 판 것」으로 남는 계약을 고정한다.

    이것이 게이트를 `mark_explored` «앞»에 둔 이유다 — 되돌릴 것이 없다.
    뒤에 뒀다면 이미 표시된 후보를 되돌려야 하고, 되돌리면 무한 반복을 막는 장치가 또 필요하다.

    Given: 검색어를 하나만 던지는 수집
    When: 수집이 막힌다
    Then: 그 후보가 여전히 「다음에 팔 후보」다
    """
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    with pytest.raises(steps.StepQualityFailed):
        collect.run(tmp_path / "run", ledger_path, lambda _: _answer({"queries": ["하나뿐"], "evidence": []}))

    remaining = ledger.next_unexplored(ledger_path)
    assert remaining is not None
    assert remaining.claim == "첫 후보"


def test_cost_is_recorded_even_when_blocked(tmp_path: Path) -> None:
    """
    목적: 막혀서 끝난 밤도 «얼마를 썼는지»는 남기는 계약을 고정한다.

    게이트에 걸렸어도 그 호출은 이미 토큰을 썼다. 기록이 없으면 밤 예산을 정할 때
    그만큼이 통째로 빠진 값으로 계산된다.

    Given: 검색어를 하나만 던지는 수집
    When: 수집이 막힌다
    Then: 비용과 검색어가 결정 로그에 남아 있다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    with pytest.raises(steps.StepQualityFailed):
        collect.run(
            run_dir,
            ledger_path,
            lambda _: _answer({"queries": ["하나뿐"], "evidence": []}, cost=0.77, tokens=88),
        )

    entries = decision_log.read(run_dir)
    costs = [entry for entry in entries if entry["event"] == decision_log.EVENT_COST]
    blocked = [entry for entry in entries if entry.get("gate") == "queries"]
    assert costs[0]["cost_usd"] == 0.77
    assert blocked, "게이트가 막은 사유가 기록되지 않았습니다"

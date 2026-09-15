"""메커니즘(3·9번 칸)과 측정 설계(10번 칸) 단계가 남기는 것의 계약을 고정한다.

둘 다 **회차의 마지막이 아니다.** 「판 것」 표시는 판정 단계의 일이고, 여기서 표시하면
그 뒤 단계가 실패할 때 **후보가 남은 칸들 없이 「판 것」으로 남아 영영 다시 안 파진다** —
수집이 표시하던 때와 글자 하나 다르지 않은 고장이다.

[중요] 둘은 **앞 단계가 남긴 파일을 입력으로 먹는다.** 메커니즘은 찬성·반증의 출처를
받아야 「이미 소멸했다는 반박이 있었나」를 물을 수 있고, 측정 설계는 수집의 파라미터 축과
실현가능성의 시장·상품을 받아야 격자를 **그 후보에 맞게** 짤 수 있다. 안 실어 보내면
에이전트가 그것을 **새로 지어내고, 그 고장은 에러를 내지 않는다.**
"""

import json
from pathlib import Path
from typing import Any

import pytest

from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import MEASUREMENT_FILENAME, MECHANISM_FILENAME
from research_lab.runner import decision_log, ledger, measurement, mechanism
from research_lab.runner.steps import StepQualityFailed

# 준비물 픽스처가 만드는 앞 단계의 수. 메커니즘은 실현가능성까지 끝난 뒤에 돌고,
# 측정 설계는 메커니즘까지 끝난 뒤에 돈다
BEFORE_MECHANISM = 4
BEFORE_MEASUREMENT = 5


def _answer(payload: object) -> AgentResult:
    """에이전트가 그 JSON 을 돌려줬다고 치는 응답."""
    text = json.dumps(payload, ensure_ascii=False)
    return AgentResult(text=text, raw=text, cost_usd=0.3, tokens=80, usage=None, elapsed_seconds=1.0, session_id="세션")


# --------------------------------------------------------------------------
# 메커니즘 — 3·9번 칸
# --------------------------------------------------------------------------


def _mechanism_payload(**overrides: Any) -> dict[str, Any]:
    """게이트를 통과하는 메커니즘 산출물."""
    payload: dict[str, Any] = {
        "edge": {
            "risk_premium": "해당 없음 — 위험을 더 지는 구조가 아니다",
            "behavioral": "연말 절세 매도 뒤 되사기와 기관 윈도드레싱",
            "structural": "1월 신규 자금 유입",
        },
        "decay": {
            "post_publication": "발표로 널리 알려져 선반영됐을 수 있다",
            "regulatory": "한국은 양도세 구조가 달라 절세 매도 유인이 작다",
            "market_structure": "패시브 비중 확대로 연말 매도 압력이 옅어졌다",
        },
        "queries": ["january effect decay", "1월 효과 소멸"],
        "sources": [{"title": "소멸 연구", "url": "https://example.com/decay"}],
        "unverified": ["국내 절세 매도 유인의 실제 크기"],
    }
    payload.update(overrides)
    return payload


def test_mechanism_prompt_carries_the_gathered_sources(prepared: Any) -> None:
    """
    목적: [중요] 앞 단계가 모은 출처가 지시문에 실리는 계약을 고정한다.

    9번 칸(왜 사라졌을 수 있나)의 답은 대개 **반증 세션이 이미 찾아 둔 것**이다.
    안 실어 보내면 같은 것을 다시 검색하거나, 더 나쁘게는 **없는 근거를 지어낸다.**

    Given: 찬성·반증이 끝난 후보 폴더
    When: 단계를 돈다
    Then: 에이전트가 받은 지시문에 양쪽 출처가 들어 있다
    """
    ready = prepared(through=BEFORE_MECHANISM)
    seen: list[str] = []

    def ask(prompt: str) -> AgentResult:
        seen.append(prompt)
        return _answer(_mechanism_payload())

    mechanism.run(ready.run_dir, ask)

    assert "1월 효과 원논문" in seen[0]
    assert "발표 후 소멸했다" in seen[0]


def test_mechanism_writes_its_own_file(prepared: Any) -> None:
    """
    목적: 3·9번 칸을 «파일»로 남기는 계약을 고정한다.

    Given: 채워진 산출물을 내놓는 응답
    When: 단계를 돈다
    Then: 후보 폴더에 파일이 생기고 두 칸이 들어 있다
    """
    ready = prepared(through=BEFORE_MECHANISM)

    mechanism.run(ready.run_dir, lambda _: _answer(_mechanism_payload()))

    written = json.loads((ready.output_dir / MECHANISM_FILENAME).read_text(encoding="utf-8"))
    assert written["claim"] == ready.candidate.claim
    assert written["edge"]["behavioral"]
    assert written["decay"]["post_publication"]


def test_mechanism_does_not_mark_the_candidate_explored(prepared: Any) -> None:
    """
    목적: [중요] 이 단계가 「판 것」 표시를 «하지 않는» 계약을 고정한다.

    표시는 회차의 마지막 단계(판정)의 일이다. 여기서 표시하면 그 뒤 측정 설계와 판정이
    실패할 때 **후보가 10·2번 칸 없이 「판 것」으로 남아 영영 다시 안 파진다.**

    Given: 후보 하나가 든 원장
    When: 이 단계가 끝난다
    Then: 그 후보는 아직 «안 판 것»으로 남아 있다
    """
    ready = prepared(through=BEFORE_MECHANISM)

    mechanism.run(ready.run_dir, lambda _: _answer(_mechanism_payload()))

    assert ledger.next_unexplored(ready.ledger_path) is not None


def test_mechanism_is_blocked_when_a_slot_is_empty(prepared: Any) -> None:
    """
    목적: 칸이 비면 막고 파일도 안 남기는 계약을 고정한다.

    Given: 9번 칸 한 자리가 빈 산출물
    When: 단계를 돈다
    Then: 「질」 실패가 오르고 파일이 없다
    """
    ready = prepared(through=BEFORE_MECHANISM)
    broken = _mechanism_payload()
    broken["decay"]["regulatory"] = ""

    with pytest.raises(StepQualityFailed):
        mechanism.run(ready.run_dir, lambda _: _answer(broken))

    assert not (ready.output_dir / MECHANISM_FILENAME).exists()


def test_mechanism_is_blocked_when_a_source_url_does_not_exist(prepared: Any, probing: Any) -> None:
    """
    목적: 적어 낸 출처가 실재하지 않으면 막는 계약을 고정한다.

    이 단계는 웹을 돌 수 있으므로 **URL 이 태어나는 자리**다. 없는 출처를 지어내는 것이
    이 저장소에 남은 유일한 위조 위험이다.

    Given: 죽은 URL 이 든 출처
    When: 단계를 돈다
    Then: 「질」 실패가 오른다
    """
    ready = prepared(through=BEFORE_MECHANISM)
    probing(dead={"https://example.com/없는문서"})

    payload = _mechanism_payload(sources=[{"title": "지어낸 것", "url": "https://example.com/없는문서"}])

    with pytest.raises(StepQualityFailed):
        mechanism.run(ready.run_dir, lambda _: _answer(payload))


def test_mechanism_does_not_probe_when_a_cheaper_gate_already_blocked(prepared: Any, probing: Any) -> None:
    """
    목적: 값싼 게이트가 막았으면 «바깥을 두드리지 않는» 계약을 고정한다 (계층 계약 §6).

    Given: 칸 게이트에 막히는 산출물과 출처 URL
    When: 단계를 돈다
    Then: 막히고, 아무 URL 도 찔리지 않는다
    """
    ready = prepared(through=BEFORE_MECHANISM)
    probed = probing()

    broken = _mechanism_payload(sources=[{"url": "https://example.com/찌르면안된다"}])
    broken["edge"]["structural"] = ""

    with pytest.raises(StepQualityFailed):
        mechanism.run(ready.run_dir, lambda _: _answer(broken))

    assert probed == []


def test_mechanism_cost_survives_a_block(prepared: Any) -> None:
    """
    목적: 막혀서 끝나도 비용이 남는 계약을 고정한다.

    막힌 회차의 비용이 안 남으면 회차 예산을 정할 때 그만큼이 통째로 빠진 값이 된다.

    Given: 게이트에 막히는 산출물
    When: 단계를 돈다
    Then: 비용과 실패가 결정 로그에 남는다
    """
    ready = prepared(through=BEFORE_MECHANISM)
    broken = _mechanism_payload()
    broken["edge"]["risk_premium"] = ""

    with pytest.raises(StepQualityFailed):
        mechanism.run(ready.run_dir, lambda _: _answer(broken))

    events = {entry["event"] for entry in decision_log.read(ready.run_dir) if entry["step"] == mechanism.STEP_NAME}
    assert decision_log.EVENT_COST in events
    assert decision_log.EVENT_FAILED in events


def test_mechanism_without_a_pinned_candidate_is_an_invariant_violation(tmp_path: Path) -> None:
    """
    목적: 그 회차의 후보가 없으면 «고장»으로 터지는 계약을 고정한다.

    러너가 건너뛰었어야 하는 자리다 (`steps.CANDIDATE_STEPS`).

    Given: 후보가 안 박힌 실행 폴더
    When: 단계를 돈다
    Then: 내부 불변조건 위반으로 터진다
    """
    with pytest.raises(RuntimeError):
        mechanism.run(tmp_path / "run", lambda _: _answer(_mechanism_payload()))


# --------------------------------------------------------------------------
# 측정 설계 — 10번 칸
# --------------------------------------------------------------------------


def _measurement_payload(**overrides: Any) -> dict[str, Any]:
    """게이트를 통과하는 측정 설계 산출물."""
    payload: dict[str, Any] = {
        "instrument": "코스닥150 을 추종하는 국내 상장 ETF. 지수가 아니라 살 수 있는 상품이다",
        "no_lookahead": "진입·청산이 달력만 보면 정해진다",
        "entry_grid": ["12월 20일", "12월 23일", "12월 26일"],
        "holding_grid": [20, 40, 60],
        "baseline": "같은 보유 기간을 아무 날에나 시작했을 때의 전체 평균",
        "direction": "위·아래를 미리 정하지 않는다",
        "expected_samples": "연 1회 x 20년 = 20건",
        "unverified": ["2000년 이전 코스닥 데이터 품질"],
    }
    payload.update(overrides)
    return payload


def test_measurement_prompt_carries_params_and_instrument(prepared: Any) -> None:
    """
    목적: [중요] 앞 단계의 «파라미터 축»과 «시장·상품»이 지시문에 실리는 계약을 고정한다.

    수집이 이미 「무엇을 얼마로 바꿀 수 있는지」를 축으로 냈고, 실현가능성이 「살 수 있는
    상품이 무엇인지」를 냈다. 안 실어 보내면 측정 설계가 그것을 **새로 지어내고**,
    그 순간 같은 후보의 두 칸이 서로 다른 말을 한다.

    Given: 앞 단계들이 끝난 후보 폴더
    When: 단계를 돈다
    Then: 파라미터 축과 시장·상품이 지시문에 들어 있다
    """
    ready = prepared(through=BEFORE_MEASUREMENT)
    seen: list[str] = []

    def ask(prompt: str) -> AgentResult:
        seen.append(prompt)
        return _answer(_measurement_payload())

    measurement.run(ready.run_dir, ask)

    assert "보유 기간" in seen[0]
    assert "코스닥150" in seen[0]
    assert "국내" in seen[0]


def test_measurement_writes_its_own_file(prepared: Any) -> None:
    """
    목적: 10번 칸을 «파일»로 남기는 계약을 고정한다.

    이 칸이 파일로 박히는 순간 **사전등록**이 따라온다 — 재기 전에 측정 방법이 고정되므로
    결과를 보고 기준을 고치는 일이 구조적으로 막힌다.

    Given: 채워진 산출물을 내놓는 응답
    When: 단계를 돈다
    Then: 후보 폴더에 파일이 생기고 격자가 들어 있다
    """
    ready = prepared(through=BEFORE_MEASUREMENT)

    measurement.run(ready.run_dir, lambda _: _answer(_measurement_payload()))

    written = json.loads((ready.output_dir / MEASUREMENT_FILENAME).read_text(encoding="utf-8"))
    assert written["entry_grid"] == ["12월 20일", "12월 23일", "12월 26일"]
    assert written["holding_grid"] == [20, 40, 60]
    assert written["baseline"]


def test_measurement_does_not_mark_the_candidate_explored(prepared: Any) -> None:
    """
    목적: 이 단계도 「판 것」 표시를 «하지 않는» 계약을 고정한다.

    Given: 후보 하나가 든 원장
    When: 이 단계가 끝난다
    Then: 그 후보는 아직 안 판 것으로 남아 있다
    """
    ready = prepared(through=BEFORE_MEASUREMENT)

    measurement.run(ready.run_dir, lambda _: _answer(_measurement_payload()))

    assert ledger.next_unexplored(ready.ledger_path) is not None


def test_measurement_is_blocked_when_a_grid_is_a_single_value(prepared: Any) -> None:
    """
    목적: 격자가 한 값인데 사유가 없으면 막고 파일도 안 남기는 계약을 고정한다.

    Given: 한 값짜리 진입 격자
    When: 단계를 돈다
    Then: 「질」 실패가 오르고 파일이 없다
    """
    ready = prepared(through=BEFORE_MEASUREMENT)

    with pytest.raises(StepQualityFailed):
        measurement.run(ready.run_dir, lambda _: _answer(_measurement_payload(entry_grid=["12월 20일"])))

    assert not (ready.output_dir / MEASUREMENT_FILENAME).exists()


def test_measurement_records_what_it_judged(prepared: Any) -> None:
    """
    목적: 무엇을 놓고 판단했는지 결정 로그에 남기는 계약을 고정한다.

    격자 크기가 로그에 있어야 나중에 「격자를 한 값으로 낸 후보가 몇이었나」를 셀 수 있다.

    Given: 채워진 산출물
    When: 단계를 돈다
    Then: 격자 크기가 결정 로그에 남는다
    """
    ready = prepared(through=BEFORE_MEASUREMENT)

    measurement.run(ready.run_dir, lambda _: _answer(_measurement_payload()))

    judged = [
        entry
        for entry in decision_log.read(ready.run_dir)
        if entry["step"] == measurement.STEP_NAME and entry["event"] == decision_log.EVENT_JUDGED
    ]
    assert judged[0]["entry_grid_size"] == 3
    assert judged[0]["holding_grid_size"] == 3

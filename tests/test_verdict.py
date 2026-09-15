"""판정 단계가 남기는 것의 계약을 고정한다 — 2번 칸 · 근거 문서 · 「판 것」 표시.

**이 단계가 회차의 마지막이다.** 그래서 「판 것」 표시가 여기로 옮겨왔다. 앞 단계가
표시하면 그 뒤 이 단계가 실패할 때 **후보가 판정 없이 「판 것」으로 남아 영영 다시
안 파진다** — 수집이 표시하던 때와, 계보가 표시하던 때와, 실현가능성이 표시하던 때와
글자 하나 다르지 않은 고장이다. 계층 계약 §4 가 「단계를 뒤에 더할 때마다 표시가 함께
옮겨간다」를 규칙으로 박아 둔 이유가 이것이다.

[중요] 판정은 **맨 마지막에** 쓴다. 측정 설계와 한 호출에 담으면 에이전트가 판정을 먼저
정하고 측정 설계를 거기 맞출 수 있다 — 이 저장소는 프롬프트 지시가 형식적으로만 지켜진
것을 세 번 확인했으므로, 순서를 지시가 아니라 **단계 경계로** 보장한다.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import LINEAGE_FILENAME, VERDICT_FILENAME
from research_lab.runner import decision_log, dossier, ledger, verdict
from research_lab.runner.steps import StepQualityFailed


def _answer(payload: object) -> AgentResult:
    """에이전트가 그 JSON 을 돌려줬다고 치는 응답."""
    text = json.dumps(payload, ensure_ascii=False)
    return AgentResult(text=text, raw=text, cost_usd=0.2, tokens=70, usage=None, elapsed_seconds=1.0, session_id="세션")


def _payload(**overrides: Any) -> dict[str, Any]:
    """게이트를 통과하는 판정 산출물."""
    payload: dict[str, Any] = {
        "verdict": "보류",
        "reason": "경제적 근거는 있으나 표본이 20건이라 시기를 둘로 쪼개면 칸당 10건이다",
        "criteria": "칸당 10건 미만이면 우연과 구별되지 않으므로 「어느 시기가 만든 값인가」를 물을 수 없다",
        "unverified_extra": ["판정 단계에서 새로 드러난 것"],
    }
    payload.update(overrides)
    return payload


def test_prompt_carries_every_earlier_output(prepared: Any) -> None:
    """
    목적: [중요] 앞 단계의 산출물이 «전부» 지시문에 실리는 계약을 고정한다.

    판정은 앞의 것을 읽고 내리는 일이다. 안 실어 보내면 에이전트가 한 줄 주장만 보고
    **자기가 아는 것으로 판정하게 되고**, 그러면 그 회차가 모은 근거는 결론에 닿지 않는다.

    Given: 앞 여섯 단계가 끝난 후보 폴더
    When: 단계를 돈다
    Then: 찬성·반증·계보·4·5번 칸·메커니즘·측정 설계가 모두 지시문에 들어 있다
    """
    ready = prepared()
    seen: list[str] = []

    def ask(prompt: str) -> AgentResult:
        seen.append(prompt)
        return _answer(_payload())

    verdict.run(ready.run_dir, ready.ledger_path, ask, dossier_dir=ready.dossier_dir)

    for expected in ("1월 효과 원논문", "발표 후 소멸했다", "윈도드레싱", "pykrx", "연 1회", "12월 23일"):
        assert expected in seen[0], expected


def test_writes_its_own_file(prepared: Any) -> None:
    """
    목적: 2번 칸을 «파일»로 남기는 계약을 고정한다.

    Given: 채워진 산출물을 내놓는 응답
    When: 단계를 돈다
    Then: 후보 폴더에 판정 파일이 생긴다
    """
    ready = prepared()

    verdict.run(ready.run_dir, ready.ledger_path, lambda _: _answer(_payload()), dossier_dir=ready.dossier_dir)

    written = json.loads((ready.output_dir / VERDICT_FILENAME).read_text(encoding="utf-8"))
    assert written["verdict"] == "보류"
    assert written["criteria"]


def test_writes_the_dossier(prepared: Any) -> None:
    """
    목적: **이 파이프라인의 제품**이 실제로 나오는 계약을 고정한다.

    단계 산출물만 남고 문서가 안 나오면 이 저장소는 아무것도 만들지 않은 것이다.

    Given: 앞 여섯 단계가 끝난 후보 폴더
    When: 단계를 돈다
    Then: 근거 문서가 생기고 11칸이 들어 있다
    """
    ready = prepared()

    verdict.run(ready.run_dir, ready.ledger_path, lambda _: _answer(_payload()), dossier_dir=ready.dossier_dir)

    written = dossier.path_for(ready.run_dir, ready.candidate, dossier_dir=ready.dossier_dir)
    assert written.is_file()
    assert "## 11." in written.read_text(encoding="utf-8")


def test_marks_the_candidate_explored(prepared: Any) -> None:
    """
    목적: [중요] 「판 것」 표시를 «이 단계»가 하는 계약을 고정한다.

    Given: 후보 하나가 든 원장
    When: 이 단계까지 끝난다
    Then: 그 후보가 판 것으로 표시돼 다음 후보가 없다
    """
    ready = prepared()

    assert ledger.next_unexplored(ready.ledger_path) is not None

    verdict.run(ready.run_dir, ready.ledger_path, lambda _: _answer(_payload()), dossier_dir=ready.dossier_dir)

    assert ledger.next_unexplored(ready.ledger_path) is None


def test_writes_the_documents_before_marking(prepared: Any) -> None:
    """
    목적: 파일을 쓴 «뒤»에 표시하는 계약을 고정한다.

    순서가 반대면 산출물 없이 후보만 「판 것」으로 남는다 — 그 후보는 다시 안 파지므로
    판정 칸이 영영 비어 있게 되고, **나중에는 완주한 회차처럼 보인다.**

    Given: 게이트에 막히는 산출물
    When: 단계를 돈다
    Then: 막히고, 문서도 없고, 후보는 안 판 것으로 남는다
    """
    ready = prepared()

    with pytest.raises(StepQualityFailed):
        verdict.run(
            ready.run_dir, ready.ledger_path, lambda _: _answer(_payload(criteria="")), dossier_dir=ready.dossier_dir
        )

    assert not dossier.path_for(ready.run_dir, ready.candidate, dossier_dir=ready.dossier_dir).exists()
    assert ledger.next_unexplored(ready.ledger_path) is not None


def test_a_missing_earlier_output_leaves_the_candidate_unexplored(prepared: Any) -> None:
    """
    목적: [중요] 조립에 실패하면 후보가 «안 판 것»으로 남는 계약을 고정한다.

    표시를 조립보다 먼저 하면 **문서 없는 후보가 닫히고**, 그 회차는 완주한 것처럼 보인다.
    이 단계가 파일 셋을 순서대로 만드는 자리라 순서가 곧 계약이다.

    Given: 앞 단계 파일 하나가 사라진 후보 폴더
    When: 단계를 돈다
    Then: 막히고 후보는 안 판 것으로 남는다
    """
    ready = prepared()
    (ready.output_dir / LINEAGE_FILENAME).unlink()

    with pytest.raises(StepQualityFailed):
        verdict.run(ready.run_dir, ready.ledger_path, lambda _: _answer(_payload()), dossier_dir=ready.dossier_dir)

    assert ledger.next_unexplored(ready.ledger_path) is not None


def test_cost_and_the_verdict_are_recorded(prepared: Any) -> None:
    """
    목적: 판정 결과가 «기계가 읽을 수 있게» 남는 계약을 고정한다.

    이 값이 로그에 있어야 나중에 「판정이 어떻게 갈렸나」를 셀 수 있다.
    회차마다 「잴 가치 있음」이 나온다면 그것이 고장 신호다.

    Given: 「보류」로 판정한 산출물
    When: 단계를 돈다
    Then: 비용과 판정이 결정 로그에 남는다
    """
    ready = prepared()

    verdict.run(ready.run_dir, ready.ledger_path, lambda _: _answer(_payload()), dossier_dir=ready.dossier_dir)

    entries = [entry for entry in decision_log.read(ready.run_dir) if entry["step"] == verdict.STEP_NAME]
    assert decision_log.EVENT_COST in {entry["event"] for entry in entries}

    judged = [entry for entry in entries if entry["event"] == decision_log.EVENT_JUDGED]
    assert judged[0]["verdict"] == "보류"


def test_without_a_pinned_candidate_it_is_an_invariant_violation(tmp_path: Path) -> None:
    """
    목적: 그 회차의 후보가 없으면 «고장»으로 터지는 계약을 고정한다.

    Given: 후보가 안 박힌 실행 폴더
    When: 단계를 돈다
    Then: 내부 불변조건 위반으로 터진다
    """
    with pytest.raises(RuntimeError):
        verdict.run(tmp_path / "run", tmp_path / "원장.md", lambda _: _answer(_payload()))


# --------------------------------------------------------------------------
# 판정 못 한 주소를 «회차의 로그에서» 모아 문서로 넘긴다
# --------------------------------------------------------------------------

BLOCKED_URL = "https://ssrn.example/abstract=1"
OTHER_BLOCKED_URL = "https://sec.example/filing"


def _record_url_check(run_dir: Path, step: str, *, unknown: list[str]) -> None:
    """수집·반증이 URL 을 찌르고 남기는 줄을 흉내 낸다."""
    from research_lab.gate import urls as url_gate
    from research_lab.runner import url_check

    decision_log.record(
        run_dir,
        step,
        decision_log.EVENT_READ,
        gate=url_check.GATE_NAME,
        alive=1,
        dead=0,
        unknown=len(unknown),
        unknown_details=["HEAD 403"],
        **{url_gate.KEY_UNKNOWN_URLS: unknown},
    )


def test_unjudged_urls_from_every_step_reach_the_document(prepared: Any) -> None:
    """
    목적: [중요] 회차 «전체»의 판정 못 한 주소가 근거 문서에 닿는 계약을 고정한다.

    수집과 반증이 각자 자기 출처를 찌르므로 그 기록이 단계별로 흩어져 있다. 한 단계만
    보면 나머지가 조용히 빠지고, **빠졌다는 사실은 아무 에러도 내지 않는다** —
    문서를 받는 쪽은 그 주소가 확인된 것이라고 읽게 된다.

    Given: 수집과 반증이 각각 판정 못 한 주소를 남긴 회차
    When: 판정 단계를 돈다
    Then: 둘 다 근거 문서에 들어 있다
    """
    ready = prepared()
    _record_url_check(ready.run_dir, "collect", unknown=[BLOCKED_URL])
    _record_url_check(ready.run_dir, "rebut", unknown=[OTHER_BLOCKED_URL])

    verdict.run(ready.run_dir, ready.ledger_path, lambda _: _answer(_payload()), dossier_dir=ready.dossier_dir)

    written = next(ready.dossier_dir.glob("*.md")).read_text(encoding="utf-8")

    assert BLOCKED_URL in written
    assert OTHER_BLOCKED_URL in written


def test_a_cycle_without_unjudged_urls_says_nothing_about_them(prepared: Any) -> None:
    """
    목적: 판정 못 한 주소가 없으면 문서가 그 이야기를 «안 하는» 계약을 고정한다.

    Given: URL 을 전부 판정한 회차
    When: 판정 단계를 돈다
    Then: 확인 못 했다는 줄이 없다
    """
    ready = prepared()
    _record_url_check(ready.run_dir, "collect", unknown=[])

    verdict.run(ready.run_dir, ready.ledger_path, lambda _: _answer(_payload()), dossier_dir=ready.dossier_dir)

    written = next(ready.dossier_dir.glob("*.md")).read_text(encoding="utf-8")

    assert "ssrn.example" not in written


def test_a_broken_url_check_line_does_not_stop_the_step(prepared: Any) -> None:
    """
    목적: 결정 로그의 모양이 어긋나도 판정 단계가 «끝까지 도는» 계약을 고정한다.

    [중요] 이 값은 **문서에 덧붙이는 말**이지 판정의 입력이 아니다. 여기서 터지면
    앞 단계 비용을 다 치른 회차가 **마지막에 깨지고**, 근거 문서가 안 나온다.
    「판정을 못 하는 것」과 「실패로 판정하는 것」은 다르다.

    Given: 목록 자리에 문자열이 든 어긋난 기록
    When: 판정 단계를 돈다
    Then: 예외 없이 문서가 나온다
    """
    from research_lab.gate import urls as url_gate
    from research_lab.runner import url_check

    ready = prepared()
    decision_log.record(
        ready.run_dir,
        "collect",
        decision_log.EVENT_READ,
        gate=url_check.GATE_NAME,
        **{url_gate.KEY_UNKNOWN_URLS: "주소가-아니라-문자열"},
    )

    verdict.run(ready.run_dir, ready.ledger_path, lambda _: _answer(_payload()), dossier_dir=ready.dossier_dir)

    assert next(ready.dossier_dir.glob("*.md")).is_file()

"""탐색과 수집이 남기는 것의 계약을 고정한다.

두 단계는 **같은 호출 계층**을 쓴다. 여기서 그 계층을 흉내 낸 것을 넣어 검사하는 이유는,
계층이 한 단계에 맞춰 깎이면 다음 단계에서 다시 갈라지기 때문이다.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from research_lab.agent.invoke import AgentResult
from research_lab.runner import collect, decision_log, explore, ledger, naming, state
from research_lab.runner.steps import StepFailed, StepQualityFailed


def _answer(payload: object, *, cost: float | None = 0.5, tokens: int | None = 100) -> AgentResult:
    """에이전트가 그 JSON 을 돌려줬다고 치는 응답."""
    text = json.dumps(payload, ensure_ascii=False)
    return AgentResult(
        text=text,
        raw=text,
        cost_usd=cost,
        tokens=tokens,
        usage=None,
        elapsed_seconds=1.0,
        session_id="세션",
    )


# --------------------------------------------------------------------------
# 탐색
# --------------------------------------------------------------------------


def test_explore_fills_the_ledger(tmp_path: Path) -> None:
    """
    목적: 탐색이 빈 원장을 채우는 계약을 고정한다.

    이것이 「사람이 후보를 적어 넣지 않아도 첫 회차가 돈다」의 실체다.

    Given: 후보 둘을 내놓는 에이전트
    When: 탐색을 돈다
    Then: 원장에 둘이 담긴다
    """
    ledger_path = tmp_path / "원장.md"
    answer = _answer(
        {
            "queries": ["1월 효과", "january effect", "small cap january"],
            "candidates": [{"claim": "첫 후보"}, {"claim": "둘째 후보"}],
        }
    )

    explore.run(tmp_path / "run", ledger_path, lambda _: answer)

    assert [entry.claim for entry in ledger.load(ledger_path)] == ["첫 후보", "둘째 후보"]


def test_explore_records_every_query(tmp_path: Path) -> None:
    """
    목적: 던진 검색어가 하나도 빠지지 않고 남는 계약을 고정한다.

    「무엇을 읽었나」가 없으면 나중에 **이 결론이 어디서 왔는지 되짚을 수 없다.**

    Given: 검색어 셋을 적어 낸 응답
    When: 탐색을 돈다
    Then: 결정 로그에 셋이 그대로 남는다
    """
    run_dir = tmp_path / "run"
    queries = ["1월 효과", "january effect", "소형주 계절성"]
    answer = _answer({"queries": queries, "candidates": [{"claim": "후보"}]})

    explore.run(run_dir, tmp_path / "원장.md", lambda _: answer)

    read_entries = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_READ]
    assert read_entries[0]["queries"] == queries
    assert read_entries[0]["query_count"] == 3


def test_explore_does_not_readd_known_candidates(tmp_path: Path) -> None:
    """
    목적: 이미 본 후보를 다시 담지 않는 계약을 고정한다.

    Given: 원장에 이미 있는 후보를 다시 내놓는 응답
    When: 탐색을 돈다
    Then: 원장이 늘지 않고, 버린 사실이 로그에 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")
    answer = _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "candidates": [{"claim": "첫 후보"}]})

    explore.run(run_dir, ledger_path, lambda _: answer)

    assert len(ledger.load(ledger_path)) == 1
    discarded = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_DISCARDED]
    assert discarded and discarded[0]["claims"] == ["첫 후보"]


def test_explore_tells_the_agent_what_is_already_known(tmp_path: Path) -> None:
    """
    목적: 이미 본 후보를 프롬프트가 알려 주는 계약을 고정한다.

    안 알려 주면 에이전트가 매번 같은 후보를 내고, 러너가 걸러 내긴 하지만
    **그만큼 그 회차의 탐색이 헛돈다.**

    Given: 후보가 든 원장
    When: 지시문을 만든다
    Then: 그 후보가 지시문에 들어 있다
    """
    assert "첫 후보" in explore.build_prompt(["첫 후보"])


def test_explore_rejects_non_json_answer(tmp_path: Path) -> None:
    """
    목적: 약속한 모양이 아닌 응답을 «실패»로 넘기는 계약을 고정한다.

    조용히 넘어가면 그 회차는 아무것도 안 담은 채 「성공」으로 끝난다.

    Given: JSON 이 아닌 응답
    When: 탐색을 돈다
    Then: StepFailed 가 오르고 원문이 실려 있다
    """
    answer = AgentResult(
        text="미안, JSON 이 아니라 줄글로 적었어",
        raw="미안, JSON 이 아니라 줄글로 적었어",
        cost_usd=None,
        tokens=None,
        usage=None,
        elapsed_seconds=1.0,
        session_id="세션",
    )

    with pytest.raises(StepFailed, match="줄글"):
        explore.run(tmp_path / "run", tmp_path / "원장.md", lambda _: answer)


# --------------------------------------------------------------------------
# 수집
# --------------------------------------------------------------------------


def test_collect_writes_evidence_and_queries(tmp_path: Path) -> None:
    """
    목적: 수집이 찬성 근거와 검색어를 «파일»로 남기는 계약을 고정한다.

    이것이 이 계획서의 기능 요구사항이다. 화면에 쓴 것은 아무도 안 본다.

    Given: 근거 하나를 내놓는 응답
    When: 수집을 돈다
    Then: 두 파일이 생기고 내용이 들어 있다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")
    answer = _answer(
        {
            "claim": "첫 후보",
            "queries": ["ㄱ", "ㄴ", "a"],
            "evidence": [{"title": "논문", "url": "https://example.com/p", "kind": "primary"}],
            "unverified": ["국내 적용 여부"],
        }
    )

    collect.run(run_dir, ledger_path, lambda _: answer)

    # 산출물은 «후보별 폴더» 안에 있다 — 한 회차가 후보 둘을 파도 덮어쓰지 않는다
    output_dir = run_dir / naming.slug("첫 후보")
    evidence = json.loads((output_dir / "찬성근거.json").read_text(encoding="utf-8"))
    queries = json.loads((output_dir / "검색어.json").read_text(encoding="utf-8"))
    assert evidence["claim"] == "첫 후보"
    assert evidence["evidence"][0]["url"] == "https://example.com/p"
    assert evidence["unverified"] == ["국내 적용 여부"]
    assert queries["queries"] == ["ㄱ", "ㄴ", "a"]


def test_collect_pins_the_candidate_for_the_later_steps(tmp_path: Path) -> None:
    """
    목적: 수집이 그 회차의 후보를 «상태에 박는» 계약을 고정한다.

    [중요] 뒤따르는 반증·계보가 **같은 후보**를 봐야 한다. 원장에 매번 「다음에 팔 후보」를
    새로 물으면 표시 시점에 따라 다른 후보가 돌아온다.

    Given: 후보 하나가 든 원장
    When: 수집을 돈다
    Then: 그 후보가 상태에 박힌다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    collect.run(run_dir, ledger_path, lambda _: _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": []}))

    pinned = state.pinned_candidate(run_dir)
    assert pinned is not None
    assert pinned.claim == "첫 후보"


def test_collect_does_not_mark_the_candidate_explored(tmp_path: Path) -> None:
    """
    목적: 수집이 후보를 «아직» 판 것으로 표시하지 않는 계약을 고정한다.

    [중요] 표시를 여기서 하면, 그 뒤 반증이 실패해 그 실행 폴더가 버려질 때
    **후보가 반증 없이 「판 것」으로 남아 영영 다시 안 파진다.** 표시는 마지막 단계의 일이다.

    Given: 후보 하나가 든 원장
    When: 수집을 돈다
    Then: 그 후보가 여전히 「다음에 팔 후보」다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    collect.run(run_dir, ledger_path, lambda _: _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": []}))

    remaining = ledger.next_unexplored(ledger_path)
    assert remaining is not None
    assert remaining.claim == "첫 후보"


def test_collect_treats_no_evidence_as_a_normal_verdict(tmp_path: Path) -> None:
    """
    목적: 찬성 근거 0건을 «고장»이 아니라 결과로 다루는 계약을 고정한다.

    원래 존재하지 않는 매매법이면 근거가 없는 것이 맞다. 실패로 다루면
    에이전트가 다음부터 **억지로 채운다.**

    Given: 근거가 하나도 없는 응답
    When: 수집을 돈다
    Then: 예외 없이 끝나고 판정이 「실체 없음」으로 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    collect.run(run_dir, ledger_path, lambda _: _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": []}))

    judged = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_JUDGED]
    assert judged[0]["verdict"] == "실체 없음"


def test_collect_records_cost_and_tokens(tmp_path: Path) -> None:
    """
    목적: 비용·토큰이 «저장소 안»에 남는 계약을 고정한다.

    이것이 있어야 회차 예산 집계가 컨테이너의 세션 로그에 의존하지 않고,
    기계를 옮겨도 과거 기록이 따라온다.

    Given: 비용과 토큰을 돌려준 응답
    When: 수집을 돈다
    Then: 결정 로그에 그 값이 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    collect.run(
        run_dir,
        ledger_path,
        lambda _: _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": []}, cost=0.42, tokens=999),
    )

    costs = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_COST]
    assert costs[0]["cost_usd"] == 0.42
    assert costs[0]["tokens"] == 999


def test_collect_without_candidate_is_rejected(tmp_path: Path) -> None:
    """
    목적: 팔 후보가 없을 때 «조용히» 넘어가지 않는 계약을 고정한다.

    빈손으로 성공 처리하면 그 회차는 「완주」로 기록되고, 나중에 산출물만 없다.

    Given: 빈 원장
    When: 수집을 돈다
    Then: 예외가 오른다
    """
    with pytest.raises(collect.NoCandidateError):
        collect.run(tmp_path / "run", tmp_path / "원장.md", lambda _: _answer({}))


def test_collect_prompt_forbids_counter_evidence(tmp_path: Path) -> None:
    """
    목적: 수집 단계가 반증을 찾지 «않게» 지시하는 계약을 고정한다.

    찬성 근거를 잔뜩 모은 맥락이 쌓인 상태에서 반증을 찾으라고 하면,
    자기가 방금 지지한 것을 스스로 무너뜨리라는 요구가 된다. 별도 세션의 일이다.

    Given: 수집 지시문
    When: 내용을 본다
    Then: 반증을 찾지 말라는 지시가 들어 있다
    """
    assert "반증은 찾지 마세요" in collect.build_prompt("아무 후보")


def test_explore_ignores_a_string_where_a_list_was_promised(tmp_path: Path) -> None:
    """
    목적: 목록 자리에 문자열이 와도 «글자 단위로 잘리지 않는» 계약을 고정한다.

    에이전트가 목록 대신 문자열 하나를 내놓는 것은 흔한 어긋남이다. 그때 `"없음"` 이
    후보 `'없'` 과 `'음'` 둘로 원장에 담기면, 원장은 append-only 이고 **중복 방지의 전부**라
    그 쓰레기가 이후 회차마다 수집 호출을 한 번씩 잡아먹는다. 예외는 나지 않는다.

    Given: queries 와 candidates 가 문자열인 응답
    When: 탐색을 돈다
    Then: 원장이 비어 있고 검색어도 세어지지 않는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"

    # 목록이 아니므로 검색어도 후보도 하나도 안 잡히고, 그 결과 검색어 게이트에도 걸린다
    with pytest.raises(StepQualityFailed):
        explore.run(run_dir, ledger_path, lambda _: _answer({"queries": "1월 효과", "candidates": "없음"}))

    assert ledger.load(ledger_path) == []
    read_entries = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_READ]
    assert read_entries[0]["query_count"] == 0


# --------------------------------------------------------------------------
# 정성 표현과 기각
#
# 정성 표현은 «기각 사유»가 아니라 «해명 요구»다. 「짧은 기간」은 격자로 받으면 재지고,
# 「옥석을 가려」는 채울 축이 없어 못 잰다. 둘을 가르는 것은 사전이 아니라
# **파라미터를 낼 수 있는가**이므로, 게이트는 그것이 적혔는지만 본다.
# --------------------------------------------------------------------------

_GRID = [{"name": "보유 기간", "unit": "거래일", "candidates": [5, 20, 60]}]


def test_explore_keeps_a_candidate_that_explains_its_parameters(tmp_path: Path) -> None:
    """
    목적: 해명된 정성 표현이 탐색에서 «살아남는» 계약을 고정한다.

    이 계약이 없으면 사전을 키울 때마다 멀쩡한 후보가 함께 죽는다.

    Given: 「단기」가 들었지만 격자를 함께 낸 후보
    When: 탐색을 돈다
    Then: 원장에 담긴다
    """
    ledger_path = tmp_path / "원장.md"
    answer = _answer(
        {
            "queries": ["ㄱ", "ㄴ", "ㄷ"],
            "candidates": [{"claim": "공시 다음날 사서 단기 보유한다", "identifier": "buyback-kr", "params": _GRID}],
        }
    )

    explore.run(tmp_path / "run", ledger_path, lambda _: answer)

    assert [entry.claim for entry in ledger.load(ledger_path)] == ["공시 다음날 사서 단기 보유한다"]


def test_explore_rejects_a_candidate_that_cannot_be_measured(tmp_path: Path) -> None:
    """
    목적: 못 잴 후보가 «원장에 쌓이지 않는» 계약을 고정한다.

    원장에 들어가면 그 후보는 언젠가 회차 하나를 통째로 가져간다. 실측에서 첫 탐색이 낸
    후보 15개 중 다수가 정성적이었고, 그것이 이 게이트를 만든 이유다.

    Given: 「옥석을 가려」가 들었고 파라미터가 없는 후보
    When: 탐색을 돈다
    Then: 팔 후보가 되지 않고, 사유가 원장과 로그에 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    answer = _answer(
        {
            "queries": ["ㄱ", "ㄴ", "ㄷ"],
            "candidates": [{"claim": "상장 후 하락한 종목 중 옥석을 가려 매수한다", "identifier": "spac-kr"}],
        }
    )

    explore.run(run_dir, ledger_path, lambda _: answer)

    # 원장에 «기각»으로 남는다 — 지우면 다음 탐색이 같은 후보를 다시 담고 또 기각한다.
    # 루트 CLAUDE.md 가 「버릴 때는 원장에 사유와 함께 남겨 다음에 또 파지 않게 한다」고 정한 자리다
    assert ledger.next_unexplored(ledger_path) is None
    assert "옥석" in ledger_path.read_text(encoding="utf-8")
    discarded = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_DISCARDED]
    assert any("옥석" in str(entry.get("reason", "")) for entry in discarded)


def test_explore_stores_the_identifier(tmp_path: Path) -> None:
    """
    목적: 탐색이 낸 짧은 식별자가 원장에 담기는 계약을 고정한다.

    Given: 식별자를 함께 낸 후보
    When: 탐색을 돈다
    Then: 그 식별자가 원장에 남는다
    """
    ledger_path = tmp_path / "원장.md"
    answer = _answer(
        {
            "queries": ["ㄱ", "ㄴ", "ㄷ"],
            "candidates": [{"claim": "분할 상장한 자회사를 상장 당일 종가에 사서 12개월 보유한다", "identifier": "spin-off"}],
        }
    )

    explore.run(tmp_path / "run", ledger_path, lambda _: answer)

    assert ledger.load(ledger_path)[0].identifier == "spin-off"


def test_collect_rejects_and_moves_to_the_next_candidate(tmp_path: Path) -> None:
    """
    목적: 해명에 실패한 후보를 «기각하고 다음으로 넘어가는» 계약을 고정한다.

    [중요] 이 경로가 있어야 **이미 쌓인 후보도 같은 문을 지난다.** 탐색에서만 걸면
    예전 후보는 그대로 팔린다. 그리고 기각은 «실패»가 아니라 판정의 결과라 회차가 멈추지 않는다.

    Given: 첫 후보는 해명하지 못하고 둘째는 해명하는 에이전트
    When: 수집을 돈다
    Then: 첫 후보가 사유와 함께 기각되고, 둘째가 그 회차의 후보가 된다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "신주 상장 이후 저점에서 재매수한다")
    ledger.append(ledger_path, "11월 첫 거래일에 사서 4월 마지막 거래일에 판다")

    # 둘 다 파라미터를 못 내는 같은 응답이다. 가르는 것은 응답이 아니라 «한 줄 주장»이며,
    # 「저점」은 사전에 걸리고 「11월 첫 거래일」은 걸리지 않는다
    collect.run(run_dir, ledger_path, lambda _: _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": [], "params": []}))

    pinned = state.pinned_candidate(run_dir)
    assert pinned is not None
    assert pinned.claim == "11월 첫 거래일에 사서 4월 마지막 거래일에 판다"
    assert "저점" in ledger_path.read_text(encoding="utf-8")


def test_collect_stops_at_the_rejection_cap(tmp_path: Path) -> None:
    """
    목적: 한 회차의 기각에 «상한»이 걸리는 계약을 고정한다.

    상한이 없으면 원장이 전부 기각될 때까지 호출을 태운다. 나중에 보면 예산은 줄었고
    산출물은 0장인데, 그런 회차는 「아무 일 없음」처럼 보여 며칠 지나서야 알아챈다.

    Given: 모두 해명 불가인 후보가 상한보다 많이 든 원장
    When: 수집을 돈다
    Then: 상한만큼만 부르고 그 회차의 수집이 끝난다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    for index in range(collect.MAX_REJECTIONS + 3):
        ledger.append(ledger_path, f"옥석을 가려 {index}번 종목을 산다")

    calls: list[str] = []

    def answering(prompt: str) -> AgentResult:
        calls.append(prompt)
        return _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": [], "params": []})

    collect.run(run_dir, ledger_path, answering)

    assert len(calls) == collect.MAX_REJECTIONS
    assert state.pinned_candidate(run_dir) is None


def test_rejection_cap_counts_the_whole_cycle(tmp_path: Path) -> None:
    """
    목적: 기각 상한이 «그 회차 전체»에 걸리는 계약을 고정한다.

    [중요] 지역 변수로만 세면 이 단계가 다시 불릴 때 0 으로 돌아간다. JSON 이 깨져
    「그 외」로 재시도되는 회차는 이 단계가 최대 세 번 불리므로 **상한이 세 배가 되고,
    그만큼 후보와 예산이 함께 탄다** — 상한을 둔 이유가 통째로 사라진다.

    Given: 이미 상한만큼 기각한 기록이 있는 실행 폴더
    When: 수집을 다시 돈다
    Then: 에이전트를 한 번도 부르지 않고 끝난다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "옥석을 가려 매수한다")
    for index in range(collect.MAX_REJECTIONS):
        decision_log.record(run_dir, "collect", decision_log.EVENT_DISCARDED, claim=f"앞서 기각한 {index}", reason="축 없음")

    calls: list[str] = []

    def counting(prompt: str) -> AgentResult:
        calls.append(prompt)
        return _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": [], "params": []})

    collect.run(run_dir, ledger_path, counting)

    assert calls == []


def test_collect_prompt_names_the_triggered_terms(tmp_path: Path) -> None:
    """
    목적: 걸린 표현을 «이름으로 짚어» 요구하는 계약을 고정한다.

    「값이 비어 있으면 적으라」고만 하면 에이전트가 자기 문장에 그런 말이 있는지를
    스스로 판정해야 한다. 판정에 실패하면 빈 목록이 오고 그 후보는 기각되는데,
    **탐색에서 한 번 통과했던 후보가 수집에서 죽는** 일이 된다.

    Given: 「단기」가 든 한 줄 주장
    When: 지시문을 만든다
    Then: 그 표현이 지시문에 이름으로 들어 있다
    """
    prompt = collect.build_prompt("공시 다음날 사서 단기 보유한다")

    assert "단기" in prompt


def test_collect_fills_in_a_missing_identifier(tmp_path: Path) -> None:
    """
    목적: 식별자가 없는 예전 후보에 식별자를 «박는» 계약을 고정한다.

    수집이 어차피 그 후보를 두고 에이전트를 부르므로 **별도 호출이 들지 않는다.**
    이것이 이미 쌓인 후보도 짧은 폴더명을 얻는 경로다.

    Given: 식별자 없이 담긴 후보와 식별자를 내는 응답
    When: 수집을 돈다
    Then: 원장에 식별자가 박히고 산출물이 그 이름의 폴더에 쌓인다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "분할 상장한 자회사를 상장 당일 종가에 사서 12개월 보유한다")

    collect.run(
        run_dir,
        ledger_path,
        lambda _: _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": [], "identifier": "spin-off"}),
    )

    assert ledger.load(ledger_path)[0].identifier == "spin-off"
    assert (run_dir / "spin-off" / "찬성근거.json").is_file()


def test_collect_records_the_parameter_grid(tmp_path: Path) -> None:
    """
    목적: 해명된 파라미터 격자가 «남는» 계약을 고정한다.

    이 격자가 나중에 측정 설계 초안으로 그대로 넘어간다. 검사에만 쓰고 버리면
    다음 단계가 같은 축을 다시 만들어야 하고, 그때 값이 달라진다.

    Given: 격자를 함께 낸 응답
    When: 수집을 돈다
    Then: 그 격자가 찬성 근거 파일에 들어 있다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "공시 다음날 사서 단기 보유한다")

    collect.run(
        run_dir,
        ledger_path,
        lambda _: _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": [], "params": _GRID}),
    )

    written = json.loads(
        (run_dir / naming.folder_name("공시 다음날 사서 단기 보유한다", None) / "찬성근거.json").read_text(encoding="utf-8")
    )
    assert written["params"] == _GRID


# --------------------------------------------------------------------------
# 출처 실재 — 배선까지 검사한다
#
# 게이트 «함수»만 검사하면 배선을 빠뜨려도 초록이고, 그 고장은 회차를 돌려 봐야 드러난다.
# 로드맵의 검증 조건도 「없는 URL 을 섞은 «문서»를 넣어 잡는다」이지
# 「게이트 함수가 잡는다」가 아니다.
# --------------------------------------------------------------------------


def test_collect_is_blocked_when_a_url_does_not_exist(tmp_path: Path, probing: Any) -> None:
    """
    목적: 지어낸 URL 이 든 찬성 근거가 «파일로 남지 않는» 계약을 고정한다.

    백테스트가 없어 부풀릴 점수가 없는 대신 유일하게 남는 위조 위험이 「없는 출처」이고,
    **읽어서는 구별되지 않는다.** 그래서 기계가 막는다.

    Given: 실재하지 않는 URL 이 든 찬성 근거
    When: 수집을 돈다
    Then: 막히고 찬성근거 파일이 안 쓰인다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")
    dead_url = "https://example.com/지어낸-논문"
    probing(dead={dead_url})
    answer = _answer(
        {
            "claim": "첫 후보",
            "queries": ["ㄱ", "ㄴ", "a"],
            "evidence": [{"title": "없는 논문", "url": dead_url, "kind": "primary"}],
        }
    )

    with pytest.raises(StepQualityFailed):
        collect.run(run_dir, ledger_path, lambda _: answer)

    assert list(run_dir.glob("**/찬성근거.json")) == []


def test_collect_is_not_blocked_when_a_url_cannot_be_judged(tmp_path: Path, probing: Any) -> None:
    """
    목적: 찔러 봤지만 «가를 수 없었던» URL 이 회차를 죽이지 않는 계약을 고정한다.

    학술지·뉴스 사이트는 봇을 막는다. 차단을 죽음으로 보면 **멀쩡한 출처가 든 회차가
    매번 죽는다** — 게이트가 약해지는 것보다 나쁘다.

    Given: 차단으로 판정 못 한 URL 이 든 찬성 근거
    When: 수집을 돈다
    Then: 막히지 않고 파일이 쓰인다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")
    blocked_url = "https://example.com/봇을-막는-학술지"
    probing(unknown={blocked_url: "HEAD 403"})
    answer = _answer(
        {
            "claim": "첫 후보",
            "queries": ["ㄱ", "ㄴ", "a"],
            "evidence": [{"title": "막힌 논문", "url": blocked_url, "kind": "primary"}],
        }
    )

    collect.run(run_dir, ledger_path, lambda _: answer)

    assert (run_dir / naming.slug("첫 후보") / "찬성근거.json").is_file()


def test_collect_records_what_it_probed(tmp_path: Path, probing: Any) -> None:
    """
    목적: 판정 분포가 결정 로그에 남는 계약을 고정한다.

    「404·410 만 죽음으로 본다」는 **가정**이고, 남는 구멍은 가짜 도메인이 이름 해석
    실패로 통과하는 것이다. 그 가정을 나중에 다시 보려면 무엇이 얼마나 판정 못 됐는지가
    쌓여 있어야 한다 — 실패 분류표를 원문으로 가르치는 것과 같은 방식이다.

    Given: 살아 있는 URL 하나와 판정 못 한 URL 하나
    When: 수집을 돈다
    Then: 결정 로그에 판정별 개수와 판정 못 한 사유가 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")
    unknown_url = "https://example.com/막힌-곳"
    probing(unknown={unknown_url: "HEAD gaierror"})
    answer = _answer(
        {
            "claim": "첫 후보",
            "queries": ["ㄱ", "ㄴ", "a"],
            "evidence": [
                {"title": "멀쩡한 논문", "url": "https://example.com/p", "kind": "primary"},
                {"title": "못 닿은 곳", "url": unknown_url, "kind": "secondary"},
            ],
        }
    )

    collect.run(run_dir, ledger_path, lambda _: answer)

    probed = [e for e in decision_log.read(run_dir) if e.get("gate") == "urls"]
    assert probed[0]["alive"] == 1
    assert probed[0]["unknown"] == 1
    assert probed[0]["unknown_details"] == ["HEAD gaierror"]

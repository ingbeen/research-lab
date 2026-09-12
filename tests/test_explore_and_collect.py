"""탐색과 수집이 남기는 것의 계약을 고정한다.

두 단계는 **같은 호출 계층**을 쓴다. 여기서 그 계층을 흉내 낸 것을 넣어 검사하는 이유는,
계층이 한 단계에 맞춰 깎이면 다음 단계에서 다시 갈라지기 때문이다.
"""

import json
from pathlib import Path

import pytest

from research_lab.agent.invoke import AgentResult
from research_lab.runner import collect, decision_log, explore, ledger, naming
from research_lab.runner.steps import StepFailed, StepQualityFailed


def _answer(payload: object, *, cost: float | None = 0.5, tokens: int | None = 100) -> AgentResult:
    """에이전트가 그 JSON 을 돌려줬다고 치는 응답."""
    text = json.dumps(payload, ensure_ascii=False)
    return AgentResult(
        text=text,
        raw=text,
        cost_usd=cost,
        tokens=tokens,
        elapsed_seconds=1.0,
        session_id="세션",
    )


# --------------------------------------------------------------------------
# 탐색
# --------------------------------------------------------------------------


def test_explore_fills_the_ledger(tmp_path: Path) -> None:
    """
    목적: 탐색이 빈 원장을 채우는 계약을 고정한다.

    이것이 「사람이 후보를 적어 넣지 않아도 첫 밤이 돈다」의 실체다.

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
    **그만큼 그 밤의 탐색이 헛돈다.**

    Given: 후보가 든 원장
    When: 지시문을 만든다
    Then: 그 후보가 지시문에 들어 있다
    """
    assert "첫 후보" in explore.build_prompt(["첫 후보"])


def test_explore_rejects_non_json_answer(tmp_path: Path) -> None:
    """
    목적: 약속한 모양이 아닌 응답을 «실패»로 넘기는 계약을 고정한다.

    조용히 넘어가면 그 밤은 아무것도 안 담은 채 「성공」으로 끝난다.

    Given: JSON 이 아닌 응답
    When: 탐색을 돈다
    Then: StepFailed 가 오르고 원문이 실려 있다
    """
    answer = AgentResult(
        text="미안, JSON 이 아니라 줄글로 적었어",
        raw="미안, JSON 이 아니라 줄글로 적었어",
        cost_usd=None,
        tokens=None,
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

    # 산출물은 «후보별 폴더» 안에 있다 — 한 밤이 후보 둘을 파도 덮어쓰지 않는다
    output_dir = run_dir / naming.slug("첫 후보")
    evidence = json.loads((output_dir / "찬성근거.json").read_text(encoding="utf-8"))
    queries = json.loads((output_dir / "검색어.json").read_text(encoding="utf-8"))
    assert evidence["claim"] == "첫 후보"
    assert evidence["evidence"][0]["url"] == "https://example.com/p"
    assert evidence["unverified"] == ["국내 적용 여부"]
    assert queries["queries"] == ["ㄱ", "ㄴ", "a"]


def test_collect_marks_the_candidate_explored(tmp_path: Path) -> None:
    """
    목적: 판 후보를 다시 꺼내지 않게 표시하는 계약을 고정한다.

    Given: 후보 하나가 든 원장
    When: 수집을 돈다
    Then: 그 후보가 판 것으로 표시돼 다음 후보가 없다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    collect.run(run_dir, ledger_path, lambda _: _answer({"queries": ["ㄱ", "ㄴ", "ㄷ"], "evidence": []}))

    assert ledger.next_unexplored(ledger_path) is None


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

    이것이 있어야 밤 예산 집계가 컨테이너의 세션 로그에 의존하지 않고,
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

    빈손으로 성공 처리하면 그 밤은 「완주」로 기록되고, 아침에 산출물만 없다.

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
    그 쓰레기가 이후 매일 밤 수집 호출을 한 번씩 잡아먹는다. 예외는 나지 않는다.

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

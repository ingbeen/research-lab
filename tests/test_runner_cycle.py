"""회차의 진입 순서와 실패 처리 계약을 고정한다.

진입 순서가 반대면 미완성을 두고 새 후보를 꺼내게 되어 **아무도 모르는 채 미완성만 쌓인다.**
①이 먼저라서 미완성이 구조적으로 최대 1개가 되는 것이 이 설계의 핵심이다.
"""

from pathlib import Path

import pytest

from research_lab.agent import invoke
from research_lab.runner import budget, cycle, decision_log, failures, ledger, state, steps, usage


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """재시도 사이의 대기를 없앤다.

    실제 값은 30초다 — 일시적인 고장이 풀릴 틈을 주려는 것이라 테스트에서는 의미가 없고,
    그대로 두면 재시도 테스트 하나가 1분을 잡아먹는다.
    """
    monkeypatch.setattr(cycle, "sleep", lambda _: None)


def _executor(calls: list[str], ledger_path: Path | None = None):
    """무엇이 실행됐는지 기록하고, 진짜 단계가 남기는 «상태»만 흉내 내는 실행기.

    탐색은 원장을 채우고 수집은 그 회차의 후보를 상태에 박는다. 둘 다 안 하면 뒤따르는
    단계가 「팔 후보 없음」·「그 회차의 후보 없음」으로 건너뛰어진다 — 그게 정상 동작이라,
    흉내 내지 않으면 **건너뛰기 갈래만 검사하게 되고 진행 갈래는 검사되지 않는다.**

    [중요] 수집은 **원장에서 꺼낸 후보**를 박는다. 진짜 수집이 그렇게 하기 때문이다
    (`collect._store`). 원장에 없는 이름을 박으면 뒤 단계가 「원장에 그 후보가 없다」로
    건너뛰어지는데, 그것은 **흉내가 틀린 것이지 러너가 틀린 것이 아니다** —
    그 갈래는 사람이 원장 줄을 지웠을 때를 위한 것이다.
    """

    def execute(step: str, run_dir: Path) -> None:
        calls.append(step)
        if step == "explore" and ledger_path is not None:
            ledger.append(ledger_path, f"탐색이 찾은 후보 {len(calls)}")
        if step == "collect" and ledger_path is not None:
            candidate = ledger.next_unexplored(ledger_path)
            if candidate is not None:
                state.pin_candidate(run_dir, state.Candidate(claim=candidate.claim, identifier=None))

    return execute


def test_empty_ledger_runs_explore_first(tmp_path: Path) -> None:
    """
    목적: 재고가 없으면 탐색부터 도는 계약을 고정한다.

    이것이 「사람이 후보를 적어 넣지 않아도 첫 회차가 돈다」의 실체다.

    Given: 빈 원장
    When: 회차를 돈다
    Then: 탐색이 먼저 실행되고 수집이 뒤따른다
    """
    calls: list[str] = []
    ledger_path = tmp_path / "원장.md"

    cycle.run_cycle(
        run_dir=tmp_path / "run",
        ledger_path=ledger_path,
        execute=_executor(calls, ledger_path),
    )

    assert calls == list(steps.STEPS)


def test_explore_is_skipped_when_stock_exists(tmp_path: Path) -> None:
    """
    목적: 원장에 재고가 있으면 탐색을 건너뛰는 계약을 고정한다.

    재고가 있는데도 회차마다 탐색을 돌리면 팔 후보를 쌓아 두고 예산만 쓴다.

    Given: 아직 안 판 후보가 든 원장
    When: 회차를 돈다
    Then: 탐색만 건너뛰고 나머지 단계가 돈다
    """
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")
    calls: list[str] = []

    result = cycle.run_cycle(run_dir=tmp_path / "run", ledger_path=ledger_path, execute=_executor(calls, ledger_path))

    assert calls == list(steps.STEPS[1:])
    assert result.skipped == ("explore",)


def test_a_deferred_candidate_is_not_counted_as_stock(tmp_path: Path) -> None:
    """
    목적: [중요] 미뤄 둔 후보를 «재고로 세지 않는» 계약을 고정한다.

    수집은 출처를 못 갖춘 후보를 원장에 표시 없이 지나친다. 그것을 재고로 세면
    **탐색이 「아직 팔 후보가 있다」며 영영 안 돌고**, 수집은 그 후보를 쓸 수 없다 —
    새 후보가 들어올 길이 막혀 **회차마다 호출만 태우며 0장을 낸다.**
    그 상태는 「실패」가 아니라 「아무 일 없음」처럼 보인다.

    Given: 원장의 유일한 후보를 미뤄 둔 실행 폴더
    When: 회차를 돈다
    Then: 탐색이 돈다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "출처를 못 갖춘 후보")
    decision_log.record(
        run_dir,
        steps.COLLECT,
        decision_log.EVENT_DEFERRED,
        claim="출처를 못 갖춘 후보",
        reason="출처가 실재하지 않는다",
    )
    calls: list[str] = []

    cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=_executor(calls, ledger_path))

    assert "explore" in calls, "재고가 미룬 후보뿐이면 새 후보를 찾아야 한다"


def test_collect_still_runs_when_the_only_stock_is_deferred(tmp_path: Path) -> None:
    """
    목적: [중요] 남은 후보가 미룬 것뿐이어도 **수집이 도는** 계약을 고정한다.

    여기서 건너뛰면 그 폴더가 **완주로 닫히고 실패 카운트가 안 올라간다.** 그러면 계속
    막히는 후보를 걷어내는 장치가 영영 안 불리고, 다음 회차는 새 폴더에서 미룬 사실을
    모른 채 같은 후보를 다시 집어 **회차마다 호출만 태우며 0장을 낸다** —
    이 저장소가 가장 경계하는 「실패가 아니라 아무 일 없음」 상태다.

    [중요] **그래서 탐색과 수집의 재고 판정이 갈린다.** 탐색에게 미룬 후보는 「새 후보가
    필요하다」이지만(그래서 빼고 센다), 수집에게는 **「돌아서 실패해야 한다」**이다.

    Given: 원장의 유일한 후보를 미뤄 두었고 탐색이 새 후보를 못 찾는 회차
    When: 회차를 돈다
    Then: 수집이 건너뛰어지지 않고 실제로 불린다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "출처를 못 갖춘 후보")
    decision_log.record(
        run_dir,
        steps.COLLECT,
        decision_log.EVENT_DEFERRED,
        claim="출처를 못 갖춘 후보",
        reason="출처가 실재하지 않는다",
    )
    calls: list[str] = []

    # 원장을 안 넘겨 탐색이 새 후보를 만들지 못하게 둔다 — 그래야 이 갈래에 선다
    cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=_executor(calls))

    assert steps.COLLECT in calls, "미룬 후보뿐이어도 수집이 돌아야 실패 카운트가 올라간다"


def test_skipped_step_still_counts_as_settled(tmp_path: Path) -> None:
    """
    목적: 건너뛴 단계를 다음 회차가 다시 잡지 않는 계약을 고정한다.

    이어받기는 「남은 일」을 묻는다. 건너뛴 단계를 「안 한 것」으로 두면
    회차마다 같은 판정을 다시 하게 된다.

    Given: 재고가 있어 탐색을 건너뛴 회차
    When: 결과를 본다
    Then: 건너뛴 단계도 마친 것으로 집계돼 회차가 끝난 것으로 판정된다
    """
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    result = cycle.run_cycle(run_dir=tmp_path / "run", ledger_path=ledger_path, execute=_executor([], ledger_path))

    assert set(result.settled) == set(steps.STEPS)
    assert result.finished is True


def test_interrupted_cycle_resumes_at_the_failed_step(tmp_path: Path) -> None:
    """
    목적: 끊긴 회차가 «멈춘 자리»부터 이어지는 계약을 고정한다.

    이 프로젝트의 목표 2 다. 끝난 단계를 다시 도는 것은 안전한 재시도가 아니라 예산 낭비다.

    Given: 수집에서 실패해 멈춘 회차
    When: 같은 실행 폴더로 다시 돈다
    Then: 탐색은 다시 돌지 않고 수집부터 이어진다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"

    def failing(step: str, _: Path) -> None:
        if step == "explore":
            ledger.append(ledger_path, "탐색이 찾은 후보")
            return
        raise steps.StepFailed("수집이 깨졌다")

    cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=failing)

    calls: list[str] = []
    cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=_executor(calls, ledger_path))

    assert calls == list(steps.STEPS[1:])


def test_limit_failure_stops_without_retrying(tmp_path: Path) -> None:
    """
    목적: 한도 소진을 재시도하지 않고 깨끗이 끝내는 계약을 고정한다.

    해봐야 또 막히고, 그 사이 남은 예산을 태운다.

    Given: 한도 소진 문구를 내는 단계
    When: 회차를 돈다
    Then: 한 번만 시도하고 멈춘다
    """
    limit_phrase = failures.patterns_for(failures.FailureKind.LIMIT)[0]
    attempts: list[str] = []

    def hitting_limit(step: str, _: Path) -> None:
        attempts.append(step)
        raise steps.StepFailed(f"앞말 {limit_phrase} 뒷말")

    result = cycle.run_cycle(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=hitting_limit)

    assert len(attempts) == 1
    assert result.failure is not None
    assert result.failure.kind is failures.FailureKind.LIMIT


def test_other_failure_is_retried_up_to_the_cap(tmp_path: Path) -> None:
    """
    목적: 「그 외」 실패에 «상한»이 걸리는 계약을 고정한다.

    상한이 없으면 한 회차 내내 같은 실패를 반복하며 토큰을 태운다. 나중에 보면 예산은 다 썼고
    산출물은 0장인데, 그런 회차는 「아무 일 없음」처럼 보여 며칠 지나서야 알아챈다.

    Given: 매번 알 수 없는 실패를 내는 단계
    When: 회차를 돈다
    Then: 정확히 상한만큼 시도하고 멈춘다
    """
    attempts: list[str] = []

    def always_failing(step: str, _: Path) -> None:
        attempts.append(step)
        raise steps.StepFailed("도무지 알 수 없는 실패")

    cycle.run_cycle(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=always_failing)

    assert len(attempts) == failures.MAX_RETRIES


def test_unexpected_exception_is_absorbed_as_other(tmp_path: Path) -> None:
    """
    목적: 예상 못 한 예외가 회차를 «통째로» 끝내지 않는 계약을 고정한다.

    여기서 터뜨리면 원문도 안 남아, 다음에 같은 모양을 만나도 가르칠 재료가 없다.

    Given: StepFailed 가 아닌 예외를 내는 단계
    When: 회차를 돈다
    Then: 예외가 밖으로 새지 않고 「그 외」로 분류된다
    """

    def exploding(step: str, _: Path) -> None:
        raise ZeroDivisionError("생각도 못 한 것")

    result = cycle.run_cycle(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=exploding)

    assert result.failure is not None
    assert result.failure.kind is failures.FailureKind.OTHER


def test_failure_result_carries_the_raw_text(tmp_path: Path) -> None:
    """
    목적: 멈춘 이유의 «원문»이 부르는 쪽까지 전해지는 계약을 고정한다.

    「재시도를 다 썼다」로 바꿔 넘기면 원문이 사라져 무엇 때문에 막혔는지 알 수 없다.

    Given: 알 수 없는 실패로 상한까지 간 회차
    When: 결과의 실패를 본다
    Then: 마지막 실패 원문이 그대로 들어 있다
    """
    raw = "서버가 이상한 소리를 했다"

    def always_failing(step: str, _: Path) -> None:
        raise steps.StepFailed(raw)

    result = cycle.run_cycle(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=always_failing)

    assert result.failure is not None
    assert result.failure.raw == raw


def _spent(session_id: str, *, cost_usd: float | None = 0.9, output_tokens: int | None = 100) -> invoke.AgentResult:
    """실패한 호출이 «쓴 것». 세션 ID 를 호출마다 다르게 받는다 — 비용 줄이 그것으로 호출을 가른다."""
    return invoke.AgentResult(
        text="",
        raw="{}",
        cost_usd=cost_usd,
        tokens=output_tokens,
        usage={"output_tokens": output_tokens} if output_tokens is not None else None,
        elapsed_seconds=1.0,
        session_id=session_id,
    )


def test_failed_call_cost_is_recorded_before_the_failure(tmp_path: Path) -> None:
    """
    목적: 실패한 호출이 쓴 돈이 결정 로그의 «비용 줄»로 남는 계약을 고정한다.

    [실측 2026-09-22] 계보 단계가 도중에 한도에 걸려 $0.9002 를 쓰고 멈췄는데, 비용 줄이 없어
    회차 로그의 쓴 돈 · 토큰 · 한도 비율에서 통째로 빠졌다. 집계는 비용 줄만 더하므로
    **실패 줄의 원문에 금액이 있어도 없는 것과 같다.**

    Given: 쓴 것을 실은 한도 실패를 내는 단계
    When: 회차를 돈다
    Then: 실패 줄 «바로 앞»에 그 호출의 비용 줄이 하나 있고, 집계에 들어가며, 재시도하지 않는다
    """
    limit_phrase = failures.patterns_for(failures.FailureKind.LIMIT)[0]
    attempts: list[str] = []

    def hitting_limit_midway(step: str, _: Path) -> None:
        attempts.append(step)
        raise steps.StepFailed(f"앞말 {limit_phrase} 뒷말", spent=_spent("세션-가", cost_usd=0.9, output_tokens=68))

    run_dir = tmp_path / "run"
    cycle.run_cycle(run_dir=run_dir, ledger_path=tmp_path / "원장.md", execute=hitting_limit_midway)

    entries = decision_log.read(run_dir)
    events = [entry["event"] for entry in entries]
    assert events.count(decision_log.EVENT_COST) == 1
    assert events.index(decision_log.EVENT_COST) + 1 == events.index(decision_log.EVENT_FAILED)
    assert budget.cost_of(run_dir) == 0.9
    assert usage.tokens_of(run_dir).new_total == 68
    assert len(attempts) == 1


def test_each_retried_call_leaves_its_own_cost_line(tmp_path: Path) -> None:
    """
    목적: 「그 외」 실패로 재시도한 호출마다 비용 줄이 «따로» 남는 계약을 고정한다.

    재시도는 호출을 새로 한다 — 세 번 불렀으면 세 번 쓴 것이다.

    Given: 호출마다 다른 세션으로 쓴 것을 실은 「그 외」 실패
    When: 회차가 상한까지 재시도한다
    Then: 비용 줄이 시도 수만큼이고 금액이 모두 더해진다
    """
    sessions = iter(["세션-1", "세션-2", "세션-3"])

    def always_failing(step: str, _: Path) -> None:
        raise steps.StepFailed("도무지 알 수 없는 실패", spent=_spent(next(sessions), cost_usd=0.5))

    run_dir = tmp_path / "run"
    cycle.run_cycle(run_dir=run_dir, ledger_path=tmp_path / "원장.md", execute=always_failing)

    costs = [entry for entry in decision_log.read(run_dir) if entry["event"] == decision_log.EVENT_COST]
    assert len(costs) == failures.MAX_RETRIES
    assert budget.cost_of(run_dir) == 0.5 * failures.MAX_RETRIES


def test_failure_without_spent_leaves_no_cost_line(tmp_path: Path) -> None:
    """
    목적: 쓴 것을 모르는 실패는 비용 줄을 «만들지 않는» 계약을 고정한다.

    지어낸 0 을 적으면 「재서 0」으로 읽혀 돈을 안 쓴 것처럼 보인다.

    Given: 쓴 것을 싣지 않은 실패
    When: 회차를 돈다
    Then: 비용 줄이 없다
    """

    def failing(step: str, _: Path) -> None:
        raise steps.StepFailed("시간이 다 됐다")

    run_dir = tmp_path / "run"
    cycle.run_cycle(run_dir=run_dir, ledger_path=tmp_path / "원장.md", execute=failing)

    assert all(entry["event"] != decision_log.EVENT_COST for entry in decision_log.read(run_dir))


def test_failure_with_nothing_measured_leaves_no_cost_line(tmp_path: Path) -> None:
    """
    목적: 결과를 실었어도 «잰 것이 하나도 없는» 실패는 비용 줄을 만들지 않는 계약을 고정한다.

    CLI 출력 자체가 JSON 이 아니면 결과의 금액 · 토큰 · 성분이 모두 빈다. 적으면 값이 빈 줄이
    남아, 종료 코드로 멈춘 같은 모양의 실패와 로그 모양이 갈린다.

    Given: 금액 · 토큰 · 성분이 모두 빈 결과를 실은 실패
    When: 회차를 돈다
    Then: 비용 줄이 없다
    """

    def failing(step: str, _: Path) -> None:
        raise steps.StepFailed("출력이 JSON 이 아니다", spent=_spent("세션-가", cost_usd=None, output_tokens=None))

    run_dir = tmp_path / "run"
    cycle.run_cycle(run_dir=run_dir, ledger_path=tmp_path / "원장.md", execute=failing)

    assert all(entry["event"] != decision_log.EVENT_COST for entry in decision_log.read(run_dir))


def test_failure_missing_only_the_amount_still_counts_its_tokens(tmp_path: Path) -> None:
    """
    목적: 금액만 빠진 실패도 토큰을 비용 줄로 남기는 계약을 고정한다.

    응답 모양은 CLI 가 정하는 것이라 금액만 빠지는 날이 올 수 있다. 그때 버리면 그 토큰이
    한도 비율에서 빠지는데, 성공한 호출은 같은 결과를 그대로 적으므로 **경로에 따라 규칙이 갈린다.**

    Given: 금액은 없고 토큰은 있는 결과를 실은 실패
    When: 회차를 돈다
    Then: 비용 줄이 하나 남고 그 토큰이 집계에 들어간다
    """

    def failing(step: str, _: Path) -> None:
        raise steps.StepFailed("금액이 빠진 응답", spent=_spent("세션-가", cost_usd=None, output_tokens=40))

    run_dir = tmp_path / "run"
    cycle.run_cycle(run_dir=run_dir, ledger_path=tmp_path / "원장.md", execute=failing)

    costs = [entry for entry in decision_log.read(run_dir) if entry["event"] == decision_log.EVENT_COST]
    assert len(costs) == 1
    assert usage.tokens_of(run_dir).new_total == 40


def test_second_cycle_cannot_start_while_one_is_running(tmp_path: Path) -> None:
    """
    목적: 같은 실행 폴더를 두 회차가 동시에 잡지 못하는 계약을 고정한다.

    Given: 이미 잠긴 실행 폴더
    When: 회차를 돌리려 한다
    Then: 예외가 오른다
    """
    run_dir = tmp_path / "run"

    with state.lock(run_dir):
        with pytest.raises(state.AlreadyRunningError):
            cycle.run_cycle(run_dir=run_dir, ledger_path=tmp_path / "원장.md", execute=_executor([]))


def test_collect_is_skipped_when_explore_finds_nothing(tmp_path: Path) -> None:
    """
    목적: 탐색이 새 후보를 못 찾았을 때 «끝나지 않는 실패»가 되지 않는 계약을 고정한다.

    탐색이 빈손인 것은 정상 결과다(원장이 포화됐거나 그 회차의 검색이 허탕이거나).
    그 상태로 수집에 들어가면 후보가 없어 예외가 나고, 상한까지 재시도한 뒤
    「다음 회차가 이어받습니다」로 보고된다. 다음 회차도 같은 자리에서 같은 일을 반복하며,
    **나중에는 아무 일도 없었던 것처럼 보인다.**

    Given: 원장을 채우지 않는 탐색
    When: 회차를 돈다
    Then: 수집이 실행되지 않고, 실패 없이 끝난다
    """
    calls: list[str] = []

    result = cycle.run_cycle(
        run_dir=tmp_path / "run",
        ledger_path=tmp_path / "원장.md",
        execute=_executor(calls),
    )

    assert calls == ["explore"]
    assert result.failure is None


def test_candidate_steps_are_skipped_without_a_candidate(tmp_path: Path) -> None:
    """
    목적: 그 회차가 후보를 못 잡았을 때 «끝나지 않는 실패»가 되지 않는 계약을 고정한다.

    [중요] 수집에 이미 같은 갈래가 있고, 후보를 보는 단계에 그것이 빠지면 같은 고장이 난다 —
    후보 없이 반증이 돌아 예외가 나고, 상한까지 재시도한 뒤 「다음 회차가 이어받습니다」로
    보고된다. 다음 회차도 같은 자리에서 같은 일을 반복하며, **나중에는 아무 일도 없었던
    것처럼 보인다.**

    Given: 원장을 채우지 않아 수집이 건너뛰어진 회차
    When: 회차를 돈다
    Then: 반증·계보도 건너뛰고 실패 없이 끝난다
    """
    calls: list[str] = []

    result = cycle.run_cycle(
        run_dir=tmp_path / "run",
        ledger_path=tmp_path / "원장.md",
        execute=_executor(calls),
    )

    assert all(step not in calls for step in steps.CANDIDATE_STEPS)
    assert result.skipped == tuple(steps.STEPS[1:])
    assert result.failure is None


def test_skip_reasons_are_recorded(tmp_path: Path) -> None:
    """
    목적: 건너뛴 «사유»가 결정 로그에 남는 계약을 고정한다.

    「건너뛰었다」만 남으면 나중에 왜 그랬는지 되짚을 수 없다. 후보를 하나도 못 판 회차는
    종료 코드로는 「완주」와 구별되지 않으므로, **그 구별이 오직 이 기록에 있다.**

    Given: 후보를 못 잡아 세 단계를 건너뛴 회차
    When: 결정 로그를 읽는다
    Then: 건너뛴 단계마다 사유가 적혀 있다
    """
    run_dir = tmp_path / "run"

    cycle.run_cycle(run_dir=run_dir, ledger_path=tmp_path / "원장.md", execute=_executor([]))

    skipped = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_SKIPPED]
    assert {entry["step"] for entry in skipped} == set(steps.STEPS[1:])
    assert all(entry["reason"].strip() for entry in skipped)


def test_last_step_is_skipped_when_the_candidate_is_already_explored(tmp_path: Path) -> None:
    """
    목적: [중요] 그 회차의 후보가 «이미 판 것»이면 마지막 단계를 건너뛰는 계약을 고정한다.

    단계를 하나 늘리면 **그 전에 완주한 실행 폴더가 「미완성」으로 보인다** — 끝난 단계는
    전부 `settled` 에 있는데 새 단계만 남아 있기 때문이다. 그 폴더에는 후보가 박혀 있어
    「후보 없음」 갈래로도 걸러지지 않으므로, 그대로 이어받으면 **이미 닫힌 후보를 두고
    새 단계만 도는 회차**가 되고 그 후보를 두 번 「판 것」으로 표시한다.

    가르는 사실은 하나다 — **원장에서 이미 「판 것」이면 더 물을 자리가 아니다.**
    사람이 손으로 `- [x]` 로 바꾼 경우도 같은 갈래로 덮인다.

    Given: 마지막 단계만 남았고, 박힌 후보가 원장에서 이미 판 것인 실행 폴더
    When: 회차를 돈다
    Then: 그 단계를 실행하지 않고 사유를 남긴 채 완주한다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    claim = "예전 판에서 이미 판 후보"

    ledger.append(ledger_path, claim)
    ledger.mark_explored(ledger_path, claim)
    state.pin_candidate(run_dir, state.Candidate(claim=claim, identifier=None))
    state.save(run_dir, {**(state.load(run_dir) or {}), "settled": list(steps.STEPS[:-1]), "skipped": []})

    calls: list[str] = []
    result = cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=_executor(calls))

    assert steps.STEPS[-1] not in calls
    assert steps.STEPS[-1] in result.skipped
    assert result.failure is None

    skipped = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_SKIPPED]
    assert any(entry["step"] == steps.STEPS[-1] and entry["reason"].strip() for entry in skipped)


def _resume_at_last_step(run_dir: Path, ledger_path: Path, claim: str) -> None:
    """마지막 단계만 남은 폴더를 만든다 — 후보가 박혀 있고 앞 단계는 다 끝난 상태."""
    state.pin_candidate(run_dir, state.Candidate(claim=claim, identifier=None))
    state.save(run_dir, {**(state.load(run_dir) or {}), "settled": list(steps.STEPS[:-1]), "skipped": []})


def test_last_step_is_skipped_when_the_candidate_is_rejected(tmp_path: Path) -> None:
    """
    목적: [중요] 기각된 후보를 「판 것」으로 «덮지 않는» 계약을 고정한다.

    마지막 단계가 `mark_explored` 를 부르면 `- [-]` 가 `- [x]` 로 바뀌고
    **바로 아래의 기각 사유 줄이 지워진다.** 원장 머리말은 기각된 줄이 사람이 고칠 때까지
    남는다고 약속하는데 그것이 깨지고, **에러도 나지 않는다.**

    Given: 박힌 후보가 원장에서 기각된 실행 폴더
    When: 회차를 돈다
    Then: 마지막 단계를 돌지 않고 기각 표시와 사유가 그대로 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    claim = "기각된 후보"

    ledger.append(ledger_path, claim)
    ledger.mark_rejected(ledger_path, claim, "축을 못 냈다")
    _resume_at_last_step(run_dir, ledger_path, claim)

    calls: list[str] = []
    cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=_executor(calls))

    assert steps.STEPS[-1] not in calls
    assert ledger.status_of(ledger_path, claim) is ledger.Status.REJECTED
    assert "축을 못 냈다" in ledger_path.read_text(encoding="utf-8")


def test_last_step_is_skipped_when_the_candidate_is_blocked(tmp_path: Path) -> None:
    """
    목적: 막힌 후보의 «사유»가 살아남는 계약을 고정한다.

    막힘은 기각과 성질이 다르다 — 판정에 닿지도 못한 것이라 **원인을 고치면 다시 팔**
    가치가 있고, 그 원인이 사유 줄에만 적혀 있다. 덮이면 고칠 단서가 사라진다.

    Given: 박힌 후보가 원장에서 막힌 실행 폴더
    When: 회차를 돈다
    Then: 마지막 단계를 돌지 않고 막힘 표시와 사유가 그대로 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    claim = "막힌 후보"

    ledger.append(ledger_path, claim)
    ledger.mark_blocked(ledger_path, claim, "세 회차 연속 막혔다")
    _resume_at_last_step(run_dir, ledger_path, claim)

    calls: list[str] = []
    cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=_executor(calls))

    assert steps.STEPS[-1] not in calls
    assert ledger.status_of(ledger_path, claim) is ledger.Status.BLOCKED
    assert "세 회차 연속 막혔다" in ledger_path.read_text(encoding="utf-8")


def test_last_step_is_skipped_when_the_candidate_line_is_gone(tmp_path: Path) -> None:
    """
    목적: [중요] 원장에서 «줄이 사라진» 후보를 «상한까지 재시도하지 않는» 계약을 고정한다.

    원장은 사람이 손으로 고치는 파일이다. 줄이 지워진 채로 마지막 단계가 돌면
    산출물을 쓴 **뒤에** `mark_explored` 가 예외를 올리고, 그것이 「그 외」로 분류되어
    **상한까지 재시도한다** — 재시도가 고칠 수 없는 조건에 단계 비용을 세 번 낸다.

    Given: 박힌 후보가 원장에 없는 실행 폴더
    When: 회차를 돈다
    Then: 마지막 단계를 돌지 않고 실패 없이 끝난다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _resume_at_last_step(run_dir, ledger_path, "원장에 없는 후보")

    calls: list[str] = []
    result = cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=_executor(calls))

    assert steps.STEPS[-1] not in calls
    assert result.failure is None


def test_retry_waits_between_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 재시도 사이에 «쉬는» 계약을 고정한다.

    「그 외」가 노리는 것은 네트워크 끊김·웹 500 같은 일시적인 고장이다.
    쉬지 않고 세 번 부르면 몇 밀리초 안에 상한을 다 써 버려, 잠깐 기다렸으면
    복구됐을 것까지 그 회차에 포기하게 된다.

    Given: 매번 실패하는 단계
    When: 회차를 돈다
    Then: 시도 사이마다 정해진 시간을 쉰다
    """
    waited: list[float] = []
    monkeypatch.setattr(cycle, "sleep", waited.append)

    def always_failing(step: str, _: Path) -> None:
        raise steps.StepFailed("일시적인 고장")

    cycle.run_cycle(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=always_failing)

    assert waited == [cycle.RETRY_DELAY_SECONDS] * (failures.MAX_RETRIES - 1)


def test_invariant_violation_is_not_swallowed(tmp_path: Path) -> None:
    """
    목적: 「실행부가 없는 단계」가 «그 외 실패»로 묻히지 않는 계약을 고정한다.

    묻히면 상한까지 헛돈 뒤 「다음 회차가 이어받습니다」라는 종료 코드로 보고되어,
    **아무 일도 안 하는 상태를 정상으로 알린다.** 그 단계는 영영 실행되지 않는다.

    Given: 실행부가 없다고 알리는 단계
    When: 회차를 돈다
    Then: 예외가 그대로 밖으로 나온다
    """

    def not_implemented(step: str, _: Path) -> None:
        raise steps.StepNotImplementedError("내부 불변조건 위반: 실행부가 없는 단계입니다")

    with pytest.raises(steps.StepNotImplementedError):
        cycle.run_cycle(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=not_implemented)

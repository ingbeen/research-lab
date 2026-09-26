"""회차와 회차 사이의 상한 — 계속 막히는 후보를 접는 계약을 고정한다.

`failures.MAX_RETRIES` 는 **한 회차 «안»의 상한**이고, 회차와 회차 사이를 세는 곳은 여기가 처음이다.

게이트가 막은 실패는 재시도 대상이 아니라 그 회차가 즉시 끝나고, 다음 회차는 **같은 실행 폴더를
이어받아 같은 단계를 다시 부른다.** 구조적으로 계속 막히는 후보라면 탐색도 수집도 영영
다시 돌지 않고 **회차마다 호출만 한 번씩 태운다.** 나중에 보면 「실패」가 아니라
「아무 일 없음」처럼 보여 며칠 지나서야 알아챈다.

[중요] **새 누적 상태를 만들지 않는다.** 셀 재료는 그 폴더의 결정 로그에 이미 있다 —
「누적 집계를 만들지 않는다」 규칙과 `collect` 가 기각 수를 결정 로그로 세는 방식 그대로다.
"""

import itertools
from collections.abc import Callable
from pathlib import Path

import pytest

from research_lab.agent.invoke import StepFailed
from research_lab.common_constants import STATE_FILENAME
from research_lab.runner import cycle, decision_log, ledger, state
from research_lab.runner.steps import StepQualityFailed

PINNED_CLAIM = "그 회차가 판 후보"

# [실측 2026-09-12] 실제로 부딪힌 한도 문구. 분류표가 이것을 「한도」로 읽는다
LIMIT_RAW = "You've hit your session limit - resets 4:40pm (Asia/Seoul)"

# 분류표가 「그 외」로 떨어뜨리는 일시적 고장
TRANSIENT_RAW = "connection reset by peer"


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """재시도 사이의 대기를 없앤다. 실제 값은 30초라 그대로 두면 한 테스트가 몇 분을 잡아먹는다."""
    monkeypatch.setattr(cycle, "sleep", lambda _: None)


def _executor(fail_at: str, *, raw: str | None = None) -> Callable[[str, Path], None]:
    """지정한 단계에서만 실패하는 실행기.

    [중요] 수집은 **실패하지 «않았을» 때만** 후보를 박는다. 진짜 수집이 그렇기 때문이다 —
    게이트는 `_store` 앞에서 막으므로 **막힌 수집은 후보를 박은 적이 없다.**
    여기서 순서를 뒤집으면 그 상황이 테스트에서 사라져, 실제로 있는 구멍을 못 본다.

    Args:
        fail_at: 실패시킬 단계
        raw: 실패 원문. None 이면 게이트가 막은 것(재시도 없음)으로 올린다
    """

    def execute(step: str, run_dir: Path) -> None:
        if step == fail_at:
            if raw is None:
                raise StepQualityFailed("게이트가 막았다")
            raise StepFailed(raw)
        if step == "collect":
            state.pin_candidate(run_dir, state.Candidate(claim=PINNED_CLAIM, identifier=None))

    return execute


def _run_cycles(
    count: int,
    *,
    run_dir: Path,
    ledger_path: Path,
    execute: Callable[[str, Path], None],
) -> cycle.CycleResult | None:
    """같은 실행 폴더로 회차를 여러 번 돌린다 — 끊긴 회차를 다음 회차가 이어받는 모양 그대로."""
    result: cycle.CycleResult | None = None
    for _ in range(count):
        result = cycle.run_cycle(run_dir=run_dir, ledger_path=ledger_path, execute=execute)
    return result


def _stocked_ledger(tmp_path: Path) -> Path:
    """수집이 꺼내 갈 후보가 이미 든 원장."""
    path = tmp_path / "원장.md"
    ledger.append(path, PINNED_CLAIM)
    return path


def test_a_stuck_candidate_is_blocked_on_the_third_cycle(tmp_path: Path) -> None:
    """
    목적: 상한에 닿은 후보를 원장에서 «걷어내는» 계약을 고정한다 — 이 상한의 본체다.

    Given: 반증이 매번 게이트에 막히는 실행 폴더
    When: 같은 폴더로 세 회차를 돈다
    Then: 그 후보가 「막힘」으로 원장에 박힌다
    """
    ledger_path = _stocked_ledger(tmp_path)

    result = _run_cycles(3, run_dir=tmp_path / "run", ledger_path=ledger_path, execute=_executor("rebut"))

    assert result is not None
    assert result.blocked_claim == PINNED_CLAIM
    assert ledger.load(ledger_path)[0].status is ledger.Status.BLOCKED


def test_two_failures_do_not_block_yet(tmp_path: Path) -> None:
    """
    목적: 상한 «전»에는 접지 않는 계약을 고정한다.

    일시적인 고장으로 두 회차 막히는 일은 있을 수 있다. 거기서 접으면 멀쩡한 후보를 버린다.

    Given: 반증이 매번 막히는 실행 폴더
    When: 두 회차만 돈다
    Then: 아직 막히지 않고 후보도 그대로다
    """
    ledger_path = _stocked_ledger(tmp_path)

    result = _run_cycles(2, run_dir=tmp_path / "run", ledger_path=ledger_path, execute=_executor("rebut"))

    assert result is not None
    assert result.blocked_claim is None
    assert ledger.load(ledger_path)[0].status is ledger.Status.UNEXPLORED


def test_a_stuck_collect_blocks_the_candidate_it_kept_picking(tmp_path: Path) -> None:
    """
    목적: [중요] **수집**이 막혔을 때도 그 후보를 걷어내는 계약을 고정한다.

    수집은 `_store` 에서야 후보를 상태에 박는데 게이트는 그 «앞»에서 막는다. 그래서
    막힌 수집에는 박힌 후보가 없고, 상태만 보고 걷어내면 **걷어낼 것이 없다.**
    그러면 다음 회차가 새 폴더에서 같은 후보를 다시 꺼내 같은 게이트에 막히고,
    **3회차마다 버려진 폴더가 하나씩 늘 뿐 아무것도 진행되지 않는다** — 이 장치가
    없애려던 무한 반복이 그대로 남는 것이다. 그래서 원장의 「다음에 팔 후보」로 되짚는다.

    Given: 수집이 매번 게이트에 막히는 실행 폴더
    When: 세 회차를 돈다
    Then: 원장에서 그 후보가 걷어내진다
    """
    ledger_path = _stocked_ledger(tmp_path)

    result = _run_cycles(3, run_dir=tmp_path / "run", ledger_path=ledger_path, execute=_executor("collect"))

    assert result is not None
    assert result.blocked_claim == PINNED_CLAIM
    assert ledger.load(ledger_path)[0].status is ledger.Status.BLOCKED


def test_a_deferred_candidate_is_not_the_one_that_gets_blocked(tmp_path: Path) -> None:
    """
    목적: [중요] 미뤄 둔 후보가 «막힌 후보 대신» 걷어내지지 않는 계약을 고정한다.

    수집은 출처를 못 갖춘 후보를 원장에 **아무 표시도 하지 않고** 미뤄 둔다. 그래서 그
    후보는 여전히 「다음에 팔 후보」의 첫 번째이고, 되짚기가 그것을 그대로 집으면
    **미뤄 둔 앞 후보가 막힘으로 걷히고 정작 막힌 뒤 후보는 멀쩡히 남는다.**
    붙는 사유는 사실이지만 대상이 틀려, 한도 소진을 상한에 세지 않기로 한 것과 같은
    이유로 **사람을 엉뚱한 곳으로 보낸다.**

    Given: 앞 후보를 미뤄 둔 기록이 있고, 수집이 매번 게이트에 막히는 실행 폴더
    When: 세 회차를 돈다
    Then: 걷어내지는 것은 미뤄 둔 앞 후보가 아니라 그 다음 후보다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "미뤄 둔 앞 후보")
    ledger.append(ledger_path, "실제로 막힌 뒤 후보")
    decision_log.record(
        run_dir,
        "collect",
        decision_log.EVENT_DEFERRED,
        claim="미뤄 둔 앞 후보",
        reason="출처가 실재하지 않는다",
    )

    result = _run_cycles(3, run_dir=run_dir, ledger_path=ledger_path, execute=_executor("collect"))

    assert result is not None
    assert result.blocked_claim == "실제로 막힌 뒤 후보"
    assert ledger.status_of(ledger_path, "미뤄 둔 앞 후보") is ledger.Status.UNEXPLORED
    assert ledger.status_of(ledger_path, "실제로 막힌 뒤 후보") is ledger.Status.BLOCKED


def test_the_deferred_candidate_is_the_one_that_gets_blocked(tmp_path: Path) -> None:
    """
    목적: [중요] 미룸 상한으로 막힌 폴더에서 **실제로 막힌 후보**를 걷는 계약을 고정한다.

    수집이 A·B 를 미루고 상한에 닿으면 그 뒤 회차는 **에이전트를 한 번도 안 부르고**
    즉시 실패하므로 3회차에 닿는다. 그때 되짚기가 미룬 것을 빼고 고르면 **C** 를 집는데,
    C 는 **물어본 적조차 없는 후보**다 — 원장에 「3회차 연속 막혔다」는 사유와 함께 박히지만
    그 사유는 C 에 대해 거짓이고, 정작 막힌 A·B 는 멀쩡히 남아 다음 폴더에서 또 막힌다.

    Given: A·B 를 미뤄 둔 기록이 있고 수집이 매번 막히는 실행 폴더 (원장은 A·B·C)
    When: 세 회차를 돈다
    Then: 걷히는 것이 C 가 아니라 미뤄 둔 것 중 하나다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    for claim in ("미뤄 둔 A", "미뤄 둔 B", "물어본 적 없는 C"):
        ledger.append(ledger_path, claim)
    for claim in ("미뤄 둔 A", "미뤄 둔 B"):
        decision_log.record(
            run_dir,
            "collect",
            decision_log.EVENT_DEFERRED,
            claim=claim,
            reason="출처가 실재하지 않는다",
        )
    # 상한에 닿아 «에이전트를 한 번도 안 부르고» 끝난 상태다 — 그 사실이 가르는 조건이다
    decision_log.record(
        run_dir,
        "collect",
        decision_log.EVENT_FAILED,
        gate=decision_log.GATE_DEFERRED_STUCK,
        reason="출처를 갖춘 후보를 찾지 못했습니다",
    )

    result = _run_cycles(3, run_dir=run_dir, ledger_path=ledger_path, execute=_executor("collect"))

    assert result is not None
    assert result.blocked_claim in {"미뤄 둔 A", "미뤄 둔 B"}, "막힌 것은 미룬 후보다"
    assert ledger.status_of(ledger_path, "물어본 적 없는 C") is ledger.Status.UNEXPLORED


def test_hitting_the_subscription_limit_never_blocks_a_candidate(tmp_path: Path) -> None:
    """
    목적: [중요] 한도 소진을 상한에 «세지 않는» 계약을 고정한다.

    이 파이프라인은 **남는 구독 토큰으로 돈다.** 한도에 걸리는 회차는 «정상»이고
    다음 회차가 이어받으면 된다. 그걸 세면 **아무 문제 없는 후보가
    사흘 만에 원장에서 걷어내지고**, 붙는 사유는 「단계가 3회차 연속 막혔다」라
    사실이지만 원인을 가리키지 않아 **사람을 엉뚱한 곳으로 보낸다.**

    Given: 세 회차 내리 한도에 걸리는 실행 폴더
    When: 세 회차를 돈다
    Then: 후보가 그대로 남고 폴더도 안 접힌다
    """
    ledger_path = _stocked_ledger(tmp_path)
    run_dir = tmp_path / "run"

    result = _run_cycles(3, run_dir=run_dir, ledger_path=ledger_path, execute=_executor("rebut", raw=LIMIT_RAW))

    assert result is not None
    assert result.blocked_claim is None
    assert ledger.load(ledger_path)[0].status is ledger.Status.UNEXPLORED
    assert state.closed_reason(run_dir) is None


def test_retries_within_one_cycle_count_as_one_cycle(tmp_path: Path) -> None:
    """
    목적: [중요] 한 회차의 **재시도**를 여러 회차로 «세지 않는» 계약을 고정한다.

    「그 외」 실패는 한 회차에 세 번까지 다시 해보고, 그때마다 결정 로그에 한 줄씩 남는다.
    그 줄을 그냥 세면 **첫 회차에 바로 상한에 닿아** 멀쩡한 후보가 한 회차 만에 걷어내진다.
    게이트가 막은 실패도 단계와 러너가 각각 한 줄씩 남겨 같은 고장을 만든다.

    Given: 「그 외」로 매번 실패해 회차마다 세 번씩 재시도되는 실행 폴더
    When: 두 회차를 돈다
    Then: 아직 막히지 않는다
    """
    ledger_path = _stocked_ledger(tmp_path)

    result = _run_cycles(
        2,
        run_dir=tmp_path / "run",
        ledger_path=ledger_path,
        execute=_executor("rebut", raw="웹이 500 을 냈다"),
    )

    assert result is not None
    assert result.blocked_claim is None


def _in_turn(fail_at: str, raws: list[str | None]) -> Callable[[str, Path], None]:
    """지정한 단계를 부를 때마다 `raws` 를 차례로 돌며 실패하는 실행기.

    `None` 은 게이트가 막은 것(재시도 없음)이다. 수집은 `_executor` 와 같은 이유로
    실패하지 않았을 때만 후보를 박는다.
    """
    turns = itertools.cycle(raws)

    def execute(step: str, run_dir: Path) -> None:
        if step == fail_at:
            raw = next(turns)
            if raw is None:
                raise StepQualityFailed("게이트가 막았다")
            raise StepFailed(raw)
        if step == "collect":
            state.pin_candidate(run_dir, state.Candidate(claim=PINNED_CLAIM, identifier=None))

    return execute


def test_a_cycle_that_ended_on_the_limit_is_not_counted(tmp_path: Path) -> None:
    """
    목적: [중요] 첫 시도가 「그 외」였어도 «한도로 끝난» 회차는 세지 않는 계약을 고정한다.

    세는 것은 그 회차의 «마지막» 실패다. 첫 시도의 갈래로 세면 네트워크가 한 번 끊긴 뒤
    한도에 걸린 회차가 「막힌 회차」로 세어지고, 새벽 회차는 한도에 자주 걸리므로
    **멀쩡한 후보가 막힘 상한에 닿아 `- [!]` 로 걷힌다.**

    Given: 매 회차 첫 시도는 연결 끊김 · 재시도는 한도로 끝나는 실행 폴더
    When: 세 회차를 돈다
    Then: 후보가 그대로 남고 폴더도 안 접힌다
    """
    ledger_path = _stocked_ledger(tmp_path)
    run_dir = tmp_path / "run"

    result = _run_cycles(
        3, run_dir=run_dir, ledger_path=ledger_path, execute=_in_turn("rebut", [TRANSIENT_RAW, LIMIT_RAW])
    )

    assert result is not None
    assert result.blocked_claim is None
    assert ledger.load(ledger_path)[0].status is ledger.Status.UNEXPLORED
    assert state.closed_reason(run_dir) is None


def test_a_cycle_that_used_up_its_retries_is_counted(tmp_path: Path) -> None:
    """
    목적: 「그 외」로 재시도 상한까지 간 회차는 «한 번» 세는 계약을 고정한다.

    Given: 매 회차 「그 외」로 상한까지 실패하는 실행 폴더
    When: 세 회차를 돈다
    Then: 3회차에 그 후보가 걷힌다
    """
    ledger_path = _stocked_ledger(tmp_path)

    result = _run_cycles(
        3, run_dir=tmp_path / "run", ledger_path=ledger_path, execute=_in_turn("rebut", [TRANSIENT_RAW])
    )

    assert result is not None
    assert result.blocked_claim == PINNED_CLAIM


def test_a_transient_failure_that_recovered_is_not_counted(tmp_path: Path) -> None:
    """
    목적: 재시도로 «성공한» 회차의 실패 줄은 세지 않는 계약을 고정한다.

    그 줄을 세면 다음에 같은 단계가 막혔을 때 이미 한 번 막힌 것으로 출발한다.

    Given: 첫 시도는 「그 외」로 실패하고 재시도는 성공하는 단계
    When: 그 단계를 돌고 막힌 회차를 센다
    Then: 0 이다
    """
    run_dir = tmp_path / "run"
    outcomes = iter([StepFailed(TRANSIENT_RAW), None])

    def execute(_step: str, _run_dir: Path) -> None:
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome

    assert cycle._execute_with_retries(run_dir, "rebut", execute) is None
    assert cycle._failed_cycles(run_dir, "rebut") == 0


def test_a_transient_failure_then_a_gate_block_counts_once(tmp_path: Path) -> None:
    """
    목적: 한 회차 안에서 「그 외」 뒤에 게이트에 막히면 «한 번만» 세는 계약을 고정한다.

    Given: 첫 시도는 「그 외」, 재시도는 게이트에 막히는 단계
    When: 그 단계를 돌고 막힌 회차를 센다
    Then: 1 이다
    """
    run_dir = tmp_path / "run"
    outcomes = iter([StepFailed(TRANSIENT_RAW), StepQualityFailed("게이트가 막았다")])

    def execute(_step: str, _run_dir: Path) -> None:
        raise next(outcomes)

    assert cycle._execute_with_retries(run_dir, "rebut", execute) is not None
    assert cycle._failed_cycles(run_dir, "rebut") == 1


def test_a_failure_line_without_an_attempt_is_not_counted(tmp_path: Path) -> None:
    """
    목적: 시도 번호가 없는 실패 줄은 «세지 않는» 계약을 고정한다.

    시도 번호는 러너가 재시도하며 적는다. 그것이 없는 줄은 어느 회차의 어느 시도인지
    모르는 줄이고, 모를 때 세는 쪽으로 떨어지면 **물어볼 이유가 없는 후보가 일찍 걷힌다.**

    Given: 갈래는 있으나 시도 번호가 없는 실패 줄들
    When: 막힌 회차를 센다
    Then: 0 이다
    """
    run_dir = tmp_path / "run"
    decision_log.record(run_dir, "rebut", decision_log.EVENT_FAILED, kind="other", raw="시도 번호 없음")
    decision_log.record(run_dir, "rebut", decision_log.EVENT_FAILED, kind="quality", raw="시도 번호 없음")

    assert cycle._failed_cycles(run_dir, "rebut") == 0


def test_blocked_run_dir_is_closed(tmp_path: Path) -> None:
    """
    목적: [중요] 접은 실행 폴더에 «닫힘» 표시가 남는 계약을 고정한다.

    후보를 원장에서 걷어내도 그 폴더의 「그 회차의 후보」는 살아 있다. 표시가 없으면
    다음 회차가 그 폴더를 이어받아 **같은 단계를 또 부르고 또 막힌다** — 접은 의미가 없어진다.

    Given: 세 회차 막혀 접힌 실행 폴더
    When: 결과와 상태를 본다
    Then: 사유와 함께 닫혀 있고, 그 사유가 결과에도 실려 있다
    """
    run_dir = tmp_path / "run"

    result = _run_cycles(3, run_dir=run_dir, ledger_path=_stocked_ledger(tmp_path), execute=_executor("rebut"))

    assert result is not None
    assert result.closed_reason is not None
    assert state.closed_reason(run_dir) is not None


def test_a_run_without_a_candidate_closes_without_touching_the_ledger(tmp_path: Path) -> None:
    """
    목적: 후보를 쓰지 않는 단계에서 막혔을 때 원장을 «건드리지 않는» 계약을 고정한다.

    탐색은 원장에서 후보를 꺼내지 않으므로 걷어낼 것이 없다. 여기서 「다음에 팔 후보」로
    되짚으면 **애먼 후보가 걷어내진다.** 그래도 폴더는 접어야 다음 회차가 새로 시작한다.

    Given: 탐색이 매번 막히고 원장이 빈 실행 폴더
    When: 세 회차를 돈다
    Then: 원장은 그대로이고 폴더만 닫히며, 접혔다는 사실이 결과에 실린다
    """
    ledger_path = tmp_path / "원장.md"
    run_dir = tmp_path / "run"

    result = _run_cycles(3, run_dir=run_dir, ledger_path=ledger_path, execute=_executor("explore"))

    assert result is not None
    assert result.blocked_claim is None
    assert result.closed_reason is not None
    assert ledger.load(ledger_path) == []
    assert state.closed_reason(run_dir) is not None


def test_a_candidate_missing_from_the_ledger_does_not_crash_the_cycle(tmp_path: Path) -> None:
    """
    목적: 걷어낼 후보가 원장에 «없어도» 그 회차가 죽지 않는 계약을 고정한다.

    원장은 사람이 손으로 고치는 파일이라 그 사이 줄이 지워질 수 있다. 여기서 예외가
    오르면 이미 실패한 회차 위에 예외가 겹쳐 **실패 원문이 묻힌다.** 폴더는 그래도 닫아야 한다.

    Given: 상태에 박힌 후보가 원장에는 없는 실행 폴더
    When: 세 회차를 돈다
    Then: 예외 없이 끝나고 폴더가 닫힌다
    """
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "사람이 남겨 둔 다른 후보")
    run_dir = tmp_path / "run"
    state.pin_candidate(run_dir, state.Candidate(claim="원장에 없는 후보", identifier=None))

    def always_blocked(step: str, run_dir_of_step: Path) -> None:
        raise StepQualityFailed("게이트가 막았다")

    _run_cycles(3, run_dir=run_dir, ledger_path=ledger_path, execute=always_blocked)

    assert state.closed_reason(run_dir) is not None


def test_a_legacy_state_file_reads_as_open(tmp_path: Path) -> None:
    """
    목적: 「닫힘」 칸이 «없는» 예전 상태 파일을 안 닫힌 것으로 읽는 계약을 고정한다.

    이 필드가 생기기 전에 만들어진 폴더가 이미 쌓여 있다. 없는 것을 닫힘으로 읽으면
    **이어받을 수 있던 회차가 통째로 버려진다.**

    Given: 진행만 적힌 예전 상태 파일
    When: 닫힘 여부를 묻는다
    Then: 안 닫힌 것으로 읽힌다
    """
    run_dir = tmp_path / "run"
    state.save(run_dir, {"settled": ["explore"], "skipped": []})

    assert state.closed_reason(run_dir) is None


def test_a_broken_state_file_reads_as_open(tmp_path: Path) -> None:
    """
    목적: 깨진 상태 파일 때문에 판정이 «죽지 않는» 계약을 고정한다.

    판정을 못 하는 것과 실패로 판정하는 것은 다르다. 여기서 터뜨리면 그 폴더 하나 때문에
    이후 모든 회차가 선다.

    Given: 반쯤 쓰이다 끊긴 상태 파일
    When: 닫힘 여부를 묻는다
    Then: 예외 없이 안 닫힌 것으로 읽힌다
    """
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    # 파일명은 계층이 공유하는 계약이라 한 곳에서만 정한다. 여기 박아 두면 그 이름이 바뀔 때
    # 이 테스트는 **아무도 안 읽는 파일을 쓰고 그냥 통과한다** — 검사가 조용히 사라진다
    (run_dir / STATE_FILENAME).write_text("{깨진", encoding="utf-8")

    assert state.closed_reason(run_dir) is None


def test_a_null_reason_does_not_leak_as_the_word_none(tmp_path: Path) -> None:
    """
    목적: 사유가 `null` 로 적혀 있어도 「None」이라는 말이 «보고되지 않는» 계약을 고정한다.

    사람이 상태 파일을 손으로 고칠 수 있고, `str(None)` 은 `"None"` 이라 비어 있지 않다 —
    기본 문구가 안 걸리고 **사유가 「None」으로 사람에게 나간다.**

    Given: 사유가 null 로 적힌 닫힘 표시
    When: 닫힘 여부를 묻는다
    Then: 닫힌 것으로 읽히되 사유가 「None」은 아니다
    """
    run_dir = tmp_path / "run"
    state.save(run_dir, {"settled": [], "skipped": [], "closed": {"reason": None}})

    reason = state.closed_reason(run_dir)

    assert reason is not None
    assert reason != "None"

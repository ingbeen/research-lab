"""밤의 진입 순서와 실패 처리 계약을 고정한다.

진입 순서가 반대면 미완성을 두고 새 후보를 꺼내게 되어 **아무도 모르는 채 미완성만 쌓인다.**
①이 먼저라서 미완성이 구조적으로 최대 1개가 되는 것이 이 설계의 핵심이다.
"""

from pathlib import Path

import pytest

from research_lab.runner import failures, ledger, night, state, steps


@pytest.fixture(autouse=True)
def _no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """재시도 사이의 대기를 없앤다.

    실제 값은 30초다 — 일시적인 고장이 풀릴 틈을 주려는 것이라 테스트에서는 의미가 없고,
    그대로 두면 재시도 테스트 하나가 1분을 잡아먹는다.
    """
    monkeypatch.setattr(night, "sleep", lambda _: None)


def _executor(calls: list[str], ledger_path: Path | None = None):
    """무엇이 실행됐는지 기록하고, 탐색이면 원장을 채우는 실행기.

    진짜 탐색이 하는 일이 원장을 채우는 것이라, 안 채우면 뒤따르는 수집이
    「팔 후보 없음」으로 건너뛰어진다 — 그게 정상 동작이다.
    """

    def execute(step: str, run_dir: Path) -> None:
        calls.append(step)
        if step == "explore" and ledger_path is not None:
            ledger.append(ledger_path, f"탐색이 찾은 후보 {len(calls)}")

    return execute


def test_empty_ledger_runs_explore_first(tmp_path: Path) -> None:
    """
    목적: 재고가 없으면 탐색부터 도는 계약을 고정한다.

    이것이 「사람이 후보를 적어 넣지 않아도 첫 밤이 돈다」의 실체다.

    Given: 빈 원장
    When: 밤을 돈다
    Then: 탐색이 먼저 실행되고 수집이 뒤따른다
    """
    calls: list[str] = []
    ledger_path = tmp_path / "원장.md"

    night.run_night(
        run_dir=tmp_path / "run",
        ledger_path=ledger_path,
        execute=_executor(calls, ledger_path),
    )

    assert calls == list(steps.STEPS)


def test_explore_is_skipped_when_stock_exists(tmp_path: Path) -> None:
    """
    목적: 원장에 재고가 있으면 탐색을 건너뛰는 계약을 고정한다.

    재고가 있는데도 매일 탐색을 돌리면 팔 후보를 쌓아 두고 예산만 쓴다.

    Given: 아직 안 판 후보가 든 원장
    When: 밤을 돈다
    Then: 수집만 실행된다
    """
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")
    calls: list[str] = []

    result = night.run_night(run_dir=tmp_path / "run", ledger_path=ledger_path, execute=_executor(calls))

    assert calls == ["collect"]
    assert result.skipped == ("explore",)


def test_skipped_step_still_counts_as_settled(tmp_path: Path) -> None:
    """
    목적: 건너뛴 단계를 다음 밤이 다시 잡지 않는 계약을 고정한다.

    이어받기는 「남은 일」을 묻는다. 건너뛴 단계를 「안 한 것」으로 두면
    매일 밤 같은 판정을 다시 하게 된다.

    Given: 재고가 있어 탐색을 건너뛴 밤
    When: 결과를 본다
    Then: 건너뛴 단계도 마친 것으로 집계돼 밤이 끝난 것으로 판정된다
    """
    ledger_path = tmp_path / "원장.md"
    ledger.append(ledger_path, "첫 후보")

    result = night.run_night(run_dir=tmp_path / "run", ledger_path=ledger_path, execute=_executor([]))

    assert set(result.settled) == set(steps.STEPS)
    assert result.finished is True


def test_interrupted_night_resumes_at_the_failed_step(tmp_path: Path) -> None:
    """
    목적: 끊긴 밤이 «멈춘 자리»부터 이어지는 계약을 고정한다.

    이 프로젝트의 목표 2 다. 끝난 단계를 다시 도는 것은 안전한 재시도가 아니라 예산 낭비다.

    Given: 수집에서 실패해 멈춘 밤
    When: 같은 실행 폴더로 다시 돈다
    Then: 탐색은 다시 돌지 않고 수집만 실행된다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"

    def failing(step: str, _: Path) -> None:
        if step == "explore":
            ledger.append(ledger_path, "탐색이 찾은 후보")
            return
        raise steps.StepFailed("수집이 깨졌다")

    night.run_night(run_dir=run_dir, ledger_path=ledger_path, execute=failing)

    calls: list[str] = []
    night.run_night(run_dir=run_dir, ledger_path=ledger_path, execute=_executor(calls, ledger_path))

    assert calls == ["collect"]


def test_limit_failure_stops_without_retrying(tmp_path: Path) -> None:
    """
    목적: 한도 소진을 재시도하지 않고 깨끗이 끝내는 계약을 고정한다.

    해봐야 또 막히고, 그 사이 남은 예산을 태운다.

    Given: 한도 소진 문구를 내는 단계
    When: 밤을 돈다
    Then: 한 번만 시도하고 멈춘다
    """
    limit_phrase = failures.patterns_for(failures.FailureKind.LIMIT)[0]
    attempts: list[str] = []

    def hitting_limit(step: str, _: Path) -> None:
        attempts.append(step)
        raise steps.StepFailed(f"앞말 {limit_phrase} 뒷말")

    result = night.run_night(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=hitting_limit)

    assert len(attempts) == 1
    assert result.failure is not None
    assert result.failure.kind is failures.FailureKind.LIMIT


def test_other_failure_is_retried_up_to_the_cap(tmp_path: Path) -> None:
    """
    목적: 「그 외」 실패에 «상한»이 걸리는 계약을 고정한다.

    상한이 없으면 밤새 같은 실패를 반복하며 토큰을 태운다. 아침에 보면 예산은 다 썼고
    산출물은 0장인데, 그런 밤은 「아무 일 없음」처럼 보여 며칠 지나서야 알아챈다.

    Given: 매번 알 수 없는 실패를 내는 단계
    When: 밤을 돈다
    Then: 정확히 상한만큼 시도하고 멈춘다
    """
    attempts: list[str] = []

    def always_failing(step: str, _: Path) -> None:
        attempts.append(step)
        raise steps.StepFailed("도무지 알 수 없는 실패")

    night.run_night(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=always_failing)

    assert len(attempts) == failures.MAX_RETRIES


def test_unexpected_exception_is_absorbed_as_other(tmp_path: Path) -> None:
    """
    목적: 예상 못 한 예외가 밤을 «통째로» 끝내지 않는 계약을 고정한다.

    여기서 터뜨리면 원문도 안 남아, 다음에 같은 모양을 만나도 가르칠 재료가 없다.

    Given: StepFailed 가 아닌 예외를 내는 단계
    When: 밤을 돈다
    Then: 예외가 밖으로 새지 않고 「그 외」로 분류된다
    """

    def exploding(step: str, _: Path) -> None:
        raise ZeroDivisionError("생각도 못 한 것")

    result = night.run_night(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=exploding)

    assert result.failure is not None
    assert result.failure.kind is failures.FailureKind.OTHER


def test_failure_result_carries_the_raw_text(tmp_path: Path) -> None:
    """
    목적: 멈춘 이유의 «원문»이 부르는 쪽까지 전해지는 계약을 고정한다.

    「재시도를 다 썼다」로 바꿔 넘기면 원문이 사라져 무엇 때문에 막혔는지 알 수 없다.

    Given: 알 수 없는 실패로 상한까지 간 밤
    When: 결과의 실패를 본다
    Then: 마지막 실패 원문이 그대로 들어 있다
    """
    raw = "서버가 이상한 소리를 했다"

    def always_failing(step: str, _: Path) -> None:
        raise steps.StepFailed(raw)

    result = night.run_night(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=always_failing)

    assert result.failure is not None
    assert result.failure.raw == raw


def test_second_night_cannot_start_while_one_is_running(tmp_path: Path) -> None:
    """
    목적: 같은 실행 폴더를 두 밤이 동시에 잡지 못하는 계약을 고정한다.

    Given: 이미 잠긴 실행 폴더
    When: 밤을 돌리려 한다
    Then: 예외가 오른다
    """
    run_dir = tmp_path / "run"

    with state.lock(run_dir):
        with pytest.raises(state.AlreadyRunningError):
            night.run_night(run_dir=run_dir, ledger_path=tmp_path / "원장.md", execute=_executor([]))


def test_collect_is_skipped_when_explore_finds_nothing(tmp_path: Path) -> None:
    """
    목적: 탐색이 새 후보를 못 찾았을 때 «끝나지 않는 실패»가 되지 않는 계약을 고정한다.

    탐색이 빈손인 것은 정상 결과다(원장이 포화됐거나 그날 검색이 허탕이거나).
    그 상태로 수집에 들어가면 후보가 없어 예외가 나고, 상한까지 재시도한 뒤
    「다음 밤이 이어받습니다」로 보고된다. 다음 밤도 같은 자리에서 같은 일을 반복하며,
    **아침에는 아무 일도 없었던 것처럼 보인다.**

    Given: 원장을 채우지 않는 탐색
    When: 밤을 돈다
    Then: 수집이 실행되지 않고, 실패 없이 끝난다
    """
    calls: list[str] = []

    result = night.run_night(
        run_dir=tmp_path / "run",
        ledger_path=tmp_path / "원장.md",
        execute=_executor(calls),
    )

    assert calls == ["explore"]
    assert result.skipped == ("collect",)
    assert result.failure is None


def test_retry_waits_between_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 재시도 사이에 «쉬는» 계약을 고정한다.

    「그 외」가 노리는 것은 네트워크 끊김·웹 500 같은 일시적인 고장이다.
    쉬지 않고 세 번 부르면 몇 밀리초 안에 상한을 다 써 버려, 잠깐 기다렸으면
    복구됐을 것까지 그 밤에 포기하게 된다.

    Given: 매번 실패하는 단계
    When: 밤을 돈다
    Then: 시도 사이마다 정해진 시간을 쉰다
    """
    waited: list[float] = []
    monkeypatch.setattr(night, "sleep", waited.append)

    def always_failing(step: str, _: Path) -> None:
        raise steps.StepFailed("일시적인 고장")

    night.run_night(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=always_failing)

    assert waited == [night.RETRY_DELAY_SECONDS] * (failures.MAX_RETRIES - 1)


def test_invariant_violation_is_not_swallowed(tmp_path: Path) -> None:
    """
    목적: 「실행부가 없는 단계」가 «그 외 실패»로 묻히지 않는 계약을 고정한다.

    묻히면 상한까지 헛돈 뒤 「다음 밤이 이어받습니다」라는 종료 코드로 보고되어,
    **아무 일도 안 하는 상태를 정상으로 알린다.** 그 단계는 영영 실행되지 않는다.

    Given: 실행부가 없다고 알리는 단계
    When: 밤을 돈다
    Then: 예외가 그대로 밖으로 나온다
    """

    def not_implemented(step: str, _: Path) -> None:
        raise steps.StepNotImplementedError("내부 불변조건 위반: 실행부가 없는 단계입니다")

    with pytest.raises(steps.StepNotImplementedError):
        night.run_night(run_dir=tmp_path / "run", ledger_path=tmp_path / "원장.md", execute=not_implemented)

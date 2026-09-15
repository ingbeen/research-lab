"""진입점(`scripts/run_cycle.py`)의 계약을 고정한다.

[중요] 이 파일이 없어서 **「이어받기가 무인 실행에서 아예 안 된다」를 105개 테스트가
전부 통과하면서 놓쳤다.** 러너 «라이브러리»의 이어받기는 검사됐지만, 그 라이브러리를
어떤 실행 폴더로 부를지 정하는 곳이 여기이고 그 판단이 검사 밖이었다.
"""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_entrypoint() -> Any:
    """스크립트를 모듈로 읽어 온다 (패키지가 아니라 파일이다)."""
    spec = importlib.util.spec_from_file_location("run_cycle", PROJECT_ROOT / "scripts" / "run_cycle.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """실행 폴더 뿌리를 임시 폴더로 격리한 진입점."""
    module = _load_entrypoint()
    monkeypatch.setattr(module, "RUNS_DIR", tmp_path / "runs")
    return module


def _make_run(module: Any, name: str, settled: list[str]) -> Path:
    """상태 파일이 든 실행 폴더를 만든다."""
    from research_lab.runner import state

    run_dir = module.RUNS_DIR / name
    state.save(run_dir, {"settled": settled, "skipped": []})
    return run_dir


def test_resume_picks_up_the_unfinished_cycle(entrypoint: Any) -> None:
    """
    목적: 인자 «없이» 불렸을 때 미완성을 이어받는 계약을 고정한다.

    이것이 회차의 첫 단계인 「① 미완성」이다. 무인 실행은 언제나 인자 없이 불리므로,
    여기서 새 폴더를 만들면 **이어받기가 영영 동작하지 않는다** — 끊긴 지난 회차는
    아무도 손대지 않은 채 쌓이고, 끝난 단계를 회차마다 다시 돈다.

    Given: 탐색만 끝난 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 돌아온다
    """
    unfinished = _make_run(entrypoint, "20260101_0100", ["explore"])

    assert entrypoint._resolve_run_dir(None) == unfinished


def test_finished_cycle_is_not_resumed(entrypoint: Any) -> None:
    """
    목적: 다 끝난 회차를 다시 잡지 않는 계약을 고정한다.

    이어받으면 완성된 산출물 위에 다시 쓴다.

    Given: 모든 단계가 끝난 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 아니라 새 폴더가 돌아온다
    """
    from research_lab.runner import steps

    finished = _make_run(entrypoint, "20260101_0100", list(steps.STEPS))

    assert entrypoint._resolve_run_dir(None) != finished


def test_newest_unfinished_cycle_wins(entrypoint: Any) -> None:
    """
    목적: 미완성이 여럿이면 «가장 최근» 것을 잡는 계약을 고정한다.

    Given: 미완성 실행 폴더 둘
    When: 인자 없이 실행 폴더를 고른다
    Then: 나중 것이 돌아온다
    """
    _make_run(entrypoint, "20260101_0100", [])
    newer = _make_run(entrypoint, "20260102_0100", [])

    assert entrypoint._resolve_run_dir(None) == newer


def test_locked_cycle_is_skipped(entrypoint: Any) -> None:
    """
    목적: 다른 프로세스가 «지금 잡고 있는» 폴더를 고르지 않는 계약을 고정한다.

    골라 봐야 잠금에 막혀 그 회차는 아무것도 못 한다.

    Given: 실제로 잠겨 있는 미완성 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 아니다
    """
    from research_lab.runner import state

    locked = _make_run(entrypoint, "20260101_0100", [])

    with state.lock(locked):
        assert entrypoint._resolve_run_dir(None) != locked


def test_cycle_with_a_leftover_lock_file_is_resumed(entrypoint: Any) -> None:
    """
    목적: [중요] **강제 종료가 남긴 잠금 «파일»이 있어도 이어받는** 계약을 고정한다.

    [실측 2026-09-14] 컨테이너가 죽으면 잠금 파일이 남는다(`SIGKILL`·`SIGTERM` 둘 다).
    파일 존재를 「잠김」으로 읽으면 **그 폴더가 영구히 이어받히지 않는다** — 후보는
    「판 것」이 안 됐으니 다음 회차가 원장에서 같은 후보를 다시 꺼내 **수집을 다시 사고**,
    버려진 폴더가 쌓이는데 **에러도 경고도 없다.** 설계가 「컨테이너가 죽어도 같은 방식으로
    복구된다」고 적어 둔 바로 그 자리다.

    Given: 아무도 잡고 있지 않은 잠금 파일이 남은 미완성 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더를 이어받는다
    """
    from research_lab.common_constants import LOCK_FILENAME

    leftover = _make_run(entrypoint, "20260101_0100", ["explore"])
    (leftover / LOCK_FILENAME).write_text("죽은 회차가 남긴 것", encoding="utf-8")

    assert entrypoint._resolve_run_dir(None) == leftover


def test_stale_step_names_do_not_stop_the_pipeline(entrypoint: Any) -> None:
    """
    목적: 예전 단계 이름이 든 상태가 파이프라인을 세우지 «않는» 계약을 고정한다.

    단계 이름을 바꾸면 예전 상태 파일이 남는다. 그걸 만나 터지면 **그 폴더 하나 때문에
    이후 모든 회차가 시작조차 못 한다.**

    Given: 정의에 없는 단계 이름이 든 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 예외 없이 새 폴더가 돌아온다
    """
    stale = _make_run(entrypoint, "20260101_0100", ["옛날에_있던_단계"])

    assert entrypoint._resolve_run_dir(None) != stale


def test_unfinished_cycle_without_a_candidate_is_skipped(entrypoint: Any) -> None:
    """
    목적: 그 회차의 후보가 «안 박힌» 미완성을 이어받지 않는 계약을 고정한다.

    [중요] 단계를 늘리면 예전 상태 파일이 그대로 남는다. 수집까지 끝난 예전 회차는
    남은 단계가 반증인데 **그 회차가 어느 후보를 팠는지 상태에 없다.** 그대로 이어받으면
    후보 없이 반증이 돌아 상한까지 헛돈다. 단계 이름을 바꿨을 때 예전 상태를 건너뛰는
    것과 같은 갈래이며, 그 폴더 하나 때문에 파이프라인이 서면 안 된다.

    Given: 수집까지 끝났지만 후보가 안 박힌 예전 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 아니라 새 폴더가 돌아온다
    """
    stale = _make_run(entrypoint, "20260101_0100", ["explore", "collect"])

    assert entrypoint._resolve_run_dir(None) != stale


def test_unfinished_cycle_with_a_candidate_is_resumed(entrypoint: Any) -> None:
    """
    목적: 후보가 박힌 미완성은 «그대로 이어받는» 계약을 고정한다.

    위 계약이 지나치게 넓으면 정상적인 이어받기까지 버린다 — 반증에서 끊긴 회차는
    후보가 박혀 있으므로 반드시 이어받아야 한다. 다시 돌면 수집을 처음부터 하게 되어
    **그 후보의 찬성 근거를 한 번 더 사게 된다.**

    Given: 수집까지 끝나고 후보가 박힌 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 돌아온다
    """
    from research_lab.runner import state

    unfinished = _make_run(entrypoint, "20260101_0100", ["explore", "collect"])
    state.pin_candidate(unfinished, state.Candidate(claim="그 회차가 판 후보", identifier="pinned"))

    assert entrypoint._resolve_run_dir(None) == unfinished


def test_closed_cycle_is_not_resumed(entrypoint: Any) -> None:
    """
    목적: [중요] 「막힘」으로 «닫힌» 폴더를 이어받지 않는 계약을 고정한다 (설계 §10.1 E).

    이것이 없으면 E 가 통째로 동작하지 않는다. 후보를 원장에서 걷어내도 그 폴더의
    「그 회차의 후보」는 살아 있어, 다음 회차가 이어받아 **같은 단계를 또 부르고 또 막힌다.**
    바로 위 계약(후보가 박힌 미완성은 이어받는다)이 여기서는 정확히 반대로 작용하므로
    닫힘을 «먼저» 봐야 한다.

    Given: 후보가 박혀 있지만 막힘으로 닫힌 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 아니라 새 폴더가 돌아온다
    """
    from research_lab.runner import state

    closed = _make_run(entrypoint, "20260101_0100", ["explore", "collect"])
    state.pin_candidate(closed, state.Candidate(claim="막힌 후보", identifier="stuck"))
    state.close(closed, "반증 단계가 세 회차 연속 막혔다")

    assert entrypoint._resolve_run_dir(None) != closed


def test_explicit_run_dir_wins(entrypoint: Any) -> None:
    """
    목적: 사람이 지정한 폴더를 그대로 쓰는 계약을 고정한다.

    Given: 지정된 폴더와, 그것과 다른 미완성 폴더
    When: 지정해서 실행 폴더를 고른다
    Then: 지정한 쪽이 돌아온다
    """
    _make_run(entrypoint, "20260101_0100", [])
    chosen = Path("/tmp/사람이-고른-폴더")

    assert entrypoint._resolve_run_dir(chosen) == chosen


def test_agent_env_drops_the_api_key(entrypoint: Any) -> None:
    """
    목적: 에이전트에게 넘길 환경에서 API 키가 «빠지는» 계약을 고정한다.

    환경을 통째로 물려주면 이 변수가 조용히 딸려 들어가고, 그 순간
    구독 대신 API 로 과금된다.

    Given: API 키가 든 환경
    When: 넘길 환경을 만든다
    Then: 그 변수가 없다
    """
    made = entrypoint._agent_env({"ANTHROPIC_API_KEY": "값", "PATH": "/bin", "HOME": "/home/x"})

    assert "ANTHROPIC_API_KEY" not in made
    assert made == {"PATH": "/bin", "HOME": "/home/x"}


def test_billing_guard_blocks_the_run(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: API 키가 있으면 «한 줄도 돌기 전에» 멈추는 계약을 고정한다.

    Given: API 키가 설정된 환경
    When: 회차를 돌린다
    Then: 인증 갈래의 종료 코드로 끝난다
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-예시")

    assert entrypoint.main([]) == entrypoint.EXIT_AUTH


def test_exit_codes_are_all_distinct(entrypoint: Any) -> None:
    """
    목적: 갈래마다 다른 종료 코드를 주는 계약을 고정한다.

    무인 실행에서 사람이 받는 신호가 이것뿐이다. 둘이 겹치면
    「인증이 끊겨 며칠 안 돈 상태」와 「그냥 한도에 걸린 회차」가 구별되지 않는다.

    Given: 정의된 종료 코드들
    When: 값을 견준다
    Then: 모두 다르다
    """
    codes = [
        entrypoint.EXIT_OK,
        entrypoint.EXIT_INCOMPLETE,
        entrypoint.EXIT_LIMIT,
        entrypoint.EXIT_AUTH,
        entrypoint.EXIT_SECRET,
    ]

    assert len(set(codes)) == len(codes)


# --------------------------------------------------------------------------
# 단계 배선 — 이름 하나가 회차를 통째로 죽이는 자리다
# --------------------------------------------------------------------------


def test_every_defined_step_has_an_implementation(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] 정의된 단계가 «하나도 빠짐없이» 실행부에 연결된 계약을 고정한다.

    단계 목록에 이름을 더하면서 배선을 안 붙이거나 이름을 잘못 적으면 그 회차가 그 자리에서
    죽는다. 그 예외는 일부러 재시도 대상이 아니라 **그대로 터지므로** 회차가 통째로 끝난다.

    무엇보다 그 고장은 **에이전트를 부르고 난 뒤**에야 드러나던 자리였다 — 앞 단계들의
    비용을 다 치르고 마지막에 깨진다.

    Given: 모든 단계 모듈을 부름만 기록하도록 바꾼 진입점
    When: 정의된 단계 이름을 하나씩 넘긴다
    Then: 전부 어딘가로 연결되고, 부른 단계 수가 정의된 수와 같다
    """
    from research_lab.runner import steps

    called: list[str] = []

    for name in ("explore", "collect", "rebut", "lineage", "feasibility", "mechanism", "measurement", "verdict"):
        module = getattr(entrypoint, name)
        monkeypatch.setattr(module, "run", lambda *_args, _name=name, **_kwargs: called.append(_name))

    for step in steps.STEPS:
        entrypoint.dispatch(step, Path("실행폴더"), ledger_path=Path("원장.md"), ask=lambda _: None)

    assert called == list(steps.STEPS)


def test_an_undefined_step_is_a_breakage_not_a_failure(entrypoint: Any) -> None:
    """
    목적: 실행부가 없는 이름이 «고장»으로 터지는 계약을 고정한다.

    「그 외」 실패로 묻히면 상한까지 헛돈 뒤 「다음 회차가 이어받습니다」로 보고되어,
    **아무 일도 안 하는 상태를 정상으로 알린다.**

    Given: 정의에 없는 단계 이름
    When: 배선에 넘긴다
    Then: 실행부 없음으로 터진다
    """
    from research_lab.runner import steps

    with pytest.raises(steps.StepNotImplementedError):
        entrypoint.dispatch("없는단계", Path("실행폴더"), ledger_path=Path("원장.md"), ask=lambda _: None)


def test_only_the_new_steps_carry_a_schema(entrypoint: Any) -> None:
    """
    목적: [실측 2026-09-14] 응답 모양 강제를 «새 세 단계»에만 거는 계약을 고정한다.

    앞의 다섯은 이미 실측으로 검증된 경로다. 갈아 끼우면 돌던 것을 새 플래그에 얹는 셈이라,
    스키마가 어긋나는 날 **되던 단계까지 함께 죽는다.**

    Given: 단계별 스키마 표
    When: 키를 본다
    Then: 새 세 단계만 들어 있고, 전부 정의된 단계 이름이다
    """
    from research_lab.runner import steps

    assert set(entrypoint.STEP_SCHEMAS) == {"mechanism", "measurement", "verdict"}
    assert set(entrypoint.STEP_SCHEMAS) <= set(steps.STEPS)


# --------------------------------------------------------------------------
# 예산 루프 — 「한 장 만들고 끝」이 아니라 예산이 남는 한 «돈다»
# --------------------------------------------------------------------------


def _finished() -> Any:
    """근거 문서를 실제로 낸 회차의 결과."""
    from research_lab.runner import cycle, steps

    return cycle.CycleResult(tuple(steps.STEPS), (), None)


def _nothing_produced() -> Any:
    """단계가 전부 «건너뛰어져» 끝난 회차 — 원장 포화·닫기만 하는 회차의 모양이다."""
    from research_lab.runner import cycle, steps

    return cycle.CycleResult(tuple(steps.STEPS), tuple(steps.STEPS), None)


def _failed(kind: Any) -> Any:
    """그 자리에서 멈춘 회차의 결과."""
    from research_lab.runner import cycle, steps
    from research_lab.runner.failures import Failure

    return cycle.CycleResult(tuple(steps.STEPS[:2]), (), Failure(kind=kind, raw="원문"))


def _stub_cycle(
    entrypoint: Any, monkeypatch: pytest.MonkeyPatch, *, outcomes: list[Any], cost_usd: float
) -> list[Path]:
    """회차 실행을 미리 정한 결과로 바꾸고, 어느 폴더가 돌았는지 돌려준다.

    진짜 단계가 남기는 것 중 **루프 판정에 쓰이는 셋**만 흉내 낸다 — 상태 파일 · 비용 줄 ·
    **근거 문서를 냈다는 표시**. 하나라도 없으면 다음 반복이 같은 폴더를 이어받거나
    「한 단위」 표본이 안 생겨, **흉내가 모자라서 통과하는 테스트**가 된다.

    [중요] 세 번째가 늦게 추가됐다. 문서를 냈다는 표시를 안 남기면 표본이 0건이 되어
    루프가 첫 반복에서 「표본 없음」으로 멈추는데, 그것은 **흉내의 결함**이지 코드의 동작이 아니다.
    """
    from research_lab.runner import cycle, decision_log, state, steps

    seen: list[Path] = []
    queue = list(outcomes)

    def run_cycle(*, run_dir: Path, ledger_path: Path, execute: Any) -> Any:
        seen.append(run_dir)
        outcome = queue.pop(0) if queue else outcomes[-1]
        state.save(run_dir, {"settled": list(outcome.settled), "skipped": list(outcome.skipped)})
        decision_log.record(
            run_dir, "collect", decision_log.EVENT_COST, cost_usd=cost_usd, tokens=1, elapsed_seconds=1.0
        )
        if outcome.produced:
            decision_log.record(
                run_dir,
                steps.STEPS[-1],
                decision_log.EVENT_JUDGED,
                claim="한 줄 주장",
                verdict="보류",
                dossier=f"{run_dir.name}_후보.md",
            )
        return outcome

    monkeypatch.setattr(cycle, "run_cycle", run_cycle)
    monkeypatch.setattr(entrypoint.secrets, "scan", lambda _roots: [])
    return seen


def test_a_second_new_run_dir_does_not_collide(entrypoint: Any) -> None:
    """
    목적: [중요] 같은 «분»에 두 번째 실행 폴더를 만들어도 이름이 겹치지 않는 계약을 고정한다.

    폴더 이름이 `YYYYMMDD_HHMM` 이라 분 단위인데, **전부 건너뛴 회차는 비용 0 에 몇 초면
    끝난다.** 겹치면 방금 완주한 폴더를 다시 잡아 남은 단계가 없다는 답이 돌아오고,
    **아무 일도 안 하는 회차가 상한까지 반복된다.**

    Given: 방금 만든 이름의 폴더가 이미 있다
    When: 새 실행 폴더 이름을 다시 고른다
    Then: 다른 이름이 돌아오고, 앞 여덟 글자(날짜)는 그대로다
    """
    from research_lab.common_constants import RUN_DIR_DATE_LENGTH

    first = entrypoint._new_run_dir()
    first.mkdir(parents=True)

    second = entrypoint._new_run_dir()

    assert second != first
    assert not second.exists()
    assert second.name[:RUN_DIR_DATE_LENGTH] == first.name[:RUN_DIR_DATE_LENGTH]


def test_the_loop_goes_to_the_next_candidate_while_budget_remains(
    entrypoint: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    목적: 한 장을 끝내고 예산이 남으면 «다음 후보로 가는» 계약을 고정한다 (설계 §3.1.1).

    **남는 토큰을 쓰는 것이 이 프로젝트의 목적**이라, 일찍 끝났다고 멈추면 목적과 어긋난다.

    Given: 예산 $10 · 한 장에 $4 가 드는 회차
    When: 회차를 돈다
    Then: 남은 예산이 한 장의 절반에 못 미칠 때까지 돌고, 실행 폴더가 매번 다르다
    """
    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_finished()], cost_usd=4.0)

    assert entrypoint.main(["--cycle-budget-usd", "10"]) == entrypoint.EXIT_OK
    assert len(seen) == 3, "$10 에서 $4 짜리를 셋 돌면 남은 예산이 절반($2) 아래로 내려간다"
    assert len(set(seen)) == len(seen), "반복마다 «다른» 실행 폴더를 써야 한다"


def test_the_loop_stops_when_half_a_unit_is_not_left(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 「평균의 절반도 안 남았으면 시작하지 않는다」가 루프에 걸리는 계약을 고정한다.

    시작 비용(검색·컨텍스트 적재)이 매번 다시 들어, 모자란 예산으로 시작하면 순 낭비다.

    Given: 예산 $5 · 한 장에 $4 가 드는 회차
    When: 회차를 돈다
    Then: 한 장에서 멈춘다
    """
    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_finished()], cost_usd=4.0)

    assert entrypoint.main(["--cycle-budget-usd", "5"]) == entrypoint.EXIT_OK
    assert len(seen) == 1


def test_the_loop_stops_when_a_cycle_is_incomplete(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 미완성으로 끝나면 루프를 «멈추는» 계약을 고정한다.

    미완성을 이어받는 것은 **다음 회차의 첫 단계**다. 같은 회차에서 계속 밀어붙이면
    같은 자리에서 같은 이유로 막히며 예산만 태운다.

    Given: 예산이 넉넉한데 첫 반복이 「그 외」 실패로 끝난다
    When: 회차를 돈다
    Then: 한 번만 돌고 미완성 종료 코드로 끝난다
    """
    from research_lab.runner.failures import FailureKind

    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_failed(FailureKind.OTHER)], cost_usd=1.0)

    assert entrypoint.main(["--cycle-budget-usd", "100"]) == entrypoint.EXIT_INCOMPLETE
    assert len(seen) == 1


def test_the_loop_stops_when_nothing_was_produced(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] 한 장을 «실제로 못 낸» 반복이면 멈추는 계약을 고정한다.

    이 한 조건이 세 경우를 덮는다 — 원장이 포화라 전부 건너뛴 회차 · 탐색이 새 후보를
    못 찾은 회차 · 「닫기만 하는 회차」. **셋 다 다음 반복이 같은 자리에 다시 서므로**,
    안 막으면 비용 0 짜리 회차가 반복 상한까지 돈다.

    Given: 예산이 넉넉한데 단계가 전부 건너뛰어진 회차
    When: 회차를 돈다
    Then: 완주로 보고하되 한 번만 돈다
    """
    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_nothing_produced()], cost_usd=0.0)

    assert entrypoint.main(["--cycle-budget-usd", "100"]) == entrypoint.EXIT_OK
    assert len(seen) == 1


def test_the_loop_stops_immediately_on_limit(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 한도 소진이면 «즉시» 멈추고 그 갈래로 알리는 계약을 고정한다.

    한도는 재시도 대상이 아니다 — 해 봐야 또 막힌다. 그리고 넘어가서 과금되지 않으므로
    이것은 «정상»이다. 다음 회차가 이어받는다.

    Given: 첫 반복이 한도 소진으로 끝난다
    When: 회차를 돈다
    Then: 한 번만 돌고 한도 갈래의 종료 코드로 끝난다
    """
    from research_lab.runner.failures import FailureKind

    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_failed(FailureKind.LIMIT)], cost_usd=0.0)

    assert entrypoint.main(["--cycle-budget-usd", "100"]) == entrypoint.EXIT_LIMIT
    assert len(seen) == 1


def test_the_loop_has_a_hard_iteration_cap(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] 예산 계산이 틀려도 한 회차가 «영원히 돌지 않는» 계약을 고정한다.

    상한이 없으면 한 회차 내내 같은 일을 반복하며 예산을 태우고, 나중에 보면
    **예산은 다 썼고 산출물은 0장**이다. 그런 회차는 「실패」가 아니라 「아무 일 없음」처럼
    보여 며칠 지나서야 알아챈다.

    [주의] 상한 값에 기존 재시도 상한(3)의 관용을 가져오지 않는다. 그것들은 «실패 재시도»의
    상한이고 이것은 «정상 반복»의 폭주 감지라, 3 으로 두면 예산이 남아도 세 장에서 멈춰
    **상한이 정책을 대신하게 된다.**

    Given: 한 장이 사실상 공짜라 남은 예산이 언제나 충분해 보이는 상황
    When: 회차를 돈다
    Then: 반복 상한만큼만 돌고 끝난다
    """
    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_finished()], cost_usd=0.001)

    assert entrypoint.main(["--cycle-budget-usd", "1000"]) == entrypoint.EXIT_OK
    assert len(seen) == entrypoint.MAX_CYCLE_ITERATIONS
    assert entrypoint.MAX_CYCLE_ITERATIONS > 3, "재시도 상한의 관용을 그대로 쓰면 상한이 정책을 대신한다"


def test_every_iteration_is_scanned_for_secrets(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] 자격증명 스캔이 «반복마다» 걸리는 계약을 고정한다.

    이 저장소는 PUBLIC 이고 그 스캔이 커밋 전 1차 방어다. 루프가 폴더를 여럿 만드는데
    마지막 것만 검사하면 **앞의 폴더들이 통째로 검사에서 빠진다** — 그리고 그 사실은
    아무 에러도 내지 않는다.

    Given: 여러 번 도는 회차
    When: 회차를 돈다
    Then: 반복마다 그 실행 폴더가 검사 범위에 들어간다
    """
    scanned: list[tuple[Path, ...]] = []

    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_finished()], cost_usd=4.0)
    monkeypatch.setattr(entrypoint.secrets, "scan", lambda roots: scanned.append(tuple(roots)) or [])

    entrypoint.main(["--cycle-budget-usd", "10"])

    assert len(scanned) == len(seen) > 1
    for run_dir, roots in zip(seen, scanned, strict=True):
        assert run_dir in roots


def test_a_secret_stops_the_loop_at_that_iteration(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 자격증명이 걸리면 «그 자리에서» 멈추는 계약을 고정한다.

    발견하고도 계속 돌면 같은 유출이 폴더마다 쌓인다.

    Given: 첫 반복에서 자격증명이 걸린다
    When: 회차를 돈다
    Then: 한 번만 돌고 자격증명 갈래의 종료 코드로 끝난다
    """
    from research_lab.gate.secrets import Finding

    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_finished()], cost_usd=1.0)
    monkeypatch.setattr(
        entrypoint.secrets,
        "scan",
        lambda _roots: [Finding(path=Path("어딘가"), rule="anthropic-oauth-token", line_number=1)],
    )

    assert entrypoint.main(["--cycle-budget-usd", "100"]) == entrypoint.EXIT_SECRET
    assert len(seen) == 1


def test_the_stop_reason_is_recorded(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 루프가 «왜» 멈췄는지가 로그에 남는 계약을 고정한다.

    한 장에서 멈춘 것도 정상 결과다 — 원장 재고와 그 후보의 비용에 따라 한 장이 맞을 수
    있다. 그래서 확인할 것은 「몇 장을 냈나」가 아니라 **「왜 거기서 멈췄나가 남았나」**이고,
    「한 단위」를 몇 표본으로 쟀는지가 함께 있어야 나중에 그 값을 근거로 쓸 수 있다.

    Given: 예산이 모자라 한 장에서 멈추는 회차
    When: 회차를 돈다
    Then: 결정 로그에 멈춘 사유와 표본 수가 남는다
    """
    from research_lab.runner import decision_log

    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_finished()], cost_usd=4.0)
    entrypoint.main(["--cycle-budget-usd", "5"])

    budget_lines = [entry for entry in decision_log.read(seen[-1]) if entry.get("event") == decision_log.EVENT_BUDGET]

    assert budget_lines, "루프의 판정이 결정 로그에 남아야 한다"
    last = budget_lines[-1]
    assert last.get("reason"), "왜 멈췄는지가 적혀야 한다"
    assert last.get("unit_samples") is not None, "「한 단위」를 몇 표본으로 쟀는지가 함께 있어야 한다"
    assert last.get("spent_usd") is not None and last.get("produced") is not None


def test_the_cycle_records_its_own_start_and_end(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 회차가 «자기 시작과 끝»을 저장소 안의 로그에 남기는 계약을 고정한다.

    [중요] 회차는 주로 새벽에 돈다. 시작 기록이 없으면 강제 종료된 회차가 **아무 흔적도
    남기지 못하고**, 아침에 「중단됐다」와 「아예 안 돌았다」를 가릴 수 없다.
    종료 코드도 지금까지 화면에만 나갔는데, 그 화면 기록은 **저장소 밖**이라 따라오지 않는다.

    Given: 여러 장을 내는 회차
    When: 회차를 돈다
    Then: 시작과 종료가 «각각 한 번» 남고, 종료에 코드와 요약이 들어 있다
    """
    from research_lab.runner import cycle_log

    seen = _stub_cycle(entrypoint, monkeypatch, outcomes=[_finished()], cost_usd=4.0)

    assert entrypoint.main(["--cycle-budget-usd", "10"]) == entrypoint.EXIT_OK

    entries = cycle_log.read(entrypoint.RUNS_DIR)
    started = [entry for entry in entries if entry["event"] == cycle_log.EVENT_STARTED]
    finished = [entry for entry in entries if entry["event"] == cycle_log.EVENT_FINISHED]

    assert len(started) == 1, "폴더를 여럿 만든 회차도 «한 회차»다"
    assert len(finished) == 1
    assert started[0]["cycle_id"] == finished[0]["cycle_id"], "짝이 지어져야 중단을 판정할 수 있다"
    assert finished[0]["exit_code"] == entrypoint.EXIT_OK
    assert finished[0]["produced"] == len(seen)
    assert cycle_log.unfinished_ids(entrypoint.RUNS_DIR) == []


def test_a_secret_finding_still_records_the_end(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: [중요] **루프 중간에서 바로 돌아 나가는** 경로에서도 종료가 남는 계약을 고정한다.

    자격증명이 걸리면 그 자리에서 멈추고 나간다. 그 경로가 종료를 안 적으면 **사람이
    손대야 하는 바로 그 회차가 「중단」으로 보이고**, 원인을 컨테이너나 에이전트에서 찾게 된다.

    Given: 첫 반복에서 자격증명이 걸린다
    When: 회차를 돈다
    Then: 자격증명 갈래의 종료 코드가 로그에 남고, 짝 없는 시작이 없다
    """
    from research_lab.gate.secrets import Finding
    from research_lab.runner import cycle_log

    _stub_cycle(entrypoint, monkeypatch, outcomes=[_finished()], cost_usd=1.0)
    monkeypatch.setattr(
        entrypoint.secrets,
        "scan",
        lambda _roots: [Finding(path=Path("어딘가"), rule="anthropic-oauth-token", line_number=1)],
    )

    assert entrypoint.main(["--cycle-budget-usd", "100"]) == entrypoint.EXIT_SECRET

    finished = [e for e in cycle_log.read(entrypoint.RUNS_DIR) if e["event"] == cycle_log.EVENT_FINISHED]
    assert len(finished) == 1
    assert finished[0]["exit_code"] == entrypoint.EXIT_SECRET
    assert cycle_log.unfinished_ids(entrypoint.RUNS_DIR) == []


def test_an_incomplete_cycle_records_its_exit_code(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 미완성으로 끝난 회차도 «끝났다»고 적히는 계약을 고정한다.

    미완성은 정상 결과다 — 다음 회차가 이어받는다. 그것이 중단으로 보이면
    **고칠 것이 없는 자리를 들여다보게** 된다.

    Given: 미완성으로 끝나는 회차
    When: 회차를 돈다
    Then: 그 종료 코드가 로그에 남는다
    """
    from research_lab.runner import cycle_log
    from research_lab.runner.failures import FailureKind

    _stub_cycle(entrypoint, monkeypatch, outcomes=[_failed(FailureKind.OTHER)], cost_usd=1.0)

    assert entrypoint.main(["--cycle-budget-usd", "100"]) == entrypoint.EXIT_INCOMPLETE

    finished = [e for e in cycle_log.read(entrypoint.RUNS_DIR) if e["event"] == cycle_log.EVENT_FINISHED]
    assert finished[0]["exit_code"] == entrypoint.EXIT_INCOMPLETE


def test_the_billing_guard_records_nothing(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 과금 가드가 막은 회차가 «시작으로 기록되지 않는» 계약을 고정한다.

    [중요] 가드는 한 줄이라도 돌기 «전»에 막는 것이다. 그 앞에 시작을 적으면
    **돌지도 않은 회차가 「시작했다」로 남고**, 짝이 없으니 중단으로 읽힌다 —
    실제로는 아무것도 시작되지 않았고 사람이 환경을 고쳐야 하는 상태다.

    Given: 환경에 API 키가 있다
    When: 회차를 부른다
    Then: 인증 갈래로 끝나고 회차 로그가 비어 있다
    """
    from research_lab.runner import cycle_log

    monkeypatch.setenv("ANTHROPIC_API_KEY", "값은-중요하지-않다")

    assert entrypoint.main([]) == entrypoint.EXIT_AUTH
    assert cycle_log.read(entrypoint.RUNS_DIR) == []


def test_the_end_line_carries_the_token_components(entrypoint: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 그 회차가 쓴 토큰 성분이 종료 줄에 실리는 계약을 고정한다.

    「한 회차가 5시간 한도의 몇 %인가」를 되짚으려면 **회차 단위의 합**이 한 줄에 있어야
    한다. 단계별 값은 폴더마다 흩어져 있고, 한 회차가 폴더를 여럿 만들 수 있다.

    Given: 성분이 든 비용 줄을 남기는 회차
    When: 회차를 돈다
    Then: 종료 줄에 성분 합이 실린다
    """
    from research_lab.runner import cycle_log, decision_log, state, steps

    def run_cycle(*, run_dir: Path, ledger_path: Path, execute: Any) -> Any:
        outcome = _finished()
        state.save(run_dir, {"settled": list(outcome.settled), "skipped": list(outcome.skipped)})
        decision_log.record(
            run_dir,
            "collect",
            decision_log.EVENT_COST,
            cost_usd=4.0,
            tokens=160,
            tokens_input=100,
            tokens_output=50,
            tokens_cache_creation=10,
            tokens_cache_read=90_000,
        )
        decision_log.record(
            run_dir, steps.STEPS[-1], decision_log.EVENT_JUDGED, claim="주장", verdict="보류", dossier="문서.md"
        )
        return outcome

    from research_lab.runner import cycle

    monkeypatch.setattr(cycle, "run_cycle", run_cycle)
    monkeypatch.setattr(entrypoint.secrets, "scan", lambda _roots: [])

    entrypoint.main(["--cycle-budget-usd", "1"])

    finished = [e for e in cycle_log.read(entrypoint.RUNS_DIR) if e["event"] == cycle_log.EVENT_FINISHED][0]

    assert finished["tokens_input"] == 100
    assert finished["tokens_cache_read"] == 90_000, "한도는 캐시에서 읽은 토큰도 먹는다"

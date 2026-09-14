"""예산 루프의 판정 계약을 고정한다 — 「한 단위」를 어떻게 재고 언제 멈추나.

이 파일이 막는 고장은 셋이고 **셋 다 에러를 내지 않는다.**

- **표본이 없는데 「한 단위 = 0」으로 읽는 것.** 그러면 남은 예산이 언제나 충분해 보여
  루프가 상한까지 돈다. 「잴 수 없었다」와 「0이었다」는 다르다
- **비용 0 으로 완주한 폴더를 표본에 넣는 것.** 원장이 포화라 전부 건너뛴 회차도
  단계가 전부 `settled` 라 「완주」로 읽히는데, 그것은 「한 장을 만든 것」이 아니다.
  섞이면 중앙값이 0 쪽으로 끌려 위와 같은 고장이 난다
- **한 표본을 그대로 평균으로 쓰는 것.** 같은 단계가 후보에 따라 두 배 드는 것이
  실측으로 확인됐으므로, 한 표본으로 잡으면 그 배수만큼 틀린다
"""

import json
from pathlib import Path

from research_lab.common_constants import DECISION_LOG_FILENAME
from research_lab.runner import budget, decision_log, state, steps

# 실측된 두 회차의 비용. 이 둘이 **2배 넘게 갈리는 것**이 이 모듈이 존재하는 이유다
CHEAP_RUN_USD = 1.9609
COSTLY_RUN_USD = 4.5735


def _make_run(runs_dir: Path, name: str, *, costs: list[float], settled: list[str] | None = None) -> Path:
    """비용 줄이 든 실행 폴더 하나를 만든다.

    `settled` 를 안 주면 **완주한** 폴더가 된다. 표본이 되려면 완주해야 하기 때문이다.
    """
    run_dir = runs_dir / name
    state.save(run_dir, {"settled": list(steps.STEPS) if settled is None else settled, "skipped": []})
    for spent in costs:
        decision_log.record(run_dir, "collect", decision_log.EVENT_COST, cost_usd=spent, tokens=1, elapsed_seconds=1.0)
    return run_dir


def test_no_samples_is_not_zero(tmp_path: Path) -> None:
    """
    목적: 표본이 없을 때 「한 단위」가 «0 이 아니라 없음»임을 고정한다.

    0 으로 읽으면 남은 예산이 언제나 충분해 보여 **루프가 상한까지 돈다.**
    「잴 수 없었다」와 「0이었다」를 구별하지 못하는 계측은 계측이 아니라 잡음이다.

    Given: 실행 폴더가 하나도 없는 뿌리
    When: 「한 단위」를 잰다
    Then: 표본이 0건이고 값이 None 이며, 다음 장을 시작하지 않는다
    """
    unit = budget.unit_cost(tmp_path / "runs")

    assert unit.samples == 0
    assert unit.median_usd is None
    assert budget.shortfall_reason(unit, remaining_usd=1000.0) is not None


def test_zero_cost_completed_run_is_not_a_sample(tmp_path: Path) -> None:
    """
    목적: 비용 0 으로 완주한 폴더가 표본에서 빠지는 계약을 고정한다.

    원장이 포화라 전부 건너뛴 회차도 단계가 전부 `settled` 라 「완주」로 읽힌다.
    그것은 **「한 장을 만든 것」이 아니다.** 섞이면 중앙값이 0 쪽으로 끌리고,
    그러면 남은 예산이 늘 충분해 보여 이 파일이 막으려는 고장이 그대로 난다.

    Given: 비용 0 으로 완주한 폴더와, 값이 있는 폴더
    When: 「한 단위」를 잰다
    Then: 표본은 하나뿐이고 그 값이 비용이 있는 쪽이다
    """
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260101_0100", costs=[])
    _make_run(runs_dir, "20260102_0100", costs=[COSTLY_RUN_USD])

    unit = budget.unit_cost(runs_dir)

    assert unit.samples == 1
    assert unit.median_usd == COSTLY_RUN_USD


def test_unfinished_run_is_not_a_sample(tmp_path: Path) -> None:
    """
    목적: 미완성 폴더가 표본에서 빠지는 계약을 고정한다.

    [중요] 이 한 줄이 **단계를 늘리기 전에 완주한 폴더를 자동으로 걸러낸다.**
    다섯 단계이던 시절의 완주 폴더는 여덟 단계 기준으로 `settled` 가 모자라고,
    실제로 그 회차는 근거 문서를 내지 않았다 — 「한 장」의 표본이 아니다.

    Given: 앞 단계만 끝난 폴더와, 완주한 폴더
    When: 「한 단위」를 잰다
    Then: 완주한 쪽만 표본이 된다
    """
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260101_0100", costs=[CHEAP_RUN_USD], settled=list(steps.STEPS[:-1]))
    _make_run(runs_dir, "20260102_0100", costs=[COSTLY_RUN_USD])

    unit = budget.unit_cost(runs_dir)

    assert unit.samples == 1
    assert unit.median_usd == COSTLY_RUN_USD


def test_unit_is_neither_sample_when_two_differ(tmp_path: Path) -> None:
    """
    목적: 두 표본이 2배 갈릴 때 「한 단위」가 어느 한쪽이 아님을 고정한다.

    한 표본을 그대로 평균으로 잡으면 **그 배수만큼 틀린다** — 같은 단계가 후보에 따라
    두 배 드는 것이 실측으로 확인됐다. 그래서 분포에서 뽑는다.

    Given: 실측된 두 회차의 비용($1.9609 · $4.5735)
    When: 「한 단위」를 잰다
    Then: 두 값 사이에 있고, 어느 쪽과도 같지 않으며, min·max 가 함께 남는다
    """
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260101_0100", costs=[CHEAP_RUN_USD])
    _make_run(runs_dir, "20260102_0100", costs=[COSTLY_RUN_USD])

    unit = budget.unit_cost(runs_dir)

    assert unit.samples == 2
    assert unit.median_usd is not None
    assert CHEAP_RUN_USD < unit.median_usd < COSTLY_RUN_USD
    assert unit.min_usd == CHEAP_RUN_USD
    assert unit.max_usd == COSTLY_RUN_USD


def test_a_run_cost_is_the_sum_of_its_steps(tmp_path: Path) -> None:
    """
    목적: 한 폴더의 비용이 «그 폴더의 모든 단계 합»임을 고정한다.

    「한 단위」는 문서 한 장을 만드는 데 든 총액이지 단계 하나의 값이 아니다.

    Given: 단계마다 비용이 적힌 완주 폴더
    When: 그 폴더의 비용을 잰다
    Then: 합이 나온다
    """
    runs_dir = tmp_path / "runs"
    run_dir = _make_run(runs_dir, "20260101_0100", costs=[0.5, 1.25, 0.25])

    assert budget.cost_of(run_dir) == 2.0


def test_below_half_a_unit_does_not_start(tmp_path: Path) -> None:
    """
    목적: 「평균의 절반도 안 남았으면 시작하지 않는다」를 고정한다.

    시작 비용(검색·컨텍스트 적재)이 매번 다시 들어, 모자란 예산으로 시작하면 순 낭비다.

    Given: 한 단위가 $4 인 표본
    When: 남은 예산이 $1 이다
    Then: 시작하지 않고 그 사유를 돌려준다
    """
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260101_0100", costs=[4.0])

    reason = budget.shortfall_reason(budget.unit_cost(runs_dir), remaining_usd=1.0)

    assert reason is not None
    assert "1" in reason and "4" in reason, "남은 예산과 한 단위가 사유에 드러나야 한다"


def test_half_a_unit_is_enough_to_start(tmp_path: Path) -> None:
    """
    목적: 절반이 남았으면 시작하는 계약을 고정한다.

    [중요] 모자란 예산으로 시작해 미완성이 되는 것은 «사고가 아니다» — 다음 회차가
    이어받으므로 일이 버려지지 않고, 미완성은 구조적으로 최대 1개라 쌓이지도 않는다.
    그래서 임계를 보수적으로 올리지 않는다. 그러면 **남는 토큰을 쓴다는 목적과 어긋난다.**

    Given: 한 단위가 $4 인 표본
    When: 남은 예산이 딱 절반($2)이다
    Then: 시작한다
    """
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260101_0100", costs=[4.0])

    assert budget.shortfall_reason(budget.unit_cost(runs_dir), remaining_usd=2.0) is None


def test_one_sample_still_starts(tmp_path: Path) -> None:
    """
    목적: 표본이 하나여도 루프가 도는 계약을 고정한다.

    [중요] 「표본이 적으니 안 돈다」로 두면 회차당 한 장씩만 쌓여 **표본이 늘지 않고,
    루프가 영영 안 도는 자리에 스스로 갇힌다.** 대신 표본 수를 로그에 적어,
    그 값을 근거로 쓸 때 「한 표본이었다」가 드러나게 한다.

    Given: 표본이 하나뿐인 뿌리
    When: 예산이 넉넉하다
    Then: 시작한다
    """
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260101_0100", costs=[COSTLY_RUN_USD])

    unit = budget.unit_cost(runs_dir)

    assert unit.samples == 1
    assert budget.shortfall_reason(unit, remaining_usd=COSTLY_RUN_USD) is None


def test_broken_cost_lines_do_not_raise(tmp_path: Path) -> None:
    """
    목적: 깨진 비용 줄에도 예외를 올리지 않는 계약을 고정한다.

    계층 계약 — **검사기가 죽어서 파이프라인을 멈추게 해서는 안 된다.** 결정 로그는
    회차마다 덧붙여지는 파일이라 한 줄이 반쯤 쓰이다 끊길 수 있고, 사람이 손으로
    고칠 수도 있다. 여기서 터지면 **멀쩡한 회차가 예산 판정에서 죽는다.**

    Given: 숫자가 아닌 값·빠진 열쇠·깨진 JSON 이 섞인 결정 로그
    When: 비용과 「한 단위」를 잰다
    Then: 예외 없이 읽히는 값만 더해진다
    """
    runs_dir = tmp_path / "runs"
    run_dir = _make_run(runs_dir, "20260101_0100", costs=[1.5])

    log = run_dir / DECISION_LOG_FILENAME
    with log.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"step": "rebut", "event": decision_log.EVENT_COST, "cost_usd": "비쌌다"}) + "\n")
        file.write(json.dumps({"step": "rebut", "event": decision_log.EVENT_COST}) + "\n")
        file.write(json.dumps({"step": "rebut", "event": decision_log.EVENT_COST, "cost_usd": None}) + "\n")
        file.write("{깨진 줄\n")

    assert budget.cost_of(run_dir) == 1.5
    assert budget.unit_cost(runs_dir).samples == 1


def test_unreadable_state_is_skipped_not_raised(tmp_path: Path) -> None:
    """
    목적: 상태 파일이 깨진 폴더를 건너뛰는 계약을 고정한다.

    진입점이 같은 이유로 같게 동작한다 — 그 폴더 하나 때문에 파이프라인이 서면 안 된다.

    Given: 상태 파일이 깨진 폴더와 멀쩡한 완주 폴더
    When: 「한 단위」를 잰다
    Then: 예외 없이 멀쩡한 쪽만 표본이 된다
    """
    runs_dir = tmp_path / "runs"
    broken = runs_dir / "20260101_0100"
    broken.mkdir(parents=True)
    (broken / "state.json").write_text("{깨졌다", encoding="utf-8")
    _make_run(runs_dir, "20260102_0100", costs=[COSTLY_RUN_USD])

    assert budget.unit_cost(runs_dir).samples == 1


def test_unknown_step_name_in_state_is_skipped(tmp_path: Path) -> None:
    """
    목적: 정의에 없는 단계 이름이 든 예전 상태를 건너뛰는 계약을 고정한다.

    단계 이름을 바꾼 뒤에 남은 폴더가 여기 걸린다. 「완주했나」를 판정하려면 단계 이름을
    봐야 하는데, 모르는 이름에서 터지면 **예전 폴더 하나가 이후 모든 회차의 예산 판정을 죽인다.**

    Given: 예전 이름이 든 상태 파일과 멀쩡한 완주 폴더
    When: 「한 단위」를 잰다
    Then: 예외 없이 멀쩡한 쪽만 표본이 된다
    """
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260101_0100", costs=[CHEAP_RUN_USD], settled=["explore", "옛날단계"])
    _make_run(runs_dir, "20260102_0100", costs=[COSTLY_RUN_USD])

    assert budget.unit_cost(runs_dir).samples == 1


def test_log_fields_name_the_sample_count(tmp_path: Path) -> None:
    """
    목적: 「한 단위」가 로그에 «표본 수와 함께» 실리는 계약을 고정한다.

    [중요] 이 값이 없으면 나중에 그 수치를 근거로 쓸 때 **「한 표본이었다」가 드러나지 않는다.**
    min·max 를 함께 남기는 것도 같은 이유다 — 중앙값을 쓰기로 한 것 자체가 가정이고,
    그 가정을 다시 보려면 재료가 쌓여 있어야 한다.

    Given: 값이 갈리는 두 표본
    When: 로그에 실을 값을 만든다
    Then: 표본 수·중앙값·최소·최대가 모두 들어 있다
    """
    runs_dir = tmp_path / "runs"
    _make_run(runs_dir, "20260101_0100", costs=[CHEAP_RUN_USD])
    _make_run(runs_dir, "20260102_0100", costs=[COSTLY_RUN_USD])

    fields = budget.unit_cost(runs_dir).as_log_fields()

    assert fields["unit_samples"] == 2
    assert fields["unit_median_usd"] is not None
    assert fields["unit_min_usd"] == CHEAP_RUN_USD
    assert fields["unit_max_usd"] == COSTLY_RUN_USD

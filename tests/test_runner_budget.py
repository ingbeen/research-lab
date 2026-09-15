"""회차가 «쓴 돈»을 세는 계약을 고정한다.

여기서 막는 고장은 **에러를 내지 않는 것들**이다.

- **깨진 줄 하나에 터지는 것.** 결정 로그는 회차마다 덧붙여지는 파일이라 한 줄이 반쯤
  쓰이다 끊길 수 있고, 사람이 손으로 고칠 수도 있다. 여기서 터지면 **멀쩡한 회차가
  비용 집계에서 죽는다**
- **참/거짓을 1달러로 세는 것.** 파이썬에서 `True` 는 정수다
"""

import json
from pathlib import Path

from research_lab.common_constants import DECISION_LOG_FILENAME
from research_lab.runner import budget, decision_log


def _make_run(runs_dir: Path, name: str, *, costs: list[float]) -> Path:
    """단계마다 비용이 적힌 실행 폴더를 만든다."""
    run_dir = runs_dir / name
    for index, cost in enumerate(costs):
        decision_log.record(run_dir, f"단계{index}", decision_log.EVENT_COST, cost_usd=cost)
    return run_dir


def test_a_run_cost_is_the_sum_of_its_steps(tmp_path: Path) -> None:
    """
    목적: 한 폴더의 비용이 «그 폴더의 모든 단계 합»임을 고정한다.

    한 장을 만드는 데 든 총액이지 단계 하나의 값이 아니다.

    Given: 단계마다 비용이 적힌 폴더
    When: 그 폴더의 비용을 잰다
    Then: 합이 나온다
    """
    run_dir = _make_run(tmp_path / "runs", "20260101_0100", costs=[0.5, 1.25, 0.25])

    assert budget.cost_of(run_dir) == 2.0


def test_a_folder_without_a_log_costs_nothing(tmp_path: Path) -> None:
    """
    목적: 로그가 없는 폴더에서 예외 대신 0 이 나오는 계약을 고정한다.

    회차는 폴더를 «만들기 전»에도 비용을 묻는다 — 이 회차가 쓴 몫을 차분으로 세기 때문에
    시작 시점의 값이 필요하다. 그 자리에서 터지면 회차가 아예 시작되지 않는다.

    Given: 아직 아무것도 안 적힌 폴더
    When: 비용을 잰다
    Then: 0 이다
    """
    assert budget.cost_of(tmp_path / "runs" / "20260101_0100") == 0.0


def test_broken_cost_lines_do_not_raise(tmp_path: Path) -> None:
    """
    목적: 깨진 비용 줄에도 예외를 올리지 않는 계약을 고정한다.

    계층 계약 — **검사기가 죽어서 파이프라인을 멈추게 해서는 안 된다.** 결정 로그는
    회차마다 덧붙여지는 파일이라 한 줄이 반쯤 쓰이다 끊길 수 있고, 사람이 손으로
    고칠 수도 있다.

    Given: 숫자가 아닌 값·빠진 열쇠·참/거짓·깨진 JSON 이 섞인 결정 로그
    When: 비용을 잰다
    Then: 예외 없이 읽히는 값만 더해진다
    """
    run_dir = _make_run(tmp_path / "runs", "20260101_0100", costs=[1.5])

    with (run_dir / DECISION_LOG_FILENAME).open("a", encoding="utf-8") as file:
        file.write(json.dumps({"step": "rebut", "event": decision_log.EVENT_COST, "cost_usd": "비쌌다"}) + "\n")
        file.write(json.dumps({"step": "rebut", "event": decision_log.EVENT_COST}) + "\n")
        file.write(json.dumps({"step": "rebut", "event": decision_log.EVENT_COST, "cost_usd": None}) + "\n")
        # [주의] 참/거짓은 파이썬에서 정수라, 걸러내지 않으면 1달러로 더해진다
        file.write(json.dumps({"step": "rebut", "event": decision_log.EVENT_COST, "cost_usd": True}) + "\n")
        file.write("{깨진 줄\n")

    assert budget.cost_of(run_dir) == 1.5


def test_a_line_cut_mid_character_does_not_kill_the_count(tmp_path: Path) -> None:
    """
    목적: [중요] **글자가 반쯤 잘린 줄** 하나가 비용 집계를 죽이지 않는 계약을 고정한다.

    잘리는 상황이 곧 강제 종료이고, 이 저장소의 로그는 사유·주장이 전부 한글이라
    **잘린 줄은 거의 언제나 이 모양**이 된다. 파일을 통째로 디코드하면 그 한 줄이
    **파일 전체**를 못 읽게 만든다.

    Given: 마지막 줄이 한글 중간에서 끊긴 폴더
    When: 비용을 잰다
    Then: 예외 없이 멀쩡한 줄만 더해진다
    """
    run_dir = _make_run(tmp_path / "runs", "20260101_0100", costs=[1.0])
    line = json.dumps({"step": "rebut", "event": decision_log.EVENT_FAILED, "reason": "한도에 걸렸습니다"}) + "\n"
    with (run_dir / DECISION_LOG_FILENAME).open("ab") as file:
        file.write(line.encode()[:-9])

    assert budget.cost_of(run_dir) == 1.0

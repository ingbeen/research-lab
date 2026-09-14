"""진입점(`scripts/run_night.py`)의 계약을 고정한다.

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
    spec = importlib.util.spec_from_file_location("run_night", PROJECT_ROOT / "scripts" / "run_night.py")
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


def test_resume_picks_up_the_unfinished_night(entrypoint: Any) -> None:
    """
    목적: 인자 «없이» 불렸을 때 미완성을 이어받는 계약을 고정한다.

    이것이 밤의 첫 단계인 「① 미완성」이다. 무인 실행은 언제나 인자 없이 불리므로,
    여기서 새 폴더를 만들면 **이어받기가 영영 동작하지 않는다** — 어제 끊긴 밤은
    아무도 손대지 않은 채 쌓이고, 끝난 단계를 매일 다시 돈다.

    Given: 탐색만 끝난 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 돌아온다
    """
    unfinished = _make_run(entrypoint, "20260101_0100", ["explore"])

    assert entrypoint._resolve_run_dir(None) == unfinished


def test_finished_night_is_not_resumed(entrypoint: Any) -> None:
    """
    목적: 다 끝난 밤을 다시 잡지 않는 계약을 고정한다.

    이어받으면 완성된 산출물 위에 다시 쓴다.

    Given: 모든 단계가 끝난 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 아니라 새 폴더가 돌아온다
    """
    from research_lab.runner import steps

    finished = _make_run(entrypoint, "20260101_0100", list(steps.STEPS))

    assert entrypoint._resolve_run_dir(None) != finished


def test_newest_unfinished_night_wins(entrypoint: Any) -> None:
    """
    목적: 미완성이 여럿이면 «가장 최근» 것을 잡는 계약을 고정한다.

    Given: 미완성 실행 폴더 둘
    When: 인자 없이 실행 폴더를 고른다
    Then: 나중 것이 돌아온다
    """
    _make_run(entrypoint, "20260101_0100", [])
    newer = _make_run(entrypoint, "20260102_0100", [])

    assert entrypoint._resolve_run_dir(None) == newer


def test_locked_night_is_skipped(entrypoint: Any) -> None:
    """
    목적: 다른 프로세스가 잡고 있는 폴더를 고르지 않는 계약을 고정한다.

    골라 봐야 잠금에 막혀 그 밤은 아무것도 못 한다.

    Given: 잠금 파일이 있는 미완성 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 아니다
    """
    from research_lab.common_constants import LOCK_FILENAME

    locked = _make_run(entrypoint, "20260101_0100", [])
    (locked / LOCK_FILENAME).write_text("999", encoding="utf-8")

    assert entrypoint._resolve_run_dir(None) != locked


def test_stale_step_names_do_not_stop_the_pipeline(entrypoint: Any) -> None:
    """
    목적: 예전 단계 이름이 든 상태가 파이프라인을 세우지 «않는» 계약을 고정한다.

    단계 이름을 바꾸면 예전 상태 파일이 남는다. 그걸 만나 터지면 **그 폴더 하나 때문에
    이후 모든 밤이 시작조차 못 한다.**

    Given: 정의에 없는 단계 이름이 든 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 예외 없이 새 폴더가 돌아온다
    """
    stale = _make_run(entrypoint, "20260101_0100", ["옛날에_있던_단계"])

    assert entrypoint._resolve_run_dir(None) != stale


def test_unfinished_night_without_a_candidate_is_skipped(entrypoint: Any) -> None:
    """
    목적: 그 밤의 후보가 «안 박힌» 미완성을 이어받지 않는 계약을 고정한다.

    [중요] 단계를 늘리면 예전 상태 파일이 그대로 남는다. 수집까지 끝난 예전 밤은
    남은 단계가 반증인데 **그 밤이 어느 후보를 팠는지 상태에 없다.** 그대로 이어받으면
    후보 없이 반증이 돌아 상한까지 헛돈다. 단계 이름을 바꿨을 때 예전 상태를 건너뛰는
    것과 같은 갈래이며, 그 폴더 하나 때문에 파이프라인이 서면 안 된다.

    Given: 수집까지 끝났지만 후보가 안 박힌 예전 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 아니라 새 폴더가 돌아온다
    """
    stale = _make_run(entrypoint, "20260101_0100", ["explore", "collect"])

    assert entrypoint._resolve_run_dir(None) != stale


def test_unfinished_night_with_a_candidate_is_resumed(entrypoint: Any) -> None:
    """
    목적: 후보가 박힌 미완성은 «그대로 이어받는» 계약을 고정한다.

    위 계약이 지나치게 넓으면 정상적인 이어받기까지 버린다 — 반증에서 끊긴 밤은
    후보가 박혀 있으므로 반드시 이어받아야 한다. 다시 돌면 수집을 처음부터 하게 되어
    **그 후보의 찬성 근거를 한 번 더 사게 된다.**

    Given: 수집까지 끝나고 후보가 박힌 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 돌아온다
    """
    from research_lab.runner import state

    unfinished = _make_run(entrypoint, "20260101_0100", ["explore", "collect"])
    state.pin_candidate(unfinished, state.Candidate(claim="그 밤이 판 후보", identifier="pinned"))

    assert entrypoint._resolve_run_dir(None) == unfinished


def test_closed_night_is_not_resumed(entrypoint: Any) -> None:
    """
    목적: [중요] 「막힘」으로 «닫힌» 폴더를 이어받지 않는 계약을 고정한다 (설계 §10.1 E).

    이것이 없으면 E 가 통째로 동작하지 않는다. 후보를 원장에서 걷어내도 그 폴더의
    「그 밤의 후보」는 살아 있어, 다음 밤이 이어받아 **같은 단계를 또 부르고 또 막힌다.**
    바로 위 계약(후보가 박힌 미완성은 이어받는다)이 여기서는 정확히 반대로 작용하므로
    닫힘을 «먼저» 봐야 한다.

    Given: 후보가 박혀 있지만 막힘으로 닫힌 실행 폴더
    When: 인자 없이 실행 폴더를 고른다
    Then: 그 폴더가 아니라 새 폴더가 돌아온다
    """
    from research_lab.runner import state

    closed = _make_run(entrypoint, "20260101_0100", ["explore", "collect"])
    state.pin_candidate(closed, state.Candidate(claim="막힌 후보", identifier="stuck"))
    state.close(closed, "반증 단계가 세 밤 연속 막혔다")

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
    When: 밤을 돌린다
    Then: 인증 갈래의 종료 코드로 끝난다
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-예시")

    assert entrypoint.main([]) == entrypoint.EXIT_AUTH


def test_exit_codes_are_all_distinct(entrypoint: Any) -> None:
    """
    목적: 갈래마다 다른 종료 코드를 주는 계약을 고정한다.

    무인 실행에서 사람이 받는 신호가 이것뿐이다. 둘이 겹치면
    「인증이 끊겨 며칠 안 돈 상태」와 「그냥 한도에 걸린 밤」이 구별되지 않는다.

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

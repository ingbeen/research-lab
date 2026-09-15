"""회차 «생애» 로그의 계약을 고정한다 — 시작과 종료, 그리고 「중단」 판정.

이 파일이 막는 고장은 하나이고 **그것은 에러를 내지 않는다.**

- **시작 기록이 없으면 「중단됐다」와 「아예 안 돌았다」가 구별되지 않는다.**
  컨테이너가 죽으면 죽는 프로세스는 아무것도 못 적는다. 그래서 **중단은 「끝이 없다」로
  판정할 수밖에 없고, 그러려면 「시작했다」가 먼저 남아 있어야** 한다.
  회차는 주로 새벽에 도므로, 이 구별이 없으면 아침에 무슨 일이 났는지 되짚을 수 없다.

[중요] **적을 수 있는 것이 이름과 타입으로 고정돼 있다.** 결정 로그처럼 아무 값이나 받는
통로를 두지 않는 이유는, 이 파일이 **자격증명 스캔 범위 «밖»**이기 때문이다 —
회차마다 덧붙는 파일을 스캔에 넣으면 한 번 걸린 뒤 이후 모든 회차가 실패한다.
막는 것이 검사가 아니라 **모양**이어야 한다. 이 저장소는 PUBLIC 이다.
"""

from pathlib import Path

from research_lab.runner import cycle_log


def _start(runs_dir: Path, cycle_id: str) -> None:
    """회차 하나를 시작한 것으로 적는다."""
    cycle_log.started(
        runs_dir,
        cycle_id=cycle_id,
        cycle_budget_usd=10.0,
        step_budget_usd=2.0,
        ledger_name="원장.md",
        run_dir_name=None,
    )


def _finish(runs_dir: Path, cycle_id: str, *, exit_code: int = 0) -> None:
    """그 회차를 끝난 것으로 적는다."""
    cycle_log.finished(
        runs_dir,
        cycle_id=cycle_id,
        exit_code=exit_code,
        produced=1,
        spent_usd=4.5735,
        stop_reason="예산이 모자랍니다",
        last_run_dir_name="20260915_1200",
        tokens=None,
    )


def test_start_is_recorded_before_anything_else(tmp_path: Path) -> None:
    """
    목적: 시작이 «파일로» 남는 계약을 고정한다.

    이것이 없으면 강제 종료된 회차가 **아무 흔적도 남기지 못한다.**
    죽는 프로세스는 아무것도 적을 수 없으므로, 중단을 판정할 재료는 «미리 적힌 시작»뿐이다.

    Given: 아직 아무것도 없는 뿌리
    When: 회차 시작을 적는다
    Then: 그 회차의 시작이 읽히고, 시각과 인자가 함께 들어 있다
    """
    _start(tmp_path, "cyc-1")

    entries = cycle_log.read(tmp_path)

    assert len(entries) == 1
    assert entries[0]["event"] == cycle_log.EVENT_STARTED
    assert entries[0]["cycle_id"] == "cyc-1"
    assert entries[0]["cycle_budget_usd"] == 10.0
    assert entries[0]["ts"], "시각이 없으면 언제 돌았는지 되짚을 수 없다"


def test_finish_records_the_exit_code(tmp_path: Path) -> None:
    """
    목적: 종료 «코드»가 저장소 안의 로그에 남는 계약을 고정한다.

    [중요] 무인 실행에서 사람이 받는 신호가 종료 코드뿐인데, 지금까지 그 값은 화면에만
    나갔다. 그 화면 기록은 **저장소 밖**이라 기계를 옮기면 따라오지 않는다.

    Given: 시작이 적힌 회차
    When: 종료를 적는다
    Then: 종료 코드와 그 회차의 요약이 함께 남는다
    """
    _start(tmp_path, "cyc-1")
    _finish(tmp_path, "cyc-1", exit_code=2)

    finished = [entry for entry in cycle_log.read(tmp_path) if entry["event"] == cycle_log.EVENT_FINISHED]

    assert len(finished) == 1
    assert finished[0]["exit_code"] == 2
    assert finished[0]["produced"] == 1
    assert finished[0]["stop_reason"] == "예산이 모자랍니다"


def test_start_without_finish_reads_as_interrupted(tmp_path: Path) -> None:
    """
    목적: 「시작은 했는데 끝이 없다」가 중단으로 읽히는 계약을 고정한다.

    이 판정이 이 모듈의 존재 이유다. 강제 종료·컨테이너 죽음·전원 차단은 모두
    **끝을 적지 못한 채** 끝나므로, 짝이 없는 시작이 곧 그 신호다.

    Given: 끝난 회차 하나와 끝나지 않은 회차 하나
    When: 짝 없는 시작을 찾는다
    Then: 끝나지 않은 쪽만 나온다
    """
    _start(tmp_path, "끝난회차")
    _finish(tmp_path, "끝난회차")
    _start(tmp_path, "끊긴회차")

    assert cycle_log.unfinished_ids(tmp_path) == ["끊긴회차"]


def test_nothing_recorded_is_not_an_interruption(tmp_path: Path) -> None:
    """
    목적: 「아예 안 돌았다」가 중단과 구별되는 계약을 고정한다.

    예약이 아예 안 걸렸거나 트리거가 죽은 경우는 **시작조차 없다.** 그것을 중단으로 읽으면
    엉뚱한 곳(컨테이너·에이전트)을 들여다보게 된다 — 봐야 할 곳은 트리거 쪽이다.

    Given: 기록이 하나도 없는 뿌리
    When: 읽고 짝 없는 시작을 찾는다
    Then: 둘 다 비어 있고 예외가 나지 않는다
    """
    assert cycle_log.read(tmp_path) == []
    assert cycle_log.unfinished_ids(tmp_path) == []


def test_broken_lines_do_not_raise(tmp_path: Path) -> None:
    """
    목적: 깨진 줄에도 예외를 올리지 않는 계약을 고정한다.

    계층 계약 — **검사기가 죽어서 파이프라인을 멈추게 해서는 안 된다.** 이 파일은 회차마다
    덧붙여지므로 한 줄이 반쯤 쓰이다 끊길 수 있고, 사람이 손으로 고칠 수도 있다.
    여기서 터지면 **멀쩡한 회차가 시작하자마자 죽는다.**

    Given: 깨진 줄과 열쇠가 빠진 줄이 섞인 기록
    When: 읽고 짝 없는 시작을 찾는다
    Then: 예외 없이 읽히는 줄만 쓰인다
    """
    _start(tmp_path, "cyc-1")
    path = tmp_path / cycle_log.CYCLE_LOG_FILENAME
    with path.open("a", encoding="utf-8") as file:
        file.write("{깨진 줄\n")
        file.write('{"event": "started"}\n')
        file.write("\n")

    assert cycle_log.unfinished_ids(tmp_path) == ["cyc-1"]


def test_ids_are_unique_within_the_same_minute(tmp_path: Path) -> None:
    """
    목적: 회차 식별값이 «시각과 무관하게» 유일한 계약을 고정한다.

    같은 분에 두 회차가 시작할 수 있다 — 전부 건너뛴 회차는 비용 0 에 몇 초면 끝난다.
    시각으로 짝지으면 그때 **시작 둘과 종료 하나가 섞여 중단 판정이 틀린다.**

    Given: 연달아 만든 식별값 둘
    When: 비교한다
    Then: 서로 다르다
    """
    assert cycle_log.new_cycle_id() != cycle_log.new_cycle_id()


def test_tokens_ride_on_the_finish_line(tmp_path: Path) -> None:
    """
    목적: 그 회차가 쓴 토큰 성분이 종료 줄에 실리는 계약을 고정한다.

    「한 회차가 5시간 한도의 몇 %인가」를 나중에 되짚으려면 **그 회차 단위의 합**이
    한 줄에 있어야 한다. 단계별 값은 실행 폴더마다 흩어져 있고, 한 회차가 폴더를 여럿
    만들 수 있으므로 폴더만 봐서는 회차 합이 나오지 않는다.

    Given: 성분이 있는 회차
    When: 종료를 적는다
    Then: 네 성분이 그대로 남는다
    """
    from research_lab.runner import usage

    _start(tmp_path, "cyc-1")
    cycle_log.finished(
        tmp_path,
        cycle_id="cyc-1",
        exit_code=0,
        produced=2,
        spent_usd=8.0,
        stop_reason="예산이 모자랍니다",
        last_run_dir_name="20260915_1200",
        tokens=usage.Tokens(input=10, output=20, cache_creation=30, cache_read=40),
    )

    finished = [entry for entry in cycle_log.read(tmp_path) if entry["event"] == cycle_log.EVENT_FINISHED][0]

    assert finished["tokens_input"] == 10
    assert finished["tokens_output"] == 20
    assert finished["tokens_cache_creation"] == 30
    assert finished["tokens_cache_read"] == 40
    # [중요] 합계도 같이 적힌다. 보정이 이 값을 분자로 쓰므로, 없으면 사람이 성분 넷을
    # 손으로 더해야 하고 **눈으로 읽어 다시 타이핑한 값은 근거물이 아니다**
    assert finished["tokens_limit_total"] == 100


def test_a_line_cut_mid_character_does_not_raise(tmp_path: Path) -> None:
    """
    목적: [중요] **글자가 반쯤 잘린 줄**에서도 예외를 올리지 않는 계약을 고정한다.

    앞 테스트(깨진 JSON)로는 이 자리가 안 잡혔다. 파일을 통째로 문자열로 읽으면
    **잘린 한글 한 글자가 파일 전체를 못 읽게 만들고**, 그 예외는 줄 단위 JSON 가드보다
    «먼저» 터져 가드가 한 번도 돌지 않는다.

    이 로그의 사유·주장은 전부 한글이라 **잘린 줄은 거의 언제나 이 모양**이 된다.
    그리고 잘리는 상황이 바로 **중단**이므로, 여기서 터지면
    **중단을 진단하려고 만든 장치가 정작 중단된 회차에서 죽는다.**

    Given: 마지막 줄이 한글 중간에서 끊긴 기록
    When: 읽고 짝 없는 시작을 찾는다
    Then: 예외 없이 멀쩡한 줄만 읽힌다
    """
    _start(tmp_path, "cyc-1")
    path = tmp_path / cycle_log.CYCLE_LOG_FILENAME
    truncated = '{"event": "finished", "cycle_id": "cyc-1", "stop_reason": "예산이 모자랍니다"}\n'.encode()
    with path.open("ab") as file:
        # 한글 한 글자(3바이트) 중간에서 끊는다 — 강제 종료가 쓰기 도중에 떨어진 모양이다
        file.write(truncated[:-12])

    assert cycle_log.unfinished_ids(tmp_path) == ["cyc-1"], "잘린 종료 줄은 «끝»으로 세지 않는다"
    assert len(cycle_log.read(tmp_path)) == 1

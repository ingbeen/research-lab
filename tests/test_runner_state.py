"""상태 파일의 원자적 쓰기와 동시 실행 잠금 계약을 고정한다.

상태의 진실은 대화가 아니라 «파일»에 있다. 그래서 한도로 끊겨도 · 컨테이너가 죽어도 ·
PC 가 재부팅돼도 같은 방식으로 복구된다. 그 전제가 성립하려면 둘이 필요하다.

1. **반쯤 쓴 상태가 완성본 자리에 남지 않는다** — 임시 파일에 쓰고 성공했을 때만 rename
2. **두 프로세스가 같은 상태를 번갈아 쓰지 않는다** — rename 은 원자적이지만 그건 막지 못한다

[주의] 2번이 없으면 갱신 하나가 «조용히» 사라진다. 예외도 로그도 남지 않는다.
"""

import json
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

import pytest

from research_lab import common_constants
from research_lab.common_constants import LOCK_FILENAME
from research_lab.runner import state


def test_load_returns_none_when_absent(tmp_path: Path) -> None:
    """
    목적: 상태가 없는 첫 회차를 「빈 상태」로 다루는 계약을 고정한다.

    Given: 아무것도 없는 실행 폴더
    When: 상태를 읽는다
    Then: None 이 돌아온다 (예외가 아니다)
    """
    assert state.load(tmp_path) is None


def test_saved_state_round_trips(tmp_path: Path) -> None:
    """
    목적: 쓴 것을 그대로 읽어 오는 계약을 고정한다.

    Given: 단계 하나가 끝난 상태
    When: 저장하고 다시 읽는다
    Then: 같은 값이 돌아온다
    """
    payload = {"candidate": "월말 진입", "completed": ["explore"]}

    state.save(tmp_path, payload)

    assert state.load(tmp_path) == payload


def test_save_writes_to_the_agreed_filename(tmp_path: Path) -> None:
    """
    목적: 상태 파일 이름이 공통 상수에서만 정해지는 계약을 고정한다.

    이름이 두 곳에서 정해지면 한쪽만 바뀌어도 예외가 나지 않는다 —
    「상태 없음」으로 읽혀 **회차가 처음부터 다시 돈다.**

    Given: 저장된 상태
    When: 실행 폴더를 본다
    Then: `common_constants.STATE_FILENAME` 으로 파일이 있다
    """
    state.save(tmp_path, {"completed": []})

    assert (tmp_path / common_constants.STATE_FILENAME).is_file()


def test_failed_save_leaves_previous_state_intact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 쓰다가 죽어도 «완성본 자리»가 손상되지 않는 계약을 고정한다.

    이것이 「임시 파일에 쓰고 성공했을 때만 rename」의 실체다. 완성본 자리에 직접 쓰면
    도중에 죽은 순간 **읽을 수도 없고 되돌릴 수도 없는 파일**이 남는다.

    Given: 이미 저장된 상태와, 쓰는 도중 실패하는 상황
    When: 새 상태 저장이 실패한다
    Then: 이전 상태가 그대로 읽힌다
    """
    state.save(tmp_path, {"completed": ["explore"]})

    def exploding_dump(*args: object, **kwargs: object) -> None:
        raise OSError("디스크가 가득 찼다")

    monkeypatch.setattr(json, "dump", exploding_dump)

    with pytest.raises(OSError):
        state.save(tmp_path, {"completed": ["explore", "collect"]})

    monkeypatch.undo()
    assert state.load(tmp_path) == {"completed": ["explore"]}


def test_failed_save_leaves_no_stray_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    목적: 실패한 저장이 쓰레기를 남기지 않는 계약을 고정한다.

    임시 파일이 쌓이면 회차마다 늘어나고, 다음 사람이 그중 무엇이 진짜인지 판별해야 한다.

    Given: 쓰는 도중 실패하는 상황
    When: 저장이 실패한다
    Then: 실행 폴더에 상태 파일 말고는 아무것도 없다
    """

    def exploding_dump(*args: object, **kwargs: object) -> None:
        raise OSError("디스크가 가득 찼다")

    monkeypatch.setattr(json, "dump", exploding_dump)

    with pytest.raises(OSError):
        state.save(tmp_path, {"completed": []})

    monkeypatch.undo()
    assert list(tmp_path.iterdir()) == []


def test_second_lock_is_refused(tmp_path: Path) -> None:
    """
    목적: 같은 실행 폴더를 두 프로세스가 동시에 잡지 못하는 계약을 고정한다.

    이번 단계는 손으로 돌리므로 **실수로 두 번 띄우기 쉽다.** 잠금이 없으면 두 프로세스가
    같은 상태 파일을 번갈아 쓰고, 한쪽 갱신이 조용히 사라진다.

    Given: 이미 잠긴 실행 폴더
    When: 같은 폴더를 다시 잠그려 한다
    Then: 예외가 오른다
    """
    with state.lock(tmp_path):
        with pytest.raises(state.AlreadyRunningError):
            with state.lock(tmp_path):
                pass


def test_lock_is_released_after_use(tmp_path: Path) -> None:
    """
    목적: 정상 종료한 회차가 다음 회차를 막지 않는 계약을 고정한다.

    Given: 한 번 잠갔다 푼 실행 폴더
    When: 다시 잠근다
    Then: 성공한다
    """
    with state.lock(tmp_path):
        pass

    with state.lock(tmp_path):
        pass


def test_lock_is_released_even_when_the_cycle_crashes(tmp_path: Path) -> None:
    """
    목적: 예외로 끝난 회차가 다음 회차를 영구히 막지 않는 계약을 고정한다.

    이게 없으면 한 번의 실패가 **사람이 손으로 잠금 파일을 지울 때까지** 파이프라인을 세운다.
    무인 실행에서는 그 사실을 며칠 뒤에나 알게 된다.

    Given: 잠금을 잡은 채 예외가 나는 상황
    When: 예외가 밖으로 나간다
    Then: 잠금이 풀려 다음 시도가 성공한다
    """
    with pytest.raises(RuntimeError):
        with state.lock(tmp_path):
            raise RuntimeError("회차가 깨졌다")

    with state.lock(tmp_path):
        pass


# 잠금을 잡고 버티는 자식. 강제 종료를 «진짜로» 내려면 별도 프로세스가 필요하다 —
# 같은 프로세스에서는 `finally` 를 건너뛰게 만들 수 없다
LOCK_HOLDER: Final = """
import time
from pathlib import Path
from research_lab.runner import state
with state.lock(Path({run_dir!r})):
    print("held", flush=True)
    time.sleep(60)
"""


@contextmanager
def _lock_held_in_a_child(run_dir: Path, script: str = LOCK_HOLDER) -> Generator[subprocess.Popen[str]]:
    """자식 프로세스가 그 폴더의 잠금을 잡고 있는 동안만 몸통을 돈다.

    [중요] 정리를 «여기»에 둔다. 부르는 쪽에 맡기면 몸통의 단정문이 실패할 때 정리가
    건너뛰어져, **60초를 자면서 잠금을 든 자식이 남아** 뒤따르는 테스트를 막는다.
    """
    child = subprocess.Popen(
        [sys.executable, "-c", script.format(run_dir=str(run_dir))],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "held", "자식이 잠금을 못 잡았다"
        yield child
    finally:
        child.kill()
        child.wait(timeout=10)
        if child.stdout is not None:
            child.stdout.close()


def test_lock_of_a_killed_holder_is_reclaimed(tmp_path: Path) -> None:
    """
    목적: [중요] **강제 종료된 회차의 잠금이 다음 회차에 «잡히는»** 계약을 고정한다.

    [실측 2026-09-14] 예전 구현(`O_EXCL` 파일)은 `SIGKILL`·`SIGTERM` 둘 다에서
    **파일이 남았다.** 파이썬은 `SIGTERM` 핸들러를 기본으로 달지 않아 `finally` 가 안 돌고,
    컨테이너 안 PID 1 은 핸들러 없는 시그널을 무시하므로 `docker stop` 도 `SIGKILL` 로 끝난다 —
    **「얌전히 멈추는」 경로가 없다.**

    그래서 무슨 일이 났나: 진입점이 잠긴 폴더를 건너뛰므로 그 폴더는 **영구히 이어받히지
    않고**, 원장 잠금까지 남아 **이후 모든 회차가 원장에서 즉시 멈췄다.** 설계가 「컨테이너가
    죽어도 같은 방식으로 복구된다」고 적어 둔 바로 그 자리다.

    `flock` 은 커널이 프로세스 종료 시 놓아주므로 **상한값도 사람의 손질도 필요 없다.**

    Given: 잠금을 잡은 채 SIGKILL 된 프로세스
    When: 같은 폴더를 잠근다
    Then: 성공한다
    """
    with _lock_held_in_a_child(tmp_path):
        assert state.is_locked(tmp_path) is True
    # 컨텍스트를 나오며 자식을 SIGKILL 했다 — 커널이 잠금을 놓아줬어야 한다

    assert state.is_locked(tmp_path) is False
    with state.lock(tmp_path):
        pass


def test_a_leftover_lock_file_is_not_a_lock(tmp_path: Path) -> None:
    """
    목적: [중요] 잠금 «파일이 남아 있는 것»을 「잠김」으로 읽지 «않는» 계약을 고정한다.

    파일 존재로 판정하면 **그 파일 하나가 폴더를 영구히 잠근다** — 위 계약이 막으려는
    고장의 뿌리가 그것이다. 판정은 파일이 아니라 **커널이 들고 있는 잠금**이 한다.

    Given: 아무도 잡고 있지 않은 잠금 파일
    When: 잠김 여부를 묻고 잠가 본다
    Then: 잠기지 않았다고 답하고 잠금이 성공한다
    """
    (tmp_path / LOCK_FILENAME).write_text("예전 구현이 남긴 pid", encoding="utf-8")

    assert state.is_locked(tmp_path) is False
    with state.lock(tmp_path):
        pass


def test_lock_file_is_kept_after_release(tmp_path: Path) -> None:
    """
    목적: 잠금 파일을 «지우지 않는» 계약을 고정한다.

    다른 프로세스가 그 파일에 fd 를 들고 있는 동안 unlink 하면 **지워진 inode 를 잠그는**
    고전적 경쟁이 생겨, 둘이 서로 다른 파일을 잠근 채 같은 폴더를 쓴다.
    남아 있어도 해롭지 않다 — 위 계약대로 **존재가 잠김을 뜻하지 않기** 때문이다.

    Given: 한 번 잠갔다 푼 폴더
    When: 잠금 파일을 본다
    Then: 파일이 남아 있고 «잠김은 아니다»
    """
    with state.lock(tmp_path):
        pass

    assert (tmp_path / LOCK_FILENAME).is_file()
    assert state.is_locked(tmp_path) is False


def test_unlocked_folder_without_a_file_is_not_locked(tmp_path: Path) -> None:
    """
    목적: 잠금 파일이 아예 없는 폴더를 「잠김」으로 읽지 않는 계약을 고정한다.

    첫 회차의 폴더가 그 모양이다.

    Given: 잠금 파일이 없는 폴더
    When: 잠김 여부를 묻는다
    Then: 잠기지 않았다고 답한다
    """
    assert state.is_locked(tmp_path / "아직-없는-폴더") is False


def test_held_lock_is_visible_to_another_process(tmp_path: Path) -> None:
    """
    목적: «지금 도는» 회차의 잠금이 다른 프로세스에 보이는 계약을 고정한다.

    위 「남은 파일은 잠금이 아니다」가 지나치게 넓으면 **정말 도는 회차의 폴더를 훔친다.**
    둘이 같은 상태 파일을 번갈아 쓰면 한쪽 갱신이 조용히 사라진다.

    Given: 다른 프로세스가 잡고 있는 폴더
    When: 잠김 여부를 묻고 잠그려 한다
    Then: 잠겼다고 답하고 잠금이 거부된다
    """
    with _lock_held_in_a_child(tmp_path):
        assert state.is_locked(tmp_path) is True
        with pytest.raises(state.AlreadyRunningError):
            with state.lock(tmp_path):
                pass


# 잠금을 «공유»로 잡고 버티는 자식 — 판정기가 찌를 때 쓰는 것과 같은 종류다
SHARED_PROBE_HOLDER: Final = """
import fcntl, time
from pathlib import Path
path = Path({run_dir!r}) / "lock"
path.parent.mkdir(parents=True, exist_ok=True)
handle = path.open("a")
fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
print("held", flush=True)
time.sleep(60)
"""


def test_another_probe_does_not_look_like_a_lock(tmp_path: Path) -> None:
    """
    목적: [중요] 판정기 둘이 «서로» 잠김으로 읽히지 않는 계약을 고정한다.

    `is_locked` 가 배타 잠금으로 찌르면 **두 판정기가 서로 부딪힌다** — 아무도 회차를
    돌리지 않는데 한쪽이 「잠김」이라 답하고, 그러면 이어받을 수 있던 폴더가
    한 회차를 그냥 기다린다. 실제로 겹칠 수 있는 자리다(예약된 회차와 사람이 띄운 회차).

    회차는 언제나 **배타** 잠금을 잡으므로, 공유 잠금을 든 것은 판정기뿐이다.

    Given: 공유 잠금을 든 다른 프로세스
    When: 잠김 여부를 묻는다
    Then: 잠기지 않았다고 답한다
    """
    with _lock_held_in_a_child(tmp_path, SHARED_PROBE_HOLDER):
        assert state.is_locked(tmp_path) is False


def test_unwritable_lock_file_is_not_read_as_locked(tmp_path: Path) -> None:
    """
    목적: [중요] **쓸 수 없는** 잠금 파일을 「잠김」으로 읽지 «않는» 계약을 고정한다.

    `flock` 은 쓰기 권한을 요구하지 않는데 파일을 쓰기로 열면 다른 uid 가 만든
    잠금 파일에서 `PermissionError` 가 난다. 그것을 「잠김」으로 읽으면
    **아무도 잡고 있지 않은 폴더가 영구히 건너뛰어진다** — 이 구현이 없애려던
    정지 버그가 권한을 타고 그대로 돌아오는 자리다.

    잠그는 쪽도 같다. 쓰기로 열면 `AlreadyRunningError` 가 아닌 예외가 올라
    진입점이 못 잡고, 파일이 지워지지 않으므로 **이후 모든 회차가 같게 죽는다.**

    Given: 읽기 전용으로 바뀐 잠금 파일
    When: 잠김 여부를 묻고 잠가 본다
    Then: 잠기지 않았다고 답하고 잠금이 성공한다
    """
    lock_path = tmp_path / LOCK_FILENAME
    lock_path.write_text("", encoding="utf-8")
    lock_path.chmod(0o444)

    assert state.is_locked(tmp_path) is False
    with state.lock(tmp_path):
        pass


# --------------------------------------------------------------------------
# 그 회차의 후보
#
# 수집·반증·계보가 **같은 후보**를 봐야 한다. 원장에서 매번 「다음에 팔 후보」를 새로
# 물으면, 수집이 표시를 마친 뒤에는 다른 후보가 돌아오거나 아무것도 안 돌아온다.
# 상태의 주인이 하나여야 복구가 한 가지 방식으로 끝나므로 그 자리를 상태 파일로 둔다.
# --------------------------------------------------------------------------


def test_pinned_candidate_round_trips(tmp_path: Path) -> None:
    """
    목적: 그 회차의 후보가 상태 파일에 박히고 다시 읽히는 계약을 고정한다.

    Given: 후보를 박은 실행 폴더
    When: 읽는다
    Then: 주장과 식별자가 그대로 돌아온다
    """
    state.pin_candidate(tmp_path, state.Candidate(claim="첫 후보", identifier="first"))

    pinned = state.pinned_candidate(tmp_path)

    assert pinned is not None
    assert pinned.claim == "첫 후보"
    assert pinned.identifier == "first"


def test_no_candidate_reads_as_none(tmp_path: Path) -> None:
    """
    목적: 아직 후보를 안 잡은 회차를 「없음」으로 알리는 계약을 고정한다.

    예외로 올리면 「아직 수집 전」이라는 정상 상태가 실패 처리와 섞인다.

    Given: 상태가 없는 실행 폴더
    When: 후보를 묻는다
    Then: None 이 돌아온다
    """
    assert state.pinned_candidate(tmp_path) is None


def test_pinning_keeps_the_progress_already_saved(tmp_path: Path) -> None:
    """
    목적: 후보를 박아도 이미 저장된 «진행»이 지워지지 않는 계약을 고정한다.

    Given: 단계 진행이 저장된 상태
    When: 후보를 박는다
    Then: 진행이 그대로 남아 있다
    """
    state.save(tmp_path, {"settled": ["explore"], "skipped": []})

    state.pin_candidate(tmp_path, state.Candidate(claim="첫 후보", identifier=None))

    saved = state.load(tmp_path)
    assert saved is not None
    assert saved["settled"] == ["explore"]


def test_candidate_survives_progress_updates(tmp_path: Path) -> None:
    """
    목적: 진행을 저장해도 후보가 «지워지지 않는» 계약을 고정한다.

    [중요] 이 계약이 없으면 수집이 박아 둔 후보를 그 직후의 진행 저장이 덮어 지우고,
    반증이 「후보 없음」을 만난다. **예외는 그때 나므로 원인이 한 단계 뒤에서 드러난다.**

    Given: 후보가 박힌 상태
    When: 단계 진행을 저장한다
    Then: 후보가 그대로 남아 있다
    """
    state.pin_candidate(tmp_path, state.Candidate(claim="첫 후보", identifier="first"))

    saved = state.load(tmp_path) or {}
    saved.update({"settled": ["explore", "collect"], "skipped": []})
    state.save(tmp_path, saved)

    pinned = state.pinned_candidate(tmp_path)
    assert pinned is not None
    assert pinned.claim == "첫 후보"


def test_broken_candidate_reads_as_none(tmp_path: Path) -> None:
    """
    목적: 모양이 깨진 후보 기록에 «죽지 않는» 계약을 고정한다.

    사람이 상태 파일을 손으로 고칠 수도 있고, 예전 형식이 남아 있을 수도 있다.
    여기서 터뜨리면 그 실행 폴더 하나 때문에 파이프라인이 선다 —
    「없음」으로 읽으면 그 회차는 새로 시작하면 된다.

    Given: 후보 자리에 문자열이 든 상태
    When: 후보를 묻는다
    Then: 예외 없이 None 이 돌아온다
    """
    state.save(tmp_path, {"settled": [], "skipped": [], "candidate": "첫 후보"})

    assert state.pinned_candidate(tmp_path) is None


def test_a_state_file_with_broken_encoding_does_not_raise(tmp_path: Path) -> None:
    """
    목적: [중요] 인코딩이 깨진 상태 파일에 «죽지 않는» 계약을 고정한다.

    `UnicodeDecodeError` 는 `OSError` 가 아니라 `ValueError` 라, 「파일 없음」과
    「JSON 깨짐」만 잡으면 **이 갈래가 그대로 빠져나간다.** 이 저장소의 상태 파일에는
    한글 주장이 들어가므로 **반쯤 쓰이다 끊기면 거의 언제나 이 모양**이 되고,
    WSL 과 mac 을 오가는 저장소라 편집기 한 번이 같은 갈래를 만들 수 있다.

    터지면 그 폴더 하나 때문에 **이후 모든 무인 회차가 같은 자리에서 죽는다.**
    「없음」으로 읽으면 그 회차는 새로 시작하면 된다.

    Given: 한글 중간에서 끊겨 UTF-8 로 못 읽는 상태 파일
    When: 후보와 접힌 사유를 묻는다
    Then: 둘 다 예외 없이 None 이다
    """
    # 「한 후보」를 UTF-8 로 쓴 뒤 마지막 글자를 바이트 중간에서 자른다
    broken = ('{"candidate": {"claim": "한 후보"'.encode())[:-2]
    (tmp_path / common_constants.STATE_FILENAME).write_bytes(broken)

    assert state.pinned_candidate(tmp_path) is None
    assert state.closed_reason(tmp_path) is None


def test_writing_over_an_unreadable_state_does_not_raise(tmp_path: Path) -> None:
    """
    목적: [중요] 「읽어서 얹고 다시 쓰는」 자리가 못 읽는 파일에서도 죽지 않는 계약을 고정한다.

    바로 위 테스트가 «읽기»를 고정한다면 이쪽은 «쓰기»다. 그 자리가 넷이고
    (후보 박기 · 접기 · 진행 저장 둘) 한 곳만 가드가 빠지면 **그 경로에서만 회차가 죽는다.**
    특히 접기는 **이미 실패한 회차 위에서** 불리므로, 여기서 터지면 실패 원문이 묻히고
    종료 코드도 정해진 갈래 밖이 된다.

    못 읽는 파일을 빈 상태로 보고 덮어쓰는 것이 맞다 — 그 내용은 이미 읽을 수 없으므로
    잃을 것이 없고, 그대로 두면 그 폴더가 영원히 못 쓰는 자리가 된다.

    Given: 한글 중간에서 끊겨 UTF-8 로 못 읽는 상태 파일
    When: 후보를 박고 그 폴더를 접는다
    Then: 예외 없이 끝나고, 이후 읽기가 성립한다
    """
    (tmp_path / common_constants.STATE_FILENAME).write_bytes(('{"candidate": "한 후보"'.encode())[:-2])

    state.pin_candidate(tmp_path, state.Candidate(claim="새 후보", identifier="new"))
    state.close(tmp_path, "세 회차 연속 막혔다")

    pinned = state.pinned_candidate(tmp_path)
    assert pinned is not None and pinned.claim == "새 후보"
    assert state.closed_reason(tmp_path) == "세 회차 연속 막혔다"

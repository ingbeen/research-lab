"""상태 파일의 원자적 쓰기와 동시 실행 잠금 계약을 고정한다.

상태의 진실은 대화가 아니라 «파일»에 있다. 그래서 한도로 끊겨도 · 컨테이너가 죽어도 ·
PC 가 재부팅돼도 같은 방식으로 복구된다. 그 전제가 성립하려면 둘이 필요하다.

1. **반쯤 쓴 상태가 완성본 자리에 남지 않는다** — 임시 파일에 쓰고 성공했을 때만 rename
2. **두 프로세스가 같은 상태를 번갈아 쓰지 않는다** — rename 은 원자적이지만 그건 막지 못한다

[주의] 2번이 없으면 갱신 하나가 «조용히» 사라진다. 예외도 로그도 남지 않는다.
"""

import json
from pathlib import Path

import pytest

from research_lab import common_constants
from research_lab.runner import state


def test_load_returns_none_when_absent(tmp_path: Path) -> None:
    """
    목적: 상태가 없는 첫 밤을 「빈 상태」로 다루는 계약을 고정한다.

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
    「상태 없음」으로 읽혀 **밤이 처음부터 다시 돈다.**

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

    임시 파일이 쌓이면 밤마다 늘어나고, 다음 사람이 그중 무엇이 진짜인지 판별해야 한다.

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
    목적: 정상 종료한 밤이 다음 밤을 막지 않는 계약을 고정한다.

    Given: 한 번 잠갔다 푼 실행 폴더
    When: 다시 잠근다
    Then: 성공한다
    """
    with state.lock(tmp_path):
        pass

    with state.lock(tmp_path):
        pass


def test_lock_is_released_even_when_the_night_crashes(tmp_path: Path) -> None:
    """
    목적: 예외로 끝난 밤이 다음 밤을 영구히 막지 않는 계약을 고정한다.

    이게 없으면 한 번의 실패가 **사람이 손으로 잠금 파일을 지울 때까지** 파이프라인을 세운다.
    무인 실행에서는 그 사실을 며칠 뒤에나 알게 된다.

    Given: 잠금을 잡은 채 예외가 나는 상황
    When: 예외가 밖으로 나간다
    Then: 잠금이 풀려 다음 시도가 성공한다
    """
    with pytest.raises(RuntimeError):
        with state.lock(tmp_path):
            raise RuntimeError("밤이 깨졌다")

    with state.lock(tmp_path):
        pass


# --------------------------------------------------------------------------
# 그 밤의 후보
#
# 수집·반증·계보가 **같은 후보**를 봐야 한다. 원장에서 매번 「다음에 팔 후보」를 새로
# 물으면, 수집이 표시를 마친 뒤에는 다른 후보가 돌아오거나 아무것도 안 돌아온다.
# 상태의 주인이 하나여야 복구가 한 가지 방식으로 끝나므로 그 자리를 상태 파일로 둔다.
# --------------------------------------------------------------------------


def test_pinned_candidate_round_trips(tmp_path: Path) -> None:
    """
    목적: 그 밤의 후보가 상태 파일에 박히고 다시 읽히는 계약을 고정한다.

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
    목적: 아직 후보를 안 잡은 밤을 「없음」으로 알리는 계약을 고정한다.

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
    「없음」으로 읽으면 그 밤은 새로 시작하면 된다.

    Given: 후보 자리에 문자열이 든 상태
    When: 후보를 묻는다
    Then: 예외 없이 None 이 돌아온다
    """
    state.save(tmp_path, {"settled": [], "skipped": [], "candidate": "첫 후보"})

    assert state.pinned_candidate(tmp_path) is None

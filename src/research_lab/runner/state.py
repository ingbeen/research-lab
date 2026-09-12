"""밤의 상태를 파일로 소유한다.

상태의 진실은 대화가 아니라 파일에 있다. 그래서 한도로 끊겨도 · 컨테이너가 죽어도 ·
PC 가 재부팅돼도 같은 방식으로 복구된다.
"""

import json
import os
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from research_lab.common_constants import LOCK_FILENAME, STATE_FILENAME
from research_lab.runner.atomic import atomic_write

# 그 밤이 파고 있는 후보가 적히는 자리.
#
# [중요] 수집·반증·계보가 **같은 후보**를 봐야 한다. 단계마다 원장에 「다음에 팔 후보」를
# 새로 물으면, 수집이 표시를 마친 뒤에는 다른 후보가 돌아오거나 아무것도 안 돌아온다.
# 상태의 주인이 하나여야 복구가 한 가지 방식으로 끝나므로 그 자리를 이 파일로 둔다
KEY_CANDIDATE: Final = "candidate"
KEY_CLAIM: Final = "claim"
KEY_IDENTIFIER: Final = "identifier"


class AlreadyRunningError(RuntimeError):
    """같은 실행 폴더를 이미 다른 프로세스가 잡고 있을 때."""


@dataclass(frozen=True)
class Candidate:
    """그 밤이 파고 있는 후보."""

    claim: str
    # 산출물 폴더 이름이 된다. 예전에 담긴 후보에는 없다
    identifier: str | None


def load(run_dir: Path) -> dict[str, Any] | None:
    """상태를 읽는다.

    Args:
        run_dir: 그 밤의 실행 폴더

    Returns:
        저장된 상태. 아직 없으면 None — 첫 밤은 「빈 상태」이지 오류가 아니다
    """
    path = run_dir / STATE_FILENAME
    if not path.is_file():
        return None

    with path.open(encoding="utf-8") as file:
        loaded: Any = json.load(file)
    return loaded


def save(run_dir: Path, payload: Mapping[str, Any]) -> None:
    """상태를 원자적으로 저장한다.

    임시 파일에 쓰고 **성공했을 때만** 완성본 자리로 옮긴다. 완성본 자리에 직접 쓰면
    도중에 죽은 순간 **읽을 수도 없고 되돌릴 수도 없는 파일**이 남는다.

    Args:
        run_dir: 그 밤의 실행 폴더
        payload: 저장할 상태

    Raises:
        OSError: 쓰기에 실패했을 때. 그때도 이전 상태는 손상되지 않는다
    """
    with atomic_write(run_dir / STATE_FILENAME) as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def pin_candidate(run_dir: Path, candidate: Candidate) -> None:
    """그 밤이 파고 있는 후보를 상태에 박는다.

    이미 저장된 진행은 건드리지 않는다 — 읽어서 후보만 얹는다.

    Args:
        run_dir: 그 밤의 실행 폴더
        candidate: 이 밤이 파는 후보
    """
    saved = load(run_dir) or {}
    saved[KEY_CANDIDATE] = {KEY_CLAIM: candidate.claim, KEY_IDENTIFIER: candidate.identifier}
    save(run_dir, saved)


def pinned_candidate(run_dir: Path) -> Candidate | None:
    """그 밤이 파고 있는 후보를 읽는다.

    [중요] 모양이 어긋나면 **예외 대신 「없음」**을 돌려준다. 사람이 상태 파일을 손으로
    고칠 수도 있고 단계를 늘리기 전의 예전 파일이 남아 있을 수도 있는데, 여기서 터뜨리면
    그 실행 폴더 하나 때문에 파이프라인이 선다. 「없음」이면 그 밤은 새로 시작하면 된다.

    Args:
        run_dir: 그 밤의 실행 폴더

    Returns:
        박아 둔 후보. 아직 안 잡았거나 모양이 어긋나면 None
    """
    try:
        saved = load(run_dir)
    except (OSError, json.JSONDecodeError):
        # 반쯤 쓰이다 끊긴 파일이나 사람이 손으로 고치다 깨진 파일이다.
        # 「없음」으로 읽으면 그 밤은 새로 시작하면 되지만, 여기서 터뜨리면
        # 그 실행 폴더 하나 때문에 파이프라인이 선다
        return None

    if not isinstance(saved, dict):
        return None

    raw: Any = saved.get(KEY_CANDIDATE)
    if not isinstance(raw, dict):
        return None

    claim = str(raw.get(KEY_CLAIM, "")).strip()
    if not claim:
        return None

    identifier = raw.get(KEY_IDENTIFIER)
    usable = isinstance(identifier, str) and identifier.strip()
    return Candidate(claim=claim, identifier=identifier if usable else None)


@contextmanager
def lock(run_dir: Path) -> Generator[None]:
    """실행 폴더를 잠근다.

    rename 은 원자적이지만 **두 프로세스가 번갈아 쓰는 것**은 막지 못한다.
    그 경우 한쪽 갱신이 예외도 로그도 없이 사라진다.

    Args:
        run_dir: 그 밤의 실행 폴더

    Raises:
        AlreadyRunningError: 이미 잡혀 있을 때
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / LOCK_FILENAME

    try:
        # O_EXCL 은 「없을 때만 만든다」를 커널이 원자적으로 보장한다.
        # `exists()` 로 먼저 보고 만들면 그 사이에 다른 프로세스가 끼어든다
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as conflict:
        raise AlreadyRunningError(f"이미 실행 중입니다. 끝난 뒤에도 남아 있으면 이 파일을 지우세요: {path}") from conflict

    try:
        # 누가 잡고 있는지 남긴다. 잠금이 남아 있을 때 사람이 판단할 재료가 된다
        os.write(descriptor, str(os.getpid()).encode("ascii"))
    finally:
        os.close(descriptor)

    try:
        yield
    finally:
        # 예외로 끝난 밤이 다음 밤을 «영구히» 막지 않게 한다.
        # 무인 실행에서는 잠긴 채로 멈춘 사실을 며칠 뒤에나 알게 된다
        path.unlink(missing_ok=True)

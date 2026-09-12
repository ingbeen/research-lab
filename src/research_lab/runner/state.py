"""밤의 상태를 파일로 소유한다.

상태의 진실은 대화가 아니라 파일에 있다. 그래서 한도로 끊겨도 · 컨테이너가 죽어도 ·
PC 가 재부팅돼도 같은 방식으로 복구된다.
"""

import json
import os
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from research_lab.common_constants import LOCK_FILENAME, STATE_FILENAME
from research_lab.runner.atomic import atomic_write


class AlreadyRunningError(RuntimeError):
    """같은 실행 폴더를 이미 다른 프로세스가 잡고 있을 때."""


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

"""반쯤 쓴 파일이 완성본 자리에 남지 않게 한다.

상태 파일과 원장이 함께 쓴다. 완성본 자리에 직접 쓰면 도중에 죽은 순간
**읽을 수도 없고 되돌릴 수도 없는 파일**이 남는데, 둘 다 그렇게 되면 회차가 복구되지 않는다.
"""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


@contextmanager
def atomic_write(path: Path) -> Generator[TextIO]:
    """임시 파일에 쓰고 **성공했을 때만** 완성본 자리로 옮긴다.

    Args:
        path: 최종 경로. 상위 폴더가 없으면 만든다

    Yields:
        쓰기용 파일 객체 (UTF-8)

    Raises:
        OSError: 쓰기에 실패했을 때. 그때도 기존 파일은 손상되지 않고
            임시 파일도 남지 않는다
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")

    try:
        with temporary.open("w", encoding="utf-8") as file:
            yield file
            file.flush()
            # rename 이 원자적이어도 «내용»이 디스크에 닿기 전에 전원이 끊기면
            # 빈 파일이 완성본 자리에 남는다
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        # 실패해도 쓰레기를 남기지 않는다. 쌓이면 회차마다 늘어나고
        # 다음 사람이 그중 무엇이 진짜인지 판별해야 한다
        temporary.unlink(missing_ok=True)

"""밤의 상태를 파일로 소유한다.

상태의 진실은 대화가 아니라 파일에 있다. 그래서 한도로 끊겨도 · 컨테이너가 죽어도 ·
PC 가 재부팅돼도 같은 방식으로 복구된다.
"""

import fcntl
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

# 그 실행 폴더를 «접었다»고 적는 자리.
#
# [중요] 이 표시가 없으면 「막힘」 처리가 통째로 헛돈다. 후보를 원장에서 걷어내도 여기
# 박힌 「그 밤의 후보」는 살아 있어서, 다음 밤이 이 폴더를 이어받아 **같은 단계를 또 부르고
# 또 막힌다.** 남은 단계를 「했다」로 적어 닫는 길도 있지만 그건 거짓말이라,
# 무엇을 안 했는지가 기록에서 사라진다
KEY_CLOSED: Final = "closed"
KEY_REASON: Final = "reason"


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


def close(run_dir: Path, reason: str) -> None:
    """그 실행 폴더를 접는다 — 다음 밤이 이어받지 않는다.

    이미 저장된 진행은 건드리지 않는다. **무엇을 못 했는지는 그대로 남아야** 나중에
    「어디서 막혔나」를 되짚을 수 있다.

    Args:
        run_dir: 그 밤의 실행 폴더
        reason: 왜 접었나
    """
    saved = load(run_dir) or {}
    saved[KEY_CLOSED] = {KEY_REASON: reason}
    save(run_dir, saved)


def closed_reason(run_dir: Path) -> str | None:
    """그 실행 폴더가 접혔으면 그 사유를, 아니면 None 을 돌려준다.

    [중요] 모양이 어긋나거나 읽을 수 없으면 **「안 접혔다」로 읽는다.** 이 칸이 생기기 전에
    만들어진 폴더가 이미 쌓여 있고, 없는 것을 접힌 것으로 읽으면 **이어받을 수 있던 밤이
    통째로 버려진다.** `pinned_candidate` 가 같은 이유로 같게 동작한다.

    Args:
        run_dir: 그 밤의 실행 폴더

    Returns:
        접힌 사유. 안 접혔거나 판정할 수 없으면 None
    """
    try:
        saved = load(run_dir)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(saved, dict):
        return None

    raw: Any = saved.get(KEY_CLOSED)
    if not isinstance(raw, dict):
        return None

    # [주의] `str(...)` 로 감싸지 않는다. 사람이 손으로 `null` 을 적어 두면 `str(None)` 이
    # `"None"` 이 되어 **아래 기본값이 안 걸리고 사유가 「None」으로 보고된다**
    stored: Any = raw.get(KEY_REASON)
    reason = stored.strip() if isinstance(stored, str) else ""

    # 사유가 비었어도 「접혔다」는 사실은 살린다. 사유를 잃는 것보다 폴더를 다시 잡는 편이 나쁘다
    return reason or "사유가 적히지 않은 채 접혔습니다"


def is_locked(run_dir: Path) -> bool:
    """그 폴더를 «지금 도는» 밤이 잡고 있나.

    [중요] **파일 존재로 판정하지 않는다.** 강제 종료 뒤에도 파일은 남으므로, 존재를
    잠김으로 읽으면 **그 파일 하나가 폴더를 영구히 잠근다** — 그것이 예전 구현의 고장이었다.
    판정은 커널이 들고 있는 잠금이 한다: 잡아 보고 곧바로 놓는다.

    Args:
        run_dir: 그 밤의 실행 폴더

    Returns:
        지금 잡혀 있으면 True. **판정할 수 없으면 True 다** — 훔쳐서 두 밤이 한 폴더를
        번갈아 쓰는 것보다 한 밤을 미루는 쪽이 낫다
    """
    path = run_dir / LOCK_FILENAME
    if not path.is_file():
        return False

    try:
        # [중요] **읽기로 연다.** `flock` 은 쓰기 권한을 요구하지 않는데, 쓰기로 열면
        # 다른 uid 가 만든 잠금 파일에서 `PermissionError` 가 나고 아래 갈래가 그것을
        # 「잠김」으로 읽는다 — **아무도 잡고 있지 않은 폴더가 영구히 건너뛰어진다.**
        # 이 함수가 없애려던 고장이 권한을 타고 그대로 돌아오는 자리다.
        with path.open("r") as handle:
            # [중요] **공유 잠금으로 찔러 본다.** 배타 잠금으로 찌르면 «두 판정기»가
            # 서로 충돌해, 아무도 밤을 돌리지 않는데도 한쪽이 「잠김」이라 답한다.
            # 공유 잠금도 진짜 배타 홀더와는 부딪히므로 잡아야 할 것은 그대로 잡는다
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        return True
    return False


@contextmanager
def lock(run_dir: Path) -> Generator[None]:
    """실행 폴더를 잠근다.

    rename 은 원자적이지만 **두 프로세스가 번갈아 쓰는 것**은 막지 못한다.
    그 경우 한쪽 갱신이 예외도 로그도 없이 사라진다.

    [중요] **`flock` 을 쓴다. 커널이 프로세스 종료 시 놓아주기 때문이다.**
    예전 구현은 `O_EXCL` 파일이었는데, [실측 2026-09-14] `SIGKILL`·`SIGTERM` 둘 다에서
    **파일이 남았다** — 파이썬은 `SIGTERM` 핸들러를 기본으로 달지 않아 `finally` 가 안 돌고,
    컨테이너 안 PID 1 은 핸들러 없는 시그널을 무시하므로 `docker stop` 도 `SIGKILL` 로 끝난다.
    **「얌전히 멈추는」 경로가 없다.** 그래서 남은 파일이 실행 폴더를 영구히 잠그고,
    원장 잠금까지 남아 **이후 모든 밤이 원장에서 즉시 멈췄다.**

    [주의] **못 막는 것이 하나 있다** — [실측 2026-09-14] flock 은 **host↔container 경계를
    넘지 않는다.** 컨테이너가 잡고 있는 동안 호스트에서 잡으면 잡힌다(반대도 같다).
    컨테이너끼리는 같은 VM 커널이라 정상으로 막힌다. 운용 경로가 컨테이너 하나이므로
    막는 대상은 **개발용 호스트 실행과의 동시 충돌**뿐이고, 그것은 사람이 자기 터미널에서 본다.

    Args:
        run_dir: 그 밤의 실행 폴더

    Raises:
        AlreadyRunningError: 이미 잡혀 있을 때
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / LOCK_FILENAME

    # [중요] 잠금 파일을 «지우지 않는다». 다른 프로세스가 fd 를 든 채 unlink 되면
    # **지워진 inode 를 잠그는** 고전적 경쟁이 생겨, 둘이 서로 다른 파일을 잠근 채 같은
    # 폴더를 쓴다. 남아 있어도 해롭지 않다 — 존재가 잠김을 뜻하지 않기 때문이다.
    #
    # [중요] 내용도 쓰지 않는다. 파일은 잠금을 걸 «자리»일 뿐이라 빈 채로 둔다 —
    # 예전 구현은 PID 를 적었는데 그것은 **사람이 파일을 지울지 판단할 재료**였고,
    # 이제 지울 일이 없어 쓸 곳이 없다(컨테이너의 PID 1 은 호스트에서 의미도 없다).
    #
    # [중요] **읽기로 연다.** `flock` 은 쓰기 권한을 요구하지 않는데, 쓰기로 열면
    # 다른 uid 가 만든 잠금 파일에서 `PermissionError` 가 난다. 그것은
    # `AlreadyRunningError` 가 아니라 진입점이 잡지 않는 예외라 **트레이스백으로 끝나고**,
    # 파일이 지워지지 않으므로 **이후 모든 밤이 같은 자리에서 같게 죽는다** —
    # 이 구현이 없애려던 정지 버그가 권한을 타고 그대로 돌아오는 자리다.
    # `O_CREAT` 로 없을 때만 만들고, 여는 의도는 읽기로 둔다
    descriptor = os.open(path, os.O_RDONLY | os.O_CREAT)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as conflict:
            raise AlreadyRunningError(f"이미 실행 중입니다: {run_dir}") from conflict

        try:
            yield
        finally:
            # 커널이 파일을 닫을 때 어차피 놓아주지만, 명시적으로 놓아 「여기서 끝난다」를
            # 코드에 남긴다
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)

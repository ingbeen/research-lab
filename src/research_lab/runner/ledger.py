"""후보 목록(원장)을 읽고 덧붙인다.

원장은 **중복 방지의 전부**다. 없으면 같은 후보를 매일 다시 판다.
이 저장소가 누적 상태로 «만드는» 것 중 하나인 이유는 하루를 걸러도 그날 밤이 없었을 뿐
영구 손상이 아니기 때문이다 — 완주율·점수 같은 집계와 갈리는 지점이 여기다.

[중요] 사람도 손으로 고치는 파일이다. 그래서 프로그램이 통째로 다시 쓰지 않고
**줄 단위로만** 손댄다. 다시 쓰면 사람이 적어 둔 메모가 사라지고, 사라진 줄도 모른다.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from research_lab.runner.atomic import atomic_write

# 후보 한 줄의 형식. 마크다운 체크리스트라 사람이 편집기에서 그대로 읽고 고칠 수 있고,
# 머리말·메모와 «형식으로» 구별되므로 사람의 글이 후보로 잘못 읽히지 않는다
ENTRY_PATTERN: Final = re.compile(r"^- \[([ x])\] (.+)$")

UNEXPLORED_PREFIX: Final = "- [ ] "
EXPLORED_PREFIX: Final = "- [x] "

# 파일이 없을 때 처음 한 번 쓰는 머리말.
# 「사람이 손으로 고칩니다 · 없으면 어떻게 되나 · 틀리게 적으면 어떻게 되나」를 적는 것은
# quant-notify 의 상태 파일 관용이다 — 그 셋이 없으면 다음 사람이 파일을 못 건드린다
PREAMBLE: Final = """# 원장 — 후보 목록

> **사람이 손으로 고쳐도 됩니다.** 프로그램은 줄을 덧붙이거나 체크 표시만 바꿉니다.
>
> - **갱신 시점**: 탐색 단계가 새 후보를 찾을 때, 수집 단계가 후보 하나를 다 팠을 때
> - **없으면**: 첫 탐색이 이 파일을 새로 만듭니다. 그전까지 팔 후보가 없습니다
> - **틀리게 적으면**: `- [ ]` / `- [x]` 로 시작하지 않는 줄은 후보로 읽히지 않고 조용히
>   무시됩니다. 후보를 손으로 넣으려면 반드시 그 형식을 지키세요
> - **체크된 줄**(`- [x]`)은 이미 판 후보라 다시 꺼내지 않습니다

"""


@dataclass(frozen=True)
class Entry:
    """원장의 후보 한 줄."""

    claim: str
    explored: bool


class UnknownCandidateError(ValueError):
    """원장에 없는 후보를 표시하려 할 때."""


def load(path: Path) -> list[Entry]:
    """원장을 읽는다.

    Args:
        path: 원장 파일 경로

    Returns:
        담긴 순서 그대로의 후보 목록. 파일이 없으면 빈 목록 —
        첫 밤은 「후보 없음」이지 오류가 아니다
    """
    if not path.is_file():
        return []

    entries: list[Entry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        matched = ENTRY_PATTERN.match(line)
        if matched is None:
            continue
        entries.append(Entry(claim=matched.group(2).strip(), explored=matched.group(1) == "x"))
    return entries


def append(path: Path, claim: str) -> bool:
    """후보를 원장 «끝»에 덧붙인다.

    Args:
        path: 원장 파일 경로
        claim: 후보의 한 줄 주장

    Returns:
        담았으면 True, 이미 있어서 담지 않았으면 False
    """
    normalized = claim.strip()
    if any(entry.claim == normalized for entry in load(path)):
        return False

    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PREAMBLE, encoding="utf-8")

    # 통째로 다시 쓰지 않고 «덧붙인다». 탐색 밤은 한 번에 여러 줄을 담는데,
    # 다시 쓰면 직전 밤이 담은 것과 사람이 적은 메모가 사라지고 **예외도 나지 않는다**
    with path.open("a", encoding="utf-8") as file:
        # [중요] 사람이 손으로 고치는 파일이라 **마지막 줄에 개행이 없을 수 있다**
        # (많은 편집기가 그렇게 저장한다). 그대로 덧붙이면 사람이 적은 후보와 새 후보가
        # 한 줄로 붙어, 사람의 후보는 망가지고 새 후보는 통째로 사라진다.
        # 예외도 나지 않고 `append` 는 True 를 돌려준다
        if _needs_newline(path):
            file.write("\n")
        file.write(f"{UNEXPLORED_PREFIX}{normalized}\n")
    return True


def _needs_newline(path: Path) -> bool:
    """파일이 개행으로 끝나지 않는지 본다. 빈 파일은 개행이 필요 없다."""
    with path.open("rb") as file:
        try:
            file.seek(-1, 2)
        except OSError:
            return False  # 빈 파일
        return file.read(1) != b"\n"


def mark_explored(path: Path, claim: str) -> None:
    """후보를 「판 것」으로 표시한다.

    Args:
        path: 원장 파일 경로
        claim: 표시할 후보의 한 줄 주장

    Raises:
        UnknownCandidateError: 그 후보가 원장에 없을 때. 조용히 넘어가면 그 후보는
            영원히 「안 판 것」으로 남아 **매일 밤 다시 팔린다**
    """
    normalized = claim.strip()
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.is_file() else []

    found = False
    rewritten: list[str] = []
    for line in lines:
        matched = ENTRY_PATTERN.match(line.rstrip("\n"))
        if matched is not None and matched.group(2).strip() == normalized:
            rewritten.append(f"{EXPLORED_PREFIX}{normalized}\n")
            found = True
        else:
            rewritten.append(line)

    if not found:
        raise UnknownCandidateError(f"원장에 없는 후보입니다: {normalized!r}")

    # 줄 하나만 바꾸지만 파일 전체를 다시 쓰게 되므로 원자적으로 바꾼다.
    # 도중에 죽으면 **중복 방지의 전부**인 이 파일이 통째로 날아간다
    with atomic_write(path) as file:
        file.writelines(rewritten)


def next_unexplored(path: Path) -> Entry | None:
    """다음에 팔 후보를 고른다.

    고르는 규칙은 **「쌓인 순서대로」** 하나다. 「그럴듯함 순」은 아직 판 적 없는 후보를
    판정해야 하므로 근거가 없고, 그 판정 자체가 또 하나의 판단자가 된다.

    Args:
        path: 원장 파일 경로

    Returns:
        아직 안 판 후보 중 가장 먼저 담긴 것. 재고가 떨어졌으면 None —
        그 신호를 받으면 밤은 수집 대신 **탐색으로 전환**한다
    """
    for entry in load(path):
        if not entry.explored:
            return entry
    return None

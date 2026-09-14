"""후보 목록(원장)을 읽고 덧붙인다.

원장은 **중복 방지의 전부**다. 없으면 같은 후보를 매일 다시 판다.
이 저장소가 누적 상태로 «만드는» 것 중 하나인 이유는 하루를 걸러도 그날 밤이 없었을 뿐
영구 손상이 아니기 때문이다 — 완주율·점수 같은 집계와 갈리는 지점이 여기다.

[중요] 사람도 손으로 고치는 파일이다. 그래서 프로그램이 통째로 다시 쓰지 않고
**줄 단위로만** 손댄다. 다시 쓰면 사람이 적어 둔 메모가 사라지고, 사라진 줄도 모른다.

[중요] 상태가 셋인 이유는 **기각이 「실패」가 아니라 판정의 결과**이기 때문이다.
잴 수 없다고 판정한 후보를 원장에서 지우면 다음 탐색이 그것을 새 후보로 다시 담고
그 밤이 또 기각한다 — 기각은 「본 적 없다」가 아니다.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from research_lab.runner import naming
from research_lab.runner.atomic import atomic_write
from research_lab.runner.naming import MAX_IDENTIFIER_LENGTH


class Status(StrEnum):
    """후보 한 줄의 상태."""

    UNEXPLORED = "unexplored"
    EXPLORED = "explored"
    # 잴 수 없다고 판정해 버린 것. 사유는 바로 아래 줄에 적힌다
    REJECTED = "rejected"
    # 밤마다 같은 자리에서 막혀 더 해봐야 소용없다고 접은 것.
    #
    # [중요] 기각과 «성질이 다르다». 기각은 「잴 수 없다」는 **판정의 결과**이고,
    # 막힘은 판정에 닿지도 못한 것이다. 한 표시로 합치면 「잴 수 없다고 판정한 것」이라는
    # 머리말 설명이 거짓이 되고, 나중에 「막힌 것만 다시 풀자」를 골라낼 수도 없다
    BLOCKED = "blocked"


# 체크박스 안에 적히는 글자. 마크다운 체크리스트라 사람이 편집기에서 그대로 읽고 고칠 수 있다
MARK_OF: Final[dict[Status, str]] = {
    Status.UNEXPLORED: " ",
    Status.EXPLORED: "x",
    Status.REJECTED: "-",
    Status.BLOCKED: "!",
}
STATUS_OF: Final[dict[str, Status]] = {mark: status for status, mark in MARK_OF.items()}

# 후보 한 줄의 형식 — `- [ ] `식별자` — 한 줄 주장`.
#
# [중요] 식별자는 «선택»이다. 예전에 담긴 줄에는 없고, 사람이 손으로 넣을 때도 빼먹는다.
# 못 읽는 줄이 생기면 그 후보를 매일 다시 판다.
#
# 식별자 자리를 ASCII 소문자·숫자·하이픈으로 좁힌 것은 한 줄 주장이 우연히
# 「백틱으로 감싼 말 + 대시」로 시작할 때 그것을 식별자로 오독하지 않게 하려는 것이다
#
# [중요] 표시 자리의 `-` 는 반드시 **문자 클래스 끝**에 둔다. 가운데 두면 범위로 읽혀
# 기존 원장이 통째로 안 읽히고, 원장은 **중복 방지의 전부**라 그 순간 모든 후보가
# 매일 다시 팔린다 — 예외는 나지 않는다
ENTRY_PATTERN: Final = re.compile(r"^- \[([ x!-])\] (?:`([a-z0-9][a-z0-9-]*)` — )?(.+)$")

# 사유를 적는 줄. 들여쓰기가 있어 `ENTRY_PATTERN` 에 걸리지 않으므로
# **사유가 후보로 읽히지 않는다** — 사람이 적은 메모가 무시되는 것과 같은 방식이다.
#
# 접두사가 둘인 이유는 상태가 갈리기 때문이다. 다만 **구분의 정본은 표시(`- [-]`/`- [!]`)이지
# 이 문자열이 아니다** — 사람이 사유를 손으로 고쳐도 상태는 남아야 한다
REASON_INDENT: Final = "      "
REJECTION_PREFIX: Final = "기각: "
BLOCKED_PREFIX: Final = "막힘: "

# 파일이 없을 때 처음 한 번 쓰는 머리말.
# 「사람이 손으로 고칩니다 · 없으면 어떻게 되나 · 틀리게 적으면 어떻게 되나」를 적는 것은
# quant-notify 의 상태 파일 관용이다 — 그 셋이 없으면 다음 사람이 파일을 못 건드린다
PREAMBLE: Final = """# 원장 — 후보 목록

> **사람이 손으로 고쳐도 됩니다.** 프로그램은 줄을 덧붙이거나 체크 표시만 바꿉니다.
>
> - **갱신 시점**: 탐색 단계가 새 후보를 찾을 때, 밤이 후보 하나를 다 팠을 때,
>   잴 수 없다고 판정해 기각할 때, 같은 자리에서 밤마다 막혀 접을 때
> - **없으면**: 첫 탐색이 이 파일을 새로 만듭니다. 그전까지 팔 후보가 없습니다
> - **틀리게 적으면**: `- [ ]` / `- [x]` / `- [-]` / `- [!]` 로 시작하지 않는 줄은 후보로
>   읽히지 않고 조용히 무시됩니다. 후보를 손으로 넣으려면 반드시 그 형식을 지키세요
>
> | 표시 | 뜻 |
> | --- | --- |
> | `- [ ]` | 아직 안 판 후보. 밤이 위에서부터 하나씩 꺼냅니다 |
> | `- [x]` | 이미 판 후보. 다시 꺼내지 않습니다 |
> | `- [-]` | **기각한 후보.** 잴 수 없다고 판정한 것이며 사유가 바로 아래 줄에 있습니다. |
> |  | 다시 파고 싶으면 `- [ ]` 로 고치고 사유 줄을 지우세요 |
> | `- [!]` | **막힌 후보.** 잴 수 없다는 판정이 아니라, 밤마다 같은 자리에서 실패해 |
> |  | 접은 것입니다. 사유가 바로 아래 줄에 있습니다. **원인을 고친 뒤** `- [ ]` 로 |
> |  | 고치고 사유 줄을 지우면 다시 팝니다 — 안 고치면 또 같은 자리에서 막힙니다 |
>
> 주장 앞의 `` `짧은이름` `` 은 산출물 폴더 이름입니다. 없어도 됩니다 —
> 없으면 한 줄 주장에서 폴더 이름을 만듭니다.

"""


@dataclass(frozen=True)
class Entry:
    """원장의 후보 한 줄."""

    claim: str
    status: Status
    # 산출물 폴더 이름이 된다. 예전에 담긴 줄에는 없다
    identifier: str | None


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
        entries.append(
            Entry(
                claim=matched.group(3).strip(),
                status=STATUS_OF[matched.group(1)],
                identifier=matched.group(2),
            )
        )
    return entries


def append(path: Path, claim: str, identifier: str | None = None) -> bool:
    """후보를 원장 «끝»에 덧붙인다.

    Args:
        path: 원장 파일 경로
        claim: 후보의 한 줄 주장
        identifier: 산출물 폴더에 쓸 짧은 이름. 이미 쓰인 이름이면 다른 것이 주어진다.
            쓸 수 있는 문자가 없으면 식별자 없이 담는다 — 후보를 잃는 것보다 낫다

    Returns:
        담았으면 True, 이미 있어서 담지 않았으면 False
    """
    normalized = canonical_claim(claim)
    existing = load(path)
    if any(entry.claim == normalized for entry in existing):
        return False

    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PREAMBLE, encoding="utf-8")

    resolved = _resolve_identifier(existing, identifier)

    # 통째로 다시 쓰지 않고 «덧붙인다». 탐색 밤은 한 번에 여러 줄을 담는데,
    # 다시 쓰면 직전 밤이 담은 것과 사람이 적은 메모가 사라지고 **예외도 나지 않는다**
    with path.open("a", encoding="utf-8") as file:
        # [중요] 사람이 손으로 고치는 파일이라 **마지막 줄에 개행이 없을 수 있다**
        # (많은 편집기가 그렇게 저장한다). 그대로 덧붙이면 사람이 적은 후보와 새 후보가
        # 한 줄로 붙어, 사람의 후보는 망가지고 새 후보는 통째로 사라진다.
        # 예외도 나지 않고 `append` 는 True 를 돌려준다
        if _needs_newline(path):
            file.write("\n")
        file.write(_format_entry(Status.UNEXPLORED, resolved, normalized) + "\n")
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

    [중요] 이것은 **밤의 마지막 단계가 끝난 뒤에** 불려야 한다. 수집이 끝나자마자 표시하면,
    그 뒤 반증이 실패해 그 실행 폴더가 버려질 때 **후보가 반증 없이 「판 것」으로 남아
    영영 다시 안 파진다.**

    Args:
        path: 원장 파일 경로
        claim: 표시할 후보의 한 줄 주장

    Raises:
        UnknownCandidateError: 그 후보가 원장에 없을 때. 조용히 넘어가면 그 후보는
            영원히 「안 판 것」으로 남아 **매일 밤 다시 팔린다**
    """
    _rewrite(path, claim, status=Status.EXPLORED, note=None)


def mark_blocked(path: Path, claim: str, reason: str) -> None:
    """후보를 「막힘」으로 표시하고 사유를 바로 아래 줄에 적는다.

    같은 실행 폴더에서 같은 단계가 밤마다 실패할 때 부른다. **기각과 다르다** —
    잴 수 없다고 판정한 것이 아니라 판정에 닿지도 못한 것이고, 그래서 원인을 고치면
    다시 팔 가치가 있다.

    걷어내지 않으면 다음 밤이 같은 후보를 다시 잡아 **탐색도 수집도 영영 다시 돌지 않고
    매일 호출만 한 번씩 태운다.** 아침에 보면 「실패」가 아니라 「아무 일 없음」처럼 보인다.

    Args:
        path: 원장 파일 경로
        claim: 막을 후보의 한 줄 주장
        reason: 어느 단계가 왜 막혔나. 사람이 원인을 고칠 단서가 이것뿐이다

    Raises:
        UnknownCandidateError: 그 후보가 원장에 없을 때
    """
    _rewrite(path, claim, status=Status.BLOCKED, note=f"{BLOCKED_PREFIX}{reason}")


def mark_rejected(path: Path, claim: str, reason: str) -> None:
    """후보를 「기각」으로 표시하고 사유를 바로 아래 줄에 적는다.

    기각은 «실패»가 아니라 판정의 결과다. 사유를 남기는 이유는 **다음에 같은 후보를
    또 파지 않게** 하려는 것이고, 사람이 판정을 뒤집을 때 근거가 되게 하려는 것이다.

    Args:
        path: 원장 파일 경로
        claim: 기각할 후보의 한 줄 주장
        reason: 왜 기각했나. 「거부됨」만 남으면 다음 밤이 같은 시도를 반복한다

    Raises:
        UnknownCandidateError: 그 후보가 원장에 없을 때
    """
    _rewrite(path, claim, status=Status.REJECTED, note=f"{REJECTION_PREFIX}{reason}")


def assign_identifier(path: Path, claim: str, identifier: str) -> str:
    """식별자가 없는 후보에 식별자를 박는다.

    이미 쌓인 후보도 짧은 폴더명을 얻는 경로다. 그 후보를 두고 에이전트를 어차피 부르므로
    **별도 호출이 들지 않는다.**

    Args:
        path: 원장 파일 경로
        claim: 대상 후보의 한 줄 주장
        identifier: 쓰고 싶은 짧은 이름. 겹치거나 못 쓰는 형태면 다른 것이 주어진다

    Returns:
        실제로 박힌 식별자. 하나도 못 만들었으면 빈 문자열 —
        예외로 올리면 **이름 하나 때문에 그 후보를 영영 못 판다**

    Raises:
        UnknownCandidateError: 그 후보가 원장에 없을 때
    """
    resolved = _resolve_identifier(load(path), identifier)
    if resolved is None:
        return ""

    _rewrite(path, claim, status=None, note=None, identifier=resolved)
    return resolved


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
        if entry.status is Status.UNEXPLORED:
            return entry
    return None


def canonical_claim(claim: str) -> str:
    """한 줄 주장을 원장에 담을 «정규 형태»로 만든다.

    [중요] 앞머리의 백틱을 떼는 이유는 **식별자 자리와 헷갈리지 않게** 하려는 것이다.
    한 줄 주장이 우연히 `` `abc` — `` 로 시작하면 그 줄을 다시 읽을 때 앞부분이 식별자로
    읽히고 주장은 잘린 채 돌아온다. 그러면 **중복 판정이 통째로 깨져** 같은 후보가 매일
    새로 담기고, 표시를 바꾸려는 호출은 「원장에 없는 후보」로 예외를 낸다.
    에러가 아니라 **조용한 중복**으로 나타나는 고장이다.

    읽고 쓰는 양쪽이 이 함수를 지나므로 **같은 주장은 언제나 같은 문자열이 되어**
    중복 판정이 안정적으로 유지된다.

    Args:
        claim: 에이전트가 낸 한 줄 주장

    Returns:
        원장에 담을 형태
    """
    return claim.strip().lstrip("`").strip()


def _is_reason_line(line: str) -> bool:
    """프로그램이 적은 사유 줄인가.

    접두사까지 보는 것이 핵심이다. 들여쓰기만 보면 **사람이 들여 쓴 메모가 지워진다** —
    이 파일은 사람도 고치라고 만든 것이다.
    """
    return any(line.startswith(f"{REASON_INDENT}{prefix}") for prefix in (REJECTION_PREFIX, BLOCKED_PREFIX))


def _format_entry(status: Status, identifier: str | None, claim: str) -> str:
    """후보 한 줄을 만든다."""
    marked = f"- [{MARK_OF[status]}] "
    return f"{marked}`{identifier}` — {claim}" if identifier else f"{marked}{claim}"


def _resolve_identifier(existing: list[Entry], wanted: str | None) -> str | None:
    """쓸 수 있고 겹치지 않는 식별자를 고른다.

    식별자가 곧 산출물 폴더명이다. 겹치면 **두 후보의 근거가 한 폴더에 섞여 덮어쓰이는데**,
    앞 후보는 이미 「판 것」으로 표시돼 다시 파이지도 않으므로 근거가 영영 사라진다.

    못 쓰는 형태면 None 을 돌려 «식별자 없이» 가게 한다 — 이름 하나 때문에 후보를 버리는
    것보다 폴더명이 길어지는 편이 낫다.
    """
    if wanted is None or not wanted.strip():
        return None

    try:
        base = naming.identifier_slug(wanted)
    except naming.UnusableNameError:
        return None

    taken = {entry.identifier for entry in existing if entry.identifier}
    if base not in taken:
        return base

    # [중요] 꼬리를 붙인 뒤에도 «길이 한도 안»이어야 한다. 한도를 넘겨 돌려주면
    # 경로를 만들 때 다시 잘려 꼬리가 사라지고, 두 후보가 같은 폴더를 쓰게 된다 —
    # 이 함수가 막으려던 바로 그 결과다
    suffix = 2
    while True:
        tail = f"-{suffix}"
        trimmed = base[: MAX_IDENTIFIER_LENGTH - len(tail)].rstrip(naming.IDENTIFIER_SEPARATOR)
        made = f"{trimmed}{tail}"
        if made not in taken:
            return made
        suffix += 1


def _rewrite(
    path: Path,
    claim: str,
    *,
    status: Status | None,
    note: str | None,
    identifier: str | None = None,
) -> None:
    """그 후보의 줄 «하나»만 바꾸고, 메모가 있으면 바로 아래에 붙인다.

    표시를 바꾸는 것도 식별자를 박는 것도 같은 일이라 한 곳에서 한다.
    두 곳에 생기면 한쪽만 고쳐질 때 **예외 없이 형식이 갈린다.**

    메모의 «접두사까지 붙여서» 받는 이유는 기각과 막힘이 다른 말을 쓰기 때문이다.
    여기서 상태를 보고 고르게 하면 상태가 없는 호출(식별자 박기)까지 갈래를 따져야 한다.
    """
    normalized = canonical_claim(claim)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.is_file() else []

    found = False
    drop_stale_reason = False
    rewritten: list[str] = []
    for line in lines:
        if drop_stale_reason:
            drop_stale_reason = False
            if _is_reason_line(line):
                # 이 줄은 프로그램이 예전에 적은 사유다. 두면 표시와 사유가 어긋난 채 쌓여
                # (`- [!]` 아래에 「기각: ...」이 남는 식) 머리말이 약속한
                # 「사유가 바로 아래 줄에 있습니다」가 거짓이 된다.
                # **사람이 적은 메모는 접두사가 달라 여기 걸리지 않는다**
                continue

        matched = ENTRY_PATTERN.match(line.rstrip("\n"))
        if matched is None or matched.group(3).strip() != normalized or found:
            rewritten.append(line)
            continue

        found = True
        drop_stale_reason = True
        rewritten.append(
            _format_entry(
                status if status is not None else STATUS_OF[matched.group(1)],
                identifier if identifier is not None else matched.group(2),
                normalized,
            )
            + "\n"
        )
        if note is not None:
            # 여러 줄 사유가 들어와도 한 줄로 눕힌다. 줄이 나뉘면 아래 줄이
            # 사유인지 다른 것인지 형식으로 구별되지 않는다
            flattened = " ".join(note.split())
            rewritten.append(f"{REASON_INDENT}{flattened}\n")

    if not found:
        raise UnknownCandidateError(f"원장에 없는 후보입니다: {normalized!r}")

    # 줄 하나만 바꾸지만 파일 전체를 다시 쓰게 되므로 원자적으로 바꾼다.
    # 도중에 죽으면 **중복 방지의 전부**인 이 파일이 통째로 날아간다
    with atomic_write(path) as file:
        file.writelines(rewritten)

"""문서 지도(docs/INDEX.md)와 문서 배치 계약을 고정한다.

틀린 인덱스는 없는 것보다 나쁘다. 문서를 추가·삭제·이동했는데 지도를 안 고치면
다음 세션이 없는 파일을 찾거나 있는 파일을 놓친다.

[중요] 이 저장소에서는 «등록 범위»가 탐지만큼 중요하다. 리서치 산출물은 회차마다 늘어나므로
등록 의무를 씌우면 **에이전트가 회차마다 지도를 고쳐야 하고, 안 고치면 품질 검증이 실패하는데
무인 실행에는 고칠 사람이 없다.** 강제 장치가 파이프라인을 멈추는 구조가 된다.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "docs" / "INDEX.md"

# 마크다운 링크에서 경로를 뽑는다: [텍스트](경로)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

# 등록 의무 대상 폴더. **`docs` 하나뿐이다** —
# 산출물 폴더(`dossier/` · `runs/` · `ledger/`)가 전부 저장소 루트 직하라
# 이 한 줄이 곧 「산출물은 면제」 규칙이 된다
REGISTERED_DIRS = ("docs",)

# 등록 의무에서 제외하는 경로.
# `plans/` 는 주기적으로 전부 삭제되는 임시 산출물이고, `.gitkeep` 은 폴더 유지용 빈 파일이다
REGISTRATION_EXEMPT = (
    "docs/INDEX.md",  # 자기 자신
    "docs/plans/",
    ".gitkeep",
)

# 계획서 폴더를 비워도 남겨야 하는 파일.
# 폴더가 사라지면 계획서 게이트 훅이 규약 미채택으로 보고 **조용히 꺼진다**
PLANS_KEEPER_PATH = PROJECT_ROOT / "docs" / "plans" / ".gitkeep"

# 회차마다 늘어나는 산출물. 등록 의무를 씌우면 안 되는 폴더들이다
OUTPUT_DIRS = ("dossier", "runs", "ledger")


def _index_text() -> str:
    """지도 본문을 읽는다."""
    return INDEX_PATH.read_text(encoding="utf-8")


def _linked_paths() -> list[Path]:
    """지도의 마크다운 링크 중 저장소 내부 경로만 해석해 반환한다."""
    resolved: list[Path] = []
    for raw in MARKDOWN_LINK.findall(_index_text()):
        if raw.startswith(("http://", "https://", "#", "mailto:")):
            continue
        # 앵커(#절)는 떼고 파일 경로만 본다
        target = (INDEX_PATH.parent / raw.split("#")[0]).resolve()
        resolved.append(target)
    return resolved


def _tracked_files() -> list[Path]:
    """지도에 등록돼야 하는 실제 파일 목록을 만든다."""
    tracked: list[Path] = []
    for dir_name in REGISTERED_DIRS:
        for path in (PROJECT_ROOT / dir_name).rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            if any(part in relative for part in REGISTRATION_EXEMPT):
                continue
            tracked.append(path)
    return tracked


def test_index_exists() -> None:
    """
    목적: 문서 지도가 존재한다는 계약을 고정한다.

    Given: 저장소 루트
    When: docs/INDEX.md 를 찾는다
    Then: 파일이 존재하고 비어 있지 않다
    """
    assert INDEX_PATH.is_file(), f"문서 지도가 없습니다: {INDEX_PATH}"
    assert _index_text().strip(), "문서 지도가 비어 있습니다"


def test_index_links_resolve() -> None:
    """
    목적: 지도에 적힌 경로가 전부 실재함을 고정한다 (죽은 링크 차단).

    Given: 지도의 모든 내부 마크다운 링크
    When: 각 경로를 파일 시스템에서 확인한다
    Then: 존재하지 않는 경로가 하나도 없다
    """
    missing = [p for p in _linked_paths() if not p.exists()]
    assert not missing, "지도가 존재하지 않는 경로를 가리킵니다:\n" + "\n".join(
        f"  - {p.relative_to(PROJECT_ROOT) if PROJECT_ROOT in p.parents else p}" for p in missing
    )


def test_all_documents_registered() -> None:
    """
    목적: docs/ 의 모든 문서가 지도에 등록됨을 고정한다 (누락 차단).

    Given: 등록 의무 대상 폴더의 실제 파일 목록
    When: 지도가 링크한 경로 집합과 대조한다
    Then: 등록되지 않은 파일이 하나도 없다
    """
    linked = set(_linked_paths())
    unregistered = [p for p in _tracked_files() if p.resolve() not in linked]
    assert not unregistered, "지도에 등록되지 않은 문서가 있습니다. docs/INDEX.md 에 추가하세요:\n" + "\n".join(
        f"  - {p.relative_to(PROJECT_ROOT)}" for p in sorted(unregistered)
    )


@pytest.mark.parametrize(
    "required",
    [
        "CLAUDE.md",
        "docs/DESIGN.md",
        "docs/COMMANDS.md",
        "src/research_lab/CLAUDE.md",
    ],
)
def test_core_documents_linked(required: str) -> None:
    """
    목적: 진입에 반드시 필요한 문서가 지도에서 빠지지 않음을 고정한다.

    Given: 핵심 문서 경로
    When: 지도가 링크한 경로 집합을 확인한다
    Then: 해당 문서가 링크돼 있다
    """
    target = (PROJECT_ROOT / required).resolve()
    assert target in set(_linked_paths()), f"지도에 핵심 문서 링크가 없습니다: {required}"


@pytest.mark.parametrize("output_dir", OUTPUT_DIRS)
def test_output_dirs_are_not_registration_targets(output_dir: str) -> None:
    """
    목적: 리서치 산출물이 등록 «대상»이 아님을 계약으로 고정한다.

    이 줄이 없으면 나중에 누군가 「문서를 다 등록하자」며 산출물 폴더를 등록 대상에 넣는다.
    그러면 dossier 가 한 장 늘 때마다 품질 검증이 실패하고, **무인 실행에는 고칠 사람이 없다.**
    지도는 「세션이 무엇을 읽어야 하나」의 지도이고, dossier 는 읽히려고 있는 것이 아니라
    저장소 밖으로 «나가려고» 있다.

    Given: 산출물 폴더 이름
    When: 등록 의무 대상 목록을 확인한다
    Then: 들어 있지 않다
    """
    assert output_dir not in REGISTERED_DIRS


def test_plans_folder_keeper_exists() -> None:
    """
    목적: 계획서 폴더가 비어도 유지된다는 계약을 고정한다.

    폴더가 사라지면 계획서 게이트 훅이 「규약 미채택」으로 보고 **조용히 꺼진다.**
    그때부터 계획서 없는 코드 변경이 아무 저항 없이 통과한다.

    Given: docs/plans/
    When: 유지용 파일을 찾는다
    Then: .gitkeep 이 존재한다
    """
    assert PLANS_KEEPER_PATH.is_file(), "docs/plans/.gitkeep 이 없습니다. 계획서를 전부 비우면 폴더가 사라져 " "계획서 게이트 훅이 조용히 꺼집니다"

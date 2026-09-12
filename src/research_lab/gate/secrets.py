"""산출물과 로그에 자격증명이 들어갔는지 검사한다.

이 저장소는 PUBLIC 이고 에이전트가 아무도 안 볼 때 매일 밤 파일을 쓴다.
자매 저장소에는 없던 위험이라 **규칙이 아니라 기계가** 막는다.

[중요] 이 검사기는 «사후» 장치다. 발견했을 때 파일은 이미 쓰여 있다.
1차 방어는 컨테이너에 넣는 자격증명을 Claude 토큰 하나로 줄이고 그 HOME 을 저장소 «밖»에
두는 것이며, 여기는 마지막 그물이다.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from research_lab.common_constants import DOSSIER_DIR, LEDGER_DIR

# 탐지 규칙. **이름을 붙이는 이유**는 발견을 기록할 때 값 대신 이름을 남기기 위해서다.
#
# [중요] 이 표는 러너가 «그 밤에 쓴» 경로에만 적용된다. 저장소 전체로 넓히면
# 계약 테스트와 계획서에 든 같은 리터럴에 걸려 **매일 밤이 실패한다** —
# 그 고장은 진짜 유출과 구별되지 않아, 사람이 결과를 안 믿게 된다
RULES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("anthropic-oauth-token", re.compile(r"sk-ant-oat\d")),
    ("anthropic-api-key", re.compile(r"sk-ant-")),
    ("private-key-header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
)


@dataclass(frozen=True)
class Finding:
    """어디서 무엇이 걸렸나.

    [중요] **값 자체를 담지 않는다.** 발견을 로그에 남기는데 그 로그가 값을 담으면
    자격증명이 산출물에서 로그로 «옮겨갈» 뿐이고, 그 로그도 PUBLIC 저장소에 있다.
    조치에 필요한 것은 「어느 파일 몇 번째 줄에 무엇이 걸렸나」이지 값이 아니다.
    """

    path: Path
    rule: str
    line_number: int


def scan_roots(run_dir: Path) -> tuple[Path, ...]:
    """그 밤의 검사 범위를 만든다.

    [중요] **지난 밤들의 실행 폴더를 넣지 않는다.** `runs/` 전체를 넘기면 과거 어느 밤에
    한 번 걸린 파일이 **이후 모든 밤을 영구히 실패시킨다** — 아무도 그 파일을 치우지 않고,
    `runs/` 는 git 에서 빠져 있어 눈에 띄지도 않는다. 게다가 밤마다 검사 대상이 누적돼
    시간이 계속 늘어난다.

    Args:
        run_dir: 그 밤의 실행 폴더

    Returns:
        그 밤에 러너가 쓴 곳들 — 이번 실행 폴더 · 근거 문서 · 원장
    """
    return (run_dir, DOSSIER_DIR, LEDGER_DIR)


def scan(roots: Iterable[Path]) -> list[Finding]:
    """주어진 경로들에서 자격증명 모양을 찾는다.

    Args:
        roots: 검사할 폴더 또는 파일. **러너가 그 밤에 쓴 곳만** 넘긴다
            (`common_constants.SECRET_SCAN_ROOTS`)

    Returns:
        발견 목록. 없으면 빈 목록

    [중요] **어떤 파일 때문에도 예외를 올리지 않는다.** 판정을 «못 하는 것»과
    «실패로 판정하는 것»은 다르다. 검사기가 죽으면 읽을 수 있었던 나머지 파일까지
    함께 검사를 못 받는다.
    """
    findings: list[Finding] = []
    for root in roots:
        for path in _files_under(root):
            findings.extend(_scan_file(path))
    return findings


def _files_under(root: Path) -> list[Path]:
    """그 경로 아래의 파일을 모은다. 없는 경로는 「발견 없음」이다.

    `dossier/` 는 첫 근거 문서가 나오기 전까지 존재하지 않는다.
    이걸 실패로 보면 **첫 밤이 무조건 실패한다.**
    """
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _scan_file(path: Path) -> list[Finding]:
    """파일 하나를 훑는다. 못 읽으면 조용히 건너뛴다."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # 이미지·바이너리이거나 권한이 없는 경우다. 자격증명은 사람이 읽는 텍스트로
        # 새는 것이 사실상 전부라, 여기서 멈추는 것보다 넘어가는 편이 낫다
        return []

    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in RULES:
            if pattern.search(line):
                findings.append(Finding(path=path, rule=rule, line_number=line_number))
                # 한 줄에서 규칙 하나만 보고한다. 같은 값이 여러 규칙에 걸려도
                # 조치는 「그 줄을 지우는 것」 하나다
                break
    return findings

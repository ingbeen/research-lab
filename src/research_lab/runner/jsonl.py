"""덧붙이기만 하는 JSONL 파일을 읽고 쓴다 — 두 로그가 공유하는 바닥.

결정 로그(실행 폴더의 과정)와 회차 로그(회차의 생애)는 **자리와 계약이 다르지만
파일을 다루는 방식은 같다.** 두 벌로 두면 **한 곳만 고쳐질 때 다른 쪽이 조용히 낡는다** —
실제로 아래 디코드 문제가 두 곳에 똑같이 있었고, 코드 리뷰가 그것을 두 번 찾아야 했다.

[중요] **깨진 줄에서 예외를 올리지 않는다.** 이 파일들은 회차마다 덧붙여지므로
한 줄이 반쯤 쓰이다 끊길 수 있고, 사람이 손으로 고칠 수도 있다. 여기서 터지면
**정작 원인을 되짚어야 할 때 아무것도 못 보고**, 읽는 쪽이 예산 판정이면
**멀쩡한 회차가 판정에서 죽는다**(계층 계약 §3).

[중요] 그래서 **바이트로 읽어 «줄 단위로» 관대하게 디코드한다.** 파일을 통째로 문자열로
읽으면 **한글이 반쯤 잘린 줄 하나가 파일 전체를 못 읽게 만든다** — 그 예외는 줄 단위
JSON 가드보다 «먼저» 터지므로 가드가 한 번도 돌지 않는다. 이 저장소의 로그는 사유·주장이
전부 한글이라 잘린 줄은 거의 언제나 이 모양이 된다.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from research_lab.common_constants import KST


def append(path: Path, entry: dict[str, Any]) -> None:
    """한 줄 덧붙인다 — 시각을 맨 앞에 붙여서.

    Args:
        path: JSONL 파일
        entry: 그 줄에 적을 것

    [주의] 덧붙이기만 한다. 다시 쓰면 앞부분이 사라지고 **예외도 나지 않는다.**
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = {"ts": datetime.now(KST).isoformat(timespec="seconds"), **entry}
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(stamped, ensure_ascii=False) + "\n")


def read(path: Path) -> list[dict[str, Any]]:
    """적힌 순서대로 읽는다.

    Args:
        path: JSONL 파일

    Returns:
        읽히는 줄만. 파일이 없으면 빈 목록. **깨진 줄은 건너뛴다** —
        잘린 글자든 깨진 JSON 이든 객체가 아닌 값이든 예외를 올리지 않는다
    """
    if not path.is_file():
        return []

    # [중요] `read_text` 를 쓰지 않는다. 그쪽은 파일을 통째로 디코드하므로
    # 잘린 한글 한 글자가 **파일 전체**를 못 읽게 만든다
    text = path.read_bytes().decode("utf-8", errors="replace")

    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            loaded: Any = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            entries.append(loaded)
    return entries

"""그 회차의 «과정»을 남긴다.

산출물(dossier)은 **결론**이고 이 로그는 **과정**이다. 둘을 섞으면 dossier 가 읽히지 않는다.

줄글이 아니라 JSONL 인 이유는 「나중에 기계가 훑을 것」이기 때문이다 —
게이트 기준이나 프롬프트를 고쳤을 때 **과거 로그를 다시 읽어 「지금 기준이면 판정이
달라졌을 후보」를 찾아낼 수 있어야** 한다. 줄글로 남기면 그 질문에 답할 수 없다.

[중요] **비용·토큰·소요 시간도 여기 적는다.** 그래야 회차 예산 집계가 저장소 «안»에서
완결되어, 컨테이너의 세션 로그에 의존하지 않고 기계를 옮겨도 기록이 따라온다.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import DECISION_LOG_FILENAME, KST

# 이벤트 종류. 「무엇을 읽었나 · 무엇을 기준으로 판단했나 · 무엇을 버렸고 왜」를
# 나중에 기계가 골라낼 수 있도록 이름을 고정한다 — 자유 문자열이면 훑을 때 매번 추측해야 한다
EVENT_READ: Final = "read"
EVENT_JUDGED: Final = "judged"
EVENT_DISCARDED: Final = "discarded"
EVENT_SKIPPED: Final = "skipped"
EVENT_FAILED: Final = "failed"
EVENT_COST: Final = "cost"

# 같은 자리에서 회차마다 실패해 그 후보와 실행 폴더를 접었다.
#
# [중요] 「버렸다」(`EVENT_DISCARDED`)와 갈라 둔다. 수집이 **기각 수를 그 이름으로 세므로**,
# 막힘을 같은 이름으로 적으면 그 회차의 기각 상한이 조용히 앞당겨진다 —
# 이름을 고정해 두는 이유가 바로 이런 자리다
EVENT_BLOCKED: Final = "blocked"


def record(run_dir: Path, step: str, event: str, **fields: Any) -> None:
    """결정 한 건을 덧붙인다.

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 어느 단계에서 일어난 일인가
        event: 이벤트 종류 (`EVENT_*`)
        **fields: 그 이벤트의 내용. 검색어 목록·URL 목록·판단 기준·버린 이유·
            토큰과 비용·실패 원문 등이 들어온다

    [주의] 덧붙이기만 한다. 다시 쓰면 그 회차의 앞부분이 사라지고 **예외도 나지 않는다**
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "ts": datetime.now(KST).isoformat(timespec="seconds"),
        "step": step,
        "event": event,
        **fields,
    }

    with (run_dir / DECISION_LOG_FILENAME).open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_cost(run_dir: Path, step: str, result: AgentResult) -> None:
    """한 번의 호출이 쓴 비용·토큰·시간을 남긴다.

    네 단계가 똑같이 적는 값이라 한 곳에서 만든다. 네 벌로 흩어져 있으면
    **한 곳만 고쳐질 때 회차 예산 집계가 그 단계에서만 어긋나고**, 합계가 틀렸다는 것은
    드러나지 않는다.

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 어느 단계의 호출인가
        result: 에이전트 호출 결과
    """
    record(
        run_dir,
        step,
        EVENT_COST,
        cost_usd=result.cost_usd,
        tokens=result.tokens,
        elapsed_seconds=round(result.elapsed_seconds, 1),
        session_id=result.session_id,
    )


def read(run_dir: Path) -> list[dict[str, Any]]:
    """그 회차의 결정 로그를 읽는다.

    Args:
        run_dir: 그 회차의 실행 폴더

    Returns:
        적힌 순서 그대로의 기록. 파일이 없으면 빈 목록.
        **깨진 줄은 건너뛴다** — 한 줄이 깨졌다고 그 회차의 나머지 기록을 통째로
        못 읽게 되면, 정작 원인을 되짚어야 할 때 아무것도 못 본다
    """
    path = run_dir / DECISION_LOG_FILENAME
    if not path.is_file():
        return []

    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            loaded: Any = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            entries.append(loaded)
    return entries

"""탐색 단계 — 후보 «목록»을 만들어 원장에 담는다.

넓게 훑고 얕아도 된다. 산출물은 후보마다 **한 줄 주장** 하나다.
수집보다 싸고, **이 단계가 있어서 사람이 후보를 적어 넣지 않아도 첫 밤이 돈다.**
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import EXPLORE_RESULT_FILENAME
from research_lab.gate import queries as query_gate
from research_lab.runner import decision_log, ledger
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

# 프롬프트만 받아 에이전트를 부르는 쪽. 이 단계는 «어떻게» 부르는지 모른다 —
# 그래야 호출 계층이 단계에 맞춰 깎이지 않고, 돌려보지 않고도 이 단계를 검사할 수 있다
AgentCaller = Callable[[str], AgentResult]

# 한 밤에 담을 후보 수의 상한. 많이 담는 것이 목적이 아니라 **수집이 팔 재고**를 만드는 것이라,
# 한 번에 너무 많이 담으면 오래된 후보가 계속 뒤로 밀린다
MAX_CANDIDATES: Final = 15

PROMPT: Final = """이 저장소의 `.claude/skills/night-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 탐색

아직 검증되지 않은 **매매법 후보 목록**을 만듭니다. 넓게 훑고, 얕아도 됩니다.
후보 하나를 깊게 파는 것은 다른 단계의 일입니다.

- 대상 시장은 **국내 주식과 미국 주식 둘 다**입니다. 한쪽만 훑지 마세요
- 후보마다 **한 줄 주장**을 적습니다 — 「무엇을 언제 사고 언제 파는가」가 한 문장에 들어가야 합니다
- 최대 {max_candidates}개까지만 담습니다
- 검색어는 한국어와 영어를 모두 돌리고, **던진 검색어를 하나도 빼지 않고** 적습니다

## 이미 본 후보 (다시 담지 마세요)

{known}

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"queries": ["던진 검색어 전부"], "candidates": [{{"claim": "한 줄 주장", "why": "왜 후보로 볼 만한가", "market": "국내|미국"}}]}}
"""


def build_prompt(known_claims: list[str]) -> str:
    """탐색 지시문을 만든다.

    Args:
        known_claims: 원장에 이미 있는 후보들. 같은 것을 또 담으면 그만큼 그 밤이 헛돈다

    Returns:
        에이전트에게 줄 지시문
    """
    listed = "\n".join(f"- {claim}" for claim in known_claims) if known_claims else "(아직 없음)"
    return PROMPT.format(max_candidates=MAX_CANDIDATES, known=listed)


def run(run_dir: Path, ledger_path: Path, ask: AgentCaller) -> None:
    """탐색을 한 번 돌고 원장에 담는다.

    Args:
        run_dir: 그 밤의 실행 폴더
        ledger_path: 원장 경로
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        StepFailed: 응답이 약속한 모양이 아닐 때. **원문을 통째로 실어 보낸다** —
            분류와 재시도는 러너가 하고, 원문이 없으면 다음에 같은 모양을 못 가르친다
    """
    # 단계가 자기 산출물 폴더를 만든다. 부르는 쪽이 만들어 줬을 것이라 가정하면
    # 호출 경로가 늘 때마다 같은 실수를 되풀이한다
    run_dir.mkdir(parents=True, exist_ok=True)

    known = [entry.claim for entry in ledger.load(ledger_path)]
    result = ask(build_prompt(known))

    payload = invoke.parse_json_answer(result, what="탐색")
    queries = _as_strings(payload.get("queries"))
    candidates = _as_list(payload.get("candidates"))

    # 원문을 먼저 남긴다. 아래에서 무엇이 걸러지든 「에이전트가 무엇을 냈나」는 남아야 한다.
    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남으므로 원자적으로 바꾼다
    with atomic_write(run_dir / EXPLORE_RESULT_FILENAME) as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    decision_log.record(run_dir, "explore", decision_log.EVENT_READ, queries=queries, query_count=len(queries))

    added, duplicates = _store(ledger_path, candidates)

    decision_log.record(
        run_dir,
        "explore",
        decision_log.EVENT_JUDGED,
        added=added,
        proposed=len(candidates),
    )
    if duplicates:
        decision_log.record(
            run_dir,
            "explore",
            decision_log.EVENT_DISCARDED,
            reason="이미 원장에 있는 후보",
            claims=duplicates,
        )

    decision_log.record(
        run_dir,
        "explore",
        decision_log.EVENT_COST,
        cost_usd=result.cost_usd,
        tokens=result.tokens,
        elapsed_seconds=round(result.elapsed_seconds, 1),
        session_id=result.session_id,
    )

    # [중요] 후보를 «담은 뒤에» 검사한다. 찾은 후보를 버리면 그 밤이 통째로 헛돌고,
    # 다음 밤은 원장에 재고가 생겨 탐색을 건너뛰므로 이 실패가 반복되지도 않는다
    shortfall = query_gate.shortfall_reason(queries)
    if shortfall is not None:
        decision_log.record(run_dir, "explore", decision_log.EVENT_FAILED, gate="queries", reason=shortfall)
        raise StepQualityFailed(f"탐색 검색어 부족 — {shortfall}")


def _as_list(value: Any) -> list[Any]:
    """목록이어야 하는 값을 목록으로만 받는다.

    [중요] 이 검사가 없으면 **문자열이 글자 단위로 잘린다.** 에이전트가 목록 대신
    문자열 하나를 내놓는 것은 흔한 어긋남인데, 그때 `"없음"` 이 후보 `'없'` 과 `'음'`
    둘로 원장에 담긴다. 원장은 append-only 이고 **중복 방지의 전부**라,
    그 쓰레기는 이후 매일 밤 수집 호출을 한 번씩 잡아먹는다. 예외는 나지 않는다.
    """
    return value if isinstance(value, list) else []


def _as_strings(value: Any) -> list[str]:
    """문자열 목록이어야 하는 값을 추려 받는다. 위와 같은 이유로 목록만 받는다."""
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _store(ledger_path: Path, candidates: list[Any]) -> tuple[int, list[str]]:
    """후보를 원장에 담고, 담은 수와 중복으로 버린 것을 돌려준다."""
    added = 0
    duplicates: list[str] = []
    # 원장을 한 번만 읽는다. `ledger.append` 는 호출마다 파일 전체를 다시 읽고 파싱하므로,
    # 후보마다 부르면 원장 크기에 대해 O(n^2) 이 된다 — 원장은 매일 밤 자라는 파일이다
    seen = {entry.claim for entry in ledger.load(ledger_path)}

    for candidate in candidates[:MAX_CANDIDATES]:
        claim = _claim_of(candidate)
        if not claim:
            continue
        if claim in seen:
            duplicates.append(claim)
            continue
        if ledger.append(ledger_path, claim):
            seen.add(claim)
            added += 1
        else:
            duplicates.append(claim)

    return added, duplicates


def _claim_of(candidate: Any) -> str:
    """후보 항목에서 한 줄 주장을 꺼낸다. 모양이 어긋난 항목은 빈 문자열로 돌린다."""
    if isinstance(candidate, dict):
        return str(candidate.get("claim", "")).strip()
    if isinstance(candidate, str):
        return candidate.strip()
    return ""

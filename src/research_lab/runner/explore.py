"""탐색 단계 — 후보 «목록»을 만들어 원장에 담는다.

넓게 훑고 얕아도 된다. 산출물은 후보마다 **한 줄 주장** 하나다.
수집보다 싸고, **이 단계가 있어서 사람이 후보를 적어 넣지 않아도 첫 회차가 돈다.**
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import EXPLORE_RESULT_FILENAME
from research_lab.gate import quantified
from research_lab.gate import queries as query_gate
from research_lab.runner import decision_log, ledger
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

# 프롬프트만 받아 에이전트를 부르는 쪽. 이 단계는 «어떻게» 부르는지 모른다 —
# 그래야 호출 계층이 단계에 맞춰 깎이지 않고, 돌려보지 않고도 이 단계를 검사할 수 있다
AgentCaller = Callable[[str], AgentResult]

# 한 회차에 담을 후보 수의 상한. 많이 담는 것이 목적이 아니라 **수집이 팔 재고**를 만드는 것이라,
# 한 번에 너무 많이 담으면 오래된 후보가 계속 뒤로 밀린다
MAX_CANDIDATES: Final = 15

PROMPT: Final = """이 저장소의 `.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 탐색

아직 검증되지 않은 **매매법 후보 목록**을 만듭니다. 넓게 훑고, 얕아도 됩니다.
후보 하나를 깊게 파는 것은 다른 단계의 일입니다.

- 대상 시장은 **국내 주식과 미국 주식 둘 다**입니다. 한쪽만 훑지 마세요
- 후보마다 **한 줄 주장**을 적습니다 — 「무엇을 언제 사고 언제 파는가」가 한 문장에 들어가야 합니다
- 후보마다 **짧은 영문 식별자**를 붙입니다 (소문자·숫자·하이픈, 예: `pead-us`).
  산출물 폴더 이름이 되므로 짧고 서로 달라야 합니다
- 최대 {max_candidates}개까지만 담습니다
- 검색어는 한국어와 영어를 모두 돌리고, **던진 검색어를 하나도 빼지 않고** 적습니다

## 값이 비어 있는 표현에는 «파라미터 축»을 붙입니다

「짧은 기간」·「단기」·「크게 상회」처럼 값이 비어 있는 말을 써도 됩니다.
다만 그럴 때는 **무엇을 얼마로 바꿀 수 있는지**를 `params` 에 적으세요 —
축 이름과 단위, 그리고 **서로 다른 숫자 후보값 2개 이상**입니다.

- 「짧은 기간 내 동시 매수」 → `{{"name": "동시 매수 판정 창", "unit": "거래일", "candidates": [5, 10, 20]}}`
- 「전저점 대비」 → `{{"name": "전저점 산정 일수", "unit": "거래일", "candidates": [20, 60]}}`

**축을 못 정하겠으면 그 후보를 적지 마세요.** 「옥석을 가려」처럼 무엇을 채울지조차
없는 말과, 「(미래) 저점에서 산다」처럼 판정 시점에 알 수 없는 값이 여기 걸립니다.
임의로 값 하나를 채우면 **어떤 값을 넣느냐가 결론을 만듭니다.**

## 이미 본 후보 (다시 담지 마세요)

{known}

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"queries": ["던진 검색어 전부"], "candidates": [{{"claim": "한 줄 주장", "identifier": "짧은-영문-이름", "why": "왜 후보로 볼 만한가", "market": "국내|미국", "params": [{{"name": "축 이름", "unit": "단위", "candidates": [숫자, 숫자]}}]}}]}}
"""


def build_prompt(known_claims: list[str]) -> str:
    """탐색 지시문을 만든다.

    Args:
        known_claims: 원장에 이미 있는 후보들. 같은 것을 또 담으면 그만큼 그 회차가 헛돈다

    Returns:
        에이전트에게 줄 지시문
    """
    listed = "\n".join(f"- {claim}" for claim in known_claims) if known_claims else "(아직 없음)"
    return PROMPT.format(max_candidates=MAX_CANDIDATES, known=listed)


def run(run_dir: Path, ledger_path: Path, ask: AgentCaller) -> None:
    """탐색을 한 번 돌고 원장에 담는다.

    Args:
        run_dir: 그 회차의 실행 폴더
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
    queries = payload_helpers.as_strings(payload.get("queries"))
    candidates = payload_helpers.as_list(payload.get("candidates"))

    # 원문을 먼저 남긴다. 아래에서 무엇이 걸러지든 「에이전트가 무엇을 냈나」는 남아야 한다.
    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남으므로 원자적으로 바꾼다
    with atomic_write(run_dir / EXPLORE_RESULT_FILENAME) as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    decision_log.record(run_dir, "explore", decision_log.EVENT_READ, queries=queries, query_count=len(queries))

    added, duplicates, rejected = _store(ledger_path, candidates)

    decision_log.record(
        run_dir,
        "explore",
        decision_log.EVENT_JUDGED,
        added=added,
        proposed=len(candidates),
        rejected=len(rejected),
    )
    if duplicates:
        decision_log.record(
            run_dir,
            "explore",
            decision_log.EVENT_DISCARDED,
            reason="이미 원장에 있는 후보",
            claims=duplicates,
        )
    for claim, why in rejected:
        # 기각은 후보마다 사유가 다르므로 한 줄씩 남긴다. 묶어서 세면
        # 「무엇이 왜 걸렸나」가 사라져 사전을 고칠 재료가 없어진다
        decision_log.record(run_dir, "explore", decision_log.EVENT_DISCARDED, claim=claim, reason=why)

    decision_log.record_cost(run_dir, "explore", result)

    # [중요] 후보를 «담은 뒤에» 검사한다. 찾은 후보를 버리면 그 회차가 통째로 헛돌고,
    # 다음 회차는 원장에 재고가 생겨 탐색을 건너뛰므로 이 실패가 반복되지도 않는다
    shortfall = query_gate.shortfall_reason(queries)
    if shortfall is not None:
        decision_log.record(run_dir, "explore", decision_log.EVENT_FAILED, gate="queries", reason=shortfall)
        raise StepQualityFailed(f"탐색 검색어 부족 — {shortfall}")


def _store(ledger_path: Path, candidates: list[Any]) -> tuple[int, list[str], list[tuple[str, str]]]:
    """후보를 원장에 담고, 담은 수와 중복·기각으로 버린 것을 돌려준다.

    [중요] **기각된 후보도 원장에 남긴다.** 지우면 다음 탐색이 같은 후보를 새 후보로
    다시 담고 그 회차가 또 기각한다 — 기각은 「본 적 없다」가 아니다.
    """
    added = 0
    duplicates: list[str] = []
    rejected: list[tuple[str, str]] = []
    # 중복은 «여기서» 먼저 걸러 낸다. 그래야 같은 후보를 두 번 낸 응답이 파일을 두 번
    # 건드리지 않는다.
    #
    # [주의] 이것이 원장 읽기를 «한 번»으로 만들지는 않는다 — `append` 는 호출마다 다시 읽고
    # `mark_rejected` 는 다시 쓴다. 한 회차의 후보 수가 `MAX_CANDIDATES` 로 묶여 있어 실제
    # 비용은 작지만, **원장이 아주 커지면 여기가 먼저 느려진다.** 그때는 줄 단위 손질을
    # 한 번에 모아 쓰는 쪽으로 바꾼다
    seen = {entry.claim for entry in ledger.load(ledger_path)}

    for candidate in candidates[:MAX_CANDIDATES]:
        claim = _text_of(candidate, "claim")
        if not claim:
            continue
        if claim in seen:
            duplicates.append(claim)
            continue

        if not ledger.append(ledger_path, claim, identifier=_text_of(candidate, "identifier") or None):
            duplicates.append(claim)
            continue

        seen.add(claim)
        shortfall = quantified.shortfall_reason(claim, _params_of(candidate))
        if shortfall is None:
            added += 1
            continue

        # 담은 «뒤에» 기각으로 돌린다. 중복 방지는 담겨 있어야 작동하기 때문이다
        ledger.mark_rejected(ledger_path, claim, shortfall)
        rejected.append((claim, shortfall))

    return added, duplicates, rejected


def _text_of(candidate: Any, key: str) -> str:
    """후보 항목에서 문자열 한 칸을 꺼낸다. 모양이 어긋난 항목은 빈 문자열로 돌린다."""
    if isinstance(candidate, dict):
        return str(candidate.get(key, "")).strip()
    if isinstance(candidate, str) and key == "claim":
        return candidate.strip()
    return ""


def _params_of(candidate: Any) -> Any:
    """후보 항목에서 파라미터 축을 꺼낸다. 모양 검사는 게이트가 한다."""
    return candidate.get("params") if isinstance(candidate, dict) else None

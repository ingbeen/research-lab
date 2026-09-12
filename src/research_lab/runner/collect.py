"""수집 단계 — 후보 하나의 «찬성 근거»를 모은다.

여기가 깊게 파는 자리다. 후보 하나만 본다.

[중요] **반증은 이 단계가 찾지 않는다.** 찬성 근거를 잔뜩 모은 맥락이 쌓인 상태에서
「이제 반증을 찾아라」라고 하면 자기가 방금 지지한 것을 스스로 무너뜨리라는 요구가 되고,
**사람도 잘 못 한다.** 반증은 한 줄 주장만 받는 별도 세션의 일이다.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import PRO_EVIDENCE_FILENAME, SEARCH_QUERIES_FILENAME
from research_lab.gate import queries as query_gate
from research_lab.runner import decision_log, ledger, naming
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]


class NoCandidateError(RuntimeError):
    """원장에 팔 후보가 없을 때."""


PROMPT: Final = """이 저장소의 `.claude/skills/night-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 수집

아래 후보 **하나**의 찬성 근거를 모읍니다. 다른 후보는 보지 마세요.

> {claim}

- 검색어를 **한국어와 영어로 각각** 갈아 끼우며 3회 이상 던지고, **던진 것을 전부** 적습니다
- 근거마다 **URL · 발행일 · 1차인지 2차인지**를 함께 적습니다
- **실제로 연 URL 만** 적습니다. 기억으로 URL 을 만들어 내지 마세요 —
  링크를 못 찾았으면 URL 을 비우고 `unverified` 에 적습니다
- **반증은 찾지 마세요.** 다른 단계의 일입니다
- 찬성 근거가 하나도 없으면 빈 목록으로 두세요. **「실체 없음」도 정상 결과입니다**
- 비용·세금·슬리피지는 적지 마세요

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"claim": "받은 한 줄 주장 그대로", "queries": ["던진 검색어 전부"], "evidence": [{{"title": "", "url": "", "published": "YYYY-MM-DD 또는 unknown", "kind": "primary|secondary", "says": "이 출처가 주장을 어떻게 뒷받침하나"}}], "unverified": ["확인하지 못한 것"]}}
"""


def build_prompt(claim: str) -> str:
    """수집 지시문을 만든다.

    Args:
        claim: 팔 후보의 한 줄 주장

    Returns:
        에이전트에게 줄 지시문
    """
    return PROMPT.format(claim=claim)


def run(run_dir: Path, ledger_path: Path, ask: AgentCaller) -> None:
    """후보 하나를 파고 찬성 근거를 파일로 남긴다.

    Args:
        run_dir: 그 밤의 실행 폴더
        ledger_path: 원장 경로
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        NoCandidateError: 원장에 팔 후보가 없을 때. 탐색이 먼저 돌아야 한다
        StepFailed: 응답이 약속한 모양이 아닐 때
    """
    # 단계가 자기 산출물 폴더를 만든다. 부르는 쪽이 만들어 줬을 것이라 가정하면
    # 호출 경로가 늘 때마다 같은 실수를 되풀이한다
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate = ledger.next_unexplored(ledger_path)
    if candidate is None:
        raise NoCandidateError("원장에 아직 안 판 후보가 없습니다. 탐색이 먼저 돌아야 합니다.")

    result = ask(build_prompt(candidate.claim))
    payload = invoke.parse_json_answer(result, what="수집")

    queries = [str(query) for query in payload.get("queries", []) if str(query).strip()]
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    unverified = payload.get("unverified") if isinstance(payload.get("unverified"), list) else []

    # 무엇을 읽었고 얼마를 썼는지는 «게이트 앞»에서 남긴다.
    # 막혀서 끝나도 그 밤이 무엇을 했고 얼마를 태웠는지는 기록에 남아야 한다
    decision_log.record(run_dir, "collect", decision_log.EVENT_READ, queries=queries, query_count=len(queries))
    decision_log.record(
        run_dir,
        "collect",
        decision_log.EVENT_COST,
        cost_usd=result.cost_usd,
        tokens=result.tokens,
        elapsed_seconds=round(result.elapsed_seconds, 1),
        session_id=result.session_id,
    )

    # [중요] 게이트를 `mark_explored` «앞»에 둔다. 여기서 막히면 후보가 「안 판 것」으로
    # 남아 **다음 밤이 자연히 다시 판다** — 되돌릴 것이 없다.
    # 뒤에 뒀다면 이미 표시된 후보를 되돌려야 하고, 되돌리면 무한 반복을 막는 장치가 또 필요하다
    shortfall = query_gate.shortfall_reason(queries)
    if shortfall is not None:
        decision_log.record(run_dir, "collect", decision_log.EVENT_FAILED, gate="queries", reason=shortfall)
        raise StepQualityFailed(f"수집 검색어 부족 — {shortfall}")

    # [중요] 산출물은 «후보별 폴더»에 넣는다. 실행 폴더 바로 아래에 고정 이름으로 쓰면
    # 한 밤이 후보 둘을 파는 순간 뒤엣것이 앞엣것을 덮어쓴다 — 앞 후보는 이미
    # 「판 것」으로 표시돼 다시 파이지도 않아 근거가 영영 사라진다.
    # 경로를 만드는 곳은 `naming` 하나여야 한다는 계층 계약이 여기서 지켜진다
    output_dir = run_dir / naming.slug(candidate.claim)

    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남는다. 아래 `mark_explored` 가 이미
    # 돌았다면 그 잘린 파일이 그 후보의 «완성된 근거»로 취급된다
    with atomic_write(output_dir / PRO_EVIDENCE_FILENAME) as file:
        json.dump(
            {"claim": candidate.claim, "evidence": evidence, "unverified": unverified},
            file,
            ensure_ascii=False,
            indent=2,
        )
    with atomic_write(output_dir / SEARCH_QUERIES_FILENAME) as file:
        json.dump({"claim": candidate.claim, "queries": queries}, file, ensure_ascii=False, indent=2)

    decision_log.record(
        run_dir,
        "collect",
        decision_log.EVENT_JUDGED,
        claim=candidate.claim,
        evidence_count=len(evidence) if isinstance(evidence, list) else 0,
        unverified_count=len(unverified) if isinstance(unverified, list) else 0,
        # 「찬성 근거 0건」은 고장이 아니라 **실체 없음이라는 정상 결과**다.
        # 그 판정을 나중에 기계가 골라낼 수 있게 이름을 붙여 둔다
        verdict="실체 없음" if not evidence else "근거 있음",
    )
    # 파일을 쓴 «뒤에» 표시한다. 순서가 반대면 산출물 없이 「판 것」으로 남아
    # 다음 밤이 그 후보를 다시 꺼내지 않는다
    ledger.mark_explored(ledger_path, candidate.claim)

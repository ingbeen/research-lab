"""수집 단계 — 후보 하나를 골라 «찬성 근거»를 모은다.

여기가 깊게 파는 자리다. 후보 하나만 본다.

[중요] **반증은 이 단계가 찾지 않는다.** 찬성 근거를 잔뜩 모은 맥락이 쌓인 상태에서
「이제 반증을 찾아라」라고 하면 자기가 방금 지지한 것을 스스로 무너뜨리라는 요구가 되고,
**사람도 잘 못 한다.** 반증은 한 줄 주장만 받는 별도 세션의 일이다.

[중요] **이 단계가 그 밤의 후보를 정한다.** 뒤따르는 반증·계보가 같은 후보를 봐야 하므로
고른 후보를 상태 파일에 박는다. 다만 **「판 것」으로 표시하지는 않는다** — 표시는
마지막 단계의 일이고, 여기서 표시하면 그 뒤 반증이 실패해 그 실행 폴더가 버려질 때
**후보가 반증 없이 「판 것」으로 남아 영영 다시 안 파진다.**
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import PRO_EVIDENCE_FILENAME, SEARCH_QUERIES_FILENAME
from research_lab.gate import quantified
from research_lab.gate import queries as query_gate
from research_lab.runner import decision_log, ledger, naming, state
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]

# 한 밤에 기각할 수 있는 후보의 수.
#
# [중요] 상한이 없으면 원장이 전부 기각될 때까지 호출을 태운다. 아침에 보면 예산은 줄었고
# 산출물은 0장인데, 그런 밤은 「실패」가 아니라 「아무 일 없음」처럼 보여 며칠 지나서야
# 알아챈다 — 「그 외」 실패에 상한을 두는 것과 같은 이유다.
#
# 상한에 닿으면 그 밤의 수집을 끝낸다. 기각은 원장에 남으므로 다음 밤이 그 뒤부터 이어간다
MAX_REJECTIONS: Final = 3


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

## 이 주장의 «파라미터 축»을 함께 냅니다

{axis_demand}

값이 비어 있는 말마다 **무엇을 얼마로 바꿀 수 있는지**를 `params` 에 적습니다 —
축 이름과 단위, 그리고 **서로 다른 숫자 후보값 2개 이상**입니다.

- 「짧은 기간 내 동시 매수」 → `{{"name": "동시 매수 판정 창", "unit": "거래일", "candidates": [5, 10, 20]}}`
- 「전저점 대비」 → `{{"name": "전저점 산정 일수", "unit": "거래일", "candidates": [20, 60]}}`

**축을 못 정하겠으면 빈 목록으로 두세요.** 「옥석을 가려」처럼 무엇을 채울지조차 없는 말과,
「(미래) 저점에서 산다」처럼 판정 시점에 알 수 없는 값이 여기 걸립니다.
그 후보는 잴 수 없는 것으로 판정되어 사유와 함께 기록되며, **그것도 정상 결과입니다** —
임의로 값 하나를 채우면 어떤 값을 넣느냐가 결론을 만듭니다.

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"claim": "받은 한 줄 주장 그대로", "identifier": "짧은-영문-이름", "queries": ["던진 검색어 전부"], "params": [{{"name": "축 이름", "unit": "단위", "candidates": [숫자, 숫자]}}], "evidence": [{{"title": "", "url": "", "published": "YYYY-MM-DD 또는 unknown", "kind": "primary|secondary", "says": "이 출처가 주장을 어떻게 뒷받침하나"}}], "unverified": ["확인하지 못한 것"]}}
"""


def build_prompt(claim: str) -> str:
    """수집 지시문을 만든다.

    [중요] 걸린 표현을 **이름으로 짚어** 요구한다. 「값이 비어 있으면 적으라」고만 하면
    에이전트가 자기 문장에 그런 말이 있는지를 스스로 판정해야 하고, 실측에서 이미
    「이 주장은 값이 다 정해졌다」고 넘어가는 모양이 나왔다. 그러면 그 후보는 기각되는데,
    **탐색에서 한 번 통과했던 후보가 수집에서 죽는** 일이 된다.

    Args:
        claim: 팔 후보의 한 줄 주장

    Returns:
        에이전트에게 줄 지시문
    """
    terms = quantified.triggered_terms(claim)
    if terms:
        demand = (
            f"이 주장에는 값이 비어 있는 표현이 있습니다 — **{' · '.join(terms)}**.\n"
            f"**이 표현들은 반드시 축으로 풀어야 합니다.** 하나도 풀지 못하면 그 후보는 "
            f"잴 수 없는 것으로 판정되어 사유와 함께 기록됩니다."
        )
    else:
        demand = "이 주장은 값이 다 정해져 있습니다. 그래도 잴 때 갈릴 축이 있으면 적고, 없으면 `params` 는 빈 목록입니다."
    return PROMPT.format(claim=claim, axis_demand=demand)


def run(run_dir: Path, ledger_path: Path, ask: AgentCaller) -> None:
    """후보를 하나 골라 찬성 근거를 파일로 남기고, 그 밤의 후보로 박는다.

    잴 수 없다고 판정된 후보는 사유와 함께 기각하고 **다음 후보로 넘어간다.**
    기각은 실패가 아니라 판정의 결과이므로 그 밤이 멈추지 않는다.

    Args:
        run_dir: 그 밤의 실행 폴더
        ledger_path: 원장 경로
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        NoCandidateError: 원장에 팔 후보가 처음부터 없을 때. 탐색이 먼저 돌아야 한다
        StepFailed: 응답이 약속한 모양이 아닐 때
        StepQualityFailed: 검색어 규율을 못 지켰을 때
    """
    # 단계가 자기 산출물 폴더를 만든다. 부르는 쪽이 만들어 줬을 것이라 가정하면
    # 호출 경로가 늘 때마다 같은 실수를 되풀이한다
    run_dir.mkdir(parents=True, exist_ok=True)

    # [중요] 기각 수를 «그 밤 전체»에서 센다. 지역 변수로만 세면 이 함수가 다시 불릴 때
    # 0 으로 돌아간다 — JSON 이 깨져 「그 외」로 재시도되는 밤은 이 함수가 최대 세 번
    # 불리므로 상한이 세 배가 되고, 그만큼 후보와 예산이 함께 탄다.
    # 그 밤의 결정 로그가 이미 기각을 기록하므로 새 상태를 만들지 않고 그것을 센다
    rejections = _rejections_so_far(run_dir)
    while True:
        if rejections >= MAX_REJECTIONS:
            # 상한에 닿았다. 그 밤의 수집은 여기서 끝나고 기각은 원장에 남으므로
            # 다음 밤이 그 뒤부터 이어간다. **부르기 «전»에 본다** — 뒤에서 보면
            # 이 단계가 다시 불릴 때마다 한 번씩 더 부르게 된다
            return

        candidate = ledger.next_unexplored(ledger_path)
        if candidate is None:
            if rejections == 0:
                raise NoCandidateError("원장에 아직 안 판 후보가 없습니다. 탐색이 먼저 돌아야 합니다.")
            # 꺼낼 수 있던 후보를 모두 기각했다. 그 밤의 수집은 여기서 끝나고
            # 뒤따르는 단계는 「그 밤의 후보 없음」으로 건너뛰어진다 — 정상 결과다
            return

        payload = _ask_about(run_dir, candidate.claim, ask)

        shortfall = quantified.shortfall_reason(candidate.claim, payload.get("params"))
        if shortfall is None:
            _store(run_dir, ledger_path, candidate, payload)
            return

        ledger.mark_rejected(ledger_path, candidate.claim, shortfall)
        decision_log.record(
            run_dir,
            "collect",
            decision_log.EVENT_DISCARDED,
            claim=candidate.claim,
            reason=shortfall,
        )
        rejections += 1


def _rejections_so_far(run_dir: Path) -> int:
    """그 밤이 지금까지 기각한 후보 수를 결정 로그에서 센다."""
    return sum(
        1
        for entry in decision_log.read(run_dir)
        if entry.get("step") == "collect" and entry.get("event") == decision_log.EVENT_DISCARDED
    )


def _ask_about(run_dir: Path, claim: str, ask: AgentCaller) -> dict[str, Any]:
    """후보 하나를 두고 에이전트를 부르고, 무엇을 읽고 얼마를 썼는지 남긴다.

    기록을 «게이트 앞»에서 남긴다. 막혀서 끝나도 그 밤이 무엇을 했고 얼마를 태웠는지는
    남아야 한다 — 없으면 밤 예산을 정할 때 그만큼이 통째로 빠진 값으로 계산된다.

    Raises:
        StepQualityFailed: 검색어가 모자랄 때
    """
    result = ask(build_prompt(claim))
    payload = invoke.parse_json_answer(result, what="수집")

    queries = payload_helpers.as_strings(payload.get("queries"))

    decision_log.record(run_dir, "collect", decision_log.EVENT_READ, queries=queries, query_count=len(queries))
    decision_log.record_cost(run_dir, "collect", result)

    shortfall = query_gate.shortfall_reason(queries)
    if shortfall is not None:
        decision_log.record(run_dir, "collect", decision_log.EVENT_FAILED, gate="queries", reason=shortfall)
        raise StepQualityFailed(f"수집 검색어 부족 — {shortfall}")

    return payload


def _store(run_dir: Path, ledger_path: Path, candidate: ledger.Entry, payload: dict[str, Any]) -> None:
    """찬성 근거를 파일로 남기고 그 후보를 그 밤의 후보로 박는다."""
    identifier = candidate.identifier
    if identifier is None:
        # 예전에 담긴 후보에는 식별자가 없다. 그 후보를 두고 에이전트를 어차피 불렀으므로
        # 여기서 박으면 «별도 호출이 들지 않는다» — 이것이 이미 쌓인 후보도
        # 짧은 폴더명을 얻는 경로다
        supplied = str(payload.get("identifier", "")).strip()
        if supplied:
            identifier = ledger.assign_identifier(ledger_path, candidate.claim, supplied) or None

    evidence = payload_helpers.as_list(payload.get("evidence"))
    unverified = payload_helpers.as_list(payload.get("unverified"))
    params = payload_helpers.as_list(payload.get("params"))
    queries = payload_helpers.as_strings(payload.get("queries"))

    # [중요] 산출물은 «후보별 폴더»에 넣는다. 실행 폴더 바로 아래에 고정 이름으로 쓰면
    # 한 밤이 후보 둘을 파는 순간 뒤엣것이 앞엣것을 덮어쓴다.
    # 경로를 만드는 곳은 `naming` 하나여야 한다는 계층 계약이 여기서 지켜진다
    output_dir = run_dir / naming.folder_name(candidate.claim, identifier)

    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남는다
    with atomic_write(output_dir / PRO_EVIDENCE_FILENAME) as file:
        json.dump(
            {"claim": candidate.claim, "params": params, "evidence": evidence, "unverified": unverified},
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
        identifier=identifier,
        evidence_count=len(evidence),
        unverified_count=len(unverified),
        # 「찬성 근거 0건」은 고장이 아니라 **실체 없음이라는 정상 결과**다.
        # 그 판정을 나중에 기계가 골라낼 수 있게 이름을 붙여 둔다
        verdict="실체 없음" if not evidence else "근거 있음",
    )

    # 파일을 쓴 «뒤에» 박는다. 순서가 반대면 산출물 없이 후보만 박혀,
    # 뒤따르는 반증·계보가 있지도 않은 근거 위에서 돈다
    state.pin_candidate(run_dir, state.Candidate(claim=candidate.claim, identifier=identifier))

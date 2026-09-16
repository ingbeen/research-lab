"""메커니즘 단계 — 근거 문서의 3번 칸(왜 우위가 있을 수 있나)과 9번 칸(왜 사라졌을 수 있나).

**둘은 한 쌍이다** — 「우위가 있었나」와 「그 우위가 아직 살아 있나」이기 때문이다.
나누면 둘 다 얕아지고, 특히 9번 칸은 통째로 빠지기 쉽다: 찬성 근거를 모으다 보면
「지금도 되나」를 안 묻게 된다.

[중요] **찬성과 반증이 모은 출처를 프롬프트에 싣는다.** 9번 칸의 답은 대개 반증 세션이
이미 찾아 둔 것이라(「발표 후 소멸했다」), 안 실어 보내면 같은 것을 다시 검색하거나
**없는 근거를 지어낸다.**

[중요] **이 단계는 「판 것」 표시를 하지 않는다.** 표시는 회차의 마지막 단계의 일이다.
여기서 표시하면 그 뒤 측정 설계와 판정이 실패할 때 **후보가 그 칸들 없이 「판 것」으로 남아
영영 다시 안 파진다.** 그래서 원장도 받지 않는다 — 안 쓰는 인자를 두면 「메커니즘도 원장을
고친다」로 읽힌다.

[중요] **검색어 게이트를 걸지 않는다.** 앞 단계가 이미 소멸 근거를 모아 왔으면 새 검색이
필요 없고, 그때 하한을 요구하면 **억지 검색을 시키게 된다.** 계보·실현가능성에 안 건 것과
같은 이유다. 던졌으면 기록만 한다.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import (
    MECHANISM_FILENAME,
    PRO_EVIDENCE_FILENAME,
    REBUTTAL_FILENAME,
)
from research_lab.gate import mechanism as mechanism_gate
from research_lab.runner import decision_log, naming, outputs, prose_check, state, url_check
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]

STEP_NAME: Final = "mechanism"


def _slots_of(fields: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    """게이트가 보는 자리 목록을 JSON Schema 의 객체로 옮긴다.

    [중요] 스키마를 손으로 다시 적지 않는다. 게이트의 목록과 두 벌이 되면 한쪽만 고쳐질 때
    **스키마는 요구하지 않는 자리를 게이트가 막거나 그 반대가 되고**, 그 어긋남은
    회차가 한 번 막히기 전까지 드러나지 않는다.
    """
    names = [key for key, _ in fields]
    return {"type": "object", "properties": {name: {"type": "string"} for name in names}, "required": names}


# 응답 모양을 CLI 가 강제한다.
#
# [실측 2026-09-14] 인라인 JSON 이고 인증보다 «먼저» 검증되며, 구독 인증에서 동작한다.
# 잘못 적으면 조용히 무시되는 것이 아니라 즉시 오류가 난다.
#
# [주의] `additionalProperties` 를 막지 않는다. 에이전트가 칸을 하나 더 얹었다고 그 회차가
# 죽을 이유가 없고, 남는 칸은 러너가 어차피 안 읽는다 — **모를 때 안전한 쪽**이다
JSON_SCHEMA: Final = json.dumps(
    {
        "type": "object",
        "properties": {
            mechanism_gate.KEY_EDGE: _slots_of(mechanism_gate.EDGE_FIELDS),
            mechanism_gate.KEY_DECAY: _slots_of(mechanism_gate.DECAY_FIELDS),
            "queries": {"type": "array", "items": {"type": "string"}},
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
                },
            },
            "unverified": {"type": "array", "items": {"type": "string"}},
        },
        "required": [mechanism_gate.KEY_EDGE, mechanism_gate.KEY_DECAY],
    },
    ensure_ascii=False,
)

PROMPT: Final = """`.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 왜 우위가 있을 수 있나 · 왜 사라졌을 수 있나

아래 주장을 두고 **두 가지**를 묻습니다.

> {claim}

① **우위가 있다면 그것이 어디서 나오나** ② **그 우위가 지금도 남아 있나**

**이 후보를 기각하거나 채택하지 마세요.** 판정은 다른 자리의 일입니다.

## 이미 모은 출처 — 먼저 여기를 보세요

찬성 근거와 반증을 앞 단계가 이미 모았습니다. **특히 반증 쪽에 「이미 사라졌다」는 답이
들어 있는 경우가 많습니다.** 여기 있는 것을 새로 검색하면 낭비입니다.

{sources}

## 무엇을 묻나

**3번 칸 — 왜 우위가 있을 수 있나 (`edge`)**

- `risk_premium`: 위험을 더 져서 받는 보상인가
- `behavioral`: 사람이 반복해 저지르는 실수(행동 편향)에서 나오나
- `structural`: 제도 · 규칙 · 시장 미시구조가 만든 것인가

**9번 칸 — 왜 사라졌을 수 있나 (`decay`)**

- `post_publication`: 알려져서 선반영됐나. **찬성 근거로 쓰인 논문 자체가 소멸의 원인일 수 있습니다**
- `regulatory`: 세제 · 규칙이 전제를 바꿨나
- `market_structure`: 참여자나 거래 방식이 달라졌나

**해당하지 않는 자리는 「해당 없음」과 그 이유를 적습니다.** 빈 채로 두는 것과 다릅니다 —
「셋 중 어느 것도 아니다」는 그 자체로 읽는 사람에게 신호입니다.

**[중요] 이 답은 저장소 밖으로 나갑니다.** 다른 문서를 가리키지 말고 **그 자리에 풀어 적으세요.**

**[중요] 웹을 새로 뒤졌다면 «실제로 연 URL 만» `sources` 에 적습니다.** 링크를 못 찾았으면
URL 을 비우고 `unverified` 에 적으세요 — 지어낸 URL 은 그 회차를 통째로 버립니다.

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"edge": {{"risk_premium": "", "behavioral": "", "structural": ""}}, "decay": {{"post_publication": "", "regulatory": "", "market_structure": ""}}, "queries": ["새로 던진 검색어가 있다면 전부"], "sources": [{{"title": "", "url": ""}}], "unverified": ["확인하지 못한 것"]}}
"""


def build_prompt(claim: str, sources: list[Any]) -> str:
    """메커니즘 지시문을 만든다.

    Args:
        claim: 그 회차의 한 줄 주장
        sources: 찬성과 반증이 모은 출처

    Returns:
        에이전트에게 줄 지시문
    """
    listed = "\n".join(_describe(source) for source in sources) if sources else "(앞 단계가 모은 출처가 없습니다)"
    return PROMPT.format(claim=claim, sources=listed)


def run(run_dir: Path, ask: AgentCaller) -> None:
    """3·9번 칸을 파일로 남긴다.

    Args:
        run_dir: 그 회차의 실행 폴더
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        RuntimeError: 그 회차의 후보가 상태에 없을 때 — 러너가 건너뛰었어야 하는 자리다
        StepFailed: 응답이 약속한 모양이 아닐 때
        StepQualityFailed: 칸의 자리가 비었거나 출처가 실재하지 않을 때
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate = state.pinned_candidate(run_dir)
    if candidate is None:
        raise RuntimeError(f"내부 불변조건 위반: 그 회차의 후보가 상태에 없습니다 — {run_dir}")

    output_dir = run_dir / naming.folder_name(candidate.claim, candidate.identifier)
    sources = _gathered_sources(output_dir)

    result = ask(build_prompt(candidate.claim, sources))
    payload = invoke.parse_json_answer(result, what="메커니즘")

    queries = payload_helpers.as_strings(payload.get("queries"))

    # 무엇을 놓고 판단했고 얼마를 썼는지는 «게이트 앞»에서 남긴다.
    # 막혀서 끝나도 그 회차가 무엇을 했고 얼마를 태웠는지는 기록에 남아야 한다
    decision_log.record(run_dir, STEP_NAME, decision_log.EVENT_READ, source_count=len(sources), queries=queries)
    decision_log.record_cost(run_dir, STEP_NAME, result)

    shortfall = mechanism_gate.shortfall_reason(payload)
    if shortfall is not None:
        decision_log.record(run_dir, STEP_NAME, decision_log.EVENT_FAILED, gate=STEP_NAME, reason=shortfall)
        raise StepQualityFailed(f"메커니즘 칸 미달 — {shortfall}")

    # [중요] 값싼 게이트가 «전부 통과한 뒤»에 부른다. 이 검사만 네트워크를 쓰므로,
    # 어차피 막힐 단계에서 URL 을 찌르는 것은 순 낭비다
    prose_check.assert_self_contained(run_dir, STEP_NAME, payload, what="메커니즘 산출물")
    url_check.assert_sources_exist(run_dir, STEP_NAME, payload.get("sources"), what="메커니즘 출처")

    _store(run_dir, output_dir, candidate, payload)


def _store(run_dir: Path, output_dir: Path, candidate: state.Candidate, payload: dict[str, Any]) -> None:
    """3·9번 칸을 파일로 남기고 무엇을 판단했는지 기록한다."""
    edge: Any = payload[mechanism_gate.KEY_EDGE]
    decay: Any = payload[mechanism_gate.KEY_DECAY]

    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남는다
    with atomic_write(output_dir / MECHANISM_FILENAME) as file:
        json.dump(
            {
                "claim": candidate.claim,
                "edge": dict(edge),
                "decay": dict(decay),
                "sources": payload_helpers.as_list(payload.get("sources")),
                "unverified": payload_helpers.as_list(payload.get("unverified")),
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    decision_log.record(
        run_dir,
        STEP_NAME,
        decision_log.EVENT_JUDGED,
        claim=candidate.claim,
        unverified_count=len(payload_helpers.as_list(payload.get("unverified"))),
    )


def _gathered_sources(output_dir: Path) -> list[Any]:
    """찬성과 반증이 남긴 출처를 한 목록으로 모은다.

    어느 쪽에서 왔는지를 함께 담는다 — 9번 칸을 채우는 쪽이 「반증에 이미 있었다」를
    바로 볼 수 있어야 하기 때문이다.

    [주의] 앞 단계의 파일이 없거나 비어도 빈 목록으로 넘어간다. 찬성 0건·반증 0건은
    **정상 결과**이고, 그때 이 단계를 세우면 정상 결과가 실패가 된다.
    """
    collected: list[Any] = []
    for filename, side, key in (
        (PRO_EVIDENCE_FILENAME, "찬성", "evidence"),
        (REBUTTAL_FILENAME, "반증", "rebuttals"),
    ):
        loaded = outputs.read(output_dir, filename)
        if loaded is None:
            continue
        for item in payload_helpers.as_list(loaded.get(key)):
            if isinstance(item, dict):
                collected.append({**item, "side": side})
    return collected


def _describe(source: Any) -> str:
    """출처 한 건을 프롬프트에 실을 한 줄로 만든다."""
    if not isinstance(source, dict):
        return f"- {source}"
    title = payload_helpers.as_text(source.get("title")) or "(제목 없음)"
    published = payload_helpers.as_text(source.get("published")) or "unknown"
    says = payload_helpers.as_text(source.get("says"))
    line = f"- [{source.get('side', '?')}] {title} · {published} · {source.get('url', '')}"
    return f"{line}\n  {says}" if says else line

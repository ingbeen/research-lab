"""계보 단계 — 모은 출처 중 «누가 원본이고 누가 베꼈나»를 가른다.

**웹에서 합의는 근거가 아니다.** 여러 곳이 같은 말을 하는 가장 흔한 이유는 서로 베꼈기
때문이다. 이 단계의 산출물은 「세 곳에서 확인」이 아니라 **「한 원본 · 복제 두 곳」**이고,
거기서 나온 **복제를 뺀 진짜 소스 수**가 dossier 의 출처 계보 칸이 된다.

[중요] 찬성과 반증의 출처를 **함께** 받는다. 한쪽만 주면 반증 쪽 출처가 원본인 경우를
통째로 놓친다.

[중요] **이 단계는 후보를 「판 것」으로 표시하지 않는다.** 표시는 회차의 «마지막» 단계의
일이고 그 자리는 실현가능성이다. 여기서 표시하면 그 뒤 4·5번 칸이 실패할 때
**후보가 그 칸들 없이 「판 것」으로 남아 영영 다시 안 파진다** — 수집이 표시하던 때와
똑같은 고장이다.

[중요] **그래서 이 단계는 원장을 받지 않는다.** 안 쓰는 인자를 두면 「계보도 원장을
고친다」로 읽힌다 — 반증이 같은 이유로 안 받는다.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import (
    LINEAGE_FILENAME,
    PRO_EVIDENCE_FILENAME,
    REBUTTAL_FILENAME,
)
from research_lab.gate import lineage as lineage_gate
from research_lab.runner import decision_log, naming, prose_check, state, url_check
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]

PROMPT: Final = """`.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 출처 계보

아래 주장을 두고 모은 출처들이 **독립된 확인인지 한 원본의 복제인지** 가릅니다.

> {claim}

## 모은 출처 (이 목록 «전부»를 다뤄야 합니다)

{sources}

## 어떻게 가르나

- 같은 문장 · 같은 예시 · **같은 숫자**가 반복되면 복제입니다. **그 덩어리의 소스 수는 1 입니다**
- 발행일이 며칠 안에 몰려 있으면 같은 원본을 받아쓴 것입니다
- 서로를 인용하는 소스들은 **한 덩어리로 셉니다**
- 판단이 서지 않으면 **본문을 다시 열어** 숫자와 예시를 맞춰 보세요

**[중요] 위 목록의 URL 은 하나도 빠짐없이** 어느 덩어리의 원본이나 복제 자리에 놓여야 합니다.
빠뜨리면 **독립 소스 수가 통째로 틀리고, 그 고장은 에러를 내지 않습니다.**

독립된 출처는 **자기 혼자인 덩어리**로 적으면 됩니다 (복제가 빈 목록).
독립 소스 수는 따로 적지 않습니다 — 자기 혼자인 덩어리가 독립 1 이라,
덩어리를 빠짐없이 나누면 그 수가 곧 덩어리 수입니다.

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"claim": "받은 한 줄 주장 그대로", "groups": [{{"origin": {{"title": "", "url": "", "published": "YYYY-MM-DD 또는 unknown"}}, "copies": [{{"title": "", "url": ""}}], "why": "왜 복제로 봤나 — 같은 숫자·같은 예시·발행일 쏠림"}}], "unverified": ["확인하지 못한 것"]}}
"""


def build_prompt(claim: str, sources: list[Any]) -> str:
    """계보 지시문을 만든다.

    Args:
        claim: 그 회차의 한 줄 주장
        sources: 찬성과 반증이 모은 출처 전부

    Returns:
        에이전트에게 줄 지시문
    """
    listed = "\n".join(_describe(source) for source in sources) if sources else "(모은 출처가 없습니다)"
    return PROMPT.format(claim=claim, sources=listed)


def run(run_dir: Path, ask: AgentCaller) -> None:
    """찬성·반증의 출처로 계보표를 만든다.

    Args:
        run_dir: 그 회차의 실행 폴더
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        RuntimeError: 그 회차의 후보가 상태에 없을 때 — 러너가 건너뛰었어야 하는 자리다
        StepFailed: 응답이 약속한 모양이 아닐 때
        StepQualityFailed: 모았던 출처를 빠뜨렸을 때
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate = state.pinned_candidate(run_dir)
    if candidate is None:
        raise RuntimeError(f"내부 불변조건 위반: 그 회차의 후보가 상태에 없습니다 — {run_dir}")

    output_dir = run_dir / naming.folder_name(candidate.claim, candidate.identifier)
    sources = _collected_sources(output_dir)

    result = ask(build_prompt(candidate.claim, sources))
    payload = invoke.parse_json_answer(result, what="계보")

    # 무엇을 놓고 판단했고 얼마를 썼는지는 «게이트 앞»에서 남긴다.
    # 막혀서 끝나도 그 회차가 무엇을 했고 얼마를 태웠는지는 기록에 남아야 한다
    decision_log.record(run_dir, "lineage", decision_log.EVENT_READ, source_count=len(sources))
    decision_log.record_cost(run_dir, "lineage", result)

    shortfall = lineage_gate.shortfall_reason(payload, source_urls=[_url_of(source) for source in sources])
    if shortfall is not None:
        decision_log.record(run_dir, "lineage", decision_log.EVENT_FAILED, gate="lineage", reason=shortfall)
        raise StepQualityFailed(f"계보 규율 미달 — {shortfall}")

    groups = payload_helpers.as_list(payload.get("groups"))
    # [중요] 에이전트에게 적게 하지 않고 «센다». 정의상 자기 혼자인 덩어리가 독립 1 이라
    # 덩어리 수와 같은데, 적게 하면 틀려도 에러가 없고 그 숫자가 6번 칸 맨 앞에 실린다.
    # 주소가 하나도 없는 덩어리는 세지 않는다 — 계보 게이트도 그런 덩어리를 «다룬 것»으로 보지
    # 않는다. 모은 출처가 없을 때 지시문의 JSON 틀을 그대로 되돌려 쓰면 그런 덩어리가 생긴다
    independent = sum(1 for group in groups if any(_url_of(source) for source in _cited_sources([group])))

    # [중요] 계보가 낸 주소도 «찔러 본다». 근거 문서의 머리말이 「아래에 적힌 URL 은 실제로
    # 호출해 살아 있는지 확인했습니다」라고 보증하는데, 이 단계만 그 검사를 안 지나면
    # 6번 칸의 주소에 한해 그 보증이 거짓이 된다.
    #
    # [중요] **계보는 앞 단계가 안 낸 주소를 새로 들 수 있다** — 「이건 저 글을 베낀 것」이라며
    # 복제를 하나 더 적는 자리가 그것이고, 거기가 없는 출처를 지어낼 수 있는 입구다.
    # 앞 단계에서 이미 찔렀다는 이유로 생략하면 **새로 들어온 주소만 검사를 비켜 간다.**
    #
    # 자리가 «게이트 뒤 · 저장 앞»인 것은 수집과 같다 — 앞에 두면 어차피 막힐 단계에서
    # 남의 서버를 두드리고, 뒤에 두면 죽은 URL 이 든 파일이 이미 쓰인 뒤다
    prose_check.assert_self_contained(run_dir, "lineage", payload, what="계보 산출물")
    url_check.assert_sources_exist(run_dir, "lineage", _cited_sources(groups), what="계보 출처")

    with atomic_write(output_dir / LINEAGE_FILENAME) as file:
        json.dump(
            {
                "claim": candidate.claim,
                "groups": groups,
                "independent_source_count": independent,
                "unverified": payload_helpers.as_list(payload.get("unverified")),
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    decision_log.record(
        run_dir,
        "lineage",
        decision_log.EVENT_JUDGED,
        claim=candidate.claim,
        collected_sources=len(sources),
        independent_source_count=independent,
    )


def _cited_sources(groups: list[Any]) -> list[Any]:
    """계보표가 든 출처를 «원본과 복제 가리지 않고» 한 목록으로 편다.

    [중요] 복제 쪽을 빼지 않는다. 「저 글을 베꼈다」는 주장의 근거가 그 복제 주소이고,
    그것을 안 찌르면 계보표는 **검증되지 않은 주장을 담은 표**가 된다.
    """
    cited: list[Any] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        cited.append(group.get("origin"))
        cited.extend(payload_helpers.as_list(group.get("copies")))
    return cited


def _collected_sources(output_dir: Path) -> list[Any]:
    """찬성과 반증이 남긴 출처를 한 목록으로 모은다.

    어느 쪽에서 왔는지를 함께 담는다 — 계보를 읽는 사람이 「반증 쪽이 원본이었다」를
    바로 볼 수 있어야 하기 때문이다.
    """
    collected: list[Any] = []
    for filename, side, key in (
        (PRO_EVIDENCE_FILENAME, "찬성", "evidence"),
        (REBUTTAL_FILENAME, "반증", "rebuttals"),
    ):
        for source in _read_sources(output_dir / filename, key):
            collected.append({**source, "side": side})
    return collected


def _read_sources(path: Path, key: str) -> list[dict[str, Any]]:
    """산출물 파일에서 URL 이 있는 출처만 읽는다.

    [주의] 읽기에 실패하면 빈 목록을 돌린다. 앞 단계가 「실체 없음」으로 끝나 파일이
    비거나 없을 수 있고, 그것은 정상 결과다 — 여기서 터뜨리면 정상 결과가 실패가 된다.
    """
    if not path.is_file():
        return []

    try:
        loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # [중요] 인코딩 오류도 함께 잡는다. `UnicodeDecodeError` 는 `OSError` 가 아니라
        # `ValueError` 라, 빠뜨리면 위 「읽기에 실패하면 빈 목록」이라는 계약이 그 갈래에서만
        # 깨진다 — 한쪽 파일이 깨졌을 뿐인데 **계보 단계가 통째로 죽는다**
        return []

    if not isinstance(loaded, dict):
        return []

    return [
        item
        for item in payload_helpers.as_list(loaded.get(key))
        if isinstance(item, dict) and payload_helpers.as_text(item.get("url"))
    ]


def _url_of(source: Any) -> str:
    """출처에서 URL 을 꺼낸다."""
    return payload_helpers.as_text(source.get("url")) if isinstance(source, dict) else ""


def _describe(source: Any) -> str:
    """출처 한 건을 프롬프트에 실을 한 줄로 만든다."""
    if not isinstance(source, dict):
        return f"- {source}"
    title = payload_helpers.as_text(source.get("title")) or "(제목 없음)"
    published = payload_helpers.as_text(source.get("published")) or "unknown"
    return f"- [{source.get('side', '?')}] {title} · {published} · {_url_of(source)}"

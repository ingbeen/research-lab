"""반증 단계 — 그 회차의 후보를 «깨려고» 든다.

**한 줄 주장만 받는다.** 수집이 무엇을 찾았는지 모르고, 알 필요도 없다.
같은 세션에서 찬성 근거를 잔뜩 모은 다음 「이제 반증을 찾아라」라고 하면 자기가 방금
지지한 것을 스스로 무너뜨리라는 요구가 되고, **사람도 잘 못 한다.**
이 세션의 유일한 임무는 「이 주장을 깨라」이고 **많이 찾을수록 잘한 것이다.**

[주의] 세션이 갈리는 것은 구조가 보장하지만 **파일을 일부러 찾아 읽는 것까지는 못 막는다.**
스킬을 읽히려면 `Read` 도구가 필요해 도구를 뺄 수 없고, 실행 디렉터리가 저장소라 그 회차의
폴더가 보인다. 그래서 판정 대신 **계측을 심는다** — 찬성 근거와 URL 이 얼마나 겹쳤나를
로그에 적되 **그것으로 막지 않는다.** 겹치는 것 자체는 정상일 수도 있다(같은 논문을
찬성·반증이 함께 인용한다).
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import (
    PRO_EVIDENCE_FILENAME,
    REBUTTAL_FILENAME,
    REBUTTAL_QUERIES_FILENAME,
)
from research_lab.gate import queries as query_gate
from research_lab.gate import rebuttal as rebuttal_gate
from research_lab.runner import decision_log, naming, state, url_check
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]

PROMPT: Final = """이 저장소의 `.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 반증

아래 주장을 **깨려고** 하세요. 이 세션의 임무는 그것 하나이고, **많이 찾을수록 잘한 것입니다.**

> {claim}

- 검색어를 **반대편으로** 갈아 끼웁니다 — 「{claim_head} 비판」 · 「... debunked」 ·
  「... doesn't work」 · 「... 실패」 · 「... 소멸」처럼 **찾는 말 자체를 바꿔야** 나옵니다
- 한국어와 영어를 모두 돌리고, **던진 검색어를 하나도 빼지 않고** 적습니다
- 반증마다 **URL · 발행일 · 1차인지 2차인지**를 함께 적습니다
- **실제로 연 URL 만** 적습니다. 기억으로 URL 을 만들어 내지 마세요 —
  링크를 못 찾았으면 URL 을 비우고 `unverified` 에 적습니다
- **찬성 근거는 찾지 마세요.** 다른 단계가 이미 했습니다
- 비용·세금·슬리피지는 적지 마세요

## 「없음」도 정상 결과입니다

반증을 못 찾았으면 `rebuttals` 를 빈 목록으로 두고, `not_found_reason` 에
**무엇을 어떻게 찾았는데 왜 없었는지**를 적으세요.
**억지로 채우지 마세요** — 없는 출처를 지어내는 것이 이 파이프라인에서 가장 나쁜 고장입니다.

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"claim": "받은 한 줄 주장 그대로", "queries": ["던진 검색어 전부"], "rebuttals": [{{"title": "", "url": "", "published": "YYYY-MM-DD 또는 unknown", "kind": "primary|secondary", "says": "이 출처가 주장을 어떻게 반박하나"}}], "not_found_reason": "반증이 0건일 때만 적습니다", "unverified": ["확인하지 못한 것"]}}
"""

# 프롬프트의 검색어 예시에 넣을 주장 앞부분의 길이.
# 한 줄 주장 전체를 검색어로 삼으라는 뜻이 아니므로 짧게 자른다
CLAIM_HEAD_LENGTH: Final = 20


def build_prompt(claim: str) -> str:
    """반증 지시문을 만든다.

    [중요] **한 줄 주장 말고는 아무것도 싣지 않는다.** 찬성 근거를 실으면 맥락을 끊으려고
    세션을 나눈 의미가 사라진다 — 손으로 그 맥락을 다시 실어 주는 셈이 된다.

    Args:
        claim: 깨야 할 한 줄 주장

    Returns:
        에이전트에게 줄 지시문
    """
    return PROMPT.format(claim=claim, claim_head=claim[:CLAIM_HEAD_LENGTH])


def run(run_dir: Path, ask: AgentCaller) -> None:
    """그 회차의 후보를 두고 반증을 모아 파일로 남긴다.

    Args:
        run_dir: 그 회차의 실행 폴더
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        RuntimeError: 그 회차의 후보가 상태에 없을 때 — 러너가 건너뛰었어야 하는 자리다
        StepFailed: 응답이 약속한 모양이 아닐 때
        StepQualityFailed: 검색어나 반증 규율을 못 지켰을 때
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate = state.pinned_candidate(run_dir)
    if candidate is None:
        raise RuntimeError(f"내부 불변조건 위반: 그 회차의 후보가 상태에 없습니다 — {run_dir}")

    result = ask(build_prompt(candidate.claim))
    payload = invoke.parse_json_answer(result, what="반증")

    queries = payload_helpers.as_strings(payload.get("queries"))

    # 무엇을 읽었고 얼마를 썼는지는 «게이트 앞»에서 남긴다.
    # 막혀서 끝나도 그 회차가 무엇을 했고 얼마를 태웠는지는 기록에 남아야 한다
    decision_log.record(run_dir, "rebut", decision_log.EVENT_READ, queries=queries, query_count=len(queries))
    decision_log.record_cost(run_dir, "rebut", result)

    for gate_name, shortfall in (
        ("queries", query_gate.shortfall_reason(queries)),
        ("rebuttal", rebuttal_gate.shortfall_reason(payload)),
    ):
        if shortfall is not None:
            decision_log.record(run_dir, "rebut", decision_log.EVENT_FAILED, gate=gate_name, reason=shortfall)
            raise StepQualityFailed(f"반증 규율 미달 — {shortfall}")

    # [중요] 값싼 게이트가 «전부 통과한 뒤»에 부른다. 이 검사만 네트워크를 쓰므로,
    # 어차피 막힐 단계에서 URL 을 찌르는 것은 순 낭비다
    url_check.assert_sources_exist(run_dir, "rebut", payload.get("rebuttals"), what="반증 출처")

    output_dir = run_dir / naming.folder_name(candidate.claim, candidate.identifier)
    rebuttals = payload_helpers.as_list(payload.get("rebuttals"))

    with atomic_write(output_dir / REBUTTAL_FILENAME) as file:
        json.dump(
            {
                "claim": candidate.claim,
                "rebuttals": rebuttals,
                "not_found_reason": payload_helpers.as_text(payload.get("not_found_reason")),
                "unverified": payload_helpers.as_list(payload.get("unverified")),
            },
            file,
            ensure_ascii=False,
            indent=2,
        )
    # 검색어도 «파일»로 남긴다. 결정 로그에만 두면 그 회차의 원자료 폴더에는 남지만
    # **후보 폴더에는 안 남아**, 나중에 그 후보의 산출물만 모아 볼 때
    # 「반대편으로 갈아 끼웠나」를 확인할 길이 사라진다
    with atomic_write(output_dir / REBUTTAL_QUERIES_FILENAME) as file:
        json.dump({"claim": candidate.claim, "queries": queries}, file, ensure_ascii=False, indent=2)

    decision_log.record(
        run_dir,
        "rebut",
        decision_log.EVENT_JUDGED,
        claim=candidate.claim,
        rebuttal_count=len(rebuttals),
        # [중요] 이 값은 **계측이지 판정이 아니다.** 이 단계가 찬성 근거 파일을 몰래 읽는 것을
        # 기계로 막을 수 없어 대신 재서 남긴다. 높으면 의심 신호이고, 사람이 본다
        overlap_with_pro_evidence=_overlap_with_pro_evidence(output_dir, rebuttals),
        # 「반증 0건」은 고장이 아니라 **실체 없음이라는 정상 결과**다 —
        # 수집의 「찬성 근거 0건」과 같은 자리다
        verdict="반증 없음" if not rebuttals else "반증 있음",
    )


def _overlap_with_pro_evidence(output_dir: Path, rebuttals: list[Any]) -> int:
    """반증 URL 중 찬성 근거에도 있던 것의 수를 센다.

    [중요] 읽기에 실패하면 0 을 돌린다. 이 값은 «계측»이라, 못 재는 것 때문에 그 회차가
    멈추면 안 된다 — 판정을 못 하는 것과 실패로 판정하는 것은 다르다.
    """
    path = output_dir / PRO_EVIDENCE_FILENAME
    if not path.is_file():
        return 0

    try:
        loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # [중요] 인코딩 오류도 함께 잡는다. `UnicodeDecodeError` 는 `OSError` 가 아니라
        # `ValueError` 라, 빠뜨리면 위 「못 재면 0」이라는 계약이 깨진다. 터지는 자리가
        # 나쁘다 — 계측은 **에이전트를 이미 부른 뒤**라 그 회차는 돈을 다 쓰고 산출물은
        # 못 남기고, 파일이 그대로 남아 **다음 회차도 같은 자리에서 죽는다**
        return 0

    if not isinstance(loaded, dict):
        return 0

    pro_urls = payload_helpers.urls_in(loaded.get("evidence"))
    return len(pro_urls & payload_helpers.urls_in(rebuttals))

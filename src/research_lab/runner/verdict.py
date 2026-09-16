"""판정 단계 — 근거 문서의 2번 칸, 그리고 **문서 한 장을 만들어 내는 자리**.

**회차의 마지막 단계다.** 그래서 「판 것」 표시가 여기로 왔다. 앞 단계가 표시하면
그 뒤 이 단계가 실패할 때 **후보가 판정 없이 「판 것」으로 남아 영영 다시 안 파진다** —
수집이 표시하던 때, 계보가 표시하던 때, 실현가능성이 표시하던 때와 글자 하나 다르지 않은
고장이고, 계층 계약 §4 가 「단계를 뒤에 더할 때마다 표시가 함께 옮겨간다」를 규칙으로
박아 둔 이유가 이것이다.

[중요] **판정은 맨 마지막에 쓴다.** 측정 설계와 한 호출에 담으면 에이전트가 판정을 먼저
정하고 측정 설계를 거기에 맞출 수 있다. 이 저장소는 프롬프트 지시가 형식적으로만 지켜진
것을 여러 번 확인했으므로, 순서를 지시가 아니라 **단계 경계로** 보장한다.

[중요] **앞 단계의 산출물을 통째로 싣는다.** 요약해서 넘기면 요약하는 쪽이 이미 판단을
한 것이 된다 — 무엇을 남기고 무엇을 버릴지가 곧 판정이다.

[중요] **파일 세 가지를 순서대로 만든다** — 판정 파일 → 근거 문서 → 「판 것」 표시.
순서가 뒤집히면 산출물 없이 후보만 닫히고, **나중에는 완주한 회차처럼 보인다.**
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import DOSSIER_DIR, VERDICT_FILENAME
from research_lab.gate import urls as url_gate
from research_lab.gate import verdict as verdict_gate
from research_lab.runner import decision_log, dossier, ledger, naming, prose_check, state, url_check
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]

STEP_NAME: Final = "verdict"

# 응답 모양을 CLI 가 강제한다.
#
# [중요] 판정값을 **`enum` 으로 묶는다.** 이 단계에서 가장 흔할 어긋남이 「조건부 채택」
# 같은 제3의 값인데, 그것이 구조적으로 불가능해진다 — 게이트가 막던 것을 한 겹 앞에서
# 막는 셈이라 **막힌 회차의 비용 자체가 안 생긴다.** 값 목록은 게이트의 것을 그대로 쓴다
JSON_SCHEMA: Final = json.dumps(
    {
        "type": "object",
        "properties": {
            verdict_gate.KEY_VERDICT: {"type": "string", "enum": list(verdict_gate.VERDICT_VALUES)},
            **{key: {"type": "string"} for key, _ in verdict_gate.TEXT_FIELDS},
            # [중요] 계측용 자리도 스키마에 «넣어야» 한다. 안 넣으면 응답에 그 열쇠가
            # 아예 안 실려 **계측이 언제나 빈 목록을 기록하고**, 「안 뒤졌다」와
            # 「잴 수 없었다」가 구별되지 않는다. 이 단계는 「새로 조사하지 말라」고
            # 지시받으므로, 이 값은 **그 지시가 지켜졌는지를 보는 자리**다
            "queries": {"type": "array", "items": {"type": "string"}},
            "unverified_extra": {"type": "array", "items": {"type": "string"}},
        },
        "required": [verdict_gate.KEY_VERDICT, *(key for key, _ in verdict_gate.TEXT_FIELDS)],
    },
    ensure_ascii=False,
)

PROMPT: Final = """이 저장소의 `.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 판정

아래 주장을 **잴 가치가 있는지** 판정합니다. 이 회차가 모은 것이 전부 아래에 있습니다.

> {claim}

**새로 조사하지 마세요.** 이 단계는 모은 것을 읽고 판정하는 자리입니다.

## 이 회차가 모은 것

{gathered}

## 무엇을 내나

**`verdict`**: **{promised}** 중 하나. 다른 말로 적지 마세요.

- **잴 가치 있음** — 재면 답이 나오는 질문이다
- **보류** — 잴 수는 있으나 그 답으로 물으려던 질문이 막힌다 (표본이 모자라는 등)
- **기각** — 재도 답이 안 나온다

**회차마다 「잴 가치 있음」이 나오면 그게 고장입니다.** 이 일의 가치는 찾는 것보다
**가짜를 그 전에 걸러내는 것**입니다. 「기각」과 「보류」도 좋은 결과입니다.

**`reason`**: 왜 그렇게 판정했나. 위에 있는 것을 근거로 적습니다.

**[중요] `criteria` — 적용한 기준 «자체»를 적습니다.**

이 문서는 다른 문서를 한 장도 열 수 없는 곳에서 읽힙니다. 그래서 규칙 이름이나 번호를
적으면 **받는 사람에게는 아무 뜻이 없는 종이**가 됩니다.

| 이렇게 적지 마세요 | 이렇게 적으세요 |
| --- | --- |
| 「표본 규칙에 걸린다」 | 「표본이 20건이라 시기를 둘로 쪼개면 칸당 10건이다. **칸당 10건 미만이면 우연과 구별되지 않으므로** 「어느 시기가 만든 값인가」를 물을 수 없다」 |
| 「집행 기준 미달」 | 「신호가 연 1회라 20년을 재도 20건이다. **표본이 그만큼이면 소수점 차이로 우열을 가릴 수 없다**」 |

**`unverified_extra`**: 판정하면서 **새로** 드러난 미검증만 적습니다.
앞 단계가 이미 적은 것은 다시 옮기지 마세요 — 그쪽은 자동으로 합쳐집니다.

**[중요] 수수료 · 세금 · 슬리피지를 판정 근거로 쓰지 마세요.** 증권사·계좌·이벤트에 따라
자릿수가 달라지고 그 폭이 기대값과 같은 크기라 **어떤 값을 넣느냐가 결론을 만듭니다.**

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"verdict": "{promised_first}", "reason": "", "criteria": "", "queries": ["웹을 뒤졌다면 던진 검색어 전부. 안 뒤졌으면 빈 목록"], "unverified_extra": ["판정하며 새로 드러난 것"]}}
"""

# 프롬프트에 실을 때 산출물마다 붙일 이름. 파일명을 그대로 보이면 에이전트가
# «파일을 찾아 읽으라는 지시»로 읽을 수 있어, 사람이 읽는 이름으로 바꿔 싣는다
SECTION_LABELS: Final = dict(dossier.REQUIRED_OUTPUTS)


def build_prompt(claim: str, loaded: dict[str, dict[str, Any]]) -> str:
    """판정 지시문을 만든다.

    Args:
        claim: 그 회차의 한 줄 주장
        loaded: 앞 단계들의 산출물

    Returns:
        에이전트에게 줄 지시문
    """
    blocks = [
        f"### {SECTION_LABELS.get(filename, filename)}\n\n```json\n{json.dumps(found, ensure_ascii=False, indent=2)}\n```"
        for filename, found in loaded.items()
    ]
    return PROMPT.format(
        claim=claim,
        gathered="\n\n".join(blocks),
        promised=" · ".join(verdict_gate.VERDICT_VALUES),
        promised_first=verdict_gate.VERDICT_VALUES[0],
    )


def run(run_dir: Path, ledger_path: Path, ask: AgentCaller, *, dossier_dir: Path = DOSSIER_DIR) -> None:
    """2번 칸을 파일로 남기고, 근거 문서를 조립하고, 그 후보를 「판 것」으로 표시한다.

    Args:
        run_dir: 그 회차의 실행 폴더
        ledger_path: 원장 경로
        ask: 프롬프트를 받아 에이전트를 부르는 쪽
        dossier_dir: 근거 문서를 쌓을 폴더

    Raises:
        RuntimeError: 그 회차의 후보가 상태에 없을 때 — 러너가 건너뛰었어야 하는 자리다
        StepFailed: 응답이 약속한 모양이 아닐 때
        StepQualityFailed: 판정 칸이 모자라거나 앞 단계의 산출물이 없을 때
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate = state.pinned_candidate(run_dir)
    if candidate is None:
        raise RuntimeError(f"내부 불변조건 위반: 그 회차의 후보가 상태에 없습니다 — {run_dir}")

    output_dir = run_dir / naming.folder_name(candidate.claim, candidate.identifier)

    # [중요] 호출 «전»에 조립 재료를 확인한다. 어차피 조립에서 막힐 회차라면
    # 판정 호출을 사는 것이 순 낭비다 — 값싼 게이트를 먼저 돌리는 것과 같은 이유다
    loaded = dossier.load_required(output_dir)

    result = ask(build_prompt(candidate.claim, loaded))
    payload = invoke.parse_json_answer(result, what="판정")

    # 무엇을 놓고 판단했고 얼마를 썼는지는 «게이트 앞»에서 남긴다
    decision_log.record(
        run_dir,
        STEP_NAME,
        decision_log.EVENT_READ,
        inputs=len(loaded),
        # [중요] 이 값은 «계측이지 판정이 아니다». 판정은 모은 것을 읽고 내리는 일이라
        # 웹 조회가 필요 없는데, 도구는 그대로 주어져 있다. 실제로 뒤지는지를 재서
        # 분포를 보고 나중에 도구 경로를 정한다
        queries=payload_helpers.as_strings(payload.get("queries")),
    )
    decision_log.record_cost(run_dir, STEP_NAME, result)

    shortfall = verdict_gate.shortfall_reason(payload)
    if shortfall is not None:
        decision_log.record(run_dir, STEP_NAME, decision_log.EVENT_FAILED, gate=STEP_NAME, reason=shortfall)
        raise StepQualityFailed(f"판정 칸 미달 — {shortfall}")

    prose_check.assert_self_contained(run_dir, STEP_NAME, payload, what="판정 산출물")
    _store(run_dir, output_dir, candidate, payload, dossier_dir=dossier_dir)

    # [중요] 파일을 쓴 «뒤에» 표시한다. 순서가 반대면 문서 없이 후보만 「판 것」으로 남아
    # 그 후보는 다시 안 파지고, 나중에는 완주한 회차처럼 보인다
    ledger.mark_explored(ledger_path, candidate.claim)


def _unverified_urls(run_dir: Path) -> list[str]:
    """그 회차에서 실재를 «확인하지 못한» 주소를 결정 로그에서 모은다.

    [중요] **회차 전체를 본다.** 수집과 반증이 각자 자기 출처를 찌르므로 기록이 단계별로
    흩어져 있는데, 한 단계만 보면 나머지가 조용히 빠지고 **빠졌다는 사실은 아무 에러도
    내지 않는다** — 문서를 받는 쪽은 그 주소가 확인된 것이라고 읽게 된다.

    [중요] 다만 한 단계 안에서는 **마지막 판정만** 본다. 수집은 출처가 죽으면 다시 묻고
    후보까지 바꾸므로, 한 단계가 판정을 여러 번 남긴다 — 앞의 것들은 **버린 답**이다.
    전부 모으면 그 문서 어디에도 없는 주소가 미검증 칸에 실리고, 받는 쪽은 본문에서
    그 주소를 찾지 못한다. **틀린 목록은 없는 목록보다 나쁘다.**

    [중요] 이 값은 **문서에 덧붙이는 말**이지 판정의 입력이 아니다. 그래서 모양이 어긋나도
    예외를 올리지 않는다 — 여기서 터지면 앞 단계 비용을 다 치른 회차가 마지막에 깨지고
    근거 문서가 안 나온다.

    Args:
        run_dir: 그 회차의 실행 폴더

    Returns:
        확인하지 못한 주소들. 같은 주소가 두 단계에서 나올 수 있으므로 중복은 접되
        **처음 나온 순서를 지킨다**
    """
    # 단계마다 «마지막» 판정으로 덮어쓴다. dict 가 넣은 순서를 지키므로 단계 순서도 남는다
    latest: dict[str, list[str]] = {}
    for entry in decision_log.read(run_dir):
        if entry.get("gate") != url_check.GATE_NAME or entry.get("event") != decision_log.EVENT_READ:
            continue
        step = payload_helpers.as_text(entry.get("step"))
        latest[step] = payload_helpers.as_strings(entry.get(url_gate.KEY_UNKNOWN_URLS))

    seen: set[str] = set()
    return [url for urls in latest.values() for url in urls if not (url in seen or seen.add(url))]


def _store(
    run_dir: Path,
    output_dir: Path,
    candidate: state.Candidate,
    payload: dict[str, Any],
    *,
    dossier_dir: Path,
) -> None:
    """판정을 파일로 남기고 근거 문서를 조립한다."""
    decision = {
        "claim": candidate.claim,
        verdict_gate.KEY_VERDICT: payload_helpers.as_text(payload.get(verdict_gate.KEY_VERDICT)),
        verdict_gate.KEY_REASON: payload.get(verdict_gate.KEY_REASON),
        verdict_gate.KEY_CRITERIA: payload.get(verdict_gate.KEY_CRITERIA),
        "unverified_extra": payload_helpers.as_list(payload.get("unverified_extra")),
    }

    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남는다
    with atomic_write(output_dir / VERDICT_FILENAME) as file:
        json.dump(decision, file, ensure_ascii=False, indent=2)

    written = dossier.assemble(
        run_dir, candidate, decision, dossier_dir=dossier_dir, unverified_urls=_unverified_urls(run_dir)
    )

    decision_log.record(
        run_dir,
        STEP_NAME,
        decision_log.EVENT_JUDGED,
        claim=candidate.claim,
        # 이 값이 로그에 있어야 나중에 「판정이 어떻게 갈렸나」를 셀 수 있다.
        # 회차마다 「잴 가치 있음」이 나온다면 그것이 고장 신호다
        verdict=decision[verdict_gate.KEY_VERDICT],
        dossier=written.name,
    )

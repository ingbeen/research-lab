"""측정 설계 단계 — 근거 문서의 10번 칸.

**이 칸이 이 문서를 「읽을 거리」에서 「의뢰서」로 바꾼다.** 여기까지 채워져야 받는 쪽이
그대로 잴 수 있고, 그래서 「그 프로젝트 규약대로」라고 쓰지 않고 **측정 설계를 전부 적는다.**

[중요] **부수 효과로 사전등록이 따라온다** — 재기 «전»에 측정 방법이 문서에 박히므로
결과를 보고 기준을 고치는 일이 구조적으로 막힌다. 별도 장치 없이 공짜로 얻는 것이라,
이 칸을 얕게 두면 그 효과까지 함께 사라진다.

[중요] **앞 단계의 파라미터 축과 시장·상품을 프롬프트에 싣는다.** 수집이 이미
「무엇을 얼마로 바꿀 수 있는지」를 축으로 냈고 실현가능성이 「살 수 있는 상품」을 냈다.
안 실어 보내면 이 단계가 그것을 **새로 지어내고**, 그 순간 같은 후보의 두 칸이 서로 다른
말을 한다 — 읽는 사람은 어느 쪽이 맞는지 알 길이 없다.

[중요] **이 단계는 「판 것」 표시를 하지 않는다.** 표시는 마지막 단계(판정)의 일이라
원장도 받지 않는다.

[중요] **검색어 게이트를 걸지 않는다.** 이 칸은 앞 산출물을 읽어 설계를 짜는 일이라
웹 조회가 필요 없을 수 있고, 하한을 요구하면 억지 검색을 시키게 된다.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import (
    FEASIBILITY_FILENAME,
    MEASUREMENT_FILENAME,
    PRO_EVIDENCE_FILENAME,
)
from research_lab.gate import measurement as measurement_gate
from research_lab.runner import decision_log, naming, outputs, state
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]

STEP_NAME: Final = "measurement"

# 응답 모양을 CLI 가 강제한다. 자리 목록은 **게이트의 것을 그대로 쓴다** —
# 두 벌이 되면 한쪽만 고쳐질 때 스키마와 게이트가 서로 다른 자리를 요구하게 되고,
# 그 어긋남은 회차가 한 번 막히기 전까지 드러나지 않는다.
#
# [주의] 격자의 `items` 타입을 묶지 않는다. 진입은 날짜 문자열, 보유는 숫자로 오는 것이
# 자연스러운데 한쪽으로 묶으면 멀쩡한 답이 거부된다
JSON_SCHEMA: Final = json.dumps(
    {
        "type": "object",
        "properties": {
            **{key: {"type": "string"} for key, _ in measurement_gate.TEXT_FIELDS},
            **{key: {"type": "array"} for key, _ in measurement_gate.GRID_FIELDS},
            measurement_gate.KEY_SINGLE_VALUE_REASON: {"type": "string"},
            # [중요] 계측용 자리도 스키마에 «넣어야» 한다. 안 넣으면 응답에 그 열쇠가
            # 아예 안 실려 **계측이 언제나 빈 목록을 기록하고**, 나중에 그 값을 보는 사람은
            # 「안 뒤졌다」로 읽는다 — 「잴 수 없었다」와 구별되지 않는다
            "queries": {"type": "array", "items": {"type": "string"}},
            "unverified": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            *(key for key, _ in measurement_gate.TEXT_FIELDS),
            *(key for key, _ in measurement_gate.GRID_FIELDS),
        ],
    },
    ensure_ascii=False,
)

PROMPT: Final = """이 저장소의 `.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 측정 설계 초안

아래 주장을 **받는 사람이 그대로 잴 수 있는 형태**로 옮깁니다.

> {claim}

**이 후보를 기각하거나 채택하지 마세요.** 판정은 다른 자리의 일입니다.
「표본이 20건뿐」처럼 걸리는 답이 나와도 **그대로 적으면 됩니다.**

## 앞 단계가 이미 정한 것 — 여기에 맞춥니다

**대상 시장**: {market}

**살 수 있는 상품**: {instrument}

**파라미터 축** (수집 단계가 낸 것. 이것이 곧 격자의 재료입니다)

{params}

**[중요] 위를 새로 정하지 마세요.** 다르게 적으면 같은 문서의 두 칸이 서로 다른 말을 합니다.

## 무엇을 묻나

- `instrument`: **실제로 살 수 있는 상품**인가. 지수로 잰 성적은 집행할 수 없는 성적입니다.
  살 수 있는 것이 없으면 **그 사실과 이유**를 적으세요
- `no_lookahead`: **판정 시점에 아는 값만** 쓰는가. 미래 참조가 들어가면 못 잴 것을 재게 됩니다
- `entry_grid`: **진입 시점 격자** — 한 값이 아니라 여러 값
- `holding_grid`: **보유 기간 격자** — 한 값이 아니라 여러 값
- `single_value_reason`: 격자가 정말 한 값뿐일 때만, **왜 하나뿐인지**
- `baseline`: **무엇과 견주는가.** 주식은 장기 상승해서 아무 날에나 사도 오른 비율이
  절반을 넘습니다. **기준선 없는 비율은 사람을 속입니다.**
  대상이 미국이면 **원화 기준과 달러 기준 중 무엇으로 재는지**도 여기 적습니다 —
  달러로 5% 올랐는데 원화로는 2%인 일이 흔합니다
- `direction`: **방향을 미리 정하지 않습니다.** 「내린다」도 유효한 신호이고,
  먼저 정하면 반대쪽 발견을 통째로 놓칩니다
- `expected_samples`: **예상 표본 수.** 몇 건쯤 나오는지를 근거와 함께

**[중요] 수수료 · 세금 · 슬리피지는 적지 마세요.** 증권사·계좌·이벤트에 따라 자릿수가 달라지고
그 폭이 기대값과 같은 크기라 **어떤 값을 넣느냐가 결론을 만듭니다.** 재는 쪽이 자기 조건으로 넣습니다.

**[중요] 이 답은 저장소 밖으로 나갑니다.** 다른 문서를 가리키지 말고 **그 자리에 전부 적으세요.**

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"instrument": "", "no_lookahead": "", "entry_grid": ["여러 값"], "holding_grid": ["여러 값"], "single_value_reason": "", "baseline": "", "direction": "", "expected_samples": "", "queries": ["웹을 뒤졌다면 던진 검색어 전부. 안 뒤졌으면 빈 목록"], "unverified": ["확인하지 못한 것"]}}
"""

# 앞 단계의 값을 못 읽었을 때 프롬프트에 들어갈 말.
#
# [중요] 빈 문자열을 끼우지 않는다. 그러면 에이전트가 「정해진 것이 없다」로 읽어
# **시장과 상품을 스스로 정하고**, 그것이 4·5번 칸과 어긋난다
MISSING_NOTE: Final = "(앞 단계의 값을 읽지 못했습니다. 한 줄 주장에서 판단하고, 확신이 없으면 `unverified` 에 적으세요.)"


def build_prompt(claim: str, *, market: str, instrument: str, params: list[Any]) -> str:
    """측정 설계 지시문을 만든다.

    Args:
        claim: 그 회차의 한 줄 주장
        market: 실현가능성이 정한 대상 시장
        instrument: 실현가능성이 정한 살 수 있는 상품
        params: 수집이 낸 파라미터 축

    Returns:
        에이전트에게 줄 지시문
    """
    listed = "\n".join(f"- {_describe(item)}" for item in params) if params else "(낸 축이 없습니다 — 값이 이미 다 정해진 주장입니다)"
    return PROMPT.format(
        claim=claim,
        market=market.strip() or MISSING_NOTE,
        instrument=instrument.strip() or MISSING_NOTE,
        params=listed,
    )


def run(run_dir: Path, ask: AgentCaller) -> None:
    """10번 칸을 파일로 남긴다.

    Args:
        run_dir: 그 회차의 실행 폴더
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        RuntimeError: 그 회차의 후보가 상태에 없을 때 — 러너가 건너뛰었어야 하는 자리다
        StepFailed: 응답이 약속한 모양이 아닐 때
        StepQualityFailed: 10번 칸의 자리가 비었거나 격자가 한 값일 때
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate = state.pinned_candidate(run_dir)
    if candidate is None:
        raise RuntimeError(f"내부 불변조건 위반: 그 회차의 후보가 상태에 없습니다 — {run_dir}")

    output_dir = run_dir / naming.folder_name(candidate.claim, candidate.identifier)
    collected = outputs.read(output_dir, PRO_EVIDENCE_FILENAME) or {}
    feasible = outputs.read(output_dir, FEASIBILITY_FILENAME) or {}
    execution: Any = feasible.get("execution")

    result = ask(
        build_prompt(
            candidate.claim,
            # [중요] `str()` 을 바로 쓰지 않는다. 예전 판이나 손으로 고친 파일에 `null` 이
            # 들어 있으면 `str(None)` 이 **`"None"` 이라는 «내용이 있는» 문자열**이 되어
            # 「못 읽었다」 안내가 안 나가고, 에이전트가 그 말을 **시장 이름으로 읽는다**
            market=payload_helpers.as_text(feasible.get("market")),
            instrument=payload_helpers.as_text(execution.get("instrument")) if isinstance(execution, dict) else "",
            params=payload_helpers.as_list(collected.get("params")),
        )
    )
    payload = invoke.parse_json_answer(result, what="측정 설계")

    entry_size = measurement_gate.distinct_size(payload.get("entry_grid"))
    holding_size = measurement_gate.distinct_size(payload.get("holding_grid"))

    # 무엇을 놓고 판단했고 얼마를 썼는지는 «게이트 앞»에서 남긴다
    decision_log.record(
        run_dir,
        STEP_NAME,
        decision_log.EVENT_READ,
        params_given=len(payload_helpers.as_list(collected.get("params"))),
        # 검색어는 «게이트 없이» 기록만 한다. 이 칸은 앞 산출물을 읽어 짜는 일이라
        # 하한을 요구하면 억지 검색을 시키게 된다
        queries=payload_helpers.as_strings(payload.get("queries")),
    )
    decision_log.record_cost(run_dir, STEP_NAME, result)

    shortfall = measurement_gate.shortfall_reason(payload)
    if shortfall is not None:
        decision_log.record(run_dir, STEP_NAME, decision_log.EVENT_FAILED, gate=STEP_NAME, reason=shortfall)
        raise StepQualityFailed(f"측정 설계 미달 — {shortfall}")

    _store(run_dir, output_dir, candidate, payload, entry_size=entry_size, holding_size=holding_size)


def _store(
    run_dir: Path,
    output_dir: Path,
    candidate: state.Candidate,
    payload: dict[str, Any],
    *,
    entry_size: int,
    holding_size: int,
) -> None:
    """10번 칸을 파일로 남기고 무엇을 판단했는지 기록한다."""
    stored: dict[str, Any] = {"claim": candidate.claim}
    for key, _ in measurement_gate.TEXT_FIELDS:
        stored[key] = payload.get(key)
    for key, _ in measurement_gate.GRID_FIELDS:
        stored[key] = payload_helpers.as_list(payload.get(key))
    # [중요] `str()` 을 바로 쓰지 않는다. 열쇠가 «있는데 값이 null» 이면 기본값이 안 먹고
    # `str(None)` = `"None"` 이 저장된다 — 10번 칸의 빈 자리 검사는 그것을 «찼다»로 읽어
    # 건너뛰지 않으므로, **저장소 밖으로 나가는 문서에 `None` 이 실린다**
    stored[measurement_gate.KEY_SINGLE_VALUE_REASON] = payload_helpers.as_text(
        payload.get(measurement_gate.KEY_SINGLE_VALUE_REASON)
    )
    stored["unverified"] = payload_helpers.as_list(payload.get("unverified"))

    with atomic_write(output_dir / MEASUREMENT_FILENAME) as file:
        json.dump(stored, file, ensure_ascii=False, indent=2)

    decision_log.record(
        run_dir,
        STEP_NAME,
        decision_log.EVENT_JUDGED,
        claim=candidate.claim,
        # 격자 크기가 로그에 있어야 나중에 「격자를 한 값으로 낸 후보가 몇이었나」를 셀 수 있다
        entry_grid_size=entry_size,
        holding_grid_size=holding_size,
        expected_samples=payload.get("expected_samples"),
    )


def _describe(param: Any) -> str:
    """파라미터 축 하나를 프롬프트에 실을 한 줄로 만든다."""
    if not isinstance(param, dict):
        return str(param)
    name = payload_helpers.as_text(param.get("name")) or "(이름 없음)"
    unit = payload_helpers.as_text(param.get("unit"))
    candidates = param.get("candidates")
    return f"{name} · 단위 {unit or '없음'} · 후보값 {candidates}"

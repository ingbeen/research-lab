"""판정(2번 칸)이 «판정 · 이유 · 적용한 기준»을 모두 담았는지 검사한다.

[중요] **「적용한 기준」을 「이유」와 다른 자리로 받는다.** 한 칸이면
「원칙 12 에 걸린다」로 적혀도 게이트가 못 본다. 이 산출물은 저장소 밖으로 나가므로
**번호는 그 자리에서 죽고**, 받는 쪽은 「왜 보류지?」에 답을 얻지 못한 채 종이만 쥔다.

자리를 갈라 두면 안 물을 수가 없다 — 11칸 구조가 자유 서술을 버린 것과 같은 이유이고,
**자립성이라는 1순위 제약을 기계가 건드릴 수 있는 유일한 지점**이다.
그래도 「기준 자체를 적었나」가 아니라 **「그 자리가 찼나」**만 본다. 내용을 판정하려 들면
게이트가 또 하나의 판단자가 된다.

[중요] 판정이 «맞는지»는 보지 않는다. 「기각」도 「보류」도 정상 결과이며,
회차마다 「잴 가치 있음」이 나오면 그게 고장이다 — 이 파이프라인의 가치는 찾는 것보다
**가짜를 그 전에 걸러내는 것**이다.
"""

from collections.abc import Mapping
from typing import Any, Final

from research_lab.gate.filled import is_filled

KEY_VERDICT: Final = "verdict"
KEY_REASON: Final = "reason"
KEY_CRITERIA: Final = "criteria"

# 판정이 쓸 수 있는 값.
#
# [중요] 값의 «내용»을 판정하는 것이 아니라 **약속된 모양인지**를 본다. 이 값이 기계로
# 읽혀야 나중에 「판정이 어떻게 갈렸나」를 셀 수 있고, 자유 문자열이면 못 센다 —
# 그리고 못 센다는 사실은 아무 에러도 내지 않는다.
#
# 「보류」가 있는 이유는 **잴 수는 있으나 그 질문이 막히는** 경우가 정상 결과이기 때문이다
# (표본이 적어 시기를 쪼갤 수 없는 후보 등). 「잴 가치 있음」과 「기각」만 두면
# 그런 후보가 둘 중 하나로 억지로 밀려 들어간다
VERDICT_VALUES: Final = ("잴 가치 있음", "보류", "기각")

TEXT_FIELDS: Final = (
    (KEY_REASON, "왜 그렇게 판정했나"),
    (KEY_CRITERIA, "적용한 기준 «자체» — 규약 이름이나 번호가 아니라 기준의 내용"),
)


def shortfall_reason(payload: Mapping[str, Any]) -> str | None:
    """판정 칸이 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    Args:
        payload: 판정 단계가 낸 산출물. 모양이 어긋나 있어도 된다

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    decision = payload.get(KEY_VERDICT)
    if not isinstance(decision, str) or decision.strip() not in VERDICT_VALUES:
        promised = " · ".join(VERDICT_VALUES)
        return f"판정(`{KEY_VERDICT}`)이 약속된 값이 아닙니다 — {promised} 중 하나로 적으세요. " f"이 값은 기계가 읽어 「판정이 어떻게 갈렸나」를 셉니다."

    for key, label in TEXT_FIELDS:
        if not is_filled(payload.get(key)):
            return (
                f"2번 칸의 「{label}」(`{key}`)가 비어 있습니다. "
                f"이 문서는 다른 문서를 한 장도 열 수 없는 곳에서 읽히므로, "
                f"**적용한 기준을 그 자리에 풀어 적어야** 「왜 이 판정인가」에 답이 됩니다."
            )

    return None

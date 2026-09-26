"""메커니즘 산출물이 3·9번 칸의 «자리»를 채웠는지 검사한다 — 설명의 내용은 보지 않는다.

3번 칸(왜 우위가 있을 수 있나)과 9번 칸(왜 사라졌을 수 있나)은 한 쌍이다 —
「우위가 있었나」와 「그 우위가 아직 살아 있나」이기 때문이다. 자유 서술로 두면
**찾은 것만 쓰고 안 찾은 것은 언급조차 안 한다.** 특히 9번 칸이 통째로 빠지기 쉽다 —
찬성 근거를 모으다 보면 「지금도 되나」를 안 묻게 된다.

[중요] **「해당 없음」이라 적을 길을 남긴다.** 그 길이 없으면 게이트가 에이전트에게
**없는 사실을 채워 넣을 압력**을 만든다 — 반증 게이트가 「0건 = 실패」를 고르지 않은 것과
같은 축이고, 이 저장소에 남은 유일한 위조 위험이 「없는 출처」이기 때문이다.

[중요] 설명의 «질»은 판정하지 않는다. 판정하려 들면 게이트가 또 하나의 판단자가 된다.
"""

from collections.abc import Mapping
from typing import Any, Final

from research_lab.gate.filled import is_filled

KEY_EDGE: Final = "edge"
KEY_DECAY: Final = "decay"

# 3번 칸의 자리. 괄호 안은 사유에 실을 «사람이 읽는 이름»이다.
#
# 셋으로 가르는 이유는 설계가 우위의 출처를 그렇게 셋으로 적어 두었기 때문이다 —
# 위험을 더 져서 받는 것인가 · 사람이 반복해 저지르는 실수인가 · 제도나 시장 구조가
# 만든 것인가. **어느 것도 아니면 그 자체가 신호**라 「해당 없음」으로 적게 한다
EDGE_FIELDS: Final = (
    ("risk_premium", "리스크 프리미엄 — 위험을 더 져서 받는 것인가"),
    ("behavioral", "행동 편향 — 사람이 반복해 저지르는 실수인가"),
    ("structural", "제도·미시구조 — 규칙이나 시장 구조가 만든 것인가"),
)

# 9번 칸의 자리.
#
# [중요] 「발표 후 소멸」을 첫 자리에 둔다. 알려지면 사라지는 것이 이 분야에서 가장 흔한
# 소멸 경로이고, 찬성 근거로 쓰인 논문 자체가 **그 소멸의 원인**인 경우가 많다
DECAY_FIELDS: Final = (
    ("post_publication", "발표 후 소멸 — 알려져서 선반영됐나"),
    ("regulatory", "제도 변화 — 세제·규칙이 전제를 바꿨나"),
    ("market_structure", "시장 구조 변화 — 참여자나 거래 방식이 달라졌나"),
)

SECTIONS: Final = ((KEY_EDGE, "3번", EDGE_FIELDS), (KEY_DECAY, "9번", DECAY_FIELDS))


def shortfall_reason(payload: Mapping[str, Any]) -> str | None:
    """3·9번 칸의 자리가 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    사유를 «문자열로» 돌리는 것은 실패 원문에 그대로 실어 보내기 위해서다.
    「게이트에 걸렸다」만 남으면 다음 회차가 무엇을 고쳐야 하는지 모른다.

    Args:
        payload: 메커니즘 단계가 낸 산출물. 모양이 어긋나 있어도 된다

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    for section_key, ordinal, fields in SECTIONS:
        section = payload.get(section_key)
        if not isinstance(section, Mapping):
            # 절이 없다는 것은 그 단계가 **아예 묻지 않았다**는 뜻이다. 목록이나 문자열이
            # 와도 여기서 막는다 — 그런 값은 비어 있지 않으므로 「적혀 있다」로 읽혀
            # 조용히 통과할 수 있다
            return f"{ordinal} 칸(`{section_key}`)이 없거나 절이 아닙니다. 그 칸이 비면 근거 문서가 미완성이 됩니다."

        for key, label in fields:
            if not is_filled(section.get(key)):
                return (
                    f"{ordinal} 칸의 「{label}」(`{key}`)가 비어 있습니다. " f"해당하지 않으면 «「해당 없음」과 그 이유»를 적으세요 — 빈 채로 두는 것과 다릅니다."
                )

    return None

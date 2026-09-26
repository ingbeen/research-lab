"""실현가능성 산출물이 4·5번 칸의 «자리»를 채웠는지 검사한다 — 답의 내용은 보지 않는다.

이 칸들을 자유 서술로 두면 **찾은 것만 쓰고 안 찾은 것은 언급조차 안 한다.** 설계 §2 의
채워 본 예시에서 실제로 문제를 잡아낸 칸이 5번(「신호가 연 1회」)이었고, 그것은
**칸이 정해져 있어서 안 물을 수가 없었기 때문에** 나왔다. 그래서 설계 §7 의 두 표가 묻는 것을
하나씩 자리로 요구한다.

[중요] **「해당 없음」이라 적을 길을 남긴다.** 그 길이 없으면 게이트가 에이전트에게
**없는 사실을 채워 넣을 압력**을 만든다 — 반증 게이트가 「0건 = 실패」를 고르지 않은 것과
같은 축이다.

[중요] **비용·세금·슬리피지는 막지 않고 «센다».** 금지어로 막으면 설계 §10.1 A 가 실측으로
뒤집은 함정에 다시 선다(진짜 원장의 후보 13개 중 12개가 사전에 걸렸다). 기각의 대가가
오탐 중 가장 크고, 이 혼입은 「없는 출처」와 달리 **읽으면 사람이 바로 본다.**
판정(2번 칸)이 아직 없으므로 그 값이 결론을 만들 자리도 아직 없다.
"""

import json
from collections.abc import Mapping
from typing import Any, Final

from research_lab.gate.filled import is_filled

KEY_MARKET: Final = "market"
KEY_DATA: Final = "data"
KEY_EXECUTION: Final = "execution"
KEY_NEEDS: Final = "needs"
KEY_AVAILABILITY: Final = "availability"

# 데이터 판정이 쓸 수 있는 값.
#
# [중요] 이것은 «값의 내용»을 판정하는 것이 아니라 **약속된 모양인지**를 보는 것이다 —
# 목록 자리에 문자열이 오면 막는 것과 같은 갈래다. 이 값이 기계로 읽혀야 나중에
# 「데이터가 이미 있던 후보가 몇이었나」를 셀 수 있다.
#
# 「막힘」이 있는 이유는 대체 사다리(대체 데이터 → 대상 축소 → 기간 축소)를 다 타고도
# 안 되는 경우가 정상 결과이기 때문이다. 그 경우에도 「막히면 무엇으로」를 적게 해
# **무엇을 시도했는지가 남는다**
AVAILABILITY_VALUES: Final = ("이미 있음", "받을 수 있음", "막힘")

# 4번 칸에서 «문장»으로 받는 자리. 괄호 안은 사유에 실을 사람이 읽는 이름이다.
#
# [중요] 설계 §7 이 자리마다 「안 물으면 생기는 일」을 함께 적어 두었다 — 미래 참조를
# 안 물으면 **못 잴 것을 재게 되고**, 생존편향을 안 물으면 **결과가 좋게 나온다. 틀리게.**
# 그래서 자리를 줄이지 않는다
DATA_TEXT_FIELDS: Final = (
    ("how_to_get", "무엇으로 어떻게 받나"),
    ("point_in_time", "그 시점에 실제로 알 수 있었나"),
    ("survivorship", "상장폐지·합병 종목이 빠져 있나"),
    ("fallback", "막히면 무엇으로 대체하나"),
)

# 5번 칸의 자리. 설계 §7 의 5번 칸 표 그대로다.
#
# [중요] 「사람이 깨어 있는 시간에 집행 가능한가」와 「분·초 단위 집행이 필요한가」는
# **다른 물음이다**(설계 §7.0). 미국장이라 한국시간 새벽에만 집행되는 것과,
# 초 단위 체결이 필요해 개인이 못 하는 것은 갈래가 다르다
EXECUTION_FIELDS: Final = (
    ("instrument", "개인이 살 수 있는 상품이 있나"),
    ("signal_frequency", "신호가 얼마나 자주 오나"),
    ("leverage", "배수를 걸 수 있나"),
    ("waking_hours", "사람이 깨어 있는 시간에 집행 가능한가"),
    ("intraday_precision", "분·초 단위 집행이 필요한가"),
)

# 5번 칸에 들어오면 «세는» 말. 막는 목록이 아니다.
#
# 오탐의 대가가 0 이라 넉넉히 담는다 — 세는 것뿐이므로 멀쩡한 후보가 죽지 않는다.
#
# [중요] 「환율」을 넣지 않는다. 환전 **스프레드**는 비용이라 5번 칸의 금지에 걸리지만,
# 환율 **노출**은 「달러로 5% 올랐는데 원화로는 2%였다」는 측정의 문제라 10번 칸
# 기준선 항목이다(설계 §7.0). 둘을 섞으면 5번 칸이 금지된 값을 들고 결론을 만들게 된다
COST_TERMS: Final = (
    "수수료",
    "세금",
    "세율",
    "양도세",
    "거래세",
    "배당소득세",
    "슬리피지",
    "거래비용",
    "매매비용",
    "스프레드",
    "환전",
    # [실측 2026-09-15] 아래 「체결가」는 «실제로 나간 문서»에서 걸러지지 않은 표현이다.
    # 5번 칸이 「시가로 살 때와 종가로 살 때의 **체결가** 차이」로 슬리피지를 논했는데
    # 사전에 그 말이 없어 계측이 빈 값으로 기록됐다. 그 0 을 「비용을 안 적었다」로 읽으면,
    # 「분포를 쌓아 나중에 판단한다」고 미뤄 둔 결정이 **데이터 없이** 내려진다.
    #
    # [중요] 사전은 «겪은 표현»으로만 늘린다. 미리 채우면 무엇이 실제로 나오는지를
    # 못 보게 되고, 이 목록의 쓸모는 바로 그 분포다.
    #
    # [탈락 2026-09-15] 「호가」를 같이 넣었다가 뺐다. **「신호가」(신호+가)를 문다** —
    # 하필 5번 칸의 필드 이름이 「신호가 얼마나 자주 오나」라 재발이 확실하고,
    # 실측으로 한 회차가 그 이유만으로 걸렸다. 「호가 스프레드」는 이미 위 「스프레드」가
    # 잡으므로 덮는 범위도 늘지 않았다. **세는 목록이라도 계통 오탐은 분포를 망친다**
    "체결가",
)


def shortfall_reason(payload: Mapping[str, Any]) -> str | None:
    """4·5번 칸의 자리가 모자라면 그 사유를, 충분하면 None 을 돌려준다.

    사유를 «문자열로» 돌리는 것은 실패 원문에 그대로 실어 보내기 위해서다.
    「게이트에 걸렸다」만 남으면 다음 회차가 무엇을 고쳐야 하는지 모른다.

    Args:
        payload: 실현가능성 단계가 낸 산출물. 모양이 어긋나 있어도 된다

    Returns:
        모자랄 때의 사유, 충분하면 None
    """
    if not is_filled(payload.get(KEY_MARKET)):
        # [중요] 시장이 없으면 「배수를 걸 수 있나」를 기각 신호로 쓸 수 없다 —
        # 「1배로만 되는데 크기가 작다」는 국내에서는 기각이지만 미국에서 3배를 확인하기
        # 전에는 기각이 아니다(설계 §7.0). 시장 없이 적힌 판정은 나중에 되짚을 수도 없다
        return f"대상 시장(`{KEY_MARKET}`)이 비어 있습니다. 「배수를 걸 수 있나」는 시장을 먼저 적어야 판정에 쓸 수 있습니다 — 국내는 2배가 상한이고 미국은 3배까지 있습니다."

    for section_key, ordinal in ((KEY_DATA, "4번"), (KEY_EXECUTION, "5번")):
        section = payload.get(section_key)
        if not isinstance(section, Mapping):
            # 절이 없다는 것은 그 단계가 **아예 묻지 않았다**는 뜻이다. 목록이나 문자열이
            # 와도 여기서 막는다 — 그런 값은 비어 있지 않으므로 「적혀 있다」로 읽혀
            # 조용히 통과할 수 있다
            return f"{ordinal} 칸(`{section_key}`)이 없거나 절이 아닙니다. 그 칸이 비면 dossier 가 미완성이 됩니다."

    data: Mapping[str, Any] = payload[KEY_DATA]
    execution: Mapping[str, Any] = payload[KEY_EXECUTION]

    needs = data.get(KEY_NEEDS)
    if not isinstance(needs, list) or not any(is_filled(item) for item in needs):
        return f"4번 칸의 「어떤 데이터가 필요한가」(`{KEY_NEEDS}`)가 비었거나 목록이 아닙니다. 안 적으면 «다 된다고 가정하고» 넘어갑니다."

    availability = data.get(KEY_AVAILABILITY)
    if not isinstance(availability, str) or availability.strip() not in AVAILABILITY_VALUES:
        promised = " · ".join(AVAILABILITY_VALUES)
        return f"4번 칸의 데이터 판정(`{KEY_AVAILABILITY}`)이 약속된 값이 아닙니다 — {promised} 중 하나로 적으세요. 이 값은 기계가 읽어 「데이터가 이미 있던 후보가 몇이었나」를 셉니다."

    for section, fields, ordinal in ((data, DATA_TEXT_FIELDS, "4번"), (execution, EXECUTION_FIELDS, "5번")):
        for key, label in fields:
            if not is_filled(section.get(key)):
                return f"{ordinal} 칸의 「{label}」(`{key}`)가 비어 있습니다. 물을 것이 없으면 «「해당 없음」과 그 이유»를 적으세요 — 빈 채로 두는 것과 다릅니다."

    return None


def cost_terms_in(section: Any) -> tuple[str, ...]:
    """그 절에 든 비용·세금·슬리피지 표현을 «센다». 판정하지 않는다.

    [중요] 이 값으로 막지 않는다. 설계 §2 가 5번 칸에서 비용을 묻지 말라고 한 것은
    **어떤 값을 넣느냐가 결론을 만들기** 때문인데, 게이트로 막으면 금지어 = 기각 구조가
    되어 멀쩡한 후보가 죽는다. 대신 분포를 쌓아 나중에 판단한다.

    Args:
        section: 5번 칸. 모양이 어긋나 있어도 된다

    Returns:
        걸린 표현. **정의된 순서**로 돌려준다 — 회차마다 순서가 달라지면 로그를 대조할 수 없다
    """
    text = _as_text(section)
    return tuple(term for term in COST_TERMS if term in text)


def _as_text(value: Any) -> str:
    """중첩된 값까지 한 덩어리 문자열로 만든다.

    [중요] 파이썬 재귀로 훑지 않는다. 에이전트가 낸 값이라 깊이를 보장할 수 없고,
    **계측 때문에 그 회차가 멈추면 안 된다** — 판정을 못 하는 것과 실패로 판정하는 것은 다르다.
    """
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)

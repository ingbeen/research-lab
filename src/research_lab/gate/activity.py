"""후보가 한 해에 «돈이 일하는 거래일»이 충분한지 판정한다.

연간 매매 기회도 드물고 보유기간도 짧은 후보는 수익을 기대하기 어렵다 — 한 해의 대부분 돈이 쉰다.
그래서 두 값을 «곱한» 연간 가동일(연간 독립 진입 시점 × 보유 거래일)로 가른다. 「둘 중 하나가
크면 된다」로 두면 두 문턱 사이에 빈틈이 생긴다 — 연 6회 × 30거래일(가동일 180)이 떨어지고,
연 4회 × 60거래일(240)이 경계에 선다.

[중요] 연횟수는 «독립 진입 시점»으로 센다. 같은 날·같은 주·같은 시즌에 몰린 사건은 한 번이다 —
같은 날 여러 종목을 사면 돈이 나뉠 뿐 돈이 도는 횟수는 한 번이다. 사건 수로 세면 연말 배당락처럼
하루에 수백 종목을 사는 후보가 연 수백 회가 된다. 이 뜻은 탐색 지시문이 에이전트에게 전하고,
여기서는 받은 숫자를 곱할 뿐이다.

[중요] 어림을 못 읽으면 거르지 않는다. 이 판정의 결과는 원장 기각이라 사람이 손대기 전까지
다시 안 파진다 — 판정을 못 한 것을 미달로 접으면 멀쩡한 후보가 영구히 버려진다.
0 을 어떻게 세는지는 `_estimates` 가 정한다.
"""

import math
from typing import Any, Final

# 연중 약 3분의 1(1년 ≈ 252거래일) 동안 돈이 일한다는 뜻이다. 이 자리인 이유는 지시문의
# 「범위는 긴 쪽」 어림으로도 드물고 짧은 대표 사례 — 옵션 만기주 연 12회 × 5거래일 = 60 ·
# 연말 배당락 연 1회 × 66거래일 = 66 — 가 걸리고, 드물어도 오래 드는 Sell in May(연 1회 ×
# 약 125거래일)는 넘기 때문이다. [실측 2026-09-29] 원장의 기존 후보 15개 대조
MIN_ACTIVE_DAYS_PER_YEAR: Final = 80

# 당일 청산의 보유를 이만큼으로 센다 — 같은 날 사고 팔아도 그날 하루는 돈이 묶인다
MIN_HOLDING_DAYS: Final = 1.0


def active_days(entries_per_year: Any, holding_days: Any) -> float | None:
    """연간 가동일 — 연간 독립 진입 시점 × 보유 거래일.

    Returns:
        두 어림을 읽을 수 있을 때만 그 곱(`_estimates`). 아니면 None(판정 못 함) — **판정 못 함은
        0 이 아니다.** 0 으로 돌리면 「가동일이 없다」로 읽혀 미달로 기각된다
    """
    estimates = _estimates(entries_per_year, holding_days)
    if estimates is None:
        return None
    entries, holding = estimates
    return entries * holding


def shortfall_reason(entries_per_year: Any, holding_days: Any, basis: Any) -> str | None:
    """가동일이 문턱에 못 미치면 원장에 실을 사유를, 넘거나 판정을 못 하면 None 을 돌려준다.

    Args:
        entries_per_year: 에이전트가 어림한 연간 독립 진입 시점 수
        holding_days: 에이전트가 어림한 보유 거래일
        basis: 그 어림의 근거. 에이전트가 쓴 글이라 줄바꿈이 섞일 수 있다

    Returns:
        미달이면 **한 줄** 사유 — 두 어림값 · 곱 · 문턱 · 근거가 든다. 사람이 판정을 뒤집을 근거가
        이것뿐이다. 한 줄이어야 하는 이유: 원장은 한 줄에 한 후보이고 사유도 한 줄이라, 근거의
        줄바꿈이 살아 있으면 그다음 줄이 원장의 새 줄로 읽혀 **게이트를 거치지 않은 후보가 담긴다**
    """
    # 표시하는 값도 곱한 값과 «같은 읽기»에서 꺼낸다 — 따로 읽으면 당일 청산을 1 로 곱해 놓고
    # 사유에는 0 이 찍혀 「0 × 4 = 4」처럼 스스로 모순인 줄이 원장에 남는다
    estimates = _estimates(entries_per_year, holding_days)
    if estimates is None:
        return None
    entries, holding = estimates
    days = entries * holding
    if days >= MIN_ACTIVE_DAYS_PER_YEAR:
        return None

    written = " ".join(basis.split()) if isinstance(basis, str) else ""
    return (
        f"연간 가동일 기준 미달 — 연간 독립 진입 시점 {entries:g}회 × 보유 {holding:g}거래일 = "
        f"{days:g}거래일로 {MIN_ACTIVE_DAYS_PER_YEAR}거래일에 못 미칩니다(탐색 단계의 어림). "
        f"어림 근거: {written or '적지 않았습니다'}"
    )


def _estimates(entries_per_year: Any, holding_days: Any) -> tuple[float, float] | None:
    """두 어림을 곱할 수 있는 모양으로 읽는다. 못 읽으면 None(판정 못 함).

    [중요] 0 은 두 어림에서 뜻이 다르다. 곱에서 한쪽이 0 이면 다른 쪽이 아무리 커도 가동일이 0 이라
    **영구 기각**으로 이어지므로, 0 을 그대로 곱하지 않는다.

    - **보유 0 은 하루로 올려 센다**(`MIN_HOLDING_DAYS`) — 당일 청산의 정직한 어림이다. 그대로 곱하면
      매일 도는 당일 청산(연 252회)까지 기각되고, 「판정 못 함」으로 흘리면 드문 당일 청산이 게이트를
      비켜 간다
    - **연횟수 0 은 판정 못 함이다** — 「모름」과도 「한 번 사서 계속 든다」와도 구별되지 않는다.
      드문 후보는 지시문이 0.5 같은 소수로 받는다
    """
    entries = _non_negative_number(entries_per_year)
    holding = _non_negative_number(holding_days)
    if entries is None or holding is None or entries == 0:
        return None
    return entries, max(holding, MIN_HOLDING_DAYS)


def _non_negative_number(value: Any) -> float | None:
    """0 이상의 유한한 숫자로 읽히는 값만 읽는다.

    [주의] 참/거짓을 먼저 뺀다. 파이썬에서 `True` 는 `int` 라 그냥 두면 1 로 곱해진다.

    따옴표 안의 숫자 하나(「12」)는 읽는다 — 에이전트가 `12` 와 `"12"` 를 섞어 내는 일이 흔하고,
    못 읽으면 그 후보가 판정 없이 통과한다. 숫자 «하나»만이다 — 「1~3」 같은 범위 글자를 풀어
    읽기 시작하면 어느 끝을 쓸지가 여기서 또 하나의 판단이 된다.

    음수는 어림이 될 수 없으니 못 읽은 것으로 본다.
    """
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        # JSON 은 자릿수 제한 없는 정수를 그대로 넘기고, 글자는 숫자가 아닐 수 있다 —
        # 게이트는 어떤 입력에도 예외를 올리지 않는다
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number

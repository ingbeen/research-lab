"""게이트들이 함께 쓰는 「숫자로 읽히나」 판정.

[중요] 정성 표현 게이트(축의 후보값)와 측정 설계 게이트(격자)가 «같은 값인가»를 이것 하나로 본다.
따로 두면 한 게이트는 `5` 와 `5.0` 을 한 값으로, 다른 게이트는 두 값으로 세어 같은 격자의 판정이
갈리고, 그 어긋남은 에러를 내지 않는다.

가동일 게이트는 이것을 쓰지 않는다 — 못 읽으면 통과(판정 못 함)라서 실수로 못 옮기는 큰 정수를
«못 읽음»으로 보내는데, 정성 표현 게이트는 못 읽으면 영구 기각이라 같은 정수를 수로 센다.
"""

import math
from typing import Any


def as_number(value: Any) -> int | float | None:
    """수이거나 숫자 하나로 읽히는 글자면 그 수를, 아니면 None 을 돌려준다.

    - 정수 · 실수는 **그대로** 돌려준다. 실수로 바꾸지 않는 것은 `float()` 가 실수 범위를 넘는 정수에서
      예외를 올리기 때문이고, 값이 같은 정수와 실수(5 · 5.0)는 바꾸지 않아도 집합에서 하나다
      (파이썬의 수 해시 규약). JSON 의 NaN · Infinity 도 받은 객체 그대로다
    - 글자는 숫자 하나로 읽히고 **유한할** 때만 그 실수다 — 에이전트는 `5` 와 `"5"` 를 섞어 낸다.
      단위 · 범위가 붙은 글자(「5%」 · 「1~3」)는 읽지 않는다. 어느 끝을 쓸지가 게이트의 판단이 된다.
      비유한 글자(「nan」 · 「inf」 · 「1e400」)를 버리는 이유 — `float("nan")` 은 부를 때마다 다른
      객체라 집합에서 겹쳐지지 않아 `["nan", "nan"]` 이 두 값으로 세어진다
    - 참/거짓은 수가 아니다. 파이썬에서 `True` 는 `int` 라 그냥 두면 1 로 읽힌다
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    if not isinstance(value, str):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None

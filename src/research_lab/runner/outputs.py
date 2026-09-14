"""앞 단계가 남긴 산출물을 읽는다 — 뒤 단계들의 «입력»이다.

회차가 길어지면서 뒤 단계일수록 앞의 것을 많이 먹는다. 메커니즘은 찬성·반증의 출처를,
측정 설계는 수집의 파라미터 축과 실현가능성의 시장·상품을, 판정은 **전부**를 받는다.
근거 문서 조립도 같은 파일들을 읽는다.

[중요] 읽는 곳을 하나로 두는 이유는 **읽기 실패를 어떻게 다룰지가 자리마다 다르기**
때문이다. 여기서는 「못 읽었다」를 `None` 으로만 알리고 **판단은 부르는 쪽에 맡긴다** —
단계 입력으로 쓸 때는 없어도 진행하는 것이 맞고(앞 단계가 「실체 없음」으로 끝났을 수 있다),
문서를 조립할 때는 **칸이 빈 채로 나가면 안 되므로** 막아야 한다.
그 둘을 여기서 하나로 정하면 한쪽이 반드시 틀린다.
"""

import json
from pathlib import Path
from typing import Any


def read(output_dir: Path, filename: str) -> dict[str, Any] | None:
    """산출물 파일 하나를 읽는다.

    Args:
        output_dir: 그 회차의 후보 폴더
        filename: 읽을 산출물의 파일명

    Returns:
        내용. 파일이 없거나 읽히지 않으면 None

    [주의] **예외를 올리지 않는다.** 반쯤 쓰다 끊긴 파일은 존재하면서 열리지 않는데,
    여기서 터뜨리면 부르는 쪽이 그것을 「없음」과 구별하지 못한 채 그 회차가 끝난다.
    """
    path = output_dir / filename
    if not path.is_file():
        return None

    try:
        loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    return loaded if isinstance(loaded, dict) else None

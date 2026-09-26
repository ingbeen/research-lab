"""지시문이 «자기가 요구하는 규율»을 스스로 지키는지 고정한다.

[실측 2026-09-16] 한 회차가 실현가능성 단계에서 0장으로 끝났다. 사유는 산출물에
「이 저장소」가 들어갔다는 것이었는데, **지시문 여덟 개가 전부 그 표현으로 시작하고
있었다.** 에이전트는 금지 대상인 토큰을 프롬프트 맨 앞에서 받아 자기 답에 되돌려 썼다.

지시가 모자랐던 것이 아니다 — 같은 프롬프트가 「그 문서를 보라로 적지 말라」고 못박고
있었고 리서치 스킬에는 대체 표현 표까지 있었다. **조건을 만드는 쪽이 어기고 있었다.**

[중요] **단계 하나가 아니라 목록을 훑는다.** 한 곳만 검사하면 단계를 더할 때 같은 실수가
조용히 돌아오고, 그것은 회차가 돌아 봐야 드러난다.

[주의] **이 검사가 못 덮는 곳이 둘 있다 — 알고 쓴다.**

- **`build_prompt` 안에서 그때 만들어지는 문자열.** 모듈 상수가 아니라 함수 안의
  리터럴이라 여기서 안 보인다. 단계마다 그 함수의 시그니처가 달라 한 자리에서 부를 수 없다
- **리서치 스킬 본문**(`.claude/skills/dossier-research/SKILL.md`). 그 문서는
  「이렇게 적지 마세요」 표에 **금지 표현을 예시로 실어야** 하므로 이 검사에 넣으면
  영원히 빨강이다. 설명 산문 쪽만 사람이 지킨다
"""

import importlib
from types import ModuleType
from typing import Any

import pytest

from research_lab import common_constants
from research_lab.gate import selfcontained
from research_lab.runner import feasibility, steps

# 훑을 깊이 상한. 프롬프트를 담는 상수는 문자열이거나 「목록 안의 문자열」 정도다
_MAX_DEPTH = 6


def _strings_in(value: Any, *, depth: int = 0) -> list[str]:
    """상수 하나에서 «사람이 읽는 문자열»을 전부 꺼낸다.

    [중요] 문자열만 집지 않는다. 프롬프트에 끼워 넣는 값이 사전이나 튜플에 담겨 있으면
    (판정값 목록 · 절 제목 등) **그것도 그대로 에이전트에게 나간다.**
    이름 하나만 집으면 그 이름이 아닌 새 상수가 검사를 비켜 간다.
    """
    if depth > _MAX_DEPTH:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [found for item in value.values() for found in _strings_in(item, depth=depth + 1)]
    if isinstance(value, list | tuple | set | frozenset):
        return [found for item in value for found in _strings_in(item, depth=depth + 1)]
    return []


def _texts_of(module: ModuleType) -> dict[str, str]:
    """그 모듈이 «자기 것으로» 들고 있는 문자열 상수를 모은다.

    [중요] **다른 모듈에서 들여온 이름은 뺀다.** `vars()` 는 import 한 것도 함께 돌려주는데,
    공용 상수에 한글 값이 하나 늘면 **여덟 단계가 한꺼번에 빨강이 되고 그 메시지는
    엉뚱한 단계의 지시문을 가리킨다** — 사유는 사실인데 대상이 틀린 자리다.
    """
    collected: dict[str, str] = {}
    for name, value in vars(module).items():
        if not name.isupper() or getattr(common_constants, name, object()) is value:
            continue
        for index, text in enumerate(_strings_in(value)):
            collected[f"{module.__name__.rsplit('.', 1)[-1]}.{name}[{index}]"] = text
    return collected


@pytest.mark.parametrize("step", steps.STEPS)
def test_every_prompt_passes_the_gate_it_enforces(step: str) -> None:
    """
    목적: [중요] 지시문이 자립성 게이트를 «스스로» 통과하는 계약을 고정한다.

    금지하는 표현을 지시문이 쓰면 그것은 **지시가 아니라 예시가 된다.**
    에이전트는 규율을 어기라는 말을 들은 적이 없지만, 어기는 문장을 먼저 읽는다.

    Given: 그 단계가 에이전트에게 내보내는 문자열 상수 전부
    When: 산출물에 걸던 것과 «같은» 게이트에 **한 번에** 넣는다
    Then: 걸리는 것이 없다
    """
    module = importlib.import_module(f"research_lab.runner.{step}")

    # 게이트는 여러 자리를 «한 번에» 받아 전부 모아 돌려주도록 만들어졌다.
    # 상수마다 따로 부르면 그 설계를 버리고 비슷한 사유가 여러 줄로 쌓인다
    reason = selfcontained.shortfall_reason(_texts_of(module))

    assert reason is None, f"지시문이 자기가 금지한 표현을 쓰고 있습니다 — {reason}"


def test_the_data_catalog_passes_the_gate_it_is_fed_into() -> None:
    """
    목적: [중요] 러너가 프롬프트에 «통째로» 싣는 데이터 카탈로그 본문도 게이트를 통과하는
    계약을 고정한다.

    그 본문은 모듈 상수가 아니라 파일이라 위 검사가 못 본다. 그런데 에이전트에게는
    지시문과 똑같이 읽힌다 — 나간 근거 문서들이 「카탈로그에 …」 · 「카탈로그는 …」 으로
    그 목록을 가리켰고, 그때 이 본문에도 같은 꼴(「카탈로그에 있다」 · 「이 카탈로그는」)이
    적혀 있었다.

    Given: 실현가능성 단계가 읽어 싣는 데이터 카탈로그 본문
    When: 산출물에 걸던 것과 «같은» 게이트에 넣는다
    Then: 걸리는 것이 없다
    """
    catalog = feasibility.load_catalog(common_constants.DATA_CATALOG_PATH)

    reason = selfcontained.shortfall_reason({"데이터 카탈로그": catalog})

    assert catalog, "카탈로그를 못 읽으면 이 검사가 빈 본문으로 통과한다"
    assert reason is None, f"카탈로그 본문이 자기가 금지한 표현을 쓰고 있습니다 — {reason}"

"""계층 간 의존 방향(`runner → agent` · `runner → gate`)이 단방향인 계약을 고정한다.

`agent` 는 어느 단계가 자기를 쓰는지 몰라야 하고, `gate` 는 값을 받아 판정만 한다.
둘 중 하나가 `runner` 를 import 하면 그 경계가 무너지는데, **파이썬은 순환만 안 생기면
아무 말도 하지 않는다** — `TYPE_CHECKING` 으로 순환을 비켜 가면 더 조용하다.
"""

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "src" / "research_lab"
FORBIDDEN_PREFIX = "research_lab.runner"


def _imported_modules(source: Path) -> list[str]:
    """그 파일이 import 하는 모듈 이름을 전부 모은다 — `TYPE_CHECKING` 블록 안의 것까지."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            found.append(node.module)
    return found


@pytest.mark.parametrize("layer", ["agent", "gate"])
def test_lower_layers_do_not_import_the_runner(layer: str) -> None:
    """
    목적: [중요] `agent` 와 `gate` 가 `runner` 를 import 하지 «않는» 계약을 고정한다.

    Given: 그 계층의 모든 모듈
    When: import 하는 모듈을 모은다
    Then: `research_lab.runner` 아래 것이 하나도 없다
    """
    sources = sorted((PACKAGE_ROOT / layer).glob("*.py"))
    offenders = [
        f"{source.name}: {module}"
        for source in sources
        for module in _imported_modules(source)
        if module == FORBIDDEN_PREFIX or module.startswith(f"{FORBIDDEN_PREFIX}.")
    ]

    assert sources, f"{layer} 계층의 모듈을 못 찾으면 이 검사가 빈 목록으로 통과한다"
    assert offenders == [], f"{layer} 계층이 runner 를 import 합니다 — {offenders}"

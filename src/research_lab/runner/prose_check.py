"""단계가 낸 산문이 «저장소 밖에서도 읽히는지» 보고, 아니면 그 단계를 막는다.

근거 문서의 1순위 제약은 「다른 문서를 한 장도 열지 않고 판단할 수 있어야 한다」이고,
그 제약이 깨지는 자리는 **에이전트가 쓴 산문**이다. 러너가 만드는 고정 문구는 이미
테스트가 고정하고 있었지만 산문은 아무도 보지 않았다.

[중요] **자리가 「조립 직전」이 아니라 「단계마다」다.** 조립은 회차의 마지막 단계라,
거기서 막으면 **이미 굳은 앞 단계 산출물**을 두고 실패한다 — 다음 회차는 마지막 단계만
다시 돌고 그 산출물은 그대로이므로 **같은 자리에서 똑같이 실패하고, 세 번이면 후보가
원장에서 걷힌다.** 고칠 수 없는 실패를 만드는 게이트는 규율을 지키는 것이 아니라
멀쩡한 후보를 버리는 것이다.

> **[실측 2026-09-15]** 실제로 그렇게 만들었다가 되돌렸다. 한 회차의 메커니즘 산출물과
> 판정 산출물에 「이 스킬」이 들어 있었고, 조립부에서 막으니 그 후보는 **영구히 완성 불가**가 됐다.

[중요] 단계마다 걸면 **위반한 그 단계가 실패하고, 다음 회차가 그 단계를 다시 돈다.**
검사는 문자열 훑기라 비용이 사실상 0 이므로 단계마다 도는 것이 문제가 되지 않는다.
"""

from pathlib import Path
from typing import Any, Final

from research_lab.gate import selfcontained
from research_lab.runner import decision_log
from research_lab.runner.steps import StepQualityFailed

GATE_NAME: Final = "selfcontained"

# 검사에서 «빼는» 열쇠 — 그 값이 근거 문서에 실리지 않거나, 실려도 고칠 수 없는 자리.
#
# [중요] 이 목록이 없으면 **고칠 수 없는 실패**가 생긴다. 이 모듈이 조립부에서 옮겨 온
# 이유가 바로 그것인데, 범위를 안 좁히면 자리만 바뀌고 같은 고장이 남는다.
#
# | 열쇠 | 왜 빼나 |
# | --- | --- |
# | `claim` | 단계마다 **원장의 한 줄 주장을 그대로 되받아 적는다.** 원장은 append-only 라 그 단계가 고칠 수 없다 |
# | `queries` | 던진 검색어 기록이다. 문서에 실리지 않고, 남의 글 제목이 그대로 들어온다 |
# | `url` · `identifier` | 주소와 짧은 이름이다. 사람이 읽는 산문이 아니다 |
SKIPPED_KEYS: Final = frozenset({"claim", "queries", "url", "identifier"})

# 중첩을 훑을 깊이 상한. 산출물은 「절 안의 목록 안의 사전」 정도라 이 깊이면 넉넉하다
_MAX_DEPTH: Final = 8


def assert_self_contained(run_dir: Path, step: str, payload: Any, *, what: str) -> None:
    """그 단계의 산출물이 함께 가지 않는 것을 가리키면 막는다.

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 부르는 단계 이름. 결정 로그에 그대로 적힌다
        payload: 그 단계가 낸 산출물 전부
        what: 사유 앞에 붙일 말 (예: 「메커니즘 산출물」)

    Raises:
        StepQualityFailed: 가리키는 말이 들어 있을 때

    [중요] 산출물을 **통째로 직렬화해** 훑되 `SKIPPED_KEYS` 는 뺀다. 어느 열쇠가 문서의
    어느 줄이 되는지는 조립부만 아는데 여기서 그 대응을 다시 적으면 **두 벌이 되어 한쪽이
    낡는다.** 열쇠 이름은 전부 영문이라 사전에 걸리지 않는다.
    """
    reason = selfcontained.shortfall_reason({what: _scannable(payload)})
    if reason is None:
        return

    decision_log.record(run_dir, step, decision_log.EVENT_FAILED, gate=GATE_NAME, reason=reason)
    raise StepQualityFailed(reason)


def _scannable(value: Any, *, depth: int = 0) -> str:
    """산출물에서 «사람이 읽는 산문»만 한 덩어리 문자열로 만든다.

    [중요] 깊이 상한을 둔다. 에이전트가 낸 값이라 구조를 보장할 수 없고,
    **검사 때문에 그 회차가 멈추면 안 된다** — 판정을 못 하는 것과 실패로 판정하는 것은 다르다.
    상한에 닿으면 그 아래는 안 본다(통과 쪽으로 떨어진다).
    """
    if depth > _MAX_DEPTH:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_scannable(item, depth=depth + 1) for key, item in value.items() if key not in SKIPPED_KEYS)
    if isinstance(value, list | tuple):
        return " ".join(_scannable(item, depth=depth + 1) for item in value)
    return ""

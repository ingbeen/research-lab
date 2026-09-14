"""`claude -p` 를 부르는 계층.

**어느 단계가 자기를 쓰는지 몰라야 한다.** 「탐색」과 「수집」이 같은 이 계층을 쓰며,
단계가 늘어도 여기는 안 바뀌는 것이 정상이다. 한 단계 때문에 이 계층이 특수해지면
다음 단계에서 다시 갈라진다.

[미검증] `--output-format json` 의 «정확한» 응답 모양과, 한도 소진 시의 실패 모양은
아직 실측되지 않았다. 그래서 파싱은 **아는 열쇠만 꺼내 보고 없으면 None 으로 두며,
원문은 언제나 통째로 들고 나간다** — 처음 부딪히는 날 그 원문이 답이 된다.
"""

import json
import subprocess
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from research_lab.agent.billing_guard import assert_subscription_only
from research_lab.runner.steps import StepFailed

CLAUDE_BINARY: Final = "claude"

# 에이전트에게 주는 도구. **필요한 것만 준다.**
# 아티팩트 도구를 주지 않는 이유는 전역 규칙대로 산출물이 «파일»이어야 하기 때문이다 —
# 아티팩트는 VSCode diff 흐름 밖이고, 무인 실행에서는 볼 사람도 없다
DEFAULT_TOOLS: Final = ("WebSearch", "WebFetch", "Read", "Write", "Glob", "Grep")

# [중요] **쓰지 않는 플래그.** 코드 주석이 아니라 이 계층의 계약으로 박는다.
#
# - `--no-session-persistence`: 세션 로그가 안 남아 **폭주 감지 fallback 이 통째로 사라진다**
# - `--disable-slash-commands`: 이 저장소가 소유한 리서치 스킬이 안 뜨는데
#   **에러는 안 난다.** 문서는 그럴듯하게 나오고, 소스 독립성·반증·1차 출처 규율만 사라진다
FORBIDDEN_FLAGS: Final = ("--no-session-persistence", "--disable-slash-commands")

# 토큰 집계에 «넣는» 필드. 캐시에서 읽은 토큰은 일부러 뺀다 — 아래 `_new_tokens` 참고
COUNTED_USAGE_KEYS: Final = ("input_tokens", "output_tokens", "cache_creation_input_tokens")


class AgentInvocationError(RuntimeError):
    """에이전트 호출 자체가 성립하지 않을 때 (바이너리 없음 등)."""


@dataclass(frozen=True)
class AgentResult:
    """한 번의 호출이 남긴 것.

    `raw` 는 언제나 채워진다. 나머지는 응답 모양이 바뀌면 None 이 될 수 있고,
    **그때도 파이프라인은 멈추지 않아야 한다.**
    """

    text: str
    raw: str
    cost_usd: float | None
    tokens: int | None
    elapsed_seconds: float
    session_id: str


def build_command(
    *,
    prompt: str,
    session_id: str,
    budget_usd: float,
    tools: Sequence[str] = DEFAULT_TOOLS,
    json_schema: str | None = None,
) -> list[str]:
    """호출 인자를 만든다.

    실행과 분리된 순수 함수다 — 인자 구성은 계약이고, 계약은 돌려보지 않고도 검사돼야 한다.

    Args:
        prompt: 에이전트에게 줄 지시
        session_id: **미리 정한** UUID. 출력에서 긁어낼 필요가 없고, 끊겼을 때 이 값으로 되붙는다
        budget_usd: 폭주 감지용 상한. **0 을 줄 수 없다** (아래 Raises)
        tools: 줄 도구 목록
        json_schema: 응답 모양을 강제할 JSON Schema. **이 계층은 그 내용을 모른다** —
            어느 단계가 어떤 모양을 원하는지는 부르는 쪽이 정하고, 여기는 값이 있을 때만
            플래그를 붙인다. 한 단계 때문에 이 계층이 특수해지면 다음 단계에서 다시 갈라진다

    Returns:
        `subprocess` 에 그대로 넘길 인자 목록

    Raises:
        ValueError: `budget_usd` 가 0 이하일 때. 0 은 **잘못된 레버**다 —
            구독 인증에서 무시되면 아무것도 안 막고, 강제되면 0달러라 한 줄도 못 돈다.
            과금을 막는 것은 이 값이 아니라 `billing_guard` 다
    """
    if budget_usd <= 0:
        raise ValueError(
            "budget_usd 는 0보다 커야 합니다. 0 은 구독에서 무시되거나(무의미) "
            "강제되면 파이프라인을 즉시 멈춥니다. 과금 방지는 billing_guard 가 하고, "
            "이 값은 «폭주 감지»용입니다."
        )

    command = [
        CLAUDE_BINARY,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--session-id",
        session_id,
        "--permission-mode",
        "bypassPermissions",
        "--max-budget-usd",
        str(budget_usd),
        "--tools",
        ",".join(tools),
    ]

    if json_schema:
        # [주의] 스키마를 걸어도 `parse_json_answer` 의 관대한 파싱을 걷어내지 않는다.
        # 그쪽은 「모양이 어긋나도 멈추지 않는다」는 보험이고, 보험은 스키마가 있다고
        # 버릴 것이 아니다 — CLI 가 스키마를 무시하는 경우에도 회차가 돌아야 한다
        command.extend(["--json-schema", json_schema])

    return command


def new_session_id() -> str:
    """세션 ID 를 미리 정해 돌려준다."""
    return str(uuid.uuid4())


def parse_json_answer(result: AgentResult, *, what: str) -> dict[str, Any]:
    """에이전트의 답에서 JSON 객체를 꺼낸다.

    [실측 2026-09-12] 프롬프트에 「다른 말 없이 JSON 하나만 출력하세요」라고 적었는데도
    에이전트가 ```json 코드펜스로 감싸서 돌려줬다. 탐색과 수집 **둘 다** 그랬고,
    그 회차는 「JSON 이 아닙니다」로 세 번 재시도한 뒤 끝났다.
    루트 `CLAUDE.md` 의 「프롬프트로 지시한 규율은 형식적으로만 지켜진다」가 여기서도 맞았다 —
    **지시가 아니라 파서가 감당해야 한다.**

    Args:
        result: 에이전트 호출 결과
        what: 실패 메시지에 쓸 단계 이름 (「탐색」·「수집」)

    Returns:
        꺼낸 JSON 객체

    Raises:
        StepFailed: 객체를 못 꺼냈을 때. **원문을 통째로 실어 보낸다**
    """
    text = _unwrap(result.text)

    try:
        loaded: Any = json.loads(text)
    except json.JSONDecodeError as broken:
        raise StepFailed(f"{what} 응답에서 JSON 을 못 꺼냈습니다: {broken}\n--- 원문 ---\n{result.raw}") from broken

    if not isinstance(loaded, dict):
        raise StepFailed(f"{what} 응답이 객체가 아닙니다\n--- 원문 ---\n{result.raw}")
    return loaded


def _unwrap(text: str) -> str:
    """코드펜스와 앞뒤 군말을 벗긴다.

    바깥 중괄호 쌍을 잡는 방식이라, 펜스로 감쌌든 앞에 한마디 덧붙였든 같은 자리를 집는다.
    """
    stripped = text.strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        # 꺼낼 것이 없으면 원문 그대로 넘겨 호출자가 원문과 함께 실패를 올리게 한다
        return stripped

    return stripped[start : end + 1]


def invoke(
    *,
    prompt: str,
    cwd: Path,
    env: Mapping[str, str],
    budget_usd: float,
    session_id: str | None = None,
    tools: Sequence[str] = DEFAULT_TOOLS,
    json_schema: str | None = None,
    timeout_seconds: float = 1800.0,
) -> AgentResult:
    """에이전트를 한 번 부른다.

    Args:
        prompt: 에이전트에게 줄 지시
        cwd: 실행 디렉터리. 이 저장소여야 `.claude/skills/` 의 리서치 스킬이 뜬다
        env: 넘길 환경변수. **통째로 물려주지 않고 부르는 쪽이 골라 넘긴다**
        budget_usd: 폭주 감지용 상한
        session_id: 미리 정한 UUID. 없으면 새로 만든다
        tools: 줄 도구 목록
        json_schema: 응답 모양을 강제할 JSON Schema. 부르는 쪽이 정한다
        timeout_seconds: 이 시간을 넘기면 끊는다

    Returns:
        응답과 비용·토큰·소요 시간

    Raises:
        billing_guard.BillingGuardError: 환경에 API 키가 있을 때
        AgentInvocationError: 호출 자체가 성립하지 않을 때
        StepFailed: 에이전트가 실패를 돌려줬을 때 — 분류는 러너가 한다
    """
    # 가장 앞에서 막는다. 넘길 환경을 «넘기기 전에» 본다
    assert_subscription_only(env)

    resolved_session = session_id or new_session_id()
    command = build_command(
        prompt=prompt,
        session_id=resolved_session,
        budget_usd=budget_usd,
        tools=tools,
        json_schema=json_schema,
    )

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=dict(env),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as missing:
        raise AgentInvocationError(f"{CLAUDE_BINARY} 를 찾을 수 없습니다. 컨테이너에 Claude Code 가 설치됐는지 확인하세요.") from missing
    except subprocess.TimeoutExpired as timed_out:
        # 시간 초과는 「그 외」 실패다. 분류는 러너가 하므로 원문만 실어 보낸다
        raise StepFailed(f"timeout after {timeout_seconds}s: {timed_out}") from timed_out

    elapsed = time.monotonic() - started
    raw = completed.stdout or ""

    if completed.returncode != 0:
        # [중요] stdout 과 stderr 을 **둘 다** 싣는다. 실패 모양이 아직 [미검증] 이라
        # 어느 쪽에 단서가 있을지 모르고, 잘라 내면 처음 부딪히는 날 답을 못 얻는다
        raise StepFailed(
            f"exit={completed.returncode}\n" f"--- stdout ---\n{raw}\n" f"--- stderr ---\n{completed.stderr}"
        )

    return _parse(raw=raw, elapsed=elapsed, session_id=resolved_session)


def _parse(*, raw: str, elapsed: float, session_id: str) -> AgentResult:
    """응답을 읽되, 모양이 달라도 «멈추지 않는다».

    아는 열쇠만 꺼내 보고 없으면 None 으로 둔다. 응답 모양이 바뀌었을 때
    **파이프라인이 죽는 것보다 「그 값을 모른다」로 남는 편이 낫다** —
    원문은 어차피 통째로 보존되므로 나중에 다시 읽을 수 있다.
    """
    payload: dict[str, Any] = {}
    try:
        loaded: Any = json.loads(raw)
        if isinstance(loaded, dict):
            payload = loaded
    except json.JSONDecodeError:
        pass

    # [중요] 종료 코드만 보면 «성공으로 끝난 실패»를 놓친다. CLI 가 결과 안에
    # `is_error` 를 실어 보내면서 0 으로 끝나는 경우가 있고, 그때 이 계층이 통과시키면
    # 실패가 한참 뒤 파싱 단계에서 「JSON 이 아닙니다」라는 **엉뚱한 진단**으로 튀어나온다.
    # 여기서 잡아야 원문이 붙은 채로 러너의 분류기에 닿는다
    if payload.get("is_error") is True:
        raise StepFailed(f"agent reported is_error\n--- 원문 ---\n{raw}")

    cost = payload.get("total_cost_usd")

    # [실측 2026-09-14] `--json-schema` 를 걸면 CLI 가 **파싱된 객체**를 이 필드에 함께 싣는다.
    # 그쪽을 먼저 쓰면 산문이나 코드펜스로 파싱이 깨질 여지가 구조적으로 사라진다 —
    # 스키마를 켜는 이유가 바로 그것이다. 스키마가 없으면 이 필드가 없어 `result` 로 돌아간다
    structured = payload.get("structured_output")
    answer = structured if isinstance(structured, dict | list) else payload.get("result", raw)

    return AgentResult(
        text=_answer_text(answer),
        raw=raw,
        cost_usd=float(cost) if isinstance(cost, int | float) else None,
        tokens=_new_tokens(payload.get("usage")),
        elapsed_seconds=elapsed,
        session_id=str(payload.get("session_id", session_id)),
    )


def _answer_text(answer: Any) -> str:
    """답을 «파싱할 수 있는» 문자열로 만든다.

    [중요] `str()` 로 바로 찍지 않는다. `--json-schema` 로 모양을 강제하면 CLI 가 답을
    **문자열이 아니라 객체로** 실어 보낼 수 있는데, 파이썬이 dict 를 문자열로 만들면
    작은따옴표 표기(`{'ok': True}`)가 되어 **JSON 으로 다시 읽히지 않는다.**

    그러면 그 회차는 「JSON 을 못 꺼냈습니다」로 실패하고 「그 외」로 분류돼 상한까지
    재시도한다 — **모양을 «강제하려고» 켠 플래그가 정확히 그 모양 때문에 회차를 태우는**
    자리이고, 원문만 봐서는 원인이 파서인지 에이전트인지 갈리지 않는다.

    [주의] 스키마를 켜지 않아도 이 가드를 둔다. 응답 모양은 CLI 가 정하는 것이라
    언제 바뀌어도 이상하지 않고, **바뀌는 날 이 가드가 없으면 조용히 재시도만 돈다.**
    """
    if isinstance(answer, dict | list):
        return json.dumps(answer, ensure_ascii=False)
    return str(answer)


def _new_tokens(usage: Any) -> int | None:
    """그 호출이 «새로» 쓴 토큰을 센다.

    [중요] `usage` 의 정수를 전부 더하면 안 된다. 캐시에서 읽은 토큰
    (`cache_read_input_tokens`)이 함께 들어가는데, 프롬프트 캐시가 도는 상황에서는
    그 값이 새 입력 토큰보다 한 자릿수 크다. 그대로 더하면 5천 토큰 쓴 단계가
    8만으로 기록되고, **이 값을 근거로 정할 회차 예산이 그 배수만큼 틀어진다.**
    이름을 나열해 세는 이유는 CLI 가 나중에 더할 새 정수 필드까지 조용히 삼키지 않기 위해서다.
    """
    if not isinstance(usage, dict):
        return None

    counted = [usage.get(name) for name in COUNTED_USAGE_KEYS]
    known = [value for value in counted if isinstance(value, int)]
    return sum(known) if known else None

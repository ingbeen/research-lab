"""`claude -p` 호출 인자의 계약을 고정한다.

인자 구성은 계약이고, 계약은 **돌려보지 않고도** 검사돼야 한다.
그래서 인자를 만드는 일과 실행하는 일을 나눠 두었다.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from research_lab.agent import invoke
from research_lab.runner.steps import StepFailed


def _command(**overrides: object) -> list[str]:
    """기본값으로 인자를 만들고 필요한 것만 바꾼다."""
    kwargs: dict[str, object] = {
        "prompt": "무엇을 해라",
        "session_id": "11111111-2222-3333-4444-555555555555",
        "budget_usd": 2.0,
    }
    kwargs.update(overrides)
    return invoke.build_command(**kwargs)  # type: ignore[arg-type]


def test_runs_in_print_mode() -> None:
    """
    목적: 무인 실행에 필요한 `-p` 가 빠지지 않는 계약을 고정한다.

    `-p` 가 없으면 대화형으로 떠서 **아무도 없는 회차에 입력을 기다린다.**

    Given: 기본 인자
    When: 명령을 만든다
    Then: `-p` 가 들어 있다
    """
    assert "-p" in _command()


def test_asks_for_json_output() -> None:
    """
    목적: 러너가 파싱할 수 있는 형식을 요구하는 계약을 고정한다.

    Given: 기본 인자
    When: 명령을 만든다
    Then: `--output-format json` 이 들어 있다
    """
    command = _command()

    assert command[command.index("--output-format") + 1] == "json"


def test_permission_prompts_are_disabled() -> None:
    """
    목적: 승인창이 뜨지 않게 하는 계약을 고정한다.

    무인 실행에서 승인창이 뜨면 프로세스가 그냥 멈춘다 — 실패가 아니라 «정지»라
    나중에야 알아챈다.

    Given: 기본 인자
    When: 명령을 만든다
    Then: `--permission-mode bypassPermissions` 가 들어 있다
    """
    command = _command()

    assert command[command.index("--permission-mode") + 1] == "bypassPermissions"


def test_session_id_is_given_not_scraped() -> None:
    """
    목적: 세션 ID 를 «미리 정해» 넘기는 계약을 고정한다.

    출력에서 긁어내면 출력 형식이 바뀌는 날 되붙기가 조용히 깨진다.

    Given: 미리 정한 세션 ID
    When: 명령을 만든다
    Then: 그 값이 그대로 들어 있다
    """
    command = _command(session_id="abc-123")

    assert command[command.index("--session-id") + 1] == "abc-123"


def test_tools_are_narrowed() -> None:
    """
    목적: 도구를 좁혀 주는 계약을 고정한다.

    bypass 모드라 도구가 넓으면 사정거리도 넓어진다.

    Given: 기본 인자
    When: 명령을 만든다
    Then: `--tools` 로 목록이 넘어간다
    """
    command = _command()

    assert command[command.index("--tools") + 1] == ",".join(invoke.DEFAULT_TOOLS)


def test_model_is_pinned_by_full_id() -> None:
    """
    목적: 모델을 «전체 ID»로 고정하는 계약을 고정한다.

    지정하지 않으면 CLI 기본값을 따르고, 별칭(`opus`)을 쓰면 다음 모델이 나오는 날
    가리키는 대상이 바뀐다 — 둘 다 **에러 없이** 회차의 모델이 달라진다.

    Given: 기본 인자
    When: 명령을 만든다
    Then: `--model` 이 전체 ID 로 들어 있다
    """
    command = _command()

    assert command[command.index("--model") + 1] == "claude-opus-5-5"


def test_effort_is_explicit() -> None:
    """
    목적: effort 를 명시하는 계약을 고정한다.

    Opus 5.5 는 effort 를 안 주면 `medium` 으로 돈다 — 모델을 올리면서 effort 는
    오히려 내려가는데 **에러는 안 난다.**

    Given: 기본 인자
    When: 명령을 만든다
    Then: `--effort xhigh` 가 들어 있다
    """
    command = _command()

    assert command[command.index("--effort") + 1] == "xhigh"


def test_artifact_tool_is_not_granted() -> None:
    """
    목적: 산출물이 «파일»로 남게 하는 계약을 고정한다.

    아티팩트는 VSCode diff 흐름 밖이고, 무인 실행에서는 볼 사람도 없다.

    Given: 기본 도구 목록
    When: 목록을 본다
    Then: 아티팩트 도구가 없다
    """
    assert not any("artifact" in tool.lower() for tool in invoke.DEFAULT_TOOLS)


@pytest.mark.parametrize("budget", [0, -1.0])
def test_zero_budget_is_rejected(budget: float) -> None:
    """
    목적: `--max-budget-usd 0` 을 «잘못된 레버»로 거부하는 계약을 고정한다.

    0 은 구독 인증에서 **무시되면** 아무것도 안 막고, **강제되면** 0달러라 한 줄도 못 돈다.
    둘 다 나쁘다. 과금을 막는 것은 이 값이 아니라 과금 가드다.

    Given: 0 이하의 예산
    When: 명령을 만든다
    Then: 예외가 오른다
    """
    with pytest.raises(ValueError, match="budget_usd"):
        _command(budget_usd=budget)


@pytest.mark.parametrize("flag", invoke.FORBIDDEN_FLAGS)
def test_forbidden_flags_are_never_passed(flag: str) -> None:
    """
    목적: 켜면 «조용히» 망가지는 플래그가 들어가지 않는 계약을 고정한다.

    - `--no-session-persistence`: 세션 로그가 안 남아 폭주 감지 fallback 이 사라진다
    - `--disable-slash-commands`: 리서치 스킬이 안 뜨는데 **에러는 안 난다.**
      문서는 그럴듯하게 나오고 소스 독립성·반증·1차 출처 규율만 사라진다

    Given: 기본 인자
    When: 명령을 만든다
    Then: 그 플래그가 없다
    """
    assert flag not in _command()


def test_session_ids_are_unique() -> None:
    """
    목적: 새 세션 ID 가 매번 달라지는 계약을 고정한다.

    같은 ID 를 다시 쓰면 지난 회차의 맥락이 딸려 들어와, 후보 하나만 봐야 할 단계가
    다른 후보의 맥락을 물고 판단한다.

    Given: 두 번의 발급
    When: 값을 비교한다
    Then: 서로 다르다
    """
    assert invoke.new_session_id() != invoke.new_session_id()


def _run_with(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: Any) -> StepFailed:
    """`subprocess.run` 을 가로채 한 번 부르고, 올라온 실패를 돌려준다.

    [중요] 진짜 `claude` 를 부르지 않는다 — 토큰을 쓰고, 한도에 걸린 모양은 일부러 만들 수 없다.
    """

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        if isinstance(outcome, BaseException):
            raise outcome
        return subprocess.CompletedProcess(command, outcome[0], stdout=outcome[1], stderr="")

    monkeypatch.setattr(invoke.subprocess, "run", fake_run)
    with pytest.raises(StepFailed) as raised:
        invoke.invoke(prompt="무엇을 해라", cwd=tmp_path, env={}, budget_usd=1.0)
    return raised.value


def test_nonzero_exit_carries_what_the_call_spent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    목적: 종료 코드가 0 이 아닌 호출도 응답에 적힌 비용을 실패와 함께 나르는 계약을 고정한다.

    [실측] 예산 상한($2.4330) · 단계 도중 한도($0.9002) 가 이 경로로 끝났고, 둘 다
    **stdout 에 비용이 적힌 JSON 이 있었는데** 결정 로그의 비용 줄에는 남지 않았다.

    Given: 종료 코드 1 과 비용이 든 JSON stdout
    When: 호출한다
    Then: 실패가 오르고 그 비용 · 토큰을 싣는다. 원문 모양(`exit=` · `--- stdout ---`)은 그대로다
    """
    stdout = json.dumps(
        {"is_error": True, "total_cost_usd": 2.4330374, "session_id": "세션-가", "usage": {"output_tokens": 30}}
    )

    failed = _run_with(monkeypatch, tmp_path, (1, stdout))

    assert failed.spent is not None
    assert failed.spent.cost_usd == 2.4330374
    assert failed.spent.tokens == 30
    assert failed.raw.startswith("exit=1\n--- stdout ---\n"), "분류표와 사람이 읽는 원문 모양을 바꾸지 않는다"


def test_nonzero_exit_without_json_carries_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    목적: stdout 이 JSON 이 아니면 «모른다»로 남는 계약을 고정한다.

    지어낸 0 을 실으면 「재서 0」으로 읽혀 **돈을 안 쓴 것처럼** 보인다.

    Given: 종료 코드 1 과 JSON 이 아닌 stdout
    When: 호출한다
    Then: 실패가 오르고 실어 보낸 것이 없다
    """
    failed = _run_with(monkeypatch, tmp_path, (1, "알 수 없는 오류로 죽었습니다"))

    assert failed.spent is None


def test_timeout_carries_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    목적: 시간 초과로 끊긴 호출은 «모른다»로 남는 계약을 고정한다.

    끊긴 CLI 는 응답을 못 낸다. 쓴 돈은 있지만 알 방법이 없고, 그것을 0 으로 적으면 거짓이다.

    Given: 시간 초과로 끊기는 호출
    When: 호출한다
    Then: 실패가 오르고 실어 보낸 것이 없다
    """
    failed = _run_with(monkeypatch, tmp_path, subprocess.TimeoutExpired(cmd="claude", timeout=1800.0))

    assert failed.spent is None

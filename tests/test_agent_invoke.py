"""`claude -p` 호출 인자의 계약을 고정한다.

인자 구성은 계약이고, 계약은 **돌려보지 않고도** 검사돼야 한다.
그래서 인자를 만드는 일과 실행하는 일을 나눠 두었다.
"""

import pytest

from research_lab.agent import invoke


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

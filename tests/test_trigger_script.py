"""예약 트리거 제어 스크립트(`scripts/trigger.sh`)의 계약을 고정한다.

[중요] 이 파일은 **셸 스크립트가 품질 검증에서 통째로 빠지기 때문에** 있다.
`validate_project.py` 는 Ruff + PyRight + Pytest 라 `.sh` 를 하나도 보지 않는다.
전역 규칙이 경고하는 「검증 장치가 없는 자리」이고, **없으면 실수가 조용히 남는다.**

[주의] 여기 담는 것은 **실제 `launchctl` 을 건드리지 않는 것뿐**이다.
테스트가 예약을 끄면 그날 회차가 통째로 빠지고, 그 사실은 다음 날 아침에야 드러난다.
`launchctl` 호출부의 검증은 자동화하지 않고 계획서의 실기계 왕복 검증이 맡는다 —
**그래서 이 파일이 초록이어도 「스크립트가 동작한다」는 뜻이 아니다.**
"""

import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "trigger.sh"

# 예약 작업의 라벨. 이 문자열이 틀리면 «엉뚱한 서비스»를 끄거나 아무것도 안 하면서
# 성공으로 보고한다 — launchctl 은 모르는 라벨에 조용히 실패하는 경로가 있다
EXPECTED_LABEL = "local.research-lab.cycle"

# 코드 파일에 들어가면 안 되는 문자의 코드포인트 범위.
# 전역 규칙 「코드 파일에는 이모지를 쓰지 않는다」가 원본이다.
#
# [중요] 범위를 «숫자»로 적는다. 정규식 리터럴로 적으면 그 리터럴 자체가 이모지를 품어
# 이 파일이 자기 검사에 걸린다 — 실제로 걸렸다.
#
#   U+FE0F              변이선택자. 경고 기호에 붙어 오는 형태를 잡는다
#   U+1F000~U+1FAFF     이모지 평면
#   U+2700~U+27BF       Dingbats
#
# 활자 기호(U+2605 별표 · U+203B 참고표 · U+2192 화살표)는 **일부러 뺐다** — 폭과 인코딩이
# 안정적이라 전역 규칙이 허용한다. 블록을 넓게 잡으면 그 문자들까지 막혀 규칙보다 엄해진다
EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0xFE0F, 0xFE0F),
    (0x1F000, 0x1FAFF),
    (0x2700, 0x27BF),
)


def _emoji_in(text: str) -> list[str]:
    """이모지로 판정되는 문자만 골라낸다."""
    return [char for char in text if any(low <= ord(char) <= high for low, high in EMOJI_RANGES)]


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """스크립트를 부르고 결과를 그대로 돌려준다."""
    return subprocess.run(
        ["/bin/bash", str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def test_script_exists_and_is_executable() -> None:
    """
    목적: 스크립트가 있고 «직접 실행»할 수 있음을 고정한다.

    문서가 `./scripts/trigger.sh` 형태로 안내하므로, 실행 권한이 없으면
    문서를 그대로 따라 한 사람이 `Permission denied` 를 만난다.

    Given: 저장소
    When: 스크립트 파일을 본다
    Then: 존재하고 실행 권한이 있다
    """
    assert SCRIPT_PATH.is_file(), f"트리거 제어 스크립트가 없습니다: {SCRIPT_PATH}"
    assert SCRIPT_PATH.stat().st_mode & 0o111, "실행 권한이 없으면 문서의 안내(`./scripts/trigger.sh`)가 그대로 실패한다"


def test_script_passes_syntax_check() -> None:
    """
    목적: [중요] 문법 오류가 «커밋되지 않게» 고정한다.

    셸 스크립트는 문법이 깨져도 **부르기 전까지 아무도 모른다.** 그리고 이 스크립트를
    부르는 시점은 대개 「예약을 급히 꺼야 할 때」라, 그 자리에서 터지면 가장 곤란하다.
    `bash -n` 은 실행하지 않고 파싱만 하므로 안전하다.

    Given: 스크립트
    When: 문법 검사를 돌린다
    Then: 통과한다
    """
    checked = subprocess.run(
        ["/bin/bash", "-n", str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert checked.returncode == 0, f"셸 문법 오류:\n{checked.stderr}"


@pytest.mark.parametrize("args", [[], ["잘못된명령"], ["off", "덤"], ["--help"]])
def test_bad_arguments_are_rejected(args: list[str]) -> None:
    """
    목적: 모르는 인자를 «돌기 전에» 거부하는 계약을 고정한다.

    이 스크립트는 예약을 끄고 켠다. 인자를 잘못 줬을 때 「아무 일도 안 하고 0 으로 끝나면」
    **껐다고 믿는데 안 꺼진 상태**가 되고, 그것이 이 작업을 하게 만든 사고와 정확히 같은 모양이다.

    Given: 인자가 없거나 정의되지 않은 인자
    When: 스크립트를 부른다
    Then: 비정상 종료하고 사용법을 알린다
    """
    result = _run(*args)

    assert result.returncode != 0, f"모르는 인자({args})를 성공으로 끝내면 「안 꺼졌는데 껐다고 믿는」 상태가 생긴다"
    assert (
        "off" in result.stderr and "on" in result.stderr and "status" in result.stderr
    ), "무엇을 해야 하는지 알 수 있어야 한다 — 전역 규칙 「사용자 중심」"


def test_argument_check_comes_before_any_launchctl_call() -> None:
    """
    목적: [중요] 인자 검증이 `launchctl` 호출보다 «앞»임을 고정한다.

    순서가 반대면 잘못된 인자로 불렀을 때 이 파일의 다른 테스트들이 **기계마다 다르게**
    동작한다 — launchctl 이 없는 곳(WSL·컨테이너)에서는 플랫폼 오류로, 있는 곳에서는
    사용법으로 끝난다. 그러면 「인자를 거부한다」는 계약이 실제로는 검사되지 않는다.

    `PATH` 를 비우면 `launchctl` 을 찾을 수 없다. 그 상태에서도 사용법이 나와야
    인자 검증이 먼저라는 뜻이다.

    Given: launchctl 을 찾을 수 없는 환경
    When: 정의되지 않은 인자로 부른다
    Then: 플랫폼 오류가 아니라 «사용법»으로 끝난다
    """
    result = _run("잘못된명령", env={"PATH": ""})

    assert result.returncode != 0
    assert "off" in result.stderr, "launchctl 을 못 찾는 환경에서도 인자 오류는 사용법으로 끝나야 한다"


def test_the_label_matches_the_scheduled_job() -> None:
    """
    목적: 제어 대상 라벨이 «예약 작업의 것»과 같음을 고정한다.

    라벨에 오타가 있으면 `launchctl` 이 엉뚱한 이름을 찾는다. 그 실패는
    「이미 꺼져 있다」와 구별하기 어려워, **끄는 명령이 조용히 아무 일도 안 할 수 있다.**

    Given: 스크립트 소스
    When: 라벨을 찾는다
    Then: 예약 작업의 라벨과 정확히 같다
    """
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert EXPECTED_LABEL in source, f"제어 대상 라벨이 «{EXPECTED_LABEL}» 이어야 한다"


def _shell_function_body(source: str, name: str) -> str:
    """셸 함수 하나의 본문을 잘라낸다.

    [중요] 파일 전체를 훑으면 «안내 메시지»에 든 같은 명령(「직접 내리려면: launchctl …」)이
    호출로 잡힌다. 그러면 실제 호출을 지워도 테스트가 초록이라 검사가 무의미해진다.
    """
    opening = f"{name}() {{"
    assert opening in source, f"셸 함수 «{name}» 을 찾을 수 없습니다"
    start = source.index(opening)
    return source[start : source.index("\n}", start)]


def test_off_does_both_halves_of_turning_it_off() -> None:
    """
    목적: [중요] `off` 가 `disable` «과» `bootout` 을 둘 다 거는 계약을 고정한다.

    이 계획서가 존재하는 이유 자체다. 하나만 하면 절반만 꺼지는데 **에러가 나지 않는다** —
    `bootout` 만 하면 재부팅에서 되살아나고(2026-09-16 에 실제로 사흘 돌았다),
    `disable` 만 하면 지금 세션에서 그대로 돈다.

    이 검사가 없으면 호출 한 줄을 지워도 나머지 테스트가 전부 초록이다.

    Given: 끄기 함수의 본문
    When: launchctl 호출을 찾는다
    Then: 두 동작이 모두 있다
    """
    body = _shell_function_body(SCRIPT_PATH.read_text(encoding="utf-8"), "do_off")

    assert 'launchctl disable "$SERVICE"' in body, "disable 이 없으면 재부팅에서 되살아난다"
    assert 'launchctl bootout "$SERVICE"' in body, "bootout 이 없으면 지금 세션에서 그대로 돈다"


def test_on_enables_before_bootstrapping() -> None:
    """
    목적: [중요] `on` 이 `enable` 을 `bootstrap` «보다 먼저» 부르는 계약을 고정한다.

    [실측 2026-09-21] disabled 인 채로 bootstrap 하면 `Bootstrap failed: 5: Input/output error`
    로 거부된다. 순서가 뒤집히면 **예전에 껐던 기계에서 켜기가 영영 실패하고**,
    그 실패는 「정의 파일이 잘못됐나」로 읽혀 엉뚱한 곳을 보게 만든다.

    Given: 켜기 함수의 본문
    When: 두 호출의 위치를 견준다
    Then: enable 이 먼저다
    """
    body = _shell_function_body(SCRIPT_PATH.read_text(encoding="utf-8"), "do_on")

    assert 'launchctl enable "$SERVICE"' in body, "enable 이 없으면 예전에 껐던 기계에서 켜지지 않는다"
    assert 'launchctl bootstrap "$DOMAIN"' in body

    assert body.index('launchctl enable "$SERVICE"') < body.index(
        'launchctl bootstrap "$DOMAIN"'
    ), "disabled 인 채로 bootstrap 하면 Input/output error 로 거부된다"


def test_the_script_carries_no_emoji() -> None:
    """
    목적: 코드 파일에 이모지가 «없음»을 고정한다.

    전역 훅이 편집 시점에 막지만, **훅은 저장소 밖에 있어 이 저장소를 다른 기계로 옮기면
    따라오지 않는다.** 이 저장소는 WSL 과 mac 을 오가므로 그 구멍이 실재한다.

    Given: 스크립트 소스
    When: 이모지를 찾는다
    Then: 하나도 없다
    """
    found = _emoji_in(SCRIPT_PATH.read_text(encoding="utf-8"))

    assert not found, f"코드 파일에는 이모지 대신 대괄호 표기를 쓴다 — 발견: {found}"

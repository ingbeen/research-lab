#!/usr/bin/env python3
"""회차 하나를 돌린다 — 이 저장소의 유일한 진입점.

무인 실행이라 **아무도 화면을 보지 않는다.** 그래서 결과를 종료 코드로 가르고,
과정은 그 회차의 실행 폴더에 파일로 남긴다.

사용법은 `docs/COMMANDS.md` 가 SoT다.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research_lab.agent import invoke  # noqa: E402
from research_lab.agent.billing_guard import BillingGuardError, assert_subscription_only  # noqa: E402
from research_lab.common_constants import (  # noqa: E402
    BASE_DIR,
    KST,
    LEDGER_PATH,
    RUN_DIR_TIME_FORMAT,
    RUNS_DIR,
)
from research_lab.gate import secrets  # noqa: E402
from research_lab.runner import (  # noqa: E402
    collect,
    cycle,
    decision_log,
    dossier,
    explore,
    feasibility,
    lineage,
    measurement,
    mechanism,
    rebut,
    state,
    steps,
    verdict,
)
from research_lab.runner.failures import FailureKind  # noqa: E402

# 종료 코드. **무인 실행에서 사람이 받는 신호가 이것뿐**이라 갈래마다 다른 값을 준다.
# 전부 0 이나 1 로 뭉치면 「인증이 끊겨 며칠 안 돈 상태」와 「그냥 한도에 걸린 회차」가 구별되지 않는다
EXIT_OK: Final = 0
EXIT_INCOMPLETE: Final = 1  # 그 외 실패 — 다음 회차가 이어받는다
EXIT_LIMIT: Final = 2  # 한도 소진 — 정상이다. 재시도하지 않는다
EXIT_AUTH: Final = 3  # 인증·과금 거부 — 사람이 손대야 한다
EXIT_SECRET: Final = 4  # 자격증명 발견 — 그 회차를 실패로 만든다

# 한 단계에 거는 폭주 감지 상한.
#
# [미검증] 「한 단계가 정상적으로 쓸 양」을 아직 재지 못했다. 이 값은 **과금 방지가 아니라
# 폭주 감지**이며(과금은 `billing_guard` 가 막는다), 실측 뒤에 조정한다.
# 구독 인증에서 이 플래그가 실제로 동작하는지도 [미검증]이다
DEFAULT_BUDGET_USD: Final = 2.0

# 응답 모양을 스키마로 강제할 단계들.
#
# [실측 2026-09-14] `--json-schema` 는 인라인 JSON 이고 구독 인증에서 동작하며, 파싱된 객체를
# 응답의 `structured_output` 에 함께 실어 준다 — 산문·코드펜스로 파싱이 깨질 여지가 사라진다.
#
# [중요] **새로 붙인 세 단계에만 건다.** 앞의 다섯은 이미 실측으로 검증된 경로라,
# 갈아 끼우면 «돌던 것»을 새 플래그에 얹는 셈이 된다. 새 단계의 실측이 쌓인 뒤에 정한다
STEP_SCHEMAS: Final = {
    mechanism.STEP_NAME: mechanism.JSON_SCHEMA,
    measurement.STEP_NAME: measurement.JSON_SCHEMA,
    verdict.STEP_NAME: verdict.JSON_SCHEMA,
}

# 컨테이너·호스트에서 에이전트에게 물려줄 환경변수.
#
# [중요] 환경을 «통째로» 물려주지 않는다. 그러면 `ANTHROPIC_API_KEY` 가 조용히 딸려 들어간다.
# 넘길 것을 이름으로 나열하는 것이 그 사고를 구조적으로 막는 방법이다
PASSED_ENV_VARS: Final = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "CLAUDE_CODE_OAUTH_TOKEN")


def main(argv: list[str] | None = None) -> int:
    """회차를 돌고 결과를 종료 코드로 알린다."""
    args = _parse_args(argv)

    try:
        # 가장 앞에서 막는다. 한 줄이라도 돈 뒤에 막으면 이미 과금된 뒤다
        assert_subscription_only(os.environ)
    except BillingGuardError as blocked:
        print(f"[중지] {blocked}", file=sys.stderr)
        return EXIT_AUTH

    run_dir = _resolve_run_dir(args.run_dir)
    agent_env = _agent_env(os.environ)

    def ask_for(step: str) -> Callable[[str], invoke.AgentResult]:
        """그 단계에 맞는 호출자를 만든다.

        [중요] 스키마를 «단계마다» 다르게 건다. 그래서 어느 단계가 무엇을 내는지는
        여기가 아니라 그 단계가 알고, 호출 계층은 값이 있을 때만 플래그를 붙인다 —
        한 단계 때문에 호출 계층이 특수해지면 다음 단계에서 다시 갈라진다.
        """

        def ask(prompt: str) -> invoke.AgentResult:
            return invoke.invoke(
                prompt=prompt,
                cwd=BASE_DIR,
                env=agent_env,
                budget_usd=args.budget_usd,
                json_schema=STEP_SCHEMAS.get(step),
            )

        return ask

    def execute(step: str, current_run_dir: Path) -> None:
        dispatch(step, current_run_dir, ledger_path=args.ledger, ask=ask_for(step))

    try:
        result = cycle.run_cycle(run_dir=run_dir, ledger_path=args.ledger, execute=execute)
    except state.AlreadyRunningError as running:
        print(f"[중지] {running}", file=sys.stderr)
        return EXIT_INCOMPLETE

    # 산출물이 생긴 «뒤에» 검사한다. 검사기는 사후 장치이고, 여기가 마지막 그물이다
    findings = secrets.scan(secrets.scan_roots(run_dir, dossier_path=_dossier_of(run_dir)))
    if findings:
        for finding in findings:
            # 값은 싣지 않는다. 그 기록도 PUBLIC 저장소에 남는다
            print(f"[자격증명] {finding.path}:{finding.line_number} ({finding.rule})", file=sys.stderr)
        decision_log.record(run_dir, "gate", decision_log.EVENT_FAILED, secrets=len(findings))
        return EXIT_SECRET

    return _report(run_dir, result)


def dispatch(step: str, run_dir: Path, *, ledger_path: Path, ask: Callable[[str], invoke.AgentResult]) -> None:
    """이름으로 그 단계의 실행부를 부른다.

    [중요] **모듈 바깥에 둔 이유는 이 자리가 검사되어야 하기 때문이다.** 단계 목록에
    이름을 더하면서 여기 가지를 안 붙이면 회차가 그 자리에서 죽고, 이름을 잘못 적으면
    같은 일이 난다 — 둘 다 **에이전트를 부르고 난 뒤**에야 드러나던 자리였다.

    Args:
        step: 실행할 단계 이름
        run_dir: 그 회차의 실행 폴더
        ledger_path: 원장 경로. **원장을 고치는 단계에만 넘긴다**
        ask: 그 단계에 맞는 에이전트 호출자

    Raises:
        steps.StepNotImplementedError: 정의된 단계인데 실행부가 없을 때
    """
    if step == "explore":
        explore.run(run_dir, ledger_path, ask)
    elif step == "collect":
        collect.run(run_dir, ledger_path, ask)
    elif step == "rebut":
        # 원장을 안 받는다 — 이 단계는 그 회차의 후보를 «상태»에서 읽고 아무것도 표시하지 않는다.
        # 안 쓰는 인자를 받아 두면 「반증도 원장을 고친다」로 읽힌다
        rebut.run(run_dir, ask)
    elif step == "lineage":
        # 위와 같은 이유로 원장을 안 받는다. 「판 것」 표시는 마지막 단계의 일이다
        lineage.run(run_dir, ask)
    elif step == "feasibility":
        feasibility.run(run_dir, ask)
    elif step == "mechanism":
        mechanism.run(run_dir, ask)
    elif step == "measurement":
        measurement.run(run_dir, ask)
    elif step == "verdict":
        # 회차의 마지막 단계라 원장을 받는다 — 여기서 근거 문서를 조립하고
        # 후보를 「판 것」으로 표시한다
        verdict.run(run_dir, ledger_path, ask)
    else:
        # 단계 목록은 `steps.STEPS` 하나가 정한다. 여기 도달했다는 것은 그 목록에
        # 이름을 더하면서 실행부를 안 붙였다는 뜻이라, 조용히 넘기면 그 단계가
        # 「했다」로 기록된 채 아무 일도 안 일어난다
        raise steps.StepNotImplementedError(f"내부 불변조건 위반: 실행부가 없는 단계입니다 — {step}")


def _dossier_of(run_dir: Path) -> Path | None:
    """그 회차가 썼을 근거 문서의 경로. 후보가 안 박혔으면 None.

    [중요] 「이 회차가 쓴 문서 하나」만 자격증명 검사에 넣기 위해서다. 문서 폴더를 통째로
    넘기면 회차마다 한 장씩 쌓이는 그 폴더에서 **한 장이 한 번 걸린 뒤 이후 모든 회차가
    실패하고**, 무인 실행에는 그것을 치울 사람이 없다.

    경로는 계산으로 나온다 — 상태에 따로 적어 두면 그 값과 실제 파일이 갈릴 수 있고,
    갈렸다는 사실은 아무 에러도 내지 않는다. 아직 안 쓰인 경로는 「발견 없음」으로 다뤄진다.
    """
    try:
        candidate = state.pinned_candidate(run_dir)
        return dossier.path_for(run_dir, candidate) if candidate is not None else None
    except Exception:
        # [중요] **여기서 터뜨리면 「마지막 그물」이 통째로 안 쳐진다.** 완주한 회차가
        # 산출물을 다 만들어 놓고 자격증명 검사 «직전»에 죽으며, 종료 코드도 정해진
        # 다섯 중 어느 것도 아니게 되어 무인 실행에서는 무슨 일이 났는지 알 수 없다.
        #
        # 갈래를 좁혀 잡지 않는 이유는, 이름을 만드는 쪽(`naming`)이 올릴 수 있는 예외가
        # 앞으로 늘어날 수 있고 **그때 이 자리가 조용히 다시 깨지기** 때문이다.
        # 문서를 못 찾아도 실행 폴더와 원장은 그대로 검사받는다
        return None


def _report(run_dir: Path, result: cycle.CycleResult) -> int:
    """무엇이 됐고 무엇이 남았는지 알린다."""
    print(f"실행 폴더: {run_dir}")
    print(f"마친 단계: {list(result.settled)}  건너뛴 단계: {list(result.skipped)}")

    if result.failure is None:
        print("회차를 완주했습니다.")
        return EXIT_OK

    print(f"[미완성] 갈래={result.failure.kind.value}", file=sys.stderr)
    print(result.failure.raw, file=sys.stderr)

    if result.closed_reason is not None:
        # 종료 코드를 늘리지 않는다 — 「기각은 실패가 아니다」와 같은 축이다.
        # 갈래를 늘리면 「인증이 끊겨 며칠 안 도는 상태」와의 구별이 흐려진다.
        #
        # [중요] 걷어낸 후보가 «없어도» 알린다. 이 실행 폴더는 영구히 버려진 것이라,
        # 안 알리면 평범한 미완성과 **출력이 글자 하나 다르지 않다**
        print(f"[막힘] {result.closed_reason} — 이 실행 폴더를 접었습니다.", file=sys.stderr)
        if result.blocked_claim is not None:
            print(f"[막힘] 이 후보를 원장에서 걷어냈습니다: {result.blocked_claim}", file=sys.stderr)

    if result.failure.kind is FailureKind.LIMIT:
        # 한도 소진은 «정상»이다. 넘어가서 과금되지 않고, 다음 회차가 이어받는다
        return EXIT_LIMIT
    if result.failure.kind is FailureKind.AUTH:
        return EXIT_AUTH
    return EXIT_INCOMPLETE


def _resolve_run_dir(explicit: Path | None) -> Path:
    """이번에 쓸 실행 폴더를 고른다 — **회차의 첫 단계인 「① 미완성」이 여기다.**

    [중요] 미완성을 찾지 않고 언제나 새 폴더를 만들면 **이어받기가 영영 동작하지 않는다.**
    무인 실행은 인자 없이 불리므로, 끊긴 지난 회차는 아무도 이어받지 못한 채 폴더만 쌓이고
    끝난 단계를 회차마다 다시 돈다. 설계가 「미완성은 구조적으로 최대 1개」라고 말하는 근거가
    바로 이 분기이며, 사람이 `--run-dir` 를 손으로 칠 때만 되는 것은 그 설계가 아니다.

    Args:
        explicit: 사람이 지정한 실행 폴더. 있으면 그대로 쓴다

    Returns:
        이어받을 폴더, 없으면 새 폴더
    """
    if explicit is not None:
        return explicit

    unfinished = _latest_unfinished_run_dir()
    if unfinished is not None:
        print(f"[이어받기] 미완성을 찾았습니다: {unfinished}")
        return unfinished

    # 하루에 두 번 돌 수 있으므로 날짜만으로는 유일해지지 않아 시각까지 넣는다
    return RUNS_DIR / datetime.now(KST).strftime(RUN_DIR_TIME_FORMAT)


def _latest_unfinished_run_dir() -> Path | None:
    """아직 안 끝난 실행 폴더 중 가장 최근 것을 찾는다.

    폴더 이름이 `YYYYMMDD_HHMM` 이라 문자열 정렬이 곧 시간 정렬이다.
    """
    if not RUNS_DIR.is_dir():
        return None

    for run_dir in sorted((path for path in RUNS_DIR.iterdir() if path.is_dir()), reverse=True):
        if state.is_locked(run_dir):
            # 다른 프로세스가 잡고 있다. 골라 봐야 잠금에 막히고, 그 사이 새 회차도 못 돈다.
            #
            # [중요] 파일 «존재»를 보지 않는다. 강제 종료 뒤에도 잠금 파일은 남으므로
            # 존재로 판정하면 **그 폴더가 영구히 이어받히지 않는다** — 후보는 「판 것」이
            # 안 됐으니 다음 회차가 원장에서 같은 후보를 다시 꺼내 수집을 다시 사고,
            # 버려진 폴더가 쌓이는데 **에러도 경고도 없다.** 판정은 `state` 한 곳이 한다
            continue

        try:
            saved = state.load(run_dir)
        except (OSError, json.JSONDecodeError):
            # 깨진 상태 파일이다. 이어받을 수 없으므로 건너뛰고 새 회차를 시작한다 —
            # 여기서 터뜨리면 그 폴더 하나 때문에 **이후 모든 회차가 서고**,
            # 무인 실행에서는 그 사실을 며칠 뒤에나 알게 된다
            continue

        if saved is None:
            continue

        if state.closed_reason(run_dir) is not None:
            # [중요] 「막힘」으로 접은 폴더다. 이것이 없으면 그 처리가 통째로 헛돈다 —
            # 후보를 원장에서 걷어내도 이 폴더의 「그 회차의 후보」는 살아 있어서,
            # 이어받으면 **같은 단계를 또 부르고 또 막힌다.** 아래 「후보가 박힌 미완성은
            # 이어받는다」 갈래가 여기서는 정확히 반대로 작용하므로 «먼저» 본다
            continue

        try:
            remaining = steps.next_step(saved.get("settled", []))
        except steps.UnknownStepError:
            # 단계 이름을 바꾼 뒤에 남은 예전 상태다. 이어받을 수 없으므로 건너뛰고
            # 새 회차를 시작한다 — 여기서 터뜨리면 그 폴더 하나 때문에 파이프라인이 선다
            continue

        if remaining is None:
            continue

        if remaining in steps.CANDIDATE_STEPS and state.pinned_candidate(run_dir) is None:
            # [중요] 단계를 늘리기 «전»에 끝난 회차가 여기 걸린다. 수집까지 끝냈지만
            # 그 회차가 어느 후보를 팠는지 상태에 없어, 이어받으면 후보 없이 반증이 돌고
            # 상한까지 헛돈다. 위 갈래와 같은 이유로 건너뛰고 새 회차를 시작한다
            continue

        return run_dir

    return None


def _agent_env(source: Mapping[str, str]) -> dict[str, str]:
    """에이전트에게 넘길 환경을 «골라» 만든다."""
    return {name: source[name] for name in PASSED_ENV_VARS if name in source}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="회차 하나를 돌린다")
    parser.add_argument(
        "--budget-usd",
        type=float,
        default=DEFAULT_BUDGET_USD,
        help="한 단계의 폭주 감지 상한. 과금 방지가 아닙니다 (기본값: %(default)s)",
    )
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH, help="원장 경로 (기본값: %(default)s)")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="이어받을 실행 폴더. 생략하면 새로 만듭니다",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())

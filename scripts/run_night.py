#!/usr/bin/env python3
"""밤 하나를 돌린다 — 이 저장소의 유일한 진입점.

무인 실행이라 **아무도 화면을 보지 않는다.** 그래서 결과를 종료 코드로 가르고,
과정은 그 밤의 실행 폴더에 파일로 남긴다.

사용법은 `docs/COMMANDS.md` 가 SoT다.
"""

import argparse
import json
import os
import sys
from collections.abc import Mapping
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
    LOCK_FILENAME,
    RUN_DIR_TIME_FORMAT,
    RUNS_DIR,
)
from research_lab.gate import secrets  # noqa: E402
from research_lab.runner import (  # noqa: E402
    collect,
    decision_log,
    explore,
    lineage,
    night,
    rebut,
    state,
    steps,
)
from research_lab.runner.failures import FailureKind  # noqa: E402

# 종료 코드. **무인 실행에서 사람이 받는 신호가 이것뿐**이라 갈래마다 다른 값을 준다.
# 전부 0 이나 1 로 뭉치면 「인증이 끊겨 며칠 안 돈 상태」와 「그냥 한도에 걸린 밤」이 구별되지 않는다
EXIT_OK: Final = 0
EXIT_INCOMPLETE: Final = 1  # 그 외 실패 — 다음 밤이 이어받는다
EXIT_LIMIT: Final = 2  # 한도 소진 — 정상이다. 재시도하지 않는다
EXIT_AUTH: Final = 3  # 인증·과금 거부 — 사람이 손대야 한다
EXIT_SECRET: Final = 4  # 자격증명 발견 — 그 밤을 실패로 만든다

# 한 단계에 거는 폭주 감지 상한.
#
# [미검증] 「한 단계가 정상적으로 쓸 양」을 아직 재지 못했다. 이 값은 **과금 방지가 아니라
# 폭주 감지**이며(과금은 `billing_guard` 가 막는다), 실측 뒤에 조정한다.
# 구독 인증에서 이 플래그가 실제로 동작하는지도 [미검증]이다
DEFAULT_BUDGET_USD: Final = 2.0

# 컨테이너·호스트에서 에이전트에게 물려줄 환경변수.
#
# [중요] 환경을 «통째로» 물려주지 않는다. 그러면 `ANTHROPIC_API_KEY` 가 조용히 딸려 들어간다.
# 넘길 것을 이름으로 나열하는 것이 그 사고를 구조적으로 막는 방법이다
PASSED_ENV_VARS: Final = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "CLAUDE_CODE_OAUTH_TOKEN")


def main(argv: list[str] | None = None) -> int:
    """밤을 돌고 결과를 종료 코드로 알린다."""
    args = _parse_args(argv)

    try:
        # 가장 앞에서 막는다. 한 줄이라도 돈 뒤에 막으면 이미 과금된 뒤다
        assert_subscription_only(os.environ)
    except BillingGuardError as blocked:
        print(f"[중지] {blocked}", file=sys.stderr)
        return EXIT_AUTH

    run_dir = _resolve_run_dir(args.run_dir)
    agent_env = _agent_env(os.environ)

    def ask(prompt: str) -> invoke.AgentResult:
        return invoke.invoke(prompt=prompt, cwd=BASE_DIR, env=agent_env, budget_usd=args.budget_usd)

    def execute(step: str, current_run_dir: Path) -> None:
        if step == "explore":
            explore.run(current_run_dir, args.ledger, ask)
        elif step == "collect":
            collect.run(current_run_dir, args.ledger, ask)
        elif step == "rebut":
            # 원장을 안 받는다 — 이 단계는 그 밤의 후보를 «상태»에서 읽고 아무것도 표시하지 않는다.
            # 안 쓰는 인자를 받아 두면 「반증도 원장을 고친다」로 읽힌다
            rebut.run(current_run_dir, ask)
        elif step == "lineage":
            lineage.run(current_run_dir, args.ledger, ask)
        else:
            # 단계 목록은 `steps.STEPS` 하나가 정한다. 여기 도달했다는 것은 그 목록에
            # 이름을 더하면서 실행부를 안 붙였다는 뜻이라, 조용히 넘기면 그 단계가
            # 「했다」로 기록된 채 아무 일도 안 일어난다
            raise steps.StepNotImplementedError(f"내부 불변조건 위반: 실행부가 없는 단계입니다 — {step}")

    try:
        result = night.run_night(run_dir=run_dir, ledger_path=args.ledger, execute=execute)
    except state.AlreadyRunningError as running:
        print(f"[중지] {running}", file=sys.stderr)
        return EXIT_INCOMPLETE

    # 산출물이 생긴 «뒤에» 검사한다. 검사기는 사후 장치이고, 여기가 마지막 그물이다
    findings = secrets.scan(secrets.scan_roots(run_dir))
    if findings:
        for finding in findings:
            # 값은 싣지 않는다. 그 기록도 PUBLIC 저장소에 남는다
            print(f"[자격증명] {finding.path}:{finding.line_number} ({finding.rule})", file=sys.stderr)
        decision_log.record(run_dir, "gate", decision_log.EVENT_FAILED, secrets=len(findings))
        return EXIT_SECRET

    return _report(run_dir, result)


def _report(run_dir: Path, result: night.NightResult) -> int:
    """무엇이 됐고 무엇이 남았는지 알린다."""
    print(f"실행 폴더: {run_dir}")
    print(f"마친 단계: {list(result.settled)}  건너뛴 단계: {list(result.skipped)}")

    if result.failure is None:
        print("밤을 완주했습니다.")
        return EXIT_OK

    print(f"[미완성] 갈래={result.failure.kind.value}", file=sys.stderr)
    print(result.failure.raw, file=sys.stderr)

    if result.failure.kind is FailureKind.LIMIT:
        # 한도 소진은 «정상»이다. 넘어가서 과금되지 않고, 다음 밤이 이어받는다
        return EXIT_LIMIT
    if result.failure.kind is FailureKind.AUTH:
        return EXIT_AUTH
    return EXIT_INCOMPLETE


def _resolve_run_dir(explicit: Path | None) -> Path:
    """이번에 쓸 실행 폴더를 고른다 — **밤의 첫 단계인 「① 미완성」이 여기다.**

    [중요] 미완성을 찾지 않고 언제나 새 폴더를 만들면 **이어받기가 영영 동작하지 않는다.**
    무인 실행은 인자 없이 불리므로, 어제 끊긴 밤은 아무도 이어받지 못한 채 폴더만 쌓이고
    끝난 단계를 매일 다시 돈다. 설계가 「미완성은 구조적으로 최대 1개」라고 말하는 근거가
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
        if (run_dir / LOCK_FILENAME).exists():
            # 다른 프로세스가 잡고 있다. 골라 봐야 잠금에 막히고, 그 사이 새 밤도 못 돈다
            continue

        try:
            saved = state.load(run_dir)
        except (OSError, json.JSONDecodeError):
            # 깨진 상태 파일이다. 이어받을 수 없으므로 건너뛰고 새 밤을 시작한다 —
            # 여기서 터뜨리면 그 폴더 하나 때문에 **이후 모든 밤이 서고**,
            # 무인 실행에서는 그 사실을 며칠 뒤에나 알게 된다
            continue

        if saved is None:
            continue

        try:
            remaining = steps.next_step(saved.get("settled", []))
        except steps.UnknownStepError:
            # 단계 이름을 바꾼 뒤에 남은 예전 상태다. 이어받을 수 없으므로 건너뛰고
            # 새 밤을 시작한다 — 여기서 터뜨리면 그 폴더 하나 때문에 파이프라인이 선다
            continue

        if remaining is None:
            continue

        if remaining in steps.CANDIDATE_STEPS and state.pinned_candidate(run_dir) is None:
            # [중요] 단계를 늘리기 «전»에 끝난 밤이 여기 걸린다. 수집까지 끝냈지만
            # 그 밤이 어느 후보를 팠는지 상태에 없어, 이어받으면 후보 없이 반증이 돌고
            # 상한까지 헛돈다. 위 갈래와 같은 이유로 건너뛰고 새 밤을 시작한다
            continue

        return run_dir

    return None


def _agent_env(source: Mapping[str, str]) -> dict[str, str]:
    """에이전트에게 넘길 환경을 «골라» 만든다."""
    return {name: source[name] for name in PASSED_ENV_VARS if name in source}


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="밤 하나를 돌린다")
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

#!/usr/bin/env python3
"""회차 하나를 돌린다 — 이 저장소의 유일한 진입점.

무인 실행이라 **아무도 화면을 보지 않는다.** 그래서 결과를 종료 코드로 가르고,
과정은 그 회차의 실행 폴더에 파일로 남긴다.

사용법은 `docs/COMMANDS.md` 가 SoT다.
"""

import argparse
import contextlib
import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, NoReturn

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
    budget,
    collect,
    cycle,
    cycle_log,
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
    usage,
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
# 인자가 잘못됐다 — 한 줄도 돌지 않았다.
#
# [중요] argparse 의 기본 종료 코드가 **2** 인데 그 자리는 「한도 소진 — 정상이며 할 일
# 없음」이다. 그대로 두면 예약 정의의 플래그 이름이 틀렸을 때 **매일 밤 아무것도 안 하면서
# 정상으로 보인다.** 게다가 인자 검사는 회차 시작 기록보다 «앞»이라 회차 로그에 줄이
# 하나도 안 남아, 「시작은 있는데 끝이 없다」로 중단을 잡는 쪽에도 안 걸린다
EXIT_USAGE: Final = 5

# 한 단계에 거는 폭주 감지 상한. 이 값은 **과금 방지가 아니라 폭주 감지**다
# (과금은 `billing_guard` 가 막는다).
#
# [실측 2026-09-15] **구독 인증에서도 이 플래그가 실제로 동작한다** — 반증 단계가
# $2.4330 에서 잘렸다. 예전 주석이 [미검증]으로 남겨 둔 물음의 답이다.
#
# [실측 2026-09-15] **그런데 그때 잘린 것이 폭주가 아니라 정상 작업이었다.** 반증 단계는
# 후보에 따라 $0.71 → $1.45 → $2.43 으로 벌어지고, 상한이 $2 라 마지막 것이 막혀
# **근거 문서 한 장이 통째로 날아갔다.** 그래서 실측 최대의 약 1.6배로 올려 둔다 —
# 정상 작업을 자르지 않으면서 자릿수가 튀는 폭주는 여전히 걸리는 자리다.
#
# [주의] 이 값을 회차 지시와 헷갈리지 않는다. 회차가 몇 장을 낼지는 `--cycle-dossiers` 가
# 정하고 단위가 «장»이다. 이쪽이 달러인 것은 선택이 아니라 제약이다 — 실제로 끊는 장치가
# CLI 의 `--max-budget-usd` 이고 그 플래그의 단위가 달러다
DEFAULT_BUDGET_USD: Final = 4.0

# 한 «회차»가 낼 근거 문서의 장수. 위 `DEFAULT_BUDGET_USD` 와 **뜻도 단위도 다르다** —
# 그쪽은 한 «단계»에 거는 폭주 감지 상한(달러)이고, 이쪽은 이 회차가 몇 장을 낼지다.
#
# [중요] **지시를 「장수」로 받는다.** 예전에는 달러 예산이었고 「한 장 비용 중앙값의 절반이
# 남았나」로 다음 장을 시작할지 정했다. 그래서 사람이 원하는 것(「네 장」)과 적는 것
# (「$12」)이 달랐고, 그 대응은 중앙값이 바뀔 때마다 조용히 달라졌다. 게다가
# [실측 2026-09-15] **그 중앙값 자체가 잘못 잡힌 적이 있다** — 문서를 안 낸 폴더가 표본에
# 섞여 한 단위가 절반으로 읽혔고, 임계도 절반이 되어 루프가 한 장 더 시작했다.
#
# [중요] **이 값이 곧 반복의 상한이다.** 예전에는 별도의 반복 상한 상수를 두었는데,
# 지시가 장수가 되면서 둘이 같은 물건이 됐다. 별도 상수를 남겨 두면 지시보다 그 상수가
# 작을 때 **상한이 정책을 대신한다.** 영원히 도는 것을 막는 일은 이 값이 그대로 맡는다.
#
# [실측 2026-09-15] 근거 문서 한 장이 5시간 창의 약 23% 다. 네 장이면 한 창을 거의 채운다 —
# **남는 구독 토큰을 쓰는 것이 이 프로젝트의 목적**이므로 그 자리를 기본값으로 둔다.
# 넘치면 한도 소진으로 깨끗이 멈추고 다음 회차가 이어받는다(과금되지 않는다)
DEFAULT_CYCLE_DOSSIERS: Final = 4

# 예산 판정을 결정 로그에 적을 때 쓰는 «단계» 이름.
#
# [주의] 정의된 단계가 아니라 **루프 자신**이다. 단계 이름과 겹치지 않아야 「그 단계가
# 몇 회차 막혔나」를 세는 쪽이 이 줄을 함께 세지 않는다
LOOP_STEP: Final = "cycle"

CONTINUE_REASON: Final = "요청한 장수가 남아 다음 후보로 갑니다"

# 회차 장수 플래그의 도움말. 문장을 «한 리터럴»로 둔다 —
# 이 저장소의 자동 포맷은 인접한 두 문자열을 길이와 무관하게 한 줄로 붙이므로,
# 나눠 적으면 「두 리터럴이 한 줄에 붙은」 모양만 남고 길이는 그대로다
CYCLE_DOSSIERS_HELP: Final = (
    "한 «회차»가 낼 근거 문서의 장수. 이 값이 곧 반복의 상한입니다. 한도가 먼저 소진되면 그 자리에서 깨끗이 멈추고 다음 회차가 이어받습니다 (기본값: %(default)s)"
)

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


@dataclass(frozen=True)
class CycleOutcome:
    """한 «회차»가 무엇을 했나 — 실행 폴더 하나가 아니라 회차 전체다."""

    exit_code: int
    produced: int
    spent_usd: float
    tokens: usage.Tokens
    stop_reason: str
    last_run_dir: Path


def main(argv: list[str] | None = None) -> int:
    """회차를 돌고 결과를 종료 코드로 알린다.

    [중요] **회차의 시작과 종료를 여기서 «한 번씩만» 적는다.** 루프 안에서 갈래마다
    적으면 어느 한 경로가 빠지고(자격증명 발견처럼 중간에서 바로 나가는 자리),
    그러면 **사람이 손대야 하는 바로 그 회차가 「중단」으로 보인다.**
    그래서 도는 일은 `_run_cycles` 가 «돌려주고», 기록은 이 함수가 한다.
    """
    args = _parse_args(argv)

    try:
        # 가장 앞에서 막는다. 한 줄이라도 돈 뒤에 막으면 이미 과금된 뒤다
        assert_subscription_only(os.environ)
    except BillingGuardError as blocked:
        # [중요] 회차 로그에 **아무것도 적지 않는다.** 여기서 막힌 것은 「시작한 회차」가
        # 아니라 「시작하지 못한 회차」다. 적으면 짝이 없어 중단으로 읽히는데,
        # 실제로는 사람이 환경을 고쳐야 하는 상태다
        print(f"[중지] {blocked}", file=sys.stderr)
        return EXIT_AUTH

    cycle_id = cycle_log.new_cycle_id()
    cycle_log.started(
        RUNS_DIR,
        cycle_id=cycle_id,
        cycle_dossiers=args.cycle_dossiers,
        step_budget_usd=args.budget_usd,
        ledger_name=args.ledger.name,
        run_dir_name=args.run_dir.name if args.run_dir is not None else None,
    )

    outcome = _run_cycles(args)

    # [중요] 화면과 저장소 안의 기록이 **같은 값**을 말해야 한다. 그래서 둘을 나란히 두고,
    # 어느 경로로 끝나도 둘 다 한 번씩 지나가게 한다
    _print_cycle_summary(outcome)
    cycle_log.finished(
        RUNS_DIR,
        cycle_id=cycle_id,
        exit_code=outcome.exit_code,
        produced=outcome.produced,
        spent_usd=round(outcome.spent_usd, budget.COST_DIGITS),
        stop_reason=outcome.stop_reason,
        last_run_dir_name=outcome.last_run_dir.name,
        tokens=outcome.tokens,
    )
    return outcome.exit_code


def _run_cycles(args: argparse.Namespace) -> CycleOutcome:
    """요청한 장수만큼 실행 폴더를 만들어 돈다.

    [중요] **종료 코드를 «돌려준다».** 여기서 `return` 하는 모든 갈래가 위 함수의
    기록을 지나가므로, 갈래를 새로 더해도 종료 기록이 빠질 수 없다.
    """
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

    # 「한 장 만들고 끝」이 아니라 요청한 장수만큼 «돈다». 남는 구독 토큰을 쓰는 것이
    # 이 프로젝트의 목적이라, 일찍 끝났다고 멈추면 목적과 어긋난다
    run_dir = _resolve_run_dir(args.run_dir)
    result: cycle.CycleResult | None = None
    spent_usd = 0.0
    spent_tokens = usage.Tokens()
    produced = 0
    stop_reason = CONTINUE_REASON

    for iteration in range(1, args.cycle_dossiers + 1):
        if iteration > 1:
            # 지정된 폴더는 «첫» 반복의 것이다. 계속 쓰면 두 번째 장이 첫 장 위에 덮인다
            run_dir = _resolve_run_dir(None)

        # [중요] 이 회차가 쓴 비용은 «차분»으로 센다. 폴더의 합을 그대로 더하면
        # 이어받은 폴더에 남아 있던 **지난 회차의 비용까지 이번 것으로 세어** 예산이
        # 조기 소진되고, 그 어긋남은 아무 에러도 내지 않는다.
        # 토큰도 같은 이유로 차분이다 — 한도 소비가 그 배수만큼 부풀면 「한 장이 한도의
        # 몇 %인가」가 조용히 틀린다
        before_usd = budget.cost_of(run_dir)
        before_tokens = usage.tokens_of(run_dir)
        try:
            result = cycle.run_cycle(run_dir=run_dir, ledger_path=args.ledger, execute=execute)
        except state.AlreadyRunningError as running:
            # [중요] 예외 «원문»을 회차 로그에 싣지 않는다. 그 문구에는 실행 폴더의
            # **절대경로**가 들어 있어, 저장소에 커밋되는 이 로그에 호스트의 사용자 폴더가
            # 그대로 남는다 — 이 저장소는 PUBLIC 이고 이 파일은 자격증명 스캔 «밖»이다.
            # 화면(저장소 밖)에는 원문 그대로 알린다 — 사람이 고칠 때 경로가 필요하다
            print(f"[중지] {running}", file=sys.stderr)
            return CycleOutcome(
                exit_code=EXIT_INCOMPLETE,
                produced=produced,
                spent_usd=spent_usd,
                tokens=spent_tokens,
                stop_reason=f"이미 도는 회차가 있어 그 폴더를 잡지 못했습니다 — {run_dir.name}",
                last_run_dir=run_dir,
            )
        spent_usd += budget.cost_of(run_dir) - before_usd
        spent_tokens = spent_tokens + (usage.tokens_of(run_dir) - before_tokens)

        # [중요] **반복마다** 검사한다. 마지막 폴더만 보면 앞의 폴더들이 통째로 빠지고,
        # 이 저장소는 PUBLIC 이라 그 누락이 그대로 공개 이력이 된다
        leaked = _report_secrets(run_dir)
        if leaked is not None:
            return CycleOutcome(
                exit_code=leaked,
                produced=produced,
                spent_usd=spent_usd,
                tokens=spent_tokens,
                stop_reason="자격증명이 발견돼 그 자리에서 멈췄습니다",
                last_run_dir=run_dir,
            )

        if result.produced:
            produced += 1

        halt = _loop_stop_reason(result, produced=produced, requested=args.cycle_dossiers)
        decision_log.record(
            run_dir,
            LOOP_STEP,
            decision_log.EVENT_BUDGET,
            iteration=iteration,
            produced=produced,
            spent_usd=round(spent_usd, budget.COST_DIGITS),
            cycle_dossiers=args.cycle_dossiers,
            # 「멈췄다」만 남으면 다음에 왜 한 장에서 끝났는지 되짚을 수 없다
            reason=halt or CONTINUE_REASON,
        )

        if halt is not None:
            stop_reason = halt
            break

    if result is None:
        raise RuntimeError(f"내부 불변조건 위반: 회차가 한 번도 돌지 않았습니다 — 요청 장수={args.cycle_dossiers}")

    return CycleOutcome(
        exit_code=_report(
            run_dir, result, produced=produced, spent_usd=spent_usd, tokens=spent_tokens, stop_reason=stop_reason
        ),
        produced=produced,
        spent_usd=spent_usd,
        tokens=spent_tokens,
        stop_reason=stop_reason,
        last_run_dir=run_dir,
    )


def _loop_stop_reason(result: cycle.CycleResult, *, produced: int, requested: int) -> str | None:
    """루프를 멈출 이유가 있으면 그 이유를, 계속해도 되면 None 을 돌려준다.

    Args:
        result: 방금 끝난 실행 폴더의 결과
        produced: 이 회차가 «지금까지» 낸 근거 문서의 장수
        requested: 이 회차에 요청된 장수

    Returns:
        멈출 이유, 계속해도 되면 None
    """
    if result.failure is not None:
        # 미완성을 이어받는 것은 **다음 회차의 첫 단계**다. 같은 회차에서 계속 밀어붙이면
        # 같은 자리에서 같은 이유로 막히며 예산만 태운다
        return "미완성으로 끝났습니다 — 이어받기는 다음 회차의 첫 단계입니다"

    if not result.produced:
        # [중요] 이 한 조건이 세 경우를 덮는다 — 원장이 포화라 전부 건너뛴 회차 ·
        # 탐색이 새 후보를 못 찾은 회차 · 「막힘」으로 접힌 폴더를 닫기만 한 회차.
        # **셋 다 다음 반복이 같은 자리에 다시 서므로**, 안 막으면 비용 0 짜리 회차가
        # 반복 상한까지 돈다
        return "이 반복이 근거 문서를 내지 못했습니다 — 다음 반복도 같은 자리에 섭니다"

    if produced >= requested:
        return f"요청한 {requested}장을 냈습니다"

    return None


def _report_secrets(run_dir: Path) -> int | None:
    """그 회차가 쓴 것에 자격증명이 들어갔는지 본다.

    산출물이 생긴 «뒤에» 검사한다. 검사기는 사후 장치이고, 여기가 마지막 그물이다.

    Args:
        run_dir: 그 반복의 실행 폴더

    Returns:
        걸렸으면 자격증명 갈래의 종료 코드, 깨끗하면 None
    """
    findings = secrets.scan(secrets.scan_roots(run_dir, dossier_path=_dossier_of(run_dir)))
    if not findings:
        return None

    for finding in findings:
        # 값은 싣지 않는다. 그 기록도 PUBLIC 저장소에 남는다
        print(f"[자격증명] {finding.path}:{finding.line_number} ({finding.rule})", file=sys.stderr)
    decision_log.record(run_dir, "gate", decision_log.EVENT_FAILED, secrets=len(findings))
    return EXIT_SECRET


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
    except Exception as unresolved:
        # [중요] 삼키되 «조용히» 삼키지 않는다. 안 남기면 「문서를 안 썼다」와
        # 「문서는 썼는데 검사 범위에서 빠졌다」가 **글자 하나 다르지 않고**,
        # 이 저장소는 PUBLIC 이라 뒤쪽은 사람이 즉시 알아야 하는 상태다
        _note_unresolved_dossier(run_dir, unresolved)
        # [중요] **여기서 터뜨리면 「마지막 그물」이 통째로 안 쳐진다.** 완주한 회차가
        # 산출물을 다 만들어 놓고 자격증명 검사 «직전»에 죽으며, 종료 코드도 정해진
        # 다섯 중 어느 것도 아니게 되어 무인 실행에서는 무슨 일이 났는지 알 수 없다.
        #
        # 갈래를 좁혀 잡지 않는 이유는, 이름을 만드는 쪽(`naming`)이 올릴 수 있는 예외가
        # 앞으로 늘어날 수 있고 **그때 이 자리가 조용히 다시 깨지기** 때문이다.
        # 문서를 못 찾아도 실행 폴더와 원장은 그대로 검사받는다
        return None


def _note_unresolved_dossier(run_dir: Path, unresolved: Exception) -> None:
    """근거 문서 경로를 못 구했다는 사실을 남긴다 — **남기다 터지지 않는다.**

    Args:
        run_dir: 그 반복의 실행 폴더
        unresolved: 경로를 못 구하게 만든 예외

    [중요] 기록이 실패해도 삼킨다. 이 함수를 부르는 자리가 「마지막 그물」을 치기 직전이라,
    기록 때문에 터지면 **고치려던 것보다 나쁜 상태**가 된다.

    [중요] 결정 로그에는 **예외 원문을 싣지 않는다.** 그 문구에는 실행 폴더의 절대경로가
    들어 있을 수 있고, 이 저장소는 PUBLIC 이다. 사람이 고칠 때 필요한 원문은
    저장소 «밖»인 화면으로 보낸다 — 자격증명 발견을 알리는 자리와 같은 방식이다.
    """
    print(f"[주의] 근거 문서 경로를 못 구해 자격증명 검사에서 빠집니다 — {unresolved}", file=sys.stderr)
    with contextlib.suppress(Exception):
        # [중요] 열쇠 이름을 여기서 «지어내지» 않는다. 실패 줄의 모양은 `decision_log` 의
        # 계약이고, 다른 실패 줄이 전부 `gate` 와 `reason` 을 쓴다. 비슷하지만 다른 이름을
        # 쓰면 **「무엇이 왜 실패했나」를 `reason` 으로 훑는 쪽이 이 줄만 건너뛴다** —
        # 하필 이 줄이 그 훑기로 드러나라고 만든 줄이다
        decision_log.record(
            run_dir,
            "gate",
            decision_log.EVENT_FAILED,
            gate="dossier-path",
            reason="근거 문서 경로를 구하지 못해 자격증명 검사 범위에서 빠졌습니다",
        )


def _report(
    run_dir: Path,
    result: cycle.CycleResult,
    *,
    produced: int,
    spent_usd: float,
    tokens: usage.Tokens,
    stop_reason: str,
) -> int:
    """그 **실행 폴더**가 어디까지 갔는지 알리고 종료 코드를 정한다.

    [주의] 회차 «전체»의 요약(장수·쓴 돈·토큰·한도 비율·멈춘 이유)은 여기서 찍지 않는다.
    이 함수는 정상 경로에서만 불리므로, 여기 찍으면 **중간에서 바로 나가는 경로**
    (자격증명 발견 · 이미 도는 회차)에서 화면에 그 숫자가 안 나온다 —
    그런데 자격증명은 **사람이 즉시 손대야 하는** 갈래다. 요약은 `main` 이 찍는다.
    """
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


def _print_cycle_summary(outcome: CycleOutcome) -> None:
    """그 «회차»가 무엇을 했는지 한 자리에서 알린다.

    [중요] 실행 폴더 하나가 아니라 회차 전체다 — 루프가 여러 장을 낼 수 있으므로
    마지막 폴더만 알리면 그 회차가 무엇을 했는지가 드러나지 않는다.

    예약 실행에서 **사람이 가장 먼저 보는 화면**이 이것이고, 같은 값이 회차 로그에도
    적힌다. 둘 중 어느 쪽을 봐도 같은 숫자가 나와야 한다.
    """
    tokens = outcome.tokens
    print(f"이번 회차: 근거 문서 {outcome.produced}장 · ${outcome.spent_usd:.{budget.COST_DIGITS}f} 사용")
    # [주의] 「한도 기준」이 붙는 쪽은 **새 토큰**이다. 캐시 읽기는 한도를 먹지 않는다
    # (`usage` 모듈 머리의 실측). 둘을 나란히 두되 어느 쪽이 비율의 분자인지를 label 로 가른다
    print(f"토큰: 한도 기준 {tokens.new_total:,} · 캐시 읽기 {tokens.cache_read:,} (한도에 안 셈)")
    print(f"5시간 한도 대비: {_share_text(tokens, produced=outcome.produced)}")
    print(f"멈춘 이유: {outcome.stop_reason}")


def _share_text(tokens: usage.Tokens, *, produced: int) -> str:
    """한도 비율을 사람이 읽는 한 줄로.

    [중요] 보정값이 없을 때 **「0%」라고 적지 않는다.** 0 은 「한도를 안 썼다」로 읽히고,
    실제로는 「분모를 모른다」다. 분모는 프로그램으로 읽을 수 없어 사람이 한 번 재서 넣는다.
    """
    calibration = usage.calibrated()
    share = usage.window_share_percent(tokens, calibration=calibration)
    if calibration is None:
        return "잴 수 없음 — 한 창의 한도를 아직 보정하지 않았습니다 (회차 전후의 사용량을 비교해 넣습니다)"
    if share is None:
        # [중요] 보정값이 있는데도 못 재는 길은 **분자가 0** 하나뿐이다. 그때 위 문구를 내면
        # 이미 들어 있는 보정값을 다시 재라고 사람을 보낸다. 분자가 0 이 되는 길도 둘이고
        # 하나는 고장이라(응답에 `usage` 가 안 실림) 여기서 0% 라고 말하지 않는다
        return "잴 수 없음 — 이 회차의 토큰이 0 입니다 (전부 건너뛴 회차이거나, 계측이 빠졌습니다)"

    per_dossier = usage.per_dossier_percent(share, produced=produced)
    tail = f" · 근거 문서 한 장당 약 {per_dossier:.1f}%" if per_dossier is not None else ""
    return f"이 회차가 한 창의 약 {share:.1f}%{tail} (보정 기준일 {calibration.measured_on})"


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

    return _new_run_dir()


def _new_run_dir() -> Path:
    """아직 쓰이지 않은 실행 폴더 이름을 고른다.

    [중요] 이름이 분 단위(`YYYYMMDD_HHMM`)인데 **전부 건너뛴 회차는 비용 0 에 몇 초면
    끝난다.** 그래서 예산 루프에서는 같은 분에 두 폴더가 필요해질 수 있고, 겹치면
    방금 완주한 폴더를 다시 잡아 「남은 단계 없음」이 돌아온다 — **아무 일도 안 하는 회차가
    반복 상한까지 돈다.**

    **형식을 바꿔서 풀지 않는다.** 앞 여덟 글자를 날짜로 읽는 쪽과 문자열 정렬이 곧
    시간 정렬이라는 전제가 거기 물려 있어, 초를 끼우면 그 둘이 함께 흔들린다.
    뒤에 순번을 붙이면 둘 다 유지된다.
    """
    stamp = datetime.now(KST).strftime(RUN_DIR_TIME_FORMAT)
    run_dir = RUNS_DIR / stamp
    ordinal = 2
    while run_dir.exists():
        run_dir = RUNS_DIR / f"{stamp}_{ordinal}"
        ordinal += 1
    return run_dir


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
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as unreadable:
            # 깨진 상태 파일이다. 이어받을 수 없으므로 건너뛰고 새 회차를 시작한다 —
            # 여기서 터뜨리면 그 폴더 하나 때문에 **이후 모든 회차가 서고**,
            # 무인 실행에서는 그 사실을 며칠 뒤에나 알게 된다.
            #
            # [중요] 인코딩 오류를 빠뜨리지 않는다(`ValueError` 계열이라 앞의 둘에 안 걸린다).
            # 이 판정은 회차 시작을 적은 «뒤»에 오므로, 여기서 죽으면 종료가 안 적혀
            # **매일 밤 「중단」으로 읽힌다** — 정작 봐야 할 곳은 그 폴더 하나다.
            #
            # [중요] 건너뛰되 «조용히» 건너뛰지 않는다. 안 알리면 그 폴더는 매일 밤 말없이
            # 버려지는데, 후보가 「판 것」으로 표시되지 않았으므로 **다음 회차가 원장에서
            # 같은 후보를 다시 꺼내 수집을 다시 산다.** 아무 기록에도 그 폴더 이름이 없다
            print(f"[주의] 상태 파일을 읽을 수 없어 건너뜁니다 — {run_dir}: {unreadable}", file=sys.stderr)
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


def _dossier_count(raw: str) -> int:
    """장수 인자를 읽는다 — **1 보다 작으면 돌기 전에 거부한다.**

    Args:
        raw: 명령줄에 적힌 값

    Returns:
        1 이상의 장수

    Raises:
        argparse.ArgumentTypeError: 정수가 아니거나 1 보다 작을 때

    [중요] 0 은 「한 장도 내지 말라」라 무인 실행에서 의미가 없고, 음수는 루프가 한 번도
    돌지 않아 **내부 불변조건 위반으로 터진다.** 둘 다 인자를 받는 자리에서 막는 것이 맞다 —
    이 값이 곧 반복의 상한이라, 여기가 「한 회차가 영원히 돌지 않는다」를 지키는 자리다.
    """
    try:
        count = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"장수는 정수여야 합니다: {raw}") from None
    if count < 1:
        raise argparse.ArgumentTypeError(f"장수는 1 이상이어야 합니다: {count}")
    return count


class _Parser(argparse.ArgumentParser):
    """인자가 틀렸을 때 «한도 소진»과 «다른» 코드로 끝나는 파서.

    [중요] argparse 의 기본값이 2 인데 그것은 이 파이프라인에서 「정상이며 할 일 없음」이다.
    무인 실행에서 사람이 받는 신호가 종료 코드뿐이라, 겹치면 **고쳐야 할 상태가
    괜찮은 상태로 보인다.**
    """

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        print(f"[중지] 인자가 잘못됐습니다 — {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = _Parser(description="회차 하나를 돌린다")
    parser.add_argument(
        "--budget-usd",
        type=float,
        default=DEFAULT_BUDGET_USD,
        help="한 «단계»의 폭주 감지 상한. 과금 방지가 아닙니다 (기본값: %(default)s)",
    )
    parser.add_argument(
        "--cycle-dossiers",
        type=_dossier_count,
        default=DEFAULT_CYCLE_DOSSIERS,
        help=CYCLE_DOSSIERS_HELP,
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

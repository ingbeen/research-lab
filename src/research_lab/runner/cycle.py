"""회차 하나를 돈다 — 진입 순서와 실패 처리.

진입 순서는 **① 미완성 → ② 후보 → ③ 탐색**이다. 순서가 반대면 미완성을 두고 새 후보를
꺼내게 되어 **아무도 모르는 채 미완성만 쌓인다.** ①이 먼저라서 미완성은 구조적으로 최대 1개다.

- **① 미완성** — 상태 파일이 있으면 끝난 단계를 건너뛰고 이어받는다
- **② 후보** — 원장에 안 판 후보가 있으면 탐색을 건너뛰고 바로 수집한다
- **③ 탐색** — 재고가 없을 때만 돈다. 그래서 **사람이 후보를 적어 넣지 않아도 첫 회차가 돈다**

[중요] **예산 루프(한 장 끝내고 남으면 다음 후보로)는 이 모듈의 일이 아니다.**
여기는 「실행 폴더 하나를 끝까지」의 책임이고, 「예산이 남으면 다음 후보로」는 그 위 층위라
진입점이 소유한다 — **회차와 실행 폴더는 다른 층위이고, 실행 폴더 하나를 여러 회차가
이어받는다.** 둘을 한 모듈에 담으면 이어받기 판정과 예산 판정이 같은 자리에서 얽힌다.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Final

from research_lab.runner import decision_log, failures, ledger, state, steps
from research_lab.runner.failures import Failure, FailureKind

# 단계를 실행하는 쪽. 러너는 «무엇을 하는지» 모르고 «언제 부를지»만 안다.
# 그래서 「탐색」과 「수집」이 같은 호출 계층을 쓰는지가 이 경계에서 검사된다
StepExecutor = Callable[[str, Path], None]

EXPLORE: Final = steps.STEPS[0]
COLLECT: Final = steps.STEPS[1]

# 재시도 사이에 쉬는 시간. 일시적인 고장이 풀릴 틈을 준다 —
# 쉬지 않으면 상한 세 번이 몇 밀리초 안에 소진된다
RETRY_DELAY_SECONDS: Final = 30.0

# 한 실행 폴더에서 같은 단계가 몇 «회차» 실패하면 접나.
#
# [중요] `failures.MAX_RETRIES` 는 **한 회차 «안»의 상한**이라 회차와 회차 사이를 세지 못한다.
# 게이트가 막은 실패는 재시도 대상이 아니라 그 회차가 즉시 끝나고, 다음 회차는 같은 폴더를
# 이어받아 같은 단계를 다시 부른다. 상한이 없으면 **탐색도 수집도 영영 다시 돌지 않고
# 회차마다 호출만 한 번씩 태우며**, 그런 회차는 「실패」가 아니라 「아무 일 없음」처럼 보여
# 며칠 지나서야 알아챈다.
#
# 값이 3인 것은 `failures.MAX_RETRIES` · `collect.MAX_REJECTIONS` 와 같은 성질의 상한이라
# 관용을 따른 것이다
MAX_STEP_FAILURES_PER_RUN: Final = 3

# 위 상한에 «세는» 실패의 갈래.
#
# [중요] 한도·인증·예산은 세지 않는다. **그것들은 후보의 문제가 아니다.**
# 이 파이프라인은 남는 구독 토큰으로 돌기 때문에 한도에 걸리는 회차가 «정상»이고(설계 §9 의 ①),
# 인증과 예산은 사람이 손대기 전에는 어떤 후보로 바꿔도 같은 자리에 선다.
# 세어 버리면 **멀쩡한 후보가 사흘 만에 원장에서 걷어내지면서 「단계가 3회차 연속 실패했다」는
# 사유가 붙는데, 그 사유는 사실이지만 원인을 가리키지 않아 사람을 엉뚱한 곳으로 보낸다.**
COUNTED_FAILURE_KINDS: Final = frozenset({FailureKind.QUALITY.value, FailureKind.OTHER.value})


@dataclass(frozen=True)
class CycleResult:
    """그 회차가 어디까지 갔나."""

    # [주의] `settled` 는 「실행했다」가 아니라 **「이 회차에서 더 볼 일이 없다」**는 뜻이다.
    # 건너뛴 단계도 여기 들어간다 — 이어받기는 「남은 일」을 물으므로 둘을 같이 다뤄야 한다.
    # 실제로 «무엇을 했는지»는 결정 로그가 구별해 남긴다
    settled: tuple[str, ...]
    skipped: tuple[str, ...]
    failure: Failure | None
    # [중요] 이 회차가 «실제로 돌린» 단계. `settled` 와 다르다 — `settled` 에는
    # **지난 회차가 마친 단계와 건너뛴 단계가 함께** 들어 있다.
    #
    # 기본값이 비어 있는 것은 «안전한 쪽»이라서다. 부르는 쪽이 안 채우면 「한 장 냈다」가
    # 아니라 「안 냈다」로 떨어지므로, 빠뜨렸을 때 장수를 부풀리지 않는다
    executed: tuple[str, ...] = ()
    # 상한에 닿아 원장에서 걷어낸 후보. 걷어낼 후보가 없었으면 None 이다.
    # 종료 코드를 늘리지 않는 대신 이 값으로 사람에게 알린다 —
    # 「기각은 실패가 아니다」와 같은 축이다
    blocked_claim: str | None = None
    # 그 실행 폴더를 접었다면 그 사유.
    #
    # [중요] `blocked_claim` 과 «따로» 둔다. 걷어낼 후보가 없는 채로 접히는 경우가 있고
    # (탐색이 막혔거나 원장에서 그 줄이 사라졌거나), 그때 알릴 것이 없으면
    # **폴더가 영구히 버려진 회차가 평범한 미완성과 글자 하나 다르지 않게 보고된다**
    closed_reason: str | None = None

    @property
    def finished(self) -> bool:
        """모든 단계를 마쳤나."""
        return self.failure is None and len(self.settled) == len(steps.STEPS)

    @property
    def produced(self) -> bool:
        """이 실행 폴더가 근거 문서를 «실제로» 냈나.

        [중요] `finished` 로는 못 가른다. `settled` 에는 **건너뛴 단계도 들어가므로**
        원장이 포화라 전부 건너뛴 회차도 「마쳤다」로 읽힌다 — 그것은 「한 장을 만든 것」이
        아니다. 예산 루프가 그 둘을 헷갈리면 **비용 0 짜리 회차가 상한까지 반복된다.**

        마지막 단계가 문서를 만들고 후보를 「판 것」으로 표시하므로(계층 계약 §4),
        **그 단계를 «실행»했는지**가 곧 이 물음의 답이다.

        [중요] 그래서 `settled` 가 아니라 `executed` 를 본다. `settled` 는 **지난 회차가
        마친 것까지** 담으므로, 이미 끝난 실행 폴더를 다시 잡으면 아무것도 안 하고도
        「냈다」가 된다 — 사람이 로그를 보려고 그 폴더를 지정하는 일은 정상이고,
        그 정상적인 호출이 완주율 집계를 오염시켜서는 안 된다
        """
        return self.failure is None and steps.STEPS[-1] in self.executed


def run_cycle(
    *,
    run_dir: Path,
    ledger_path: Path,
    execute: StepExecutor,
) -> CycleResult:
    """회차 하나를 돈다.

    Args:
        run_dir: 그 회차의 실행 폴더. 상태와 로그가 여기 쌓인다
        ledger_path: 원장 경로
        execute: 단계를 실제로 실행하는 쪽. 실패하면 `steps.StepFailed` 를 올린다

    Returns:
        어디까지 갔는지와, 멈췄다면 그 이유

    Raises:
        state.AlreadyRunningError: 같은 실행 폴더를 이미 다른 프로세스가 잡고 있을 때
    """
    # [중요] 잠금이 둘이고 «순서가 고정»이다.
    #
    # 다투는 자원은 상태 파일이 아니라 **원장**이다. 실행 폴더는 회차마다 새로 만들어져
    # 사실상 다툴 일이 없는데, 원장은 모든 회차가 함께 읽고 쓴다 — `mark_explored` 가
    # 「읽고 · 고치고 · 통째로 바꾸는」 동안 다른 회차가 `append` 하면 그 줄이 조용히 사라진다.
    # 그래서 원장을 먼저 잡는다. 순서를 뒤집으면 두 회차가 서로를 기다릴 수 있다
    with state.lock(ledger_path.parent), state.lock(run_dir):
        saved = state.load_or_empty(run_dir)
        settled: list[str] = list(saved.get("settled", []))
        skipped: list[str] = list(saved.get("skipped", []))

        # [중요] «이 회차가 돌린» 단계만 담는다. `settled` 를 쓰면 지난 회차가 마친 것까지
        # 세어, 남은 단계가 하나도 없는 폴더를 다시 잡았을 때 **에이전트를 한 번도 안 부르고
        # 「한 장 냈다」가 된다** — 그 줄이 회차 로그에 `produced 1 · spent_usd 0.0` 으로 남고,
        # 완주율을 그 파일에서 훑어 계산하므로 집계가 조용히 오염된다
        executed: list[str] = []

        while True:
            step = steps.next_step(settled)
            if step is None:
                return CycleResult(tuple(settled), tuple(skipped), None, tuple(executed))

            skip_reason = _skip_reason(step, ledger_path, run_dir)
            if skip_reason is not None:
                skipped.append(step)
                settled.append(step)
                decision_log.record(run_dir, step, decision_log.EVENT_SKIPPED, reason=skip_reason)
                _persist(run_dir, settled, skipped)
                continue

            failure = _execute_with_retries(run_dir, step, execute)
            if failure is not None:
                # 실패한 단계는 `settled` 에 넣지 않는다. 다음 회차가 ①에서 바로 이 단계를 잡는다.
                # 다만 그 「다음 회차」가 영영 반복되지 않도록 여기서 회차와 회차 사이의 상한을 본다
                blocked, closed = _close_if_stuck(run_dir, ledger_path, step)
                return CycleResult(
                    tuple(settled),
                    tuple(skipped),
                    failure,
                    tuple(executed),
                    blocked_claim=blocked,
                    closed_reason=closed,
                )

            executed.append(step)
            settled.append(step)
            _persist(run_dir, settled, skipped)


def _skip_reason(step: str, ledger_path: Path, run_dir: Path) -> str | None:
    """그 단계를 건너뛸 이유가 있으면 그 이유를, 없으면 None 을 돌려준다.

    이유를 «문자열로» 돌리는 것은 결정 로그에 그대로 적기 위해서다.
    「건너뛰었다」만 남으면 나중에 왜 그랬는지 되짚을 수 없다.
    """
    # [주의] 재고 판정은 탐색·수집에서만 쓴다. 뒤 단계에서도 계산하면 그 단계마다
    # 원장을 한 번 더 읽는데 쓰이지는 않는다
    has_stock = step in (EXPLORE, COLLECT) and ledger.next_unexplored(ledger_path) is not None

    if step == EXPLORE and has_stock:
        # 재고가 있는데도 회차마다 탐색을 돌리면 팔 후보를 쌓아 두고 예산만 쓴다
        return "원장에 아직 안 판 후보가 있어 탐색이 필요 없다"

    if step == COLLECT and not has_stock:
        # [중요] 이 갈래가 없으면 «끝나지 않는 실패»가 된다.
        # 탐색이 새 후보를 하나도 못 찾는 것은 정상 결과인데(원장이 포화됐거나 그 회차의 검색이
        # 허탕이거나), 그 상태로 수집에 들어가면 후보가 없어 예외가 나고 상한까지 재시도한 뒤
        # 「다음 회차가 이어받습니다」로 보고된다. 다음 회차도 같은 자리에서 같은 일을 반복하고,
        # 나중에는 아무 일도 없었던 것처럼 보인다
        return "원장에 팔 후보가 없다 — 탐색이 새 후보를 찾지 못했다"

    if step in steps.CANDIDATE_STEPS:
        candidate = state.pinned_candidate(run_dir)
        if candidate is None:
            # 위와 «같은 고장»이다. 수집이 후보를 잡지 못하는 경우는 둘이다 —
            # 팔 후보가 아예 없었거나, 꺼낸 후보가 모두 기각돼 상한에 닿았거나.
            # 둘 다 정상 결과이고, 그 상태로 반증에 들어가면 끝나지 않는 실패가 된다
            return "그 회차가 판 후보가 없다 — 수집이 후보를 잡지 못했다"

        status = ledger.status_of(ledger_path, candidate.claim)
        if status is not ledger.Status.UNEXPLORED:
            # [중요] **단계를 늘리면 그 전에 완주한 실행 폴더가 「미완성」으로 보인다** —
            # 끝난 단계는 전부 `settled` 에 있는데 새 단계만 남아 있기 때문이다. 그 폴더에는
            # 후보가 박혀 있어 위 갈래로도 걸러지지 않으므로, 그대로 두면 **이미 닫힌 후보를
            # 두고 새 단계만 도는 회차**가 되고 그 후보를 두 번 「판 것」으로 표시한다.
            #
            # [중요] 조건이 「판 것인가」가 아니라 **「아직 안 판 것인가」**인 이유가 셋이다.
            #
            # - **기각·막힘도 덮어야 한다.** 마지막 단계가 `mark_explored` 를 부르면
            #   `- [-]`·`- [!]` 가 `- [x]` 로 바뀌고 **바로 아래의 사유 줄이 지워진다.**
            #   원장 머리말은 기각된 줄이 사람이 고칠 때까지 남는다고 약속하는데 그것이 깨지고,
            #   막힌 이유를 적어 둔 기록이 **에러 없이** 사라진다
            # - **원장에서 줄이 사라진 경우도 덮어야 한다.** 사람이 손으로 지울 수 있는
            #   파일이고, 그 상태로 돌면 산출물을 쓴 «뒤»에 `mark_explored` 가 예외를 올려
            #   「그 외」로 분류되어 **상한까지 재시도한다** — 재시도가 고칠 수 없는 조건에
            #   단계 비용을 세 번 낸다
            # - 「판 것」 표시는 마지막 단계가 하므로 **정상적인 회차는 여기 걸리지 않는다**
            #
            # 사유에 표시를 함께 적는다. 「건너뛰었다」만 남으면 어느 경우였는지 모른다
            mark = "원장에 그 후보가 없다" if status is None else f"원장에서 이미 「{status.value}」다"
            return f"그 회차의 후보를 더 물을 자리가 아니다 — {mark}"

    return None


def _execute_with_retries(run_dir: Path, step: str, execute: StepExecutor) -> Failure | None:
    """한 단계를 실행하고, 「그 외」 실패만 상한까지 다시 해본다.

    Returns:
        성공했으면 None, 아니면 멈춘 이유
    """
    failure = Failure(kind=FailureKind.OTHER, raw="")
    for attempt in range(1, failures.MAX_RETRIES + 1):
        if attempt > 1:
            # 「그 외」가 노리는 것은 네트워크 끊김·웹 500 같은 **일시적인** 고장이다.
            # 쉬지 않고 세 번 부르면 몇 밀리초 안에 상한을 다 써 버려, 잠깐 기다렸으면
            # 복구됐을 것까지 그 회차에 포기하게 된다
            sleep(RETRY_DELAY_SECONDS)

        try:
            execute(step, run_dir)
        except steps.StepNotImplementedError:
            # [중요] 이것만은 그대로 터뜨린다. 「정의된 단계인데 실행부가 없다」는 실패가 아니라
            # 고장이고, 「그 외」로 묻히면 상한까지 헛돈 뒤 「다음 회차가 이어받습니다」로 보고되어
            # **아무 일도 안 하는 상태를 정상으로 알린다**
            raise
        except steps.StepQualityFailed as blocked:
            # 게이트가 막은 것은 분류표를 거치지 않는다. 내용이 아니라 «누가 막았는가»가
            # 갈래를 정하고, `should_retry` 가 False 라 아래에서 기록만 하고 끝난다.
            # [주의] `StepFailed` 의 하위라 **이 줄이 먼저 와야** 한다
            failure = Failure(kind=FailureKind.QUALITY, raw=blocked.raw)
        except steps.StepFailed as failed:
            failure = failures.classify(failed.raw)
        except Exception as unexpected:
            # 예상 못 한 예외도 «분류 못 한 실패»다. 여기서 터뜨리면 그 회차가 통째로 끝나고
            # 원문도 안 남아, 다음에 같은 모양을 만나도 가르칠 재료가 없다
            failure = failures.classify(repr(unexpected))
        else:
            return None

        decision_log.record(
            run_dir,
            step,
            decision_log.EVENT_FAILED,
            kind=failure.kind.value,
            attempt=attempt,
            max_retries=failures.MAX_RETRIES,
            # 원문을 «통째로» 남긴다. 처음 한도에 부딪히는 날 이것이 분류표를 가르친다
            raw=failure.raw,
        )

        if not failures.should_retry(failure.kind):
            return failure

    # 상한까지 해도 안 됐다. 그 단계만 포기하고 다음 회차로 넘긴다 —
    # 상한이 없으면 한 회차 내내 같은 실패를 반복하며 예산을 태우고, 나중에는
    # 「실패」가 아니라 「아무 일 없음」처럼 보인다.
    #
    # **마지막 실패를 그대로 돌려준다.** 「재시도를 다 썼다」로 바꿔 넘기면 원문이 사라져
    # 부르는 쪽이 무엇 때문에 막혔는지 알 수 없다. 몇 번 시도했는지는 결정 로그에 있다
    return failure


def _close_if_stuck(run_dir: Path, ledger_path: Path, step: str) -> tuple[str | None, str | None]:
    """그 단계가 이 폴더에서 상한만큼 막혔으면 후보를 걷어내고 폴더를 접는다.

    Returns:
        (걷어낸 후보의 한 줄 주장, 접은 사유). 아직 상한 전이면 둘 다 None
    """
    if _failed_cycles(run_dir, step) < MAX_STEP_FAILURES_PER_RUN:
        return None, None

    reason = f"「{step}」 단계가 {MAX_STEP_FAILURES_PER_RUN}회차 연속 막혔습니다"
    blocked = _block_candidate(run_dir, ledger_path, step, reason)

    try:
        # 후보를 걷어내도 이 폴더의 「그 회차의 후보」는 살아 있다. 접어 두지 않으면
        # 다음 회차가 이어받아 **같은 단계를 또 부르고 또 막힌다**
        state.close(run_dir, reason)
    except OSError:
        # 상태 파일이 반쯤 쓰이다 끊겼거나 쓸 수 없다. 여기서 터뜨리면 **이미 실패한 회차 위에
        # 예외가 겹쳐 실패 원문이 묻히고**, 종료 코드도 정해진 다섯 중 어느 것도 아니게 된다.
        # 접지 못했다는 사실만 남기고 넘어간다 — 다음 회차가 한 번 더 도는 것이 그보다 낫다
        decision_log.record(run_dir, step, decision_log.EVENT_FAILED, gate="close", reason="실행 폴더를 접지 못했습니다")
        return blocked, None

    decision_log.record(run_dir, step, decision_log.EVENT_BLOCKED, reason=reason, claim=blocked)
    return blocked, reason


def _block_candidate(run_dir: Path, ledger_path: Path, step: str, reason: str) -> str | None:
    """막힌 후보를 원장에서 걷어낸다.

    [중요] 상태에 박힌 후보가 없으면 **원장의 「다음에 팔 후보」로 되짚는다.**
    수집은 `_store` 에서야 후보를 박으므로 **게이트에 막힌 수집은 후보를 박은 적이 없고**,
    그대로 두면 걷어낼 것이 없어 회차마다 같은 후보에서 같은 게이트에 막힌다 —
    이 장치가 없애려던 무한 반복이 그대로 남는다.

    되짚기를 «수집에 한정»하는 이유는 탐색이 원장에서 후보를 꺼내지 않기 때문이다.
    거기서 되짚으면 탐색이 막힌 회차에 **애먼 후보가 걷어내진다.**
    """
    candidate = state.pinned_candidate(run_dir)
    claim = candidate.claim if candidate is not None else None
    if claim is None and step == COLLECT:
        stuck = ledger.next_unexplored(ledger_path)
        claim = stuck.claim if stuck is not None else None

    if claim is None:
        return None

    try:
        ledger.mark_blocked(ledger_path, claim, reason)
    except ledger.UnknownCandidateError:
        # 원장은 사람이 손으로 고치는 파일이라 그 사이 줄이 지워질 수 있다.
        # 여기서 터뜨리면 이미 실패한 회차 위에 예외가 겹쳐 실패 원문이 묻힌다
        return None
    return claim


def _failed_cycles(run_dir: Path, step: str) -> int:
    """그 단계가 «막혀서» 끝난 회차가 이 폴더에 몇 번 기록됐나 센다.

    [중요] 좁히는 조건이 둘이고 **둘 다 없으면 상한이 엉뚱하게 앞당겨진다.**

    - `attempt == 1` — 한 회차의 실패가 로그에 여러 줄을 남긴다. 게이트가 막으면 단계가
      한 줄(`gate=`)·러너가 한 줄(`attempt=`)을 적고, 「그 외」 실패는 한 회차에 세 줄
      (`attempt=1,2,3`)을 남긴다. 안 좁히면 두 배·세 배로 세어 첫 회차에 바로 닿는다
    - `kind` — 한도·인증·예산은 **후보의 문제가 아니다.** 세면 멀쩡한 후보가 사흘 만에
      걷어내진다 (`COUNTED_FAILURE_KINDS`)

    첫 시도가 실패했지만 재시도로 성공한 회차도 한 줄을 남긴다. 그래도 안전한 이유는
    **성공한 단계는 `settled` 에 들어가 이 폴더에서 다시 불리지 않고**, 이 판정은
    방금 실패를 돌려받은 자리에서만 하기 때문이다.

    **새 누적 상태를 만들지 않는다** — 셀 재료가 이미 그 폴더에 쌓여 있다.
    """
    return sum(
        1
        for entry in decision_log.read(run_dir)
        if entry.get("step") == step
        and entry.get("event") == decision_log.EVENT_FAILED
        and entry.get("attempt") == 1
        and entry.get("kind") in COUNTED_FAILURE_KINDS
    )


def _persist(run_dir: Path, settled: list[str], skipped: list[str]) -> None:
    """진행 상태를 파일에 박는다. 여기까지는 다음 회차가 다시 하지 않는다.

    [중요] 읽어서 «얹는다». 통째로 덮어쓰면 수집이 방금 박아 둔 그 회차의 후보가 지워지고,
    한 단계 뒤 반증이 「후보 없음」을 만난다 — **원인과 증상이 갈라져** 되짚기 어려워진다.
    """
    saved = state.load_or_empty(run_dir)
    saved.update({"settled": settled, "skipped": skipped})
    state.save(run_dir, saved)

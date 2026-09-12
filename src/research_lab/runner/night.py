"""밤 하나를 돈다 — 진입 순서와 실패 처리.

진입 순서는 **① 미완성 → ② 후보 → ③ 탐색**이다. 순서가 반대면 미완성을 두고 새 후보를
꺼내게 되어 **아무도 모르는 채 미완성만 쌓인다.** ①이 먼저라서 미완성은 구조적으로 최대 1개다.

- **① 미완성** — 상태 파일이 있으면 끝난 단계를 건너뛰고 이어받는다
- **② 후보** — 원장에 안 판 후보가 있으면 탐색을 건너뛰고 바로 수집한다
- **③ 탐색** — 재고가 없을 때만 돈다. 그래서 **사람이 후보를 적어 넣지 않아도 첫 밤이 돈다**

[중요] 예산 루프(한 장 끝내고 남으면 다음 후보로)는 이번 범위가 아니다.
「한 단위」 평균을 잴 표본이 아직 없어서다. 여기서는 **단계 상한만** 건다.
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


@dataclass(frozen=True)
class NightResult:
    """그 밤이 어디까지 갔나."""

    # [주의] `settled` 는 「실행했다」가 아니라 **「이 밤에서 더 볼 일이 없다」**는 뜻이다.
    # 건너뛴 단계도 여기 들어간다 — 이어받기는 「남은 일」을 물으므로 둘을 같이 다뤄야 한다.
    # 실제로 «무엇을 했는지»는 결정 로그가 구별해 남긴다
    settled: tuple[str, ...]
    skipped: tuple[str, ...]
    failure: Failure | None

    @property
    def finished(self) -> bool:
        """모든 단계를 마쳤나."""
        return self.failure is None and len(self.settled) == len(steps.STEPS)


def run_night(
    *,
    run_dir: Path,
    ledger_path: Path,
    execute: StepExecutor,
) -> NightResult:
    """밤 하나를 돈다.

    Args:
        run_dir: 그 밤의 실행 폴더. 상태와 로그가 여기 쌓인다
        ledger_path: 원장 경로
        execute: 단계를 실제로 실행하는 쪽. 실패하면 `steps.StepFailed` 를 올린다

    Returns:
        어디까지 갔는지와, 멈췄다면 그 이유

    Raises:
        state.AlreadyRunningError: 같은 실행 폴더를 이미 다른 프로세스가 잡고 있을 때
    """
    # [중요] 잠금이 둘이고 «순서가 고정»이다.
    #
    # 다투는 자원은 상태 파일이 아니라 **원장**이다. 실행 폴더는 밤마다 새로 만들어져
    # 사실상 다툴 일이 없는데, 원장은 모든 밤이 함께 읽고 쓴다 — `mark_explored` 가
    # 「읽고 · 고치고 · 통째로 바꾸는」 동안 다른 밤이 `append` 하면 그 줄이 조용히 사라진다.
    # 그래서 원장을 먼저 잡는다. 순서를 뒤집으면 두 밤이 서로를 기다릴 수 있다
    with state.lock(ledger_path.parent), state.lock(run_dir):
        saved = state.load(run_dir) or {}
        settled: list[str] = list(saved.get("settled", []))
        skipped: list[str] = list(saved.get("skipped", []))

        while True:
            step = steps.next_step(settled)
            if step is None:
                return NightResult(tuple(settled), tuple(skipped), None)

            skip_reason = _skip_reason(step, ledger_path, run_dir)
            if skip_reason is not None:
                skipped.append(step)
                settled.append(step)
                decision_log.record(run_dir, step, decision_log.EVENT_SKIPPED, reason=skip_reason)
                _persist(run_dir, settled, skipped)
                continue

            failure = _execute_with_retries(run_dir, step, execute)
            if failure is not None:
                # 실패한 단계는 `settled` 에 넣지 않는다. 다음 밤이 ①에서 바로 이 단계를 잡는다
                return NightResult(tuple(settled), tuple(skipped), failure)

            settled.append(step)
            _persist(run_dir, settled, skipped)


def _skip_reason(step: str, ledger_path: Path, run_dir: Path) -> str | None:
    """그 단계를 건너뛸 이유가 있으면 그 이유를, 없으면 None 을 돌려준다.

    이유를 «문자열로» 돌리는 것은 결정 로그에 그대로 적기 위해서다.
    「건너뛰었다」만 남으면 나중에 왜 그랬는지 되짚을 수 없다.
    """
    has_stock = ledger.next_unexplored(ledger_path) is not None

    if step == EXPLORE and has_stock:
        # 재고가 있는데도 매일 탐색을 돌리면 팔 후보를 쌓아 두고 예산만 쓴다
        return "원장에 아직 안 판 후보가 있어 탐색이 필요 없다"

    if step == COLLECT and not has_stock:
        # [중요] 이 갈래가 없으면 «끝나지 않는 실패»가 된다.
        # 탐색이 새 후보를 하나도 못 찾는 것은 정상 결과인데(원장이 포화됐거나 그날 검색이
        # 허탕이거나), 그 상태로 수집에 들어가면 후보가 없어 예외가 나고 상한까지 재시도한 뒤
        # 「다음 밤이 이어받습니다」로 보고된다. 다음 밤도 같은 자리에서 같은 일을 반복하고,
        # 아침에는 아무 일도 없었던 것처럼 보인다
        return "원장에 팔 후보가 없다 — 탐색이 새 후보를 찾지 못했다"

    if step in steps.CANDIDATE_STEPS and state.pinned_candidate(run_dir) is None:
        # 위와 «같은 고장»이다. 수집이 후보를 잡지 못하는 경우는 둘이다 —
        # 팔 후보가 아예 없었거나, 꺼낸 후보가 모두 기각돼 상한에 닿았거나.
        # 둘 다 정상 결과이고, 그 상태로 반증에 들어가면 끝나지 않는 실패가 된다
        return "그 밤이 판 후보가 없다 — 수집이 후보를 잡지 못했다"

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
            # 복구됐을 것까지 그 밤에 포기하게 된다
            sleep(RETRY_DELAY_SECONDS)

        try:
            execute(step, run_dir)
        except steps.StepNotImplementedError:
            # [중요] 이것만은 그대로 터뜨린다. 「정의된 단계인데 실행부가 없다」는 실패가 아니라
            # 고장이고, 「그 외」로 묻히면 상한까지 헛돈 뒤 「다음 밤이 이어받습니다」로 보고되어
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
            # 예상 못 한 예외도 «분류 못 한 실패»다. 여기서 터뜨리면 그 밤이 통째로 끝나고
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

    # 상한까지 해도 안 됐다. 그 단계만 포기하고 다음 밤으로 넘긴다 —
    # 상한이 없으면 밤새 같은 실패를 반복하며 예산을 태우고, 아침에는
    # 「실패」가 아니라 「아무 일 없음」처럼 보인다.
    #
    # **마지막 실패를 그대로 돌려준다.** 「재시도를 다 썼다」로 바꿔 넘기면 원문이 사라져
    # 부르는 쪽이 무엇 때문에 막혔는지 알 수 없다. 몇 번 시도했는지는 결정 로그에 있다
    return failure


def _persist(run_dir: Path, settled: list[str], skipped: list[str]) -> None:
    """진행 상태를 파일에 박는다. 여기까지는 다음 밤이 다시 하지 않는다.

    [중요] 읽어서 «얹는다». 통째로 덮어쓰면 수집이 방금 박아 둔 그 밤의 후보가 지워지고,
    한 단계 뒤 반증이 「후보 없음」을 만난다 — **원인과 증상이 갈라져** 되짚기 어려워진다.
    """
    saved = state.load(run_dir) or {}
    saved.update({"settled": settled, "skipped": skipped})
    state.save(run_dir, saved)

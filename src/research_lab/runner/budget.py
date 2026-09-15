"""회차 예산 — 「한 장 더 시작해도 되나」를 판정한다.

**남는 구독 토큰을 쓰는 것이 이 프로젝트의 목적**이라, 한 장을 끝내고 예산이 남았는데
멈추면 목적과 어긋난다. 그래서 회차는 「한 장 만들고 끝」이 아니라 예산이 남는 한 돈다.

「한 단위」가 얼마인지는 **지난 회차들의 로그를 그때그때 훑어** 계산한다.
누적 파일로 저장하지 않는다 — 하루를 걸러도 표본이 하나 없을 뿐이지만, 누적 집계는
한 번 틀어지면 **틀어졌다는 사실을 아무도 모른다.**

[중요] 이 모듈이 막는 고장 넷은 **전부 에러를 내지 않는다.**

- **표본이 없는데 「한 단위 = 0」으로 읽는 것.** 그러면 남은 예산이 언제나 충분해 보여
  루프가 상한까지 돈다. 「잴 수 없었다」와 「0이었다」는 다르고, 그 둘을 구별하지 못하는
  계측은 계측이 아니라 잡음이다. 그래서 표본이 없으면 **`None`** 이다
- **비용 0 으로 완주한 폴더를 표본에 넣는 것.** 원장이 포화라 전부 건너뛴 회차도 단계가
  전부 끝난 것으로 기록되는데, 그것은 「한 장을 만든 것」이 아니다. 섞이면 중앙값이
  0 쪽으로 끌려 위와 같은 고장이 난다
- **문서를 «내지 않은» 폴더를 표본에 넣는 것.** [실측 2026-09-15] 단계를 늘리면 예전
  완주 폴더가 미완성으로 보이고, 그 회차가 남은 단계를 **건너뛰기로 채우면서** 마친 단계
  목록이 다시 꽉 찬다. 비용 가드로도 안 걸린다 — **예전 생애에 쓴 돈**이 남아 있기 때문이다.
  그래서 판정 재료를 「마친 단계」가 아니라 **「문서를 냈다는 로그」**로 둔다
- **한 표본을 그대로 평균으로 쓰는 것.** [실측] 같은 단계가 후보에 따라 두 배 드는 것이
  확인됐다(반증 $0.71 → $1.45). 그래서 **분포**에서 뽑고, 표본 수를 로그에 함께 남긴다

[중요] **중앙값을 쓰는 이유** — 두 표본이 2배 갈릴 때 평균을 「한 단위」로 잡으면
**어느 쪽에도 맞지 않는 값**이 나온다. 중앙값은 한쪽으로 끌려가지 않는다.
"""

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Final

from research_lab.runner import decision_log, steps

# 다음 한 장을 시작하려면 「한 단위」의 몇 배가 남아 있어야 하나 (0.5 = 절반).
#
# [중요] 이 값을 보수적으로 올리지 않는다. 모자란 예산으로 시작해 미완성이 되는 것은
# «사고가 아니다» — 다음 회차가 이어받으므로 일이 버려지지 않고, 미완성은 구조적으로
# 최대 1개라 쌓이지도 않는다. 올리면 **남는 토큰을 쓴다는 목적과 정면으로 어긋난다.**
# 절반인 이유는 시작 비용(검색·컨텍스트 적재)이 매번 다시 들어, 그보다 적게 남았으면
# 시작 자체가 순 낭비이기 때문이다
START_THRESHOLD_RATIO: Final = 0.5

# 결정 로그에 실을 열쇠. **표본 수가 반드시 함께 간다** — 그 값이 없으면 나중에 이 수치를
# 근거로 쓸 때 「한 표본이었다」가 드러나지 않는다
KEY_SAMPLES: Final = "unit_samples"
KEY_MEDIAN: Final = "unit_median_usd"
KEY_MIN: Final = "unit_min_usd"
KEY_MAX: Final = "unit_max_usd"

KEY_COST_USD: Final = "cost_usd"

# 돈을 적을 때의 자릿수. 한 호출의 바닥값이 $0.0951 이라 그보다 잘게 봐야 의미가 있다
COST_DIGITS: Final = 4

# 표본이 없을 때의 사유. 문장을 «한 리터럴»로 둔다 —
# 이 저장소의 자동 포맷은 인접한 두 문자열을 길이와 무관하게 한 줄로 붙이므로,
# 나눠 적으면 「두 리터럴이 한 줄에 붙은」 모양만 남고 길이는 그대로다
NO_SAMPLE_REASON: Final = "지난 회차에서 「근거 문서 한 장」의 비용을 잰 적이 없습니다 (표본 0건). 「0이 든다」가 아니라 「모른다」이므로 다음 장을 시작하지 않습니다"


@dataclass(frozen=True)
class Unit:
    """지난 회차들에서 잰 「근거 문서 한 장」의 비용 분포.

    [중요] 표본이 없으면 값이 **`None` 이지 `0` 이 아니다.** 0 으로 두면 남은 예산이
    언제나 충분해 보여, 이 모듈이 막으려는 고장이 그대로 난다.
    """

    samples: int
    median_usd: float | None
    min_usd: float | None
    max_usd: float | None

    def as_log_fields(self) -> dict[str, Any]:
        """결정 로그에 실을 모양.

        중앙값을 쓰기로 한 것 자체가 가정이라, **최소·최대를 함께 남겨** 나중에 그 가정을
        다시 볼 수 있게 한다 — 판정 못 한 URL 의 사유를 회차마다 남기는 것과 같은 방식이다.
        """
        return {
            KEY_SAMPLES: self.samples,
            KEY_MEDIAN: self.median_usd,
            KEY_MIN: self.min_usd,
            KEY_MAX: self.max_usd,
        }


def cost_of(run_dir: Path) -> float:
    """그 실행 폴더에 «지금까지» 기록된 비용의 합.

    러너가 스스로 적은 값을 쓴다. 컨테이너 HOME 의 세션 로그에 기대면 기계를 옮기는
    순간 과거가 사라진다.

    Args:
        run_dir: 실행 폴더

    Returns:
        기록된 비용의 합. 읽을 수 없는 값은 빼고 더한다 — **검사기가 죽어서 파이프라인을
        멈추게 해서는 안 된다.** 결정 로그는 회차마다 덧붙여지는 파일이라 한 줄이 반쯤
        쓰이다 끊길 수 있고, 사람이 손으로 고칠 수도 있다
    """
    return _cost_from(decision_log.read(run_dir))


def _cost_from(entries: list[dict[str, Any]]) -> float:
    """읽어 둔 결정 로그에서 비용 합을 구한다."""
    total = 0.0
    for entry in entries:
        if entry.get("event") != decision_log.EVENT_COST:
            continue
        spent = entry.get(KEY_COST_USD)
        # [주의] `bool` 을 걸러낸다. 파이썬에서 `True` 는 `int` 라 그냥 두면 1달러로 더해진다
        if isinstance(spent, int | float) and not isinstance(spent, bool):
            total += float(spent)
    return total


def unit_cost(runs_dir: Path) -> Unit:
    """「근거 문서 한 장」이 얼마였나를 지난 회차들에서 잰다.

    Args:
        runs_dir: 실행 폴더들이 쌓이는 뿌리

    Returns:
        비용 분포. 잴 표본이 없으면 `samples` 가 0 이고 값이 전부 `None` 이다
    """
    costs = [spent for spent in _completed_costs(runs_dir) if spent > 0]
    if not costs:
        return Unit(samples=0, median_usd=None, min_usd=None, max_usd=None)
    return Unit(samples=len(costs), median_usd=median(costs), min_usd=min(costs), max_usd=max(costs))


def shortfall_reason(unit: Unit, remaining_usd: float) -> str | None:
    """다음 한 장을 시작하면 «안 되는» 이유. 시작해도 되면 None.

    Args:
        unit: 지난 회차들에서 잰 한 장의 비용
        remaining_usd: 이 회차에 남은 예산

    Returns:
        멈출 이유, 계속해도 되면 None. **사유에 두 수를 다 싣는다** —
        「모자랍니다」만 남으면 나중에 그 판정이 옳았는지 되짚을 수 없다
    """
    if unit.median_usd is None:
        return NO_SAMPLE_REASON

    needed_usd = unit.median_usd * START_THRESHOLD_RATIO
    if remaining_usd < needed_usd:
        return (
            f"남은 예산 ${remaining_usd:.{COST_DIGITS}f} 이 "
            f"한 장 중앙값 ${unit.median_usd:.{COST_DIGITS}f} 의 절반(${needed_usd:.{COST_DIGITS}f})에 못 미칩니다"
            f" — 표본 {unit.samples}건"
        )
    return None


def _completed_costs(runs_dir: Path) -> list[float]:
    """근거 문서를 «낸» 실행 폴더들의 비용.

    [중요] 폴더마다 결정 로그를 **한 번만** 읽는다. 「냈나」와 「얼마였나」를 따로 물으면
    같은 파일을 두 번 파싱하는데, 이 함수는 **회차의 반복마다** 불리고 `runs/` 는
    git 에 포함돼 **회차당 한 폴더씩 영원히 늘어난다** — 지우지 않기로 한 폴더다.
    """
    if not runs_dir.is_dir():
        return []

    costs: list[float] = []
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        entries = decision_log.read(run_dir)
        if _produced_from(entries):
            costs.append(_cost_from(entries))
    return costs


def _produced_from(entries: list[dict[str, Any]]) -> bool:
    """읽어 둔 결정 로그에서 그 폴더가 근거 문서를 «실제로» 냈나를 판정한다.

    [중요] **「단계를 다 마쳤나」로는 못 가른다.** 마친 단계 목록에는 건너뛴 단계도 들어가고,
    단계를 늘리면 예전 완주 폴더가 미완성으로 보이는데 그 회차가 남은 단계를 **건너뛰기로
    채우면서 목록이 다시 꽉 찬다.** 그러면 「완주」로 읽히지만 문서는 한 장도 안 냈다.

    [실측 2026-09-15] 이 고장이 진짜 원장에서 일어났다 — 실제 폴더 넷에서 표본이 3건
    (중앙값 $2.2411)으로 잡혔고, 문서를 낸 폴더는 **하나($4.5735)**뿐이었다.
    한 단위가 절반으로 줄면 **시작 임계도 절반이 되어 루프가 실제보다 한 장 더 시작한다.**
    비용 가드(`> 0`)로도 안 걸렸다 — 그 폴더들은 **예전 생애에 쓴 돈**이 남아 있었다.

    [중요] 판정 재료는 **결정 로그에 적힌 사실** 하나다. 마지막 단계가 문서를 쓴 뒤
    그 파일명을 함께 적으므로, 그 표시가 곧 「냈다」다. 상태 파일을 읽지 않는 덕에
    **사람이 손으로 고친 폴더나 예전 단계 이름이 든 폴더에서도 판정이 죽지 않는다.**

    [주의] 파일 존재로 되짚지 않는다. 산출물 폴더는 부르는 쪽이 고를 수 있어서,
    경로를 다시 계산하면 **시험 삼아 돌린 실행과 진짜 회차가 갈리지 않는다.**

    [중요] **마지막 단계의 것만 센다.** 뒤에 단계를 더하면서 그 단계도 문서 파일명을
    적게 되면, 열쇠만 보는 판정은 **한 폴더를 두 번 「냈다」로 읽는다.**
    「판 것」 표시가 언제나 마지막 단계로 옮겨가는 것과 같은 축이다(계층 계약 §4).
    """
    last_step = steps.STEPS[-1]
    return any(
        entry.get("step") == last_step
        and entry.get("event") == decision_log.EVENT_JUDGED
        and isinstance(entry.get(decision_log.KEY_DOSSIER), str)
        for entry in entries
    )

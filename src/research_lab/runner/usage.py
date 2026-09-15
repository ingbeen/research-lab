"""토큰을 «성분별로» 세고, 5시간 한도의 몇 %에 해당하는지 계산한다.

[중요] `decision_log` 의 `tokens` 합계와 **뜻이 다르다.** 그 합계는 캐시에서 읽은 토큰을
빼고 센다 — 비용 기준으로는 옳다(캐시가 돌면 그 값이 새 입력 토큰보다 한 자릿수 크고,
그대로 더하면 비용 추정이 그 배수만큼 틀어진다). 그런데 **한도는 캐시에서 읽은 토큰도
먹으므로** 그 합계는 한도 소비의 **하한**이다. 그래서 여기서는 성분을 갈라 둔다.

[중요] 가중치를 «추정하지 않는다». 어느 성분이 한도에서 몇으로 세는지는 공개돼 있지 않다.
추정치를 넣으면 그 숫자가 근거처럼 굳으므로, 아래 보정 한 쌍이 그 가중치를 **안에 흡수**하게
만든다 — 보정은 「그 회차의 토큰 대비 관측된 %」이고, 성분을 따로 남기는 것은
**나중에 가중치가 드러나면 다시 계산할 수 있게** 하기 위해서다.

[중요] **「한도가 몇 % 남았나」를 돌려주는 통로를 두지 않는다.** 5시간 «창»이 언제
시작됐는지는 이 파이프라인이 알 수 없다. 잔량을 내는 함수를 두면 **남은 양을 아는 것처럼
보이는 숫자**가 생기고, 그것을 근거로 예산을 정하면 틀린다. 말할 수 있는 것은
「이 회차가 쓴 양이 한 창 한도의 몇 %에 해당하는가」 하나다.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from research_lab.runner import decision_log

# 성분 열쇠의 주인은 **결정 로그**다. 여기서 이름을 다시 적지 않고 «가져온다» —
# 읽는 쪽이 리터럴을 따로 들고 있으면 이름을 바꾼 날 둘이 갈리고,
# 갈렸다는 사실은 **집계가 0 으로 나오는 것 말고는 아무 신호도 내지 않는다**
KEY_INPUT: Final = decision_log.KEY_TOKENS_INPUT
KEY_OUTPUT: Final = decision_log.KEY_TOKENS_OUTPUT
KEY_CACHE_CREATION: Final = decision_log.KEY_TOKENS_CACHE_CREATION
KEY_CACHE_READ: Final = decision_log.KEY_TOKENS_CACHE_READ


@dataclass(frozen=True)
class Tokens:
    """한 호출·한 폴더·한 회차가 쓴 토큰의 성분."""

    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    @property
    def new_total(self) -> int:
        """«새로» 쓴 토큰 — 캐시에서 읽은 것을 뺀 값.

        [중요] `decision_log` 의 `tokens` 와 같은 뜻이다. 비용을 보는 쪽의 값이며
        **지난 회차 로그와의 비교가 이 뜻에 물려 있다.**
        """
        return self.input + self.output + self.cache_creation

    @property
    def all_total(self) -> int:
        """한도 기준 합 — 캐시에서 읽은 것을 «포함»한 값.

        [중요] 한도는 캐시에서 읽은 토큰도 먹는다. 빼고 세면 **한도 소비를 과소계산**하고,
        그 숫자를 근거로 예산을 정하면 실제보다 많이 쓰게 된다.
        """
        return self.new_total + self.cache_read

    def __sub__(self, other: "Tokens") -> "Tokens":
        """이 회차가 «더한» 만큼.

        [중요] 한 회차가 이어받은 폴더에는 지난 회차의 줄이 남아 있다. 폴더의 합을 그대로
        쓰면 **지난 회차의 소비까지 이번 것으로 세고**, 그 어긋남은 아무 에러도 내지 않는다.
        비용을 차분으로 세는 것과 같은 축이다.
        """
        return Tokens(
            input=self.input - other.input,
            output=self.output - other.output,
            cache_creation=self.cache_creation - other.cache_creation,
            cache_read=self.cache_read - other.cache_read,
        )

    def __add__(self, other: "Tokens") -> "Tokens":
        """여러 실행 폴더를 돈 한 회차의 합."""
        return Tokens(
            input=self.input + other.input,
            output=self.output + other.output,
            cache_creation=self.cache_creation + other.cache_creation,
            cache_read=self.cache_read + other.cache_read,
        )

    def as_log_fields(self) -> dict[str, int]:
        """로그에 실을 모양 — 결정 로그의 성분 열쇠와 «같은 이름»을 쓴다.

        이름이 같아야 회차 로그의 합과 폴더별 줄을 **같은 열쇠로 훑을 수 있다.**
        """
        return {
            KEY_INPUT: self.input,
            KEY_OUTPUT: self.output,
            KEY_CACHE_CREATION: self.cache_creation,
            KEY_CACHE_READ: self.cache_read,
        }


@dataclass(frozen=True)
class LimitCalibration:
    """사람이 한 번 재서 넣은 「한 창의 한도」.

    [중요] **분모는 프로그램으로 읽을 수 없다.** CLI 에 사용량 명령이 없고 응답에도 한도
    필드가 없다 — 한도 신호는 부딪혔을 때의 「소진 + 리셋 시각」 문구 하나뿐이다.
    그래서 회차 «전»과 «후»에 사용량 화면을 찍어 그 차이로 한 쌍을 만든다.

    [중요] `measured_on` 이 **값과 함께 나간다.** 한도 정책이 바뀌면 이 값이 조용히
    틀리므로, 날짜 없는 비율을 내지 않는다.
    """

    # `Tokens.all_total` 과 «같은 단위»다 — 분자에 무엇을 쓰는지가 분모의 뜻을 정한다
    tokens_per_window: int
    measured_on: str


# 이 계정·이 기계의 보정값. **아직 재지 않았다.**
#
# [중요] `None` 인 동안 한도 비율은 **「잴 수 없음」**이고 «0 이 아니다». 0 으로 내면
# 「한도를 안 썼다」로 읽히고, 「잴 수 없었다」와 「0이었다」를 구별하지 못하는 계측은
# 계측이 아니라 잡음이다.
#
# 재는 법: 회차 «전»과 «후»에 대화 세션의 사용량 화면을 찍어, 그 회차가 창의 몇 %를
# 먹었는지를 본다. 그 %와 이 회차의 `all_total` 로 한 창의 토큰 수를 역산해 여기 적고
# `measured_on` 에 잰 날짜를 적는다. CLI 플래그로 두지 않는 이유는, 예약 실행의 작업
# 정의에 값이 하나 더 박히면 **기본값을 고치는 날 예약 회차의 동작이 조용히 달라지기** 때문이다
CALIBRATION: Final[LimitCalibration | None] = None


def tokens_of(run_dir: Path) -> Tokens:
    """그 실행 폴더에 «지금까지» 기록된 토큰 성분의 합.

    Args:
        run_dir: 실행 폴더

    Returns:
        성분별 합. **읽을 수 없는 값은 빼고 더한다** — 검사기가 죽어서 파이프라인을
        멈추게 해서는 안 된다. 이 기능 «이전»에 쌓인 줄에는 성분이 아예 없고,
        응답 모양은 CLI 가 정하는 것이라 언제 바뀌어도 이상하지 않다
    """
    totals = dict.fromkeys(decision_log.TOKEN_COMPONENT_KEYS, 0)
    for entry in decision_log.read(run_dir):
        if entry.get("event") != decision_log.EVENT_COST:
            continue
        for key in totals:
            totals[key] += _as_count(entry.get(key))

    return Tokens(
        input=totals[KEY_INPUT],
        output=totals[KEY_OUTPUT],
        cache_creation=totals[KEY_CACHE_CREATION],
        cache_read=totals[KEY_CACHE_READ],
    )


def window_share_percent(tokens: Tokens, *, calibration: LimitCalibration | None) -> float | None:
    """그 토큰이 «한 창 한도의 몇 %»에 해당하나. 보정값이 없으면 None.

    Args:
        tokens: 그 회차가 쓴 토큰
        calibration: 사람이 재서 넣은 한 창의 한도. **기본값을 두지 않는다** —
            기본 인자는 import 시점에 한 번 굳으므로, 부르는 쪽이 모듈 상수를 «따로» 읽으면
            같은 값이 두 경로로 갈려 **비율은 비었는데 보정 날짜만 찍히는** 반쯤 채워진
            줄이 나온다. 보정값을 고르는 자리는 `calibrated()` 하나다

    Returns:
        백분율. 보정값이 없거나 분모가 0 이하면 **None 이다 — 0 이 아니다**.
        **분자가 0 일 때도 None 이다** — 아래 이유를 본다

    [중요] **성분이 0 인 것을 「0% 썼다」로 내지 않는다.** 그 값이 0 이 되는 길이 둘인데
    하나는 고장이다 — 응답에 `usage` 가 안 실리면 성분이 통째로 빠지고, 이 기능 «이전»에
    쌓인 폴더도 그렇다. 그때 0% 로 내면 **계측이 죽었다는 신호가 없고**, 나중에
    「한도를 거의 안 쓴다」는 결론을 내게 된다. 그 0 은 사실이 아니라 **측정이 없었다는 뜻**이다.

    나머지 하나(전부 건너뛴 회차라 실제로 아무것도 안 쓴 경우)는 여기서 「잴 수 없음」으로
    보이지만 **해가 없다** — 같은 줄에 장수와 쓴 돈이 0 으로 함께 적혀 있어 사람이 바로 가른다.
    """
    if calibration is None or calibration.tokens_per_window <= 0:
        return None
    if tokens.all_total <= 0:
        return None
    return tokens.all_total / calibration.tokens_per_window * 100.0


def per_dossier_percent(share_percent: float | None, *, produced: int) -> float | None:
    """근거 문서 «한 장»이 한도의 몇 %였나. 낸 장이 없으면 None.

    Args:
        share_percent: 그 회차 전체의 비율
        produced: 그 회차가 낸 근거 문서의 장수

    Returns:
        한 장당 백분율. 장수가 0 이면 **나눗셈을 하지 않는다** — 문서를 한 장도 못 낸
        회차는 정상으로 있다(원장 포화 · 「막힘」으로 접힌 폴더를 닫기만 한 회차)
    """
    if share_percent is None or produced <= 0:
        return None
    return share_percent / produced


def calibrated() -> LimitCalibration | None:
    """지금 쓸 보정값 — **이 저장소에서 보정값을 고르는 자리는 여기 하나다.**

    부르는 쪽이 모듈 상수를 각자 읽으면 **한쪽만 갈려 반쯤 채워진 줄**이 나온다 —
    비율은 비었는데 보정 날짜만 찍히는 모양이고, 그것을 보면 「보정했는데 왜 비었지」로
    읽혀 엉뚱한 곳을 보게 된다.
    """
    return CALIBRATION


def _as_count(value: Any) -> int:
    """정수로 읽히는 값만 센다.

    [주의] 참/거짓을 걸러낸다. 파이썬에서 `True` 는 `int` 라 그냥 두면 1 로 더해진다.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value

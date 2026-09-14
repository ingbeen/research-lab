"""실현가능성 게이트의 계약을 고정한다 — 4·5번 칸의 «자리»만 보고 «답»은 보지 않는다.

이 칸들은 자유 서술로 두면 **찾은 것만 쓰고 안 찾은 것은 언급조차 안 한다.** 설계 §2 의
채워 본 예시에서 실제로 문제를 잡아낸 칸이 5번(「신호가 연 1회」)이었고, 그것은
**칸이 정해져 있어서 안 물을 수가 없었기 때문에** 나왔다. 그래서 게이트는 설계 §7 의
두 표가 묻는 것을 하나씩 자리로 요구한다.

[중요] **답의 내용은 판정하지 않는다.** 「해당 없음」이라 적을 길을 남기며, 그 길이 없으면
게이트가 에이전트에게 **없는 사실을 채워 넣을 압력**을 만든다 — 반증 게이트가 「0건 = 실패」를
고르지 않은 것과 같은 축이다.

[중요] **비용·세금·슬리피지는 «막지 않고 센다».** 금지어로 막으면 설계 §10.1 A 가 실측으로
뒤집은 함정(진짜 원장의 후보 13개 중 12개가 사전에 걸렸다)에 다시 선다. 기각의 대가가
오탐 중 가장 크고, 이 혼입은 「없는 출처」와 달리 **읽으면 사람이 바로 본다.**
"""

from typing import Any

import pytest

from research_lab.gate import feasibility


def _filled() -> dict[str, Any]:
    """모든 자리가 채워진 산출물 — 여기서 하나씩 빼며 계약을 잰다."""
    return {
        "claim": "미국 주가지수 ETF 를 옵션 만기주 첫 거래일에 사서 만기일 종가에 판다",
        "market": "미국",
        "data": {
            "needs": ["미국 주가지수 ETF 일봉", "옵션 만기일 달력"],
            "availability": "이미 있음",
            "how_to_get": "미국 ETF 일봉은 yfinance 계열로 받을 수 있고, 이 기계에 원본가와 수정주가 쌍으로 받아둔 것이 있다",
            "point_in_time": "일봉 종가만 쓰므로 그날 장 마감 뒤에 알 수 있는 값이다",
            "survivorship": "지수 추종 ETF 한 종목이라 상장폐지 편향이 들어올 자리가 없다",
            "fallback": "막히면 지수 일봉으로 대체하되 집행 불가로 표시한다",
        },
        "execution": {
            "instrument": "국내 증권사로 직접 매수 가능한 미국 상장 ETF 가 있다",
            "signal_frequency": "월 1회 — 연 12건",
            "leverage": "미국은 3배 ETF 가 있다",
            "waking_hours": "미국장이라 한국시간 야간이며 서머타임으로 한 시간 움직인다",
            "intraday_precision": "종가 기준이라 분·초 집행이 필요 없다",
        },
        "unverified": ["위클리 옵션 상장 이후 월물 만기의 특별함이 희석됐는지"],
    }


# --------------------------------------------------------------------------
# 채워진 것은 통과한다
# --------------------------------------------------------------------------


def test_filled_payload_passes() -> None:
    """
    목적: 4·5번 칸이 다 채워진 산출물이 막히지 «않는» 계약을 고정한다.

    Given: 모든 자리가 채워진 산출물
    When: 검사한다
    Then: 사유가 없다
    """
    assert feasibility.shortfall_reason(_filled()) is None


def test_not_applicable_is_a_valid_answer() -> None:
    """
    목적: 「해당 없음」이라 적을 길이 남아 있는 계약을 고정한다.

    이 길이 없으면 게이트가 **없는 사실을 채워 넣을 압력**을 만든다. 생존편향이
    들어올 자리가 없는 후보에서 「생존편향을 처리했다」를 억지로 쓰게 만드는 셈이고,
    그것은 반증을 지어내게 만드는 것과 같은 고장이다.

    Given: 몇 자리에 「해당 없음」이 적힌 산출물
    When: 검사한다
    Then: 통과한다
    """
    payload = _filled()
    payload["data"]["survivorship"] = "해당 없음 — 지수 ETF 한 종목이다"
    payload["execution"]["intraday_precision"] = "해당 없음"

    assert feasibility.shortfall_reason(payload) is None


def test_gate_does_not_judge_the_quality_of_answers() -> None:
    """
    목적: 게이트가 답의 «질»을 판정하지 «않는» 계약을 고정한다.

    판정하려 들면 게이트가 또 하나의 판단자가 된다. 답이 부실한지는 나중에 사람이 본다.

    Given: 모든 자리가 한 글자로 채워진 산출물
    When: 검사한다
    Then: 통과한다
    """
    payload = _filled()
    for field, _ in feasibility.DATA_TEXT_FIELDS:
        payload["data"][field] = "x"
    for field, _ in feasibility.EXECUTION_FIELDS:
        payload["execution"][field] = "x"

    assert feasibility.shortfall_reason(payload) is None


# --------------------------------------------------------------------------
# 빈 자리는 막는다
# --------------------------------------------------------------------------


@pytest.mark.parametrize("field", [name for name, _ in feasibility.DATA_TEXT_FIELDS])
def test_empty_data_field_is_blocked(field: str) -> None:
    """
    목적: 4번 칸의 «각» 자리가 비면 막는 계약을 고정한다 (설계 §7 의 4번 칸 표).

    설계 §7 은 자리마다 「안 물으면 생기는 일」을 함께 적어 두었다 —
    미래 참조를 안 물으면 **못 잴 것을 재게 되고**, 생존편향을 안 물으면
    **결과가 좋게 나온다. 틀리게.**

    Given: 그 자리만 빈 산출물
    When: 검사한다
    Then: 사유가 나오고, 그 사유가 빈 자리를 짚는다
    """
    payload = _filled()
    payload["data"][field] = "   "

    shortfall = feasibility.shortfall_reason(payload)

    assert shortfall is not None
    assert field in shortfall


@pytest.mark.parametrize("field", [name for name, _ in feasibility.EXECUTION_FIELDS])
def test_empty_execution_field_is_blocked(field: str) -> None:
    """
    목적: 5번 칸의 «각» 자리가 비면 막는 계약을 고정한다 (설계 §7 의 5번 칸 표).

    **문제를 실제로 잡아낸 칸이 5번이다.** 설계 §2 의 예시에서 「신호가 연 1회」는
    읽자마자 걸리는데, 근거만 모으는 문서였다면 안 나왔을 항목이다.

    Given: 그 자리만 빈 산출물
    When: 검사한다
    Then: 사유가 나오고, 그 사유가 빈 자리를 짚는다
    """
    payload = _filled()
    payload["execution"][field] = ""

    shortfall = feasibility.shortfall_reason(payload)

    assert shortfall is not None
    assert field in shortfall


def test_empty_needs_is_blocked() -> None:
    """
    목적: 「어떤 데이터가 필요한가」가 비면 막는 계약을 고정한다.

    안 물으면 **다 된다고 가정하고 넘어간다** — 설계 §7 이 그 자리에 적어 둔 결과다.

    Given: 필요한 데이터가 빈 목록인 산출물
    When: 검사한다
    Then: 사유가 나온다
    """
    payload = _filled()
    payload["data"]["needs"] = []

    assert feasibility.shortfall_reason(payload) is not None


def test_missing_market_is_blocked() -> None:
    """
    목적: [중요] 시장이 안 적히면 막는 계약을 고정한다 (설계 §7.0).

    「배수를 걸 수 있나」는 **시장을 먼저 적어야** 기각 신호로 쓸 수 있다.
    「1배로만 되는데 크기가 작다」는 국내에서는 기각이지만 **미국에서는 3배를
    확인하기 전에는 기각이 아니다.** 시장 없이 적힌 판정은 나중에 되짚을 수도 없다.

    Given: 시장이 빈 산출물
    When: 검사한다
    Then: 사유가 나온다
    """
    payload = _filled()
    payload["market"] = ""

    assert feasibility.shortfall_reason(payload) is not None


@pytest.mark.parametrize("section", [feasibility.KEY_DATA, feasibility.KEY_EXECUTION])
def test_missing_section_is_blocked(section: str) -> None:
    """
    목적: 절 «자체»가 없으면 막는 계약을 고정한다.

    절이 없다는 것은 그 단계가 **아예 묻지 않았다**는 뜻이다 —
    반증 칸이 없는 것을 막는 것과 같은 자리다.

    Given: 한 절이 통째로 없는 산출물
    When: 검사한다
    Then: 사유가 나온다
    """
    payload = _filled()
    del payload[section]

    assert feasibility.shortfall_reason(payload) is not None


@pytest.mark.parametrize("wrong", ["절이 아니라 문장", ["목록"], 0, None])
def test_section_in_a_wrong_shape_is_blocked(wrong: Any) -> None:
    """
    목적: 절 자리에 매핑이 «아닌» 것이 와도 통과되지 않는 계약을 고정한다.

    에이전트가 낸 값이라 절 자리에 문자열이나 목록이 오는 일이 흔하고,
    그런 값은 비어 있지 않으므로 **「적혀 있다」로 읽혀 조용히 통과할 수 있다.**

    Given: 4번 칸 자리에 매핑이 아닌 값이 든 산출물
    When: 검사한다
    Then: 사유가 나온다
    """
    payload = _filled()
    payload["data"] = wrong

    assert feasibility.shortfall_reason(payload) is not None


# --------------------------------------------------------------------------
# 데이터 판정은 «약속된 값»이어야 한다
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", list(feasibility.AVAILABILITY_VALUES))
def test_every_promised_availability_value_passes(value: str) -> None:
    """
    목적: 약속한 판정 값 «전부»가 통과하는 계약을 고정한다.

    하나라도 막히면 그 판정을 낸 회차가 영영 통과하지 못하는데,
    **게이트 자신이 원인이라 로그만 봐서는 드러나지 않는다.**

    Given: 약속된 판정 값
    When: 검사한다
    Then: 통과한다
    """
    payload = _filled()
    payload["data"]["availability"] = value

    assert feasibility.shortfall_reason(payload) is None


def test_unpromised_availability_value_is_blocked() -> None:
    """
    목적: 약속 밖의 판정 값을 막는 계약을 고정한다.

    이것은 «값의 내용»을 판정하는 것이 아니라 **약속된 모양인지**를 보는 것이다
    — 목록 자리에 문자열이 오면 막는 것과 같은 갈래다. 이 값이 기계로 읽혀야
    「데이터가 이미 있는 후보가 몇이었나」를 나중에 셀 수 있다.

    [중요] 막힌 사유가 **약속된 값들을 알려 준다.** 알려 주지 않으면 다음 회차가
    같은 자리에서 같은 값을 또 낸다.

    Given: 약속 밖의 판정 값
    When: 검사한다
    Then: 사유가 나오고 약속된 값들이 그 사유에 들어 있다
    """
    payload = _filled()
    payload["data"]["availability"] = "아마 있을 듯"

    shortfall = feasibility.shortfall_reason(payload)

    assert shortfall is not None
    assert all(value in shortfall for value in feasibility.AVAILABILITY_VALUES)


# --------------------------------------------------------------------------
# 검사기는 죽지 않는다
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": {}, "execution": {}},
        {"market": None, "data": {"needs": "목록이 아니다"}, "execution": {"instrument": ["목록"]}},
        {"data": {"needs": [None, 0]}, "execution": {}},
    ],
)
def test_malformed_payload_does_not_crash_the_gate(payload: dict[str, Any]) -> None:
    """
    목적: 모양이 어긋난 입력에 게이트가 «죽지 않는» 계약을 고정한다.

    검사기가 죽어서 파이프라인을 멈추게 해서는 안 된다 — 계층 계약 §3 이다.
    고칠 수 있었던 것까지 그 회차를 끝낸다.

    Given: 모양이 여러 방식으로 어긋난 산출물
    When: 검사한다
    Then: 예외 없이 사유가 나온다
    """
    assert feasibility.shortfall_reason(payload) is not None


# --------------------------------------------------------------------------
# 비용 표현은 «세고» 막지 않는다
# --------------------------------------------------------------------------


def test_cost_terms_are_counted_but_not_blocked() -> None:
    """
    목적: [중요] 비용·세금·슬리피지가 5번 칸에 섞여도 «막지 않고 세는» 계약을 고정한다.

    막으면 금지어 = 기각 구조가 되어 설계 §10.1 A 가 실측으로 뒤집은 함정에 다시 선다.
    판정(2번 칸)이 아직 없으므로 **그 값이 결론을 만들 자리도 아직 없다.**
    분포를 보고 나중에 판단한다 — 겹침 계측과 같은 축이다.

    Given: 5번 칸에 수수료와 세금이 섞인 산출물
    When: 검사하고 또 센다
    Then: 막히지 않고, 걸린 표현이 돌아온다
    """
    payload = _filled()
    payload["execution"]["signal_frequency"] = "월 1회 — 왕복 수수료와 세금을 빼면 남는 게 없다"

    assert feasibility.shortfall_reason(payload) is None

    counted = feasibility.cost_terms_in(payload["execution"])
    assert "수수료" in counted
    assert "세금" in counted


def test_exchange_rate_exposure_is_not_a_cost_term() -> None:
    """
    목적: [중요] 「환율 노출」과 「환전 스프레드」를 «가르는» 계약을 고정한다 (설계 §7.0).

    환전 **스프레드**는 비용이라 5번 칸의 금지에 걸리지만, 환율 **노출**은
    「달러로 5% 올랐는데 원화로는 2%였다」는 **측정의 문제**라 10번 칸 기준선 항목이다.
    둘을 섞으면 5번 칸이 금지된 값을 들고 결론을 만들게 된다.

    Given: 환율 노출만 적힌 답과, 환전 스프레드가 적힌 답
    When: 각각 센다
    Then: 앞은 안 걸리고 뒤는 걸린다
    """
    exposure = {"waking_hours": "원화 기준 수익이 달러 수익과 다르므로 환율 노출이 있다"}
    spread = {"waking_hours": "환전 스프레드를 빼면 얼마 안 남는다"}

    assert feasibility.cost_terms_in(exposure) == ()
    assert feasibility.cost_terms_in(spread) != ()


def test_clean_execution_section_counts_nothing() -> None:
    """
    목적: 멀쩡한 5번 칸에서 아무것도 세지 «않는» 계약을 고정한다.

    늘 무언가 걸리면 계측이 신호를 주지 못한다.

    Given: 비용을 말하지 않는 5번 칸
    When: 센다
    Then: 빈 것이 돌아온다
    """
    assert feasibility.cost_terms_in(_filled()["execution"]) == ()


@pytest.mark.parametrize("wrong", [None, "문장", ["목록"], 0, {"a": {"b": "수수료"}}])
def test_cost_counter_does_not_crash(wrong: Any) -> None:
    """
    목적: 계측이 모양 어긋난 입력에 «죽지 않는» 계약을 고정한다.

    이 값은 계측이라, 못 재는 것 때문에 그 회차가 멈추면 안 된다 —
    판정을 못 하는 것과 실패로 판정하는 것은 다르다.

    Given: 모양이 어긋난 절
    When: 센다
    Then: 예외 없이 튜플이 돌아온다
    """
    assert isinstance(feasibility.cost_terms_in(wrong), tuple)

"""토큰 성분과 5시간 한도 비율의 계약을 고정한다.

이 파일이 막는 고장은 셋이고 **셋 다 에러를 내지 않는다.**

- **캐시에서 읽은 토큰을 버리는 것.** 비용 기준으로는 빼는 것이 옳지만(캐시가 돌면 그 값이
  새 입력 토큰보다 한 자릿수 크다) **한도 기준으로는 정반대**다. 성분을 따로 남기지 않으면
  나중에 가중치를 바꿔 **다시 계산할 수가 없다** — 원본을 버리고 집계만 남기는 것이다
- **보정값이 없는데 비율을 «0»으로 내는 것.** 0 은 「한도를 안 썼다」로 읽힌다.
  「잴 수 없었다」와 「0이었다」를 구별하지 못하는 계측은 계측이 아니라 잡음이다
- **「한도가 몇 % 남았나」를 말하는 것.** 5시간 «창»이 언제 시작됐는지는 파이프라인이
  알 수 없다. 말할 수 있는 것은 「이 회차가 쓴 양이 한 창 한도의 몇 %에 해당하는가」 하나다
"""

from pathlib import Path

from research_lab.runner import decision_log, usage

# 실측된 한 회차의 토큰 성분 규모. 캐시 읽기가 새 입력보다 한 자릿수 큰 것이 이 모듈의 동기다
SAMPLE = usage.Tokens(input=12_000, output=8_000, cache_creation=30_000, cache_read=480_000)


def test_new_total_excludes_cache_reads() -> None:
    """
    목적: 「새 토큰」이 캐시 읽기를 빼고 세는 계약을 고정한다.

    이 값은 **비용**을 보는 쪽의 것이며 지난 회차 로그와 비교가 물려 있다.
    뜻을 바꾸면 과거와의 비교가 조용히 끊긴다.

    Given: 네 성분이 있는 토큰
    When: 새 토큰 합을 본다
    Then: 캐시 읽기가 빠져 있다
    """
    assert SAMPLE.new_total == 12_000 + 8_000 + 30_000


def test_all_total_includes_cache_reads() -> None:
    """
    목적: 「전체 합」이 캐시 읽기를 «포함»하는 계약을 고정한다.

    [주의] 이 값은 **한도 비율의 분자가 아니다.** 한때 그렇게 보았으나
    [실측 2026-09-15] 이 부정했다 — 자세한 것은 아래 분자 테스트에 있다.
    그래도 이 성분을 계속 세는 이유는, 가중치가 나중에 드러나면 **다시 계산할 재료**가
    되기 때문이다. 원본을 버리고 집계만 남기지 않는다.

    Given: 네 성분이 있는 토큰
    When: 전체 합을 본다
    Then: 캐시 읽기가 들어 있고, 새 토큰 합보다 크다
    """
    assert SAMPLE.all_total == 12_000 + 8_000 + 30_000 + 480_000
    assert SAMPLE.all_total > SAMPLE.new_total


def test_tokens_are_summed_from_the_decision_log(tmp_path: Path) -> None:
    """
    목적: 실행 폴더의 성분이 «단계 전부의 합»으로 읽히는 계약을 고정한다.

    한 폴더는 여덟 단계를 돌고 각 단계가 자기 줄을 남긴다. 한 단계만 보면 그 폴더가
    쓴 양이 드러나지 않는다.

    Given: 두 단계의 비용 줄이 든 폴더
    When: 그 폴더의 성분을 잰다
    Then: 성분마다 합이 나온다
    """
    decision_log.record(
        tmp_path, "collect", decision_log.EVENT_COST, tokens_input=100, tokens_output=10, tokens_cache_read=1_000
    )
    decision_log.record(
        tmp_path, "rebut", decision_log.EVENT_COST, tokens_input=200, tokens_output=20, tokens_cache_read=2_000
    )

    tokens = usage.tokens_of(tmp_path)

    assert tokens.input == 300
    assert tokens.output == 30
    assert tokens.cache_read == 3_000


def test_missing_or_broken_components_do_not_raise(tmp_path: Path) -> None:
    """
    목적: 성분이 없거나 숫자가 아닐 때도 예외를 올리지 않는 계약을 고정한다.

    계층 계약 — **검사기가 죽어서 파이프라인을 멈추게 해서는 안 된다.** 지난 회차의 로그에는
    이 성분이 «아예 없고»(이 기능 이전에 쌓인 줄), 응답 모양은 CLI 가 정하는 것이라
    언제 바뀌어도 이상하지 않다.

    Given: 성분이 빠진 줄 · 문자열이 든 줄 · 참/거짓이 든 줄
    When: 성분을 잰다
    Then: 예외 없이 읽히는 값만 더해진다
    """
    decision_log.record(tmp_path, "collect", decision_log.EVENT_COST, cost_usd=1.0, tokens=123)
    decision_log.record(tmp_path, "rebut", decision_log.EVENT_COST, tokens_input="많았다", tokens_output=None)
    # [주의] 참/거짓은 파이썬에서 정수라, 걸러내지 않으면 1 로 더해진다
    decision_log.record(tmp_path, "lineage", decision_log.EVENT_COST, tokens_input=True, tokens_output=5)

    tokens = usage.tokens_of(tmp_path)

    assert tokens.input == 0
    assert tokens.output == 5


def test_difference_measures_only_this_cycle() -> None:
    """
    목적: 회차가 쓴 양을 «차분»으로 재는 계약을 고정한다.

    [중요] 한 회차가 **이어받은 폴더**에는 지난 회차의 줄이 남아 있다. 폴더의 합을 그대로
    쓰면 **지난 회차의 소비까지 이번 것으로 세고**, 그 어긋남은 아무 에러도 내지 않는다.
    비용을 차분으로 세는 것과 같은 축이다.

    Given: 호출 전과 후의 폴더 합
    When: 차를 구한다
    Then: 이번 회차가 더한 만큼만 남는다
    """
    before = usage.Tokens(input=100, output=10, cache_creation=0, cache_read=1_000)
    after = usage.Tokens(input=350, output=40, cache_creation=5, cache_read=9_000)

    added = after - before

    assert added.input == 250
    assert added.output == 30
    assert added.cache_read == 8_000


def test_share_is_none_without_calibration() -> None:
    """
    목적: 보정값이 없을 때 비율이 «0 이 아니라 없음»인 계약을 고정한다.

    0 으로 내면 「한도를 안 썼다」로 읽힌다. 분모는 프로그램으로 읽을 수 없고
    (CLI 에 사용량 명령이 없고 응답에 한도 필드가 없다) **사람이 한 번 재서 넣는 값**이므로,
    넣기 전에는 **모른다고 말해야** 한다.

    Given: 보정값이 없는 상태
    When: 한도 비율을 구한다
    Then: None 이다
    """
    assert usage.window_share_percent(SAMPLE, calibration=None) is None


def test_share_uses_new_tokens() -> None:
    """
    목적: 한도 비율의 분자가 «새 토큰»이라는 계약을 고정한다.

    보정은 「그 회차의 토큰 대비 관측된 %」 한 쌍이므로, 분자에 무엇을 쓰는지가 분모의
    뜻을 정한다. **분자를 새 토큰으로 고정해야** 보정값과 이후 계산의 단위가 같다.

    Given: 한 창이 새 토큰 기준 100만이라는 보정값
    When: 새 토큰 40만을 쓴 회차의 비율을 구한다
    Then: 40% 가 나온다 — 캐시 읽기 10만은 세지 않는다
    """
    sample = usage.Tokens(input=200_000, output=100_000, cache_creation=100_000, cache_read=100_000)

    share = usage.window_share_percent(
        sample, calibration=usage.LimitCalibration(tokens_per_window=1_000_000, measured_on="2026-09-15")
    )

    assert share is not None
    assert abs(share - 40.0) < 0.001


def test_cache_reads_do_not_move_the_share() -> None:
    """
    목적: [중요] 캐시 읽기가 한도 비율을 «바꾸지 않는» 계약을 고정한다.

    [실측 2026-09-15] 같은 날 회차 둘의 전후 사용률을 재서 창 크기를 역산했다.
    **분자를 새 토큰으로 두면 두 측정이 2.4% 안에서 일치하고, 캐시 읽기를 포함한 합으로
    두면 1.8배 어긋난다** — 어긋나는 쪽이 그때까지의 코드였다.

    | 분자 | 1차로 푼 창 | 2차로 푼 창 |
    | --- | --- | --- |
    | 새 토큰 | 1,878,750 | 1,924,835 |
    | 전체 합 | 23,635,475 | 12,825,038 |

    이 고장은 에러를 내지 않는다. 비율이 그럴듯한 숫자로 계속 나오기 때문이다.

    Given: 새 토큰이 같고 캐시 읽기만 100배 차이 나는 두 회차
    When: 각각의 한도 비율을 구한다
    Then: 두 비율이 같다
    """
    calibrated = usage.LimitCalibration(tokens_per_window=1_000_000, measured_on="2026-09-15")
    lean = usage.Tokens(input=10_000, output=10_000, cache_creation=10_000, cache_read=1_000)
    cached = usage.Tokens(input=10_000, output=10_000, cache_creation=10_000, cache_read=100_000)

    assert usage.window_share_percent(lean, calibration=calibrated) == usage.window_share_percent(
        cached, calibration=calibrated
    )


def test_the_calibration_is_filled_in_with_the_date_it_was_measured() -> None:
    """
    목적: 보정값이 «들어 있고» 잰 날짜를 달고 다니는 계약을 고정한다.

    한도 정책이 바뀌면 이 값은 조용히 틀린다. 날짜가 없으면 언제 잰 것인지 알 수 없어
    **틀렸는지조차 판정할 수 없다.** 그래서 날짜 없는 비율을 내지 않는다.

    Given: 이 저장소가 쓰는 보정값
    When: 그 값을 본다
    Then: 토큰 수가 양수이고 잰 날짜가 붙어 있다
    """
    calibration = usage.calibrated()

    assert calibration is not None, "보정값이 비어 있으면 모든 회차의 한도 비율이 「잴 수 없음」이 된다"
    assert calibration.tokens_per_window > 0
    assert calibration.measured_on


def test_per_dossier_share_needs_a_dossier() -> None:
    """
    목적: 「한 장당」 비율이 장수 0 에서 나눗셈을 하지 않는 계약을 고정한다.

    근거 문서를 한 장도 못 낸 회차가 정상으로 있다 — 원장이 포화라 전부 건너뛴 회차,
    「막힘」으로 접힌 폴더를 닫기만 한 회차. 거기서 나누면 터지거나 무한이 된다.

    Given: 한 회차의 비율
    When: 장수가 0 이다 / 2 이다
    Then: 0 이면 None, 2 면 절반이다
    """
    assert usage.per_dossier_percent(50.0, produced=0) is None

    per_dossier = usage.per_dossier_percent(50.0, produced=2)
    assert per_dossier is not None
    assert abs(per_dossier - 25.0) < 0.001


def test_there_is_no_remaining_quota_api() -> None:
    """
    목적: 「한도가 얼마 남았나」를 돌려주는 통로가 «없음»을 고정한다.

    5시간 창이 언제 시작됐는지는 파이프라인이 알 수 없다. 잔량을 내는 함수를 두면
    **남은 양을 아는 것처럼 보이는 숫자**가 생기고, 그것을 근거로 예산을 정하면 틀린다.
    이 테스트는 나중에 그 함수를 무심코 더하는 것을 막는 자리다.

    Given: 이 모듈의 공개 이름들
    When: 잔량을 뜻하는 이름을 찾는다
    Then: 하나도 없다
    """
    forbidden = [name for name in dir(usage) if not name.startswith("_") and "remaining" in name.lower()]

    assert forbidden == [], f"잔량을 내는 통로가 생겼습니다: {forbidden}"


def test_zero_tokens_are_not_zero_percent() -> None:
    """
    목적: [중요] 성분이 0 일 때 «0%»가 아니라 「잴 수 없음」인 계약을 고정한다.

    성분이 0 이 되는 길이 둘이고 **하나는 고장**이다 — 응답에 `usage` 가 안 실리면 성분이
    통째로 빠지고, 이 기능 «이전»에 쌓인 폴더도 그렇다. 그때 0% 로 내면 계측이 죽었다는
    신호가 없어, 나중에 **「한도를 거의 안 쓴다」는 결론**을 내게 된다.
    그 0 은 사실이 아니라 측정이 없었다는 뜻이다.

    [실측 2026-09-15] 실제로 과거 폴더 넷의 성분이 전부 0 으로 읽혔다 — 그 회차들이
    이 기능 이전에 돌았기 때문이다. 보정값을 넣은 뒤라면 그 0 이 그대로 0% 가 됐다.

    Given: 보정값이 있고, 성분이 0 인 토큰
    When: 한도 비율을 구한다
    Then: None 이다
    """
    calibrated = usage.LimitCalibration(tokens_per_window=1_000_000, measured_on="2026-09-15")

    assert usage.window_share_percent(usage.Tokens(), calibration=calibrated) is None

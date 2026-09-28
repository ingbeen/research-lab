"""결정 로그가 덧붙이기만 하고 기계가 훑을 수 있게 남는 계약을 고정한다.

이 로그의 쓸모는 「나중에 기계가 훑는 것」이다 — 게이트 기준이나 프롬프트를 고쳤을 때
**과거 로그를 다시 읽어 「지금 기준이면 판정이 달라졌을 후보」를 찾아내는 것**.
줄글로 남기면 그 질문에 답할 수 없고, 한 줄이 깨졌다고 전부 못 읽게 되면 정작
원인을 되짚어야 할 때 아무것도 못 본다.
"""

from pathlib import Path

from research_lab.agent import invoke
from research_lab.runner import decision_log
from research_lab.runner.failures import FailureKind


def test_missing_log_reads_as_empty(tmp_path: Path) -> None:
    """
    목적: 아직 아무것도 안 적힌 회차를 「빈 기록」으로 다루는 계약을 고정한다.

    Given: 아무것도 없는 실행 폴더
    When: 결정 로그를 읽는다
    Then: 빈 목록이 돌아온다
    """
    assert decision_log.read(tmp_path) == []


def test_recorded_entry_is_readable(tmp_path: Path) -> None:
    """
    목적: 적은 것을 그대로 읽어 오는 계약을 고정한다.

    Given: 검색어를 적은 기록
    When: 다시 읽는다
    Then: 단계·이벤트·내용이 그대로 들어 있다
    """
    decision_log.record(tmp_path, "explore", decision_log.EVENT_READ, queries=["1월 효과", "january effect"])

    entries = decision_log.read(tmp_path)

    assert len(entries) == 1
    assert entries[0]["step"] == "explore"
    assert entries[0]["event"] == decision_log.EVENT_READ
    assert entries[0]["queries"] == ["1월 효과", "january effect"]


def test_records_append_and_keep_order(tmp_path: Path) -> None:
    """
    목적: 기록이 «덧붙기»만 하는 계약을 고정한다.

    다시 쓰면 그 회차의 앞부분이 사라지고 **예외도 나지 않는다.**

    Given: 두 번의 기록
    When: 읽는다
    Then: 둘 다 적힌 순서대로 있다
    """
    decision_log.record(tmp_path, "explore", decision_log.EVENT_READ, url="https://example.com/a")
    decision_log.record(tmp_path, "collect", decision_log.EVENT_JUDGED, verdict="보류")

    events = [entry["event"] for entry in decision_log.read(tmp_path)]

    assert events == [decision_log.EVENT_READ, decision_log.EVENT_JUDGED]


def test_every_entry_is_timestamped(tmp_path: Path) -> None:
    """
    목적: 모든 기록에 시각이 붙는 계약을 고정한다.

    시각이 없으면 회차 예산을 정할 때 「무엇이 얼마나 걸렸나」를 되짚을 수 없다.

    Given: 기록 한 건
    When: 읽는다
    Then: 시각이 들어 있다
    """
    decision_log.record(tmp_path, "explore", decision_log.EVENT_COST, tokens=1234)

    assert decision_log.read(tmp_path)[0]["ts"]


def test_cost_and_tokens_are_recordable(tmp_path: Path) -> None:
    """
    목적: 비용·토큰이 «저장소 안»에 남는 계약을 고정한다.

    이것이 있어야 회차 예산 집계가 저장소 안에서 완결되어, 컨테이너 HOME 의 세션 로그에
    의존하지 않고 **기계를 옮겨도 과거 기록이 git 으로 따라온다.**

    Given: 비용과 토큰과 소요 시간을 적은 기록
    When: 읽는다
    Then: 셋 다 들어 있다
    """
    decision_log.record(
        tmp_path,
        "collect",
        decision_log.EVENT_COST,
        cost_usd=0.12,
        tokens=4321,
        elapsed_seconds=48.5,
    )

    entry = decision_log.read(tmp_path)[0]

    assert entry["cost_usd"] == 0.12
    assert entry["tokens"] == 4321
    assert entry["elapsed_seconds"] == 48.5


def test_cost_line_carries_the_token_components(tmp_path: Path) -> None:
    """
    목적: 한 호출의 토큰이 «성분별로» 남는 계약을 고정한다.

    [중요] 합계 하나만 남기면 **되돌릴 수 없다.** 합계는 캐시에서 읽은 토큰을 빼고 센다.
    가중치는 공개돼 있지 않아 나중에 바뀔 수 있고, **그때 성분이 없으면 다시 계산할 방법이 없다.**

    Given: 네 성분이 든 호출 결과
    When: 비용을 적는다
    Then: 합계와 성분이 한 줄에 함께 남는다
    """
    result = invoke.AgentResult(
        text="답",
        raw="{}",
        cost_usd=0.5,
        tokens=160,
        usage={
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 10,
            "cache_read_input_tokens": 90_000,
        },
        elapsed_seconds=12.0,
        session_id="세션",
    )

    decision_log.record_cost(tmp_path, "collect", result)

    entry = decision_log.read(tmp_path)[0]

    assert entry["tokens"] == 160
    assert entry["tokens_input"] == 100
    assert entry["tokens_output"] == 50
    assert entry["tokens_cache_creation"] == 10
    assert entry["tokens_cache_read"] == 90_000


def test_cost_line_without_components_stays_recordable(tmp_path: Path) -> None:
    """
    목적: 성분을 모를 때도 비용 줄이 «적히는» 계약을 고정한다.

    응답 모양이 바뀌면 성분이 안 올 수 있다. 그때 비용 줄 자체가 빠지면
    **예산 판정의 재료가 사라져** 루프가 「표본 없음」으로 멈춘다 — 응답 모양 변화 하나가
    회차 구조를 바꾸는 셈이다.

    Given: 성분이 없는 호출 결과
    When: 비용을 적는다
    Then: 비용과 합계는 남고, 성분 자리는 비어 있다
    """
    result = invoke.AgentResult(
        text="답", raw="{}", cost_usd=0.5, tokens=None, usage=None, elapsed_seconds=1.0, session_id="세션"
    )

    decision_log.record_cost(tmp_path, "collect", result)

    entry = decision_log.read(tmp_path)[0]

    assert entry["cost_usd"] == 0.5
    assert entry.get("tokens_input") is None


def _call(session_id: str) -> invoke.AgentResult:
    return invoke.AgentResult(
        text="답", raw="{}", cost_usd=0.5, tokens=10, usage=None, elapsed_seconds=1.0, session_id=session_id
    )


def test_the_same_call_is_recorded_once(tmp_path: Path) -> None:
    """
    목적: 같은 호출의 비용이 «두 번» 세이지 않는 계약을 고정한다.

    비용 줄을 적는 자리가 둘이다 — 결과를 돌려받은 단계와, 실패를 받은 러너. 지금은 단계가
    파싱 «뒤»에 적어 겹치지 않지만, 그 순서는 여러 단계 모듈에 흩어진 관용이라 한 곳이
    바뀌면 **같은 호출이 두 번 세이고 에러가 안 난다.** 세션 ID 는 호출마다 새로 정하므로
    그것으로 가른다.

    Given: 같은 세션 ID 의 호출 결과
    When: 비용을 두 번 적는다
    Then: 비용 줄이 하나다
    """
    decision_log.record_cost(tmp_path, "collect", _call("세션-가"))
    decision_log.record_cost(tmp_path, "collect", _call("세션-가"))

    assert len(decision_log.read(tmp_path)) == 1


def test_different_calls_are_recorded_separately(tmp_path: Path) -> None:
    """
    목적: 다른 호출은 각자 비용 줄을 남기는 계약을 고정한다.

    Given: 세션 ID 가 다른 두 호출 결과
    When: 각각 비용을 적는다
    Then: 비용 줄이 둘이다
    """
    decision_log.record_cost(tmp_path, "collect", _call("세션-가"))
    decision_log.record_cost(tmp_path, "collect", _call("세션-나"))

    assert len(decision_log.read(tmp_path)) == 2


def test_korean_is_not_escaped(tmp_path: Path) -> None:
    """
    목적: 한글이 읽을 수 있는 형태로 남는 계약을 고정한다.

    JSON 기본값은 한글을 `\\uXXXX` 로 바꾼다. 그렇게 남으면 사람이 로그를 눈으로 훑을 때
    아무것도 읽을 수 없어, 기계로 파싱하기 전에는 확인이 안 된다.

    Given: 한글이 든 기록
    When: 파일을 날것으로 본다
    Then: 한글이 그대로 보인다
    """
    decision_log.record(tmp_path, "collect", decision_log.EVENT_DISCARDED, reason="1차 출처가 없다")

    raw = (tmp_path / "decisions.jsonl").read_text(encoding="utf-8")

    assert "1차 출처가 없다" in raw


def test_broken_line_does_not_hide_the_rest(tmp_path: Path) -> None:
    """
    목적: 깨진 한 줄이 그 회차의 기록 전부를 가리지 않는 계약을 고정한다.

    한 줄이 깨졌다고 전부 못 읽게 되면, 정작 원인을 되짚어야 할 때 아무것도 못 본다.

    Given: 중간에 깨진 줄이 섞인 로그
    When: 읽는다
    Then: 멀쩡한 기록은 그대로 돌아온다
    """
    decision_log.record(tmp_path, "explore", decision_log.EVENT_READ, url="https://example.com/a")
    with (tmp_path / "decisions.jsonl").open("a", encoding="utf-8") as file:
        file.write("{여기서 깨졌다\n")
    decision_log.record(tmp_path, "collect", decision_log.EVENT_JUDGED, verdict="기각")

    entries = decision_log.read(tmp_path)

    assert [entry["event"] for entry in entries] == [
        decision_log.EVENT_READ,
        decision_log.EVENT_JUDGED,
    ]


# --------------------------------------------------------------------------
# 그 단계의 «마지막 품질 실패» — 다음 시도의 지시문에 싣는 재료
# --------------------------------------------------------------------------


def _failed(run_dir: Path, step: str, kind: FailureKind, raw: str, *, answered: bool = True) -> None:
    """러너가 한 시도를 실패로 적는 줄을 흉내 낸다. `answered` 면 그 시도에서 에이전트가 답을 냈다(비용 줄)."""
    if answered:
        decision_log.record(run_dir, step, decision_log.EVENT_COST, cost_usd=0.1, tokens=10, elapsed_seconds=1.0)
    decision_log.record(run_dir, step, decision_log.EVENT_FAILED, kind=kind.value, attempt=1, max_retries=3, raw=raw)


def test_the_last_quality_failure_of_the_step_is_returned(tmp_path: Path) -> None:
    """
    목적: [중요] 그 단계의 «마지막» 품질 실패 원문을 돌려주는 계약을 고정한다.

    품질 실패는 회차 안에서 재시도되지 않는다. 사유가 다음 시도의 지시문에 안 실리면
    **같은 표현 · 같은 주소를 다시 내어 같은 자리에서 막히고, 세 번이면 후보가 걷힌다.**
    앞선 것이 아니라 마지막 것이어야 그 사이에 고친 자리를 다시 짚지 않는다.

    Given: 같은 단계의 품질 실패 둘
    When: 묻는다
    Then: 나중 것의 원문
    """
    _failed(tmp_path, "mechanism", FailureKind.QUALITY, "앞선 사유")
    _failed(tmp_path, "mechanism", FailureKind.QUALITY, "나중 사유")

    assert decision_log.last_quality_failure(tmp_path, "mechanism") == "나중 사유"


def test_other_kinds_and_other_steps_are_not_returned(tmp_path: Path) -> None:
    """
    목적: 품질이 아닌 실패와 «다른 단계»의 실패는 안 돌려주는 계약을 고정한다.

    한도 · 그 외 실패는 에이전트가 고칠 사유가 아니다. 다른 단계의 사유를 실으면
    **그 단계가 모르는 자리를 고치라는 말**이 된다 — 반증에 계보 사유가 가면
    반증 세션을 떼어 둔 뜻도 흐려진다.

    Given: 이 단계의 한도 · 그 외 실패와, 다른 단계의 품질 실패
    When: 이 단계를 묻는다
    Then: 없다
    """
    _failed(tmp_path, "rebut", FailureKind.LIMIT, "한도")
    _failed(tmp_path, "rebut", FailureKind.OTHER, "JSON 깨짐")
    _failed(tmp_path, "lineage", FailureKind.QUALITY, "계보 사유")

    assert decision_log.last_quality_failure(tmp_path, "rebut") is None


def test_a_later_non_quality_failure_does_not_hide_the_quality_reason(tmp_path: Path) -> None:
    """
    목적: 품질 실패 «뒤»에 한도로 끊긴 시도가 있어도 그 사유를 돌려주는 계약을 고정한다.

    새벽 회차는 한도에 자주 걸린다. 한도로 끊긴 시도는 고친 것이 아니라 **말할 기회를
    못 얻은 것**이라, 그 앞의 품질 사유는 여전히 고칠 거리다.

    Given: 품질 실패 뒤의 한도 실패
    When: 묻는다
    Then: 품질 실패의 원문
    """
    _failed(tmp_path, "verdict", FailureKind.QUALITY, "판정 칸 미달")
    _failed(tmp_path, "verdict", FailureKind.LIMIT, "한도")

    assert decision_log.last_quality_failure(tmp_path, "verdict") == "판정 칸 미달"


def test_a_failure_before_the_agent_answered_is_not_returned(tmp_path: Path) -> None:
    """
    목적: [중요] 에이전트가 «답하기 전»에 막힌 품질 실패는 돌려주지 않는 계약을 고정한다.

    판정 단계는 부르기 전에 앞 단계 산출물을 확인하고, 없으면 품질 실패로 막는다. 그 사유는
    에이전트가 답으로 고칠 것이 아니다 — 「사유대로 고치라」와 함께 실으면 파일을 쓸 수 있는
    에이전트가 **그 산출물을 직접 써 넣어** 앞 단계의 게이트를 통째로 비켜 갈 수 있다.

    Given: 비용 줄 없이 끝난 품질 실패(부르기 전에 막힘)
    When: 묻는다
    Then: 없다
    """
    _failed(tmp_path, "verdict", FailureKind.QUALITY, "근거 문서를 조립할 수 없습니다 — 산출물이 없습니다", answered=False)

    assert decision_log.last_quality_failure(tmp_path, "verdict") is None

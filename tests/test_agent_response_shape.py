"""`--output-format json` 의 «실측된» 응답 모양에 대한 계약을 고정한다.

[실측 2026-09-12] 컨테이너에서 잘못된 토큰으로 `claude -p ... --output-format json` 을
불러 받은 실제 응답이다. 설계서가 [미검증]으로 남겨 둔 두 가지를 이 응답 하나가 닫았다.

1. **응답의 실제 필드** — `result` · `total_cost_usd` · `usage` · `session_id` · `is_error`
2. **인증 실패가 어떤 모양으로 오나** — 그리고 **종료 코드는 0 이다**

[중요] `is_error` 가 true 인데 `subtype` 은 `"success"` 였다.
**`subtype` 으로 성패를 가르면 안 된다** — `is_error` 만 믿는다.
"""

import json

import pytest

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult, StepFailed
from research_lab.runner import failures

# 실측 응답. 값이 든 필드만 남기고 줄였으며, **자격증명은 들어 있지 않다**
# (원문도 변수 «이름»만 말하고 값은 말하지 않았다)
MEASURED_AUTH_FAILURE = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "terminal_reason": "api_error",
        "result": (
            "Invalid auth token - Fix external auth token - Invalid Authorization header "
            "value from CLAUDE_CODE_OAUTH_TOKEN: it contains a non-ASCII character at "
            "character 14 (22 characters)."
        ),
        "session_id": "6fe2b9cf-bf72-4067-b1ee-fe8d8b4f7327",
        "total_cost_usd": 0,
        "num_turns": 1,
        "duration_ms": 108,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "output_tokens_details": {"thinking_tokens": 0},
            "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
        },
    }
)


def test_is_error_response_is_treated_as_a_failure() -> None:
    """
    목적: `is_error` 가 true 면 «성공으로 통과하지 않는» 계약을 고정한다.

    [실측] 이 응답은 **종료 코드 0 으로** 왔다. 종료 코드만 보면 성공이라,
    이 검사가 없으면 오류 문구가 담긴 `AgentResult` 가 정상 결과로 흘러가고
    한참 뒤 파싱 단계에서 「JSON 이 아닙니다」라는 **엉뚱한 진단**으로 튀어나온다.

    Given: 실측된 오류 응답
    When: 호출 계층이 읽는다
    Then: 실패로 올라오고 원문이 실려 있다
    """
    with pytest.raises(StepFailed) as raised:
        invoke._parse(raw=MEASURED_AUTH_FAILURE, elapsed=0.1, session_id="세션")

    assert "Invalid auth token" in str(raised.value)


def test_measured_auth_failure_classifies_as_auth() -> None:
    """
    목적: 실측된 인증 실패가 「인증·과금 거부」로 갈리는 계약을 고정한다.

    [실측] 처음에는 「그 외」로 떨어져 **3번 재시도**됐다. 설계가 「②를 ①·③과 섞으면
    며칠 조용히 안 도는 상태가 된다」고 경고한 바로 그 모양이라, 그 원문으로 분류표를 고쳤다.
    이 테스트는 **그 교훈이 되돌아가지 않게** 박아 두는 것이다.

    Given: 실측된 인증 실패 원문
    When: 분류한다
    Then: 인증 갈래이고 재시도 대상이 아니다
    """
    verdict = failures.classify(MEASURED_AUTH_FAILURE)

    assert verdict.kind is failures.FailureKind.AUTH
    assert failures.should_retry(verdict.kind) is False


def test_cache_read_tokens_are_excluded_from_the_count() -> None:
    """
    목적: 캐시에서 읽은 토큰이 집계에 «안» 들어가는 계약을 고정한다.

    [실측] 응답의 `usage` 에 `cache_read_input_tokens` 가 실제로 있다.
    프롬프트 캐시가 도는 상황에서 이 값은 새 입력 토큰보다 한 자릿수 크고,
    그대로 더하면 **회차 예산의 근거가 그 배수만큼 틀어진다.**

    Given: 캐시 읽기가 큰 usage
    When: 토큰을 센다
    Then: 새로 쓴 토큰만 세어진다
    """
    counted = invoke._new_tokens(
        {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 10,
            "cache_read_input_tokens": 90_000,
            "output_tokens_details": {"thinking_tokens": 7},
        }
    )

    assert counted == 160


def test_usage_components_survive_the_parse() -> None:
    """
    목적: 네 성분이 «그대로» 결과에 실려 나가는 계약을 고정한다.

    [중요] 바로 위 테스트가 고정한 「캐시 읽기를 빼고 센다」는 **비용** 기준이라 옳지만,
    **한도** 기준으로는 정반대다 — 한도는 캐시에서 읽은 토큰도 먹는다. 합계만 남기면
    나중에 가중치를 바꿔 **다시 계산할 수가 없다.** 그래서 이 계층은 **판정하지 않고
    응답에 있는 것을 옮긴다** — 어느 성분이 한도에서 몇으로 세는지는 이 계층이 알 일이 아니다.

    Given: 캐시 읽기가 큰 성공 응답
    When: 호출 계층이 읽는다
    Then: 합계와 «네 성분»이 함께 나온다
    """
    raw = json.dumps(
        {
            "type": "result",
            "is_error": False,
            "result": "답입니다",
            "total_cost_usd": 0.34,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 10,
                "cache_read_input_tokens": 90_000,
                "output_tokens_details": {"thinking_tokens": 7},
            },
        }
    )

    parsed = invoke._parse(raw=raw, elapsed=1.5, session_id="세션")

    assert parsed.tokens == 160, "합계의 뜻이 바뀌면 지난 회차와 비교가 끊긴다"
    assert parsed.usage == {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_creation_input_tokens": 10,
        "cache_read_input_tokens": 90_000,
    }, "중첩된 세부 항목은 싣지 않는다 — 실을 열쇠를 이름으로 고정한다"


def test_usage_components_are_none_when_absent() -> None:
    """
    목적: `usage` 가 없거나 모양이 다를 때 성분이 «없음»인 계약을 고정한다.

    응답 모양은 CLI 가 정하는 것이라 언제 바뀌어도 이상하지 않다. 그때
    **파이프라인이 죽는 것보다 「그 값을 모른다」로 남는 편이 낫다** — 이 모듈의 축이다.

    Given: `usage` 가 없는 응답과, 문자열이 들어온 응답
    When: 호출 계층이 읽는다
    Then: 둘 다 예외 없이 성분이 None 이다
    """
    without = invoke._parse(raw=json.dumps({"result": "답", "is_error": False}), elapsed=0.1, session_id="세션")
    wrong_shape = invoke._parse(
        raw=json.dumps({"result": "답", "is_error": False, "usage": "많이 씀"}), elapsed=0.1, session_id="세션"
    )

    assert without.usage is None
    assert wrong_shape.usage is None


def test_successful_response_fields_are_read() -> None:
    """
    목적: 실측된 필드 이름으로 결과를 읽는 계약을 고정한다.

    Given: 성공 응답
    When: 호출 계층이 읽는다
    Then: 응답·비용·세션 ID 가 각각 제 자리에서 나온다
    """
    raw = json.dumps(
        {
            "type": "result",
            "is_error": False,
            "result": "답입니다",
            "session_id": "세션-아이디",
            "total_cost_usd": 0.34,
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
    )

    parsed = invoke._parse(raw=raw, elapsed=1.5, session_id="쓰이지-않는-값")

    assert parsed.text == "답입니다"
    assert parsed.cost_usd == 0.34
    assert parsed.tokens == 30
    assert parsed.session_id == "세션-아이디"
    assert parsed.raw == raw


def test_structured_output_wins_over_prose() -> None:
    """
    목적: [실측 2026-09-14] 스키마가 낸 «파싱된 객체»를 먼저 쓰는 계약을 고정한다.

    `--json-schema` 를 걸면 CLI 가 `structured_output` 에 객체를 함께 싣는다. 그쪽을
    먼저 쓰면 **산문이나 코드펜스로 파싱이 깨질 여지가 구조적으로 사라진다** —
    스키마를 켜는 이유가 바로 그것이고, 안 쓰면 켜 놓고도 예전 위험을 그대로 안고 간다.

    Given: 산문이 섞인 `result` 와 «제대로 된» `structured_output` 이 함께 온 응답
    When: 호출 계층이 읽는다
    Then: 객체 쪽이 쓰인다
    """
    raw = json.dumps(
        {
            "type": "result",
            "is_error": False,
            "result": '말씀하신 대로 정리했습니다. ```json\n{"verdict": "엉뚱한 값"}\n```',
            "structured_output": {"verdict": "보류", "reason": "표본이 모자란다"},
            "session_id": "세션",
        }
    )

    parsed = invoke._parse(raw=raw, elapsed=1.0, session_id="쓰이지-않는-값")

    assert invoke.parse_json_answer(parsed, what="판정")["verdict"] == "보류"


def test_an_object_answer_stays_parsable() -> None:
    """
    목적: [중요] 답이 «객체»로 와도 JSON 으로 다시 읽히는 계약을 고정한다.

    `--json-schema` 로 모양을 강제하면 CLI 가 답을 문자열이 아니라 객체로 실어 보낼 수 있다.
    그때 파이썬이 dict 를 그대로 문자열로 만들면 작은따옴표 표기(`{'ok': True}`)가 되어
    **JSON 으로 다시 읽히지 않는다.** 그 회차는 「JSON 을 못 꺼냈습니다」로 실패하고
    「그 외」로 분류돼 상한까지 재시도하는데, **모양을 강제하려고 켠 플래그가 정확히
    그 모양 때문에 회차를 태우는** 꼴이 된다.

    스키마를 안 켜도 이 가드를 둔다 — 응답 모양은 CLI 가 정하는 것이라 언제 바뀌어도
    이상하지 않고, **바뀌는 날 이 가드가 없으면 조용히 재시도만 돈다.**

    Given: `result` 가 객체인 응답
    When: 호출 계층이 읽고, 단계가 JSON 을 꺼낸다
    Then: 예외 없이 그 객체가 나온다
    """
    raw = json.dumps(
        {
            "type": "result",
            "is_error": False,
            "result": {"verdict": "보류", "candidates": ["ㄱ"]},
            "session_id": "세션",
            "total_cost_usd": 0.1,
        }
    )

    parsed = invoke._parse(raw=raw, elapsed=1.0, session_id="쓰이지-않는-값")

    assert invoke.parse_json_answer(parsed, what="판정") == {"verdict": "보류", "candidates": ["ㄱ"]}


MEASURED_FENCED_ANSWER = '```json\n{"queries": ["ㄱ", "ㄴ", "ㄷ"], "candidates": []}\n```'

MEASURED_SESSION_LIMIT = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "stop_reason": "stop_sequence",
        "result": "You've hit your session limit - resets 4:40pm (Asia/Seoul)",
        "total_cost_usd": 0,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }
)


def test_code_fenced_json_is_unwrapped() -> None:
    """
    목적: 코드펜스로 감싼 답에서도 JSON 을 꺼내는 계약을 고정한다.

    [실측 2026-09-12] 프롬프트에 「다른 말 없이 JSON 하나만 출력하세요」라고 적었는데도
    에이전트가 ```json 으로 감쌌다. **탐색과 수집 둘 다** 그랬고, 그 회차는
    「JSON 이 아닙니다」로 세 번 재시도한 뒤 끝났다.
    루트 CLAUDE.md 의 「프롬프트로 지시한 규율은 형식적으로만 지켜진다」가 여기서도 맞았다 —
    지시가 아니라 **파서가** 감당해야 한다.

    Given: 코드펜스로 감싼 답
    When: 꺼낸다
    Then: 객체가 나온다
    """
    result = AgentResult(
        text=MEASURED_FENCED_ANSWER,
        raw=MEASURED_FENCED_ANSWER,
        cost_usd=None,
        tokens=None,
        usage=None,
        elapsed_seconds=1.0,
        session_id="세션",
    )

    assert invoke.parse_json_answer(result, what="탐색")["queries"] == ["ㄱ", "ㄴ", "ㄷ"]


def test_measured_session_limit_classifies_as_limit() -> None:
    """
    목적: 실측된 한도 소진이 「한도」 갈래로 갈리는 계약을 고정한다.

    [실측 2026-09-12] 설계서가 「일부러 만들 수 없다」고 남겨 둔 [미검증] 이었는데
    실제로 부딪혔다. 처음에는 분류표에 안 걸려 「그 외」로 떨어져 **30초씩 쉬며 두 번 더
    불렀다** — 설계가 「한도는 재시도하지 않는다, 해봐야 또 막힌다」고 정한 자리를 지나쳤다.

    Given: 실측된 한도 소진 응답
    When: 분류한다
    Then: 한도 갈래이고 재시도 대상이 아니다
    """
    verdict = failures.classify(MEASURED_SESSION_LIMIT)

    assert verdict.kind is failures.FailureKind.LIMIT
    assert failures.should_retry(verdict.kind) is False


def test_session_limit_response_is_a_failure_despite_success_subtype() -> None:
    """
    목적: 한도 소진 응답이 «성공»으로 통과하지 않는 계약을 고정한다.

    [실측] `is_error` 는 true 인데 `subtype` 은 "success" 였다.
    `subtype` 으로 성패를 가르면 한도 소진이 정상 결과로 흘러간다.

    Given: 실측된 한도 소진 응답
    When: 호출 계층이 읽는다
    Then: 실패로 올라온다
    """
    with pytest.raises(StepFailed):
        invoke._parse(raw=MEASURED_SESSION_LIMIT, elapsed=0.1, session_id="세션")


# [실측 2026-09-22] 계보 단계가 20턴을 돈 «뒤에» 세션 한도에 걸린 응답이다. 값이 든 필드만
# 남기고 줄였으며 자격증명은 들어 있지 않다. 위 `MEASURED_SESSION_LIMIT` 은 호출 «시작»에서
# 거부돼 비용이 0 이었지만, 이것은 **이미 쓴 만큼 과금된 뒤**에 멈춘 모양이다
MEASURED_MIDSTEP_LIMIT = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "stop_reason": "stop_sequence",
        "terminal_reason": "api_error",
        "api_error_status": 429,
        "result": "You've hit your session limit · resets 2:10am (Asia/Seoul)",
        "session_id": "de602fb7-3d2b-4fd9-84bb-1937a475f823",
        "total_cost_usd": 0.9001812000000001,
        "num_turns": 20,
        "usage": {
            "input_tokens": 12,
            "cache_creation_input_tokens": 49463,
            "cache_read_input_tokens": 230271,
            "output_tokens": 18540,
        },
    }
)


def test_midstep_limit_carries_what_the_call_spent() -> None:
    """
    목적: 도중에 멈춘 호출이 «쓴 것»을 실패와 함께 나르는 계약을 고정한다.

    [실측 2026-09-22] 이 응답의 $0.9002 가 결정 로그의 어느 비용 줄에도 남지 않아
    회차 로그의 쓴 돈 · 토큰 · 한도 비율에서 통째로 빠졌다. 비용 줄은 단계가 결과를
    «돌려받은 뒤» 적는데, 이 호출은 결과 대신 실패를 올렸기 때문이다.

    Given: 실측된 «단계 도중» 한도 소진 응답
    When: 호출 계층이 읽는다
    Then: 실패로 올라오되, 그 호출의 비용 · 새 토큰 · 성분 · 세션을 함께 싣는다
    """
    with pytest.raises(StepFailed) as raised:
        invoke._parse(raw=MEASURED_MIDSTEP_LIMIT, elapsed=210.1, session_id="쓰이지-않는-값")

    spent = raised.value.spent
    assert spent is not None
    assert spent.cost_usd == 0.9001812000000001
    assert spent.tokens == 68_015, "새 토큰 = 입력 + 출력 + 캐시 생성. 캐시 읽기는 뺀다"
    assert spent.usage == {
        "input_tokens": 12,
        "output_tokens": 18540,
        "cache_creation_input_tokens": 49463,
        "cache_read_input_tokens": 230271,
    }
    assert spent.session_id == "de602fb7-3d2b-4fd9-84bb-1937a475f823"


def test_start_of_call_rejection_carries_a_measured_zero() -> None:
    """
    목적: 시작에서 거부된 호출의 비용이 «잴 수 없음»이 아니라 «0»으로 실리는 계약을 고정한다.

    이 로그는 「재서 0 이었다」와 「잴 수 없었다」를 가른다. 응답에 0 이 적혀 왔으면 0 이다.

    Given: 실측된 인증 실패 응답(비용 0)
    When: 호출 계층이 읽는다
    Then: 실어 보낸 비용이 None 이 아니라 0 이다
    """
    with pytest.raises(StepFailed) as raised:
        invoke._parse(raw=MEASURED_AUTH_FAILURE, elapsed=0.1, session_id="세션")

    spent = raised.value.spent
    assert spent is not None
    assert spent.cost_usd == 0


@pytest.mark.parametrize("answer", ["JSON 이 아닌 산문", '["목록", "이지", "객체가", "아니다"]'])
def test_unparsable_answer_carries_the_result(answer: str) -> None:
    """
    목적: 답에서 JSON 객체를 못 꺼낸 실패가 «받은 결과»를 그대로 나르는 계약을 고정한다.

    [실측] 과거 회차에서 이 경로로 세 번 샜다 — 에이전트는 끝까지 돌아 돈을 썼는데
    단계가 비용을 적기 «전»에 파싱이 실패해 그 비용이 어디에도 남지 않았다.

    Given: 객체로 읽히지 않는 답 (산문 · 배열)
    When: 단계가 JSON 을 꺼낸다
    Then: 실패가 오르고, 실어 보낸 것이 넘겨받은 결과 자신이다
    """
    result = AgentResult(
        text=answer, raw=answer, cost_usd=0.6, tokens=500, usage=None, elapsed_seconds=1.0, session_id="세션"
    )

    with pytest.raises(StepFailed) as raised:
        invoke.parse_json_answer(result, what="탐색")

    assert raised.value.spent is result


def test_null_session_id_falls_back_to_the_given_one() -> None:
    """
    목적: 응답의 세션 ID 가 `null` 이어도 «"None"» 이라는 글자가 되지 않는 계약을 고정한다.

    [중요] `str(None)` 은 `"None"` 이라는 «내용이 있는» 문자열이다. 비용 줄은 세션 ID 로
    같은 호출을 가르므로, 서로 다른 호출이 둘 다 `"None"` 을 가지면 **뒤의 비용 줄이
    같은 호출로 보여 버려진다.** 열쇠가 «있고» 값이 `null` 이면 `dict.get` 의 기본값도 안 쓰인다.

    Given: 세션 ID 가 null 인 응답
    When: 호출 계층이 읽는다
    Then: 미리 정한 세션 ID 가 쓰인다
    """
    raw = json.dumps({"type": "result", "is_error": False, "result": "답", "session_id": None})

    parsed = invoke._parse(raw=raw, elapsed=1.0, session_id="미리-정한-값")

    assert parsed.session_id == "미리-정한-값"

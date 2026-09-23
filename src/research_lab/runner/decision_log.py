"""그 회차의 «과정»을 남긴다.

산출물(dossier)은 **결론**이고 이 로그는 **과정**이다. 둘을 섞으면 dossier 가 읽히지 않는다.

줄글이 아니라 JSONL 인 이유는 「나중에 기계가 훑을 것」이기 때문이다 —
게이트 기준이나 프롬프트를 고쳤을 때 **과거 로그를 다시 읽어 「지금 기준이면 판정이
달라졌을 후보」를 찾아낼 수 있어야** 한다. 줄글로 남기면 그 질문에 답할 수 없다.

[중요] **비용·토큰·소요 시간도 여기 적는다.** 그래야 회차 예산 집계가 저장소 «안»에서
완결되어, 컨테이너의 세션 로그에 의존하지 않고 기계를 옮겨도 기록이 따라온다.
"""

from pathlib import Path
from typing import Any, Final

from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import DECISION_LOG_FILENAME
from research_lab.runner import jsonl, payload

# 이벤트 종류. 「무엇을 읽었나 · 무엇을 기준으로 판단했나 · 무엇을 버렸고 왜」를
# 나중에 기계가 골라낼 수 있도록 이름을 고정한다 — 자유 문자열이면 훑을 때 매번 추측해야 한다
EVENT_READ: Final = "read"
EVENT_JUDGED: Final = "judged"
EVENT_DISCARDED: Final = "discarded"
EVENT_SKIPPED: Final = "skipped"
EVENT_FAILED: Final = "failed"
EVENT_COST: Final = "cost"

# 비용 줄에 적는 토큰 «성분»의 열쇠 -> 응답의 `usage` 필드 이름.
#
# [중요] 이 이름은 **이 로그의 계약**이라 여기가 주인이다. 읽는 쪽(`usage`)이 자기 이름을
# 따로 들고 있으면 둘이 갈릴 수 있고, 갈렸다는 사실은 **집계가 0 으로 나오는 것 말고는
# 아무 신호도 내지 않는다.**
#
# [중요] 합계(`tokens`)와 «따로» 적는다. 성분이 없으면 나중에 가중치를 바꿔 다시 계산할
# 수 없다 — 원본을 버리고 집계만 남기는 것이다. 실제로 그 덕에 한 번 되짚었다:
# 한때 「한도는 캐시에서 읽은 토큰도 먹는다」고 보았으나 성분이 남아 있어 **그 가정이
# 틀렸다는 것을 나중에 확인할 수 있었다**(실측은 `usage` 모듈 머리).
KEY_TOKENS_INPUT: Final = "tokens_input"
KEY_TOKENS_OUTPUT: Final = "tokens_output"
KEY_TOKENS_CACHE_CREATION: Final = "tokens_cache_creation"
KEY_TOKENS_CACHE_READ: Final = "tokens_cache_read"

TOKEN_COMPONENT_KEYS: Final = {
    KEY_TOKENS_INPUT: "input_tokens",
    KEY_TOKENS_OUTPUT: "output_tokens",
    KEY_TOKENS_CACHE_CREATION: "cache_creation_input_tokens",
    KEY_TOKENS_CACHE_READ: "cache_read_input_tokens",
}

# 마지막 단계가 근거 문서를 쓴 뒤 그 파일명을 적는 열쇠.
#
# [중요] **이 이름도 이 로그의 계약이라 여기가 주인이다.** 적는 쪽(마지막 단계)과
# 읽는 쪽(예산 표본 판정)이 각자 리터럴을 들고 있으면, 이름을 바꾼 날 **판정이 조용히
# 거짓이 되어** 표본이 0건이 되고 루프가 회차마다 한 장에서 멈춘다 — 에러도 테스트 실패도 없다
KEY_DOSSIER: Final = "dossier"

# 예산 루프가 「한 장 더 갈까」를 판정했다.
#
# [중요] 「판정했다」(`EVENT_JUDGED`)와 갈라 둔다. 그쪽은 **그 후보를 잴 가치가 있나**의
# 판정이라 나중에 「판정이 어떻게 갈렸나」를 셀 때 쓰이는데, 같은 이름으로 적으면
# 예산 판정이 그 집계에 섞여 들어간다 — 이름을 고정해 두는 이유가 이런 자리다
EVENT_BUDGET: Final = "budget"

# 출처를 끝내 못 갖춘 후보를 그 실행 폴더에서 «미뤄 두었다» — 원장에는 아무 표시도 안 한다.
#
# [중요] 「버렸다」(`EVENT_DISCARDED`)와 갈라 둔다. 수집이 **기각 수를 그 이름으로 세므로**,
# 미룸을 같은 이름으로 적으면 그 회차의 기각 상한이 조용히 앞당겨진다.
#
# [중요] 「건너뛰었다」(`EVENT_SKIPPED`)와도 갈라 둔다. 그쪽은 **단계가 통째로 안 돈 것**이고
# 이것은 그 단계 «안»에서 후보 하나를 지나친 것이다. 같은 이름으로 적으면 둘 다 못 세는데,
# 미룬 후보를 세는 일이 무한 반복을 막는 유일한 장치라 그 손실이 곧 고장이 된다 —
# 원장에 표시를 안 남기기로 했으므로 **이 로그가 그 사실의 유일한 주인**이다
EVENT_DEFERRED: Final = "deferred"

# 같은 자리에서 회차마다 실패해 그 후보와 실행 폴더를 접었다.
#
# [중요] 「버렸다」(`EVENT_DISCARDED`)와 갈라 둔다. 수집이 **기각 수를 그 이름으로 세므로**,
# 막힘을 같은 이름으로 적으면 그 회차의 기각 상한이 조용히 앞당겨진다 —
# 이름을 고정해 두는 이유가 바로 이런 자리다
EVENT_BLOCKED: Final = "blocked"

# «미룸 때문에» 그 단계를 더 못 갔다는 표시. 게이트 이름 자리에 적는다.
#
# [중요] 이 표시가 말하는 것은 **「막힌 것이 미뤄 둔 후보들이다」**이지 「상한에 닿았다」가
# 아니다. 상한에 닿아 끝나는 경우와, 남은 후보를 전부 미뤄 더 꺼낼 것이 없는 경우가
# 모두 여기 오며 **둘 다 막힌 것은 미룬 후보들**이다.
#
# 이 표시가 없으면 계속 막히는 폴더를 접을 때 그 사정이, 「다음 후보를 집어 거기서
# 막힌」 경우와 구별되지 않아 **물어본 적조차 없는 후보가 걷힌다.**
GATE_DEFERRED_STUCK: Final = "deferred-stuck"


def record(run_dir: Path, step: str, event: str, **fields: Any) -> None:
    """결정 한 건을 덧붙인다.

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 어느 단계에서 일어난 일인가
        event: 이벤트 종류 (`EVENT_*`)
        **fields: 그 이벤트의 내용. 검색어 목록·URL 목록·판단 기준·버린 이유·
            토큰과 비용·실패 원문 등이 들어온다

    [주의] 덧붙이기만 한다. 다시 쓰면 그 회차의 앞부분이 사라지고 **예외도 나지 않는다**
    """
    jsonl.append(run_dir / DECISION_LOG_FILENAME, {"step": step, "event": event, **fields})


def record_cost(run_dir: Path, step: str, result: AgentResult) -> None:
    """한 번의 호출이 쓴 비용·토큰·시간을 남긴다.

    모든 단계와 러너가 똑같이 적는 값이라 한 곳에서 만든다. 여러 벌로 흩어져 있으면
    **한 곳만 고쳐질 때 회차 예산 집계가 그 자리에서만 어긋나고**, 합계가 틀렸다는 것은
    드러나지 않는다.

    **같은 호출(세션 ID)은 한 번만 적는다.** 그 폴더에 이미 적혀 있으면 아무것도 하지 않는다.

    Args:
        run_dir: 그 회차의 실행 폴더
        step: 어느 단계의 호출인가
        result: 에이전트 호출 결과
    """
    # [중요] 비용 줄을 적는 자리가 둘이다 — 결과를 돌려받은 단계와, 실패를 받은 러너.
    # 지금은 단계가 파싱 «뒤»에 적어 겹치지 않지만 그 순서는 여러 단계 모듈에 흩어진
    # 관용이라, 한 곳이 바뀌면 **같은 호출이 두 번 세이고 에러가 안 난다.**
    # 세션 ID 는 호출마다 새로 정하므로 그것으로 가른다
    if any(
        entry.get("event") == EVENT_COST and entry.get("session_id") == result.session_id for entry in read(run_dir)
    ):
        return

    # [중요] 성분을 모를 때는 **열쇠를 아예 넣지 않는다.** `None` 으로 채우면
    # 「잴 수 없었다」가 「0 이었다」와 구별되지 않는다
    components = {
        key: result.usage[field]
        for key, field in TOKEN_COMPONENT_KEYS.items()
        if result.usage is not None and field in result.usage
    }

    record(
        run_dir,
        step,
        EVENT_COST,
        cost_usd=result.cost_usd,
        tokens=result.tokens,
        elapsed_seconds=round(result.elapsed_seconds, 1),
        session_id=result.session_id,
        **components,
    )


def deferral_state(run_dir: Path, step: str) -> tuple[list[str], bool]:
    """미뤄 둔 후보들과 «상한에 닿았는지»를 로그 한 번으로 함께 읽는다.

    [중요] 둘을 따로 물으면 같은 파일을 두 번 판다. 이 로그는 폴더를 이어받을 때마다
    길어지고, 두 값이 필요한 자리는 **계속 막히는 폴더를 접는 경로** — 이미 느려진 자리다.

    Args:
        run_dir: 그 실행 폴더
        step: 미룬 단계의 이름

    Returns:
        `(미뤄 둔 후보들, 미룸 때문에 막혔나)`. 후보 목록은 **미룬 순서를 지킨다** —
        뒤에 그중 하나를 골라야 하는 자리가 있고, 집합으로 돌려주면 그 선택이
        **글자 정렬에 좌우되어** 「왜 이것이 걷혔나」를 설명할 수 없다
    """
    claims: list[str] = []
    capped = False
    for entry in read(run_dir):
        if entry.get("step") != step:
            continue
        event = entry.get("event")
        if event == EVENT_DEFERRED:
            claim = payload.as_text(entry.get("claim"))
            if claim and claim not in claims:
                claims.append(claim)
        elif event == EVENT_FAILED and entry.get("gate") == GATE_DEFERRED_STUCK:
            capped = True
    return claims, capped


def deferred_claims(run_dir: Path, step: str) -> list[str]:
    """그 단계가 그 실행 폴더에서 «미뤄 둔» 후보들의 한 줄 주장.

    [중요] 미룸은 **원장에 아무 표시도 남기지 않으므로 이 로그가 그 사실의 유일한 주인**이다.
    이 목록이 없으면 미룬 후보가 여전히 「다음에 팔 후보」의 첫 번째라
    **같은 후보를 영원히 다시 꺼낸다.** 기각 수를 이 로그로 세는 것과 같은 방식이며,
    새 누적 상태를 만들지 않는 이유도 같다.

    [중요] **읽는 쪽이 둘이라 여기에 둔다.** 후보를 꺼내는 쪽(수집)과 계속 막히는 후보를
    걷어내는 쪽(회차)이 **같은 목록**을 봐야 한다. 걷어내는 쪽이 이것을 모르면 미룬 후보가
    원장에서 여전히 첫 번째라, **막힌 후보 대신 미뤄 둔 후보를 걷어낸다** —
    사유는 사실인데 대상이 틀려 사람을 엉뚱한 곳으로 보낸다. 한쪽에 두고 다른 쪽이
    자기 것을 따로 세면 그 둘이 갈릴 수 있고, 갈렸다는 사실은 아무 신호도 내지 않는다.

    Args:
        run_dir: 그 실행 폴더
        step: 미룬 단계의 이름

    Returns:
        미뤄 둔 후보들, **미룬 순서 그대로**. 로그가 없거나 깨졌으면 빈 목록 —
        그때는 한 번 더 시도할 뿐이고, **판정을 못 했다고 파이프라인을 멈추지는 않는다**
    """
    claims, _ = deferral_state(run_dir, step)
    return claims


def read(run_dir: Path) -> list[dict[str, Any]]:
    """그 회차의 결정 로그를 읽는다.

    Args:
        run_dir: 그 회차의 실행 폴더

    Returns:
        적힌 순서 그대로의 기록. 파일이 없으면 빈 목록.
        **깨진 줄은 건너뛴다** — 한 줄이 깨졌다고 그 회차의 나머지 기록을 통째로
        못 읽게 되면, 정작 원인을 되짚어야 할 때 아무것도 못 본다.
        잘린 글자까지 견디는 것은 `jsonl.read` 가 맡는다
    """
    return jsonl.read(run_dir / DECISION_LOG_FILENAME)

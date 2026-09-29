"""탐색 단계 — 후보 «목록»을 만들어 원장에 담는다.

넓게 훑고 얕아도 된다. 산출물은 후보마다 **한 줄 주장** 하나다.
수집보다 싸고, **이 단계가 있어서 사람이 후보를 적어 넣지 않아도 첫 회차가 돈다.**
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import EXPLORE_RESULT_FILENAME
from research_lab.gate import activity as activity_gate
from research_lab.gate import queries as query_gate
from research_lab.runner import decision_log, ledger
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

# 프롬프트만 받아 에이전트를 부르는 쪽. 이 단계는 «어떻게» 부르는지 모른다 —
# 그래야 호출 계층이 단계에 맞춰 깎이지 않고, 돌려보지 않고도 이 단계를 검사할 수 있다
AgentCaller = Callable[[str], AgentResult]

# 한 회차에 담을 후보 수의 상한. 많이 담는 것이 목적이 아니라 **수집이 팔 재고**를 만드는 것이라,
# 한 번에 너무 많이 담으면 오래된 후보가 계속 뒤로 밀린다.
#
# [중요] 세는 것은 **원장에 새로 적는 줄**이다. 중복 · 빈 주장은 자리를 먹지 않는다 —
# 거르기 «전» 목록에 걸면 원장에 이미 있는 주장이 앞자리를 먹고 **새 주장이 「상한 초과」로
# 버려진다.** 원장이 커질수록 에이전트가 아는 후보를 되풀이할 공산이 커지므로 그만큼 새 후보가
# 들어올 길이 좁아진다
MAX_CANDIDATES: Final = 15


@dataclass
class _Stored:
    """한 번의 탐색 답이 원장에 무엇을 남기고 무엇을 버렸나."""

    added: int = 0
    duplicates: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    # 상한을 넘어 «보지도 않고» 버린 새 주장 — 에이전트가 낸 글자 그대로
    overflow: list[str] = field(default_factory=list)
    # 연간 가동일이 모자라 기각으로 담은 후보와 그 어림값. 기준을 고친 날 과거 판정을 다시 가를 재료다
    activity_rejected: list[dict[str, Any]] = field(default_factory=list)
    # 어림을 못 읽어 거르지 않고 담은 주장. 이 수가 크면 기준이 사실상 꺼져 있다는 뜻이다
    activity_undecided: list[str] = field(default_factory=list)


# [중요] 응답 틀의 두 어림 자리를 «숫자로» 채우지 않는다. 예시 숫자가 문턱을 넘는 값이면 틀을 베낀
# 답이 전부 통과해 기준이 흔적 없이 꺼진다 — 글자로 두면 베낀 답은 「판정 못 함」으로 로그에 남는다
PROMPT: Final = """`.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 탐색

아직 검증되지 않은 **매매법 후보 목록**을 만듭니다. 넓게 훑고, 얕아도 됩니다.
후보 하나를 깊게 파는 것은 다른 단계의 일입니다.

- 대상 시장은 **국내 주식과 미국 주식 둘 다**입니다. 한쪽만 훑지 마세요
- 후보마다 **한 줄 주장**을 적습니다 — 「무엇을 언제 사고 언제 파는가」가 한 문장에 들어가야 합니다
- 후보마다 **짧은 영문 식별자**를 붙입니다 (소문자·숫자·하이픈, 예: `pead-us`).
  산출물 폴더 이름이 되므로 짧고 서로 달라야 합니다
- 최대 {max_candidates}개까지만 담습니다
- 검색어는 한국어와 영어를 모두 돌리고, **던진 검색어를 하나도 빼지 않고** 적습니다

## 잴 수 있는 후보만 적습니다

「짧은 기간」·「단기」·「크게 상회」처럼 값이 비어 있는 말을 써도 됩니다 — 그 말마다
무엇을 얼마로 바꿔 잴지는 후보를 깊게 파는 단계가 따로 받습니다.

**다만 무엇을 채울지 정할 수 없는 말이 든 후보는 적지 마세요.** 「옥석을 가려」처럼 무엇을
채울지조차 없는 말, 「(미래) 저점에서 산다」처럼 판정 시점에 알 수 없는 값, 「편입이 예상되는」처럼
누가 언제 무엇을 보고 예상하는지 없는 말이 여기 걸립니다.
임의로 값 하나를 채우면 **어떤 값을 넣느냐가 결론을 만듭니다.**

## 돈이 일하는 기간이 너무 짧은 후보는 적지 않습니다

매매 기회도 드물고 보유기간도 짧으면 한 해의 대부분 돈이 쉬어 수익을 기대하기 어렵습니다.
그래서 후보마다 **연간 가동일 = 연간 독립 진입 시점 × 보유 거래일** 을 어림하고, 그 값이
**{min_active_days}거래일 미만**인 후보는 적지 마세요. 적더라도 기각으로 담깁니다.

- **연간 독립 진입 시점**(`entries_per_year`): 한 해에 돈을 새로 넣는 시점의 수입니다.
  같은 날 · 같은 주 · 같은 실적 시즌처럼 한꺼번에 몰리는 사건은 **한 번**으로 셉니다 —
  같은 날 여러 종목을 사면 돈이 나뉠 뿐 돈이 도는 횟수는 한 번입니다.
  사건이 연중 흩어져 오면 사건 수에 가깝습니다. 연 1회보다 드물면 0.5(2년에 한 번)처럼 소수로 적습니다
- **보유 거래일**(`holding_days`): 한 번 사서 팔 때까지의 거래일 수입니다(1개월 ≈ 21거래일, 1년 ≈ 252거래일).
  주장에 범위가 있으면 **긴 쪽**을, 「단기」처럼 값이 빈 말이면 그 말이 보통 뜻하는 범위의 **긴 쪽**을 적습니다.
  같은 날 사고 팔면(당일 청산) 1 로 적습니다
- 두 값은 **숫자 하나씩**으로 적습니다. 정확할 필요는 없지만 반드시 어림합니다
- **어림 근거**(`activity_basis`): 두 값을 어떻게 어림했는지 한 문장으로 적습니다

## 이미 본 후보 (다시 담지 마세요)

{known}

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요. `entries_per_year` · `holding_days` 자리에는 설명 대신
후보마다 어림한 **따옴표 없는 숫자**를 적습니다.

{{"queries": ["던진 검색어 전부"], "candidates": [{{"claim": "한 줄 주장", "identifier": "짧은-영문-이름", "why": "왜 후보로 볼 만한가", "market": "국내|미국", "entries_per_year": "연간 독립 진입 시점(숫자)", "holding_days": "보유 거래일(숫자)", "activity_basis": "어림 근거"}}]}}
"""


def build_prompt(known_claims: list[str]) -> str:
    """탐색 지시문을 만든다.

    Args:
        known_claims: 원장에 이미 있는 후보들. 같은 것을 또 담으면 그만큼 그 회차가 헛돈다

    Returns:
        에이전트에게 줄 지시문
    """
    listed = "\n".join(f"- {claim}" for claim in known_claims) if known_claims else "(아직 없음)"
    return PROMPT.format(
        max_candidates=MAX_CANDIDATES,
        known=listed,
        min_active_days=activity_gate.MIN_ACTIVE_DAYS_PER_YEAR,
    )


def run(run_dir: Path, ledger_path: Path, ask: AgentCaller) -> None:
    """탐색을 한 번 돌고 원장에 담는다.

    Args:
        run_dir: 그 회차의 실행 폴더
        ledger_path: 원장 경로
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        StepFailed: 응답이 약속한 모양이 아닐 때. **원문을 통째로 실어 보낸다** —
            분류와 재시도는 러너가 하고, 원문이 없으면 다음에 같은 모양을 못 가르친다
    """
    # 단계가 자기 산출물 폴더를 만든다. 부르는 쪽이 만들어 줬을 것이라 가정하면
    # 호출 경로가 늘 때마다 같은 실수를 되풀이한다
    run_dir.mkdir(parents=True, exist_ok=True)

    known = [entry.claim for entry in ledger.load(ledger_path)]
    result = ask(build_prompt(known))

    payload = invoke.parse_json_answer(result, what="탐색")
    queries = payload_helpers.as_strings(payload.get("queries"))
    candidates = payload_helpers.as_list(payload.get("candidates"))

    decision_log.record(run_dir, "explore", decision_log.EVENT_READ, queries=queries, query_count=len(queries))
    # [중요] 비용은 응답을 읽은 «직후»에 적는다. 아래의 파일·원장 기록은 `StepFailed` 가 아닌
    # 예외(`OSError` 등)로도 죽는데, 그 길에는 비용을 실어 나를 자리가 없어 **이미 쓴 돈이
    # 회차의 쓴 돈 · 토큰 · 한도 비율에서 통째로 빠진다**
    decision_log.record_cost(run_dir, "explore", result)

    # 원문을 먼저 남긴다. 아래에서 무엇이 걸러지든 「에이전트가 무엇을 냈나」는 남아야 한다.
    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남으므로 원자적으로 바꾼다
    with atomic_write(run_dir / EXPLORE_RESULT_FILENAME) as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    stored = _store(ledger_path, candidates)

    decision_log.record(
        run_dir,
        "explore",
        decision_log.EVENT_JUDGED,
        added=stored.added,
        proposed=len(candidates),
        overflow=len(stored.overflow),
        activity_rejected=stored.activity_rejected,
        activity_undecided=stored.activity_undecided,
    )
    if stored.duplicates:
        decision_log.record(
            run_dir,
            "explore",
            decision_log.EVENT_DISCARDED,
            reason="이미 원장에 있는 후보",
            claims=stored.duplicates,
        )
    if stored.empty:
        decision_log.record(run_dir, "explore", decision_log.EVENT_DISCARDED, reason="주장이 비어 있다", claims=stored.empty)
    if stored.overflow:
        # 상한 밖은 보지도 않고 버린다. 기록 없이 자르면 에이전트가 무엇을 냈는지가 로그에서 사라진다
        decision_log.record(
            run_dir,
            "explore",
            decision_log.EVENT_DISCARDED,
            reason=f"한 회차에 담는 후보 상한(MAX_CANDIDATES={MAX_CANDIDATES})을 넘었다",
            claims=stored.overflow,
        )

    # [중요] 후보를 «담은 뒤에» 검사한다. 찾은 후보를 버리면 그 회차가 통째로 헛돌고,
    # 다음 회차는 원장에 재고가 생겨 탐색을 건너뛰므로 이 실패가 반복되지도 않는다
    shortfall = query_gate.shortfall_reason(queries)
    if shortfall is not None:
        decision_log.record(run_dir, "explore", decision_log.EVENT_FAILED, gate="queries", reason=shortfall)
        raise StepQualityFailed(f"탐색 검색어 부족 — {shortfall}")


def _store(ledger_path: Path, candidates: list[Any]) -> _Stored:
    """후보를 원장에 담고, 담은 수와 중복·빈 주장 · 상한 초과로 버린 것을 돌려준다.

    [중요] **정성 표현으로 거르지 않는다.** 탐색 에이전트는 사전을 모르므로 값이 다 정해진
    주장(「미국 장기채 ETF …」)에도 축을 안 내고, 여기서 거르면 사전 오탐이 원장에 영구 기각으로
    박혀 수집의 「값이 정해진 말」 선언까지 오지 못한다. 판정은 걸린 표현을 글자 그대로 짚고 선언을
    받는 수집 한 곳이 한다. 대가는 못 잴 후보가 담겨 수집 호출 한 번을 쓰고 기각되는 것이며,
    수집의 회차당 기각 상한이 그 폭을 묶는다.

    [중요] 주장은 **원장의 정규 형태로 맞춘 뒤** 다룬다. 원장이 정규 형태로 읽히므로
    여기서 에이전트가 낸 글자 그대로 비교하면 줄바꿈 하나에 중복 판정이 어긋난다.
    정규 형태가 비는 주장은 원장이 거부하므로 담기 «전»에 걸러 에이전트가 낸 글자 그대로 돌려준다.
    """
    stored = _Stored()
    # 중복은 «여기서» 먼저 걸러 낸다. 그래야 같은 후보를 두 번 낸 응답이 파일을 두 번
    # 건드리지 않는다.
    #
    # [주의] 이것이 원장 읽기를 «한 번»으로 만들지는 않는다 — `append` 는 호출마다 다시 읽는다.
    # 한 회차의 후보 수가 `MAX_CANDIDATES` 로 묶여 있어 실제
    # 비용은 작지만, **원장이 아주 커지면 여기가 먼저 느려진다.** 그때는 줄 단위 손질을
    # 한 번에 모아 쓰는 쪽으로 바꾼다
    seen = {entry.claim for entry in ledger.load(ledger_path)}
    overflowed: set[str] = set()

    for candidate in candidates:
        written = _text_of(candidate, "claim")
        claim = ledger.canonical_claim(written)
        if not claim:
            stored.empty.append(written)
            continue
        if claim in seen:
            stored.duplicates.append(claim)
            continue
        if stored.added >= MAX_CANDIDATES:
            # 거른 «뒤»에 센다 — 이 자리에 온 것은 원장에 없는 새 주장이다.
            # 같은 주장을 두 번 낸 답이면 한 번만 남긴다 — 로그의 수로 상한을 가늠한다.
            # `seen` 에 넣지 않는 것은 「이미 원장에 있는 후보」로 잘못 적히지 않게 하려는 것이다
            if claim not in overflowed:
                overflowed.add(claim)
                stored.overflow.append(written)
            continue

        if not ledger.append(ledger_path, claim, identifier=_text_of(candidate, "identifier") or None):
            stored.duplicates.append(claim)
            continue

        seen.add(claim)
        stored.added += 1
        _judge_activity(ledger_path, claim, candidate, stored)

    return stored


def _judge_activity(ledger_path: Path, claim: str, candidate: Any, stored: _Stored) -> None:
    """방금 담은 후보의 연간 가동일을 판정해, 모자라면 그 자리에서 기각으로 표시한다.

    [중요] 담은 «뒤»에 기각한다. 담지 않고 버리면 다음 탐색이 같은 후보를 또 내고 그 회차가 또
    거른다 — 기각은 「본 적 없다」가 아니다. 두 쓰기 사이에 죽으면 그 후보는 「안 판」으로 남아
    수집이 평소대로 판다. 안전한 쪽이다.
    """
    fields = candidate if isinstance(candidate, dict) else {}
    entries = fields.get("entries_per_year")
    holding = fields.get("holding_days")

    days = activity_gate.active_days(entries, holding)
    if days is None:
        stored.activity_undecided.append(claim)
        return

    try:
        basis = payload_helpers.as_text(fields.get("activity_basis"))
    except RecursionError:
        # 근거를 펴는 `as_text` 는 재귀라 아주 깊게 중첩된 근거에서 한도에 닿는다. 여기는 원장에 담은
        # «뒤»라 죽으면 그 후보가 판정 없이 「안 판」으로 남는다. 근거는 사유 글자에만 쓰이고 판정은
        # 두 숫자로 하므로, 근거를 모르는 것으로 두고 판정은 한다
        basis = ""
    reason = activity_gate.shortfall_reason(entries, holding, basis)
    if reason is None:
        return

    ledger.mark_rejected(ledger_path, claim, reason)
    stored.activity_rejected.append(
        {"claim": claim, "entries_per_year": entries, "holding_days": holding, "active_days": days}
    )


def _text_of(candidate: Any, key: str) -> str:
    """후보 항목에서 문자열 한 칸을 꺼낸다. 모양이 어긋난 항목은 빈 문자열로 돌린다."""
    if isinstance(candidate, dict):
        return payload_helpers.as_text(candidate.get(key))
    if isinstance(candidate, str) and key == "claim":
        return candidate.strip()
    return ""

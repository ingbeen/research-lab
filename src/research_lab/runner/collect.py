"""수집 단계 — 후보 하나를 골라 «찬성 근거»를 모은다.

여기가 깊게 파는 자리다. 후보 하나만 본다.

[중요] **반증은 이 단계가 찾지 않는다.** 찬성 근거를 잔뜩 모은 맥락이 쌓인 상태에서
「이제 반증을 찾아라」라고 하면 자기가 방금 지지한 것을 스스로 무너뜨리라는 요구가 되고,
**사람도 잘 못 한다.** 반증은 한 줄 주장만 받는 별도 세션의 일이다.

[중요] **이 단계가 그 회차의 후보를 정한다.** 뒤따르는 반증·계보가 같은 후보를 봐야 하므로
고른 후보를 상태 파일에 박는다. 다만 **「판 것」으로 표시하지는 않는다** — 표시는
마지막 단계의 일이고, 여기서 표시하면 그 뒤 반증이 실패해 그 실행 폴더가 버려질 때
**후보가 반증 없이 「판 것」으로 남아 영영 다시 안 파진다.**
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import PRO_EVIDENCE_FILENAME, SEARCH_QUERIES_FILENAME
from research_lab.gate import quantified
from research_lab.gate import queries as query_gate
from research_lab.runner import decision_log, ledger, naming, prose_check, state, steps, url_check
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]

# 한 회차에 기각할 수 있는 후보의 수.
#
# [중요] 상한이 없으면 원장이 전부 기각될 때까지 호출을 태운다. 나중에 보면 예산은 줄었고
# 산출물은 0장인데, 그런 회차는 「실패」가 아니라 「아무 일 없음」처럼 보여 며칠 지나서야
# 알아챈다 — 「그 외」 실패에 상한을 두는 것과 같은 이유다.
#
# 상한에 닿으면 그 회차의 수집을 끝낸다. 기각은 원장에 남으므로 다음 회차가 그 뒤부터 이어간다
MAX_REJECTIONS: Final = 3

# 출처가 실재하지 않을 때 «다시 물어보는» 횟수.
#
# [중요] 이 저장소의 다른 상한은 모두 3인데 여기만 1인 이유는 **상한이 곱셈으로 걸리기**
# 때문이다 — 다시 묻기는 후보를 바꾸는 루프 «안»에 있어 한 단계의 호출 수가
# `(이 값 + 1) x 지나친 후보 수` 가 되고, 그 위에 **회차의 재시도가 한 겹 더 곱해진다**
# (「그 외」 실패로 이 단계가 다시 불리면 아직 기록되지 않은 후보를 처음부터 다시 판다).
# [실측 2026-09-16] 수집 한 번이 $0.79 라 3 으로 두면 한 회차 예산을 통째로 태운다.
#
# 그리고 **한 번 짚어 줬는데도 또 죽은 URL 을 내면 그것은 그 시도의 실수가 아니다** —
# 그 후보의 출처를 실제로 못 찾고 있는 것이고, 그때는 다음 후보로 가는 편이 낫다
MAX_SOURCE_RETRIES: Final = 1

# 출처를 못 갖춰 «미뤄 두는» 후보의 수 상한.
#
# [중요] 기각과 «따로» 센다. 미룸은 후보 하나당 호출이 두 번이라 더 비싸고, 무엇보다
# 상한이 없으면 **원장에 든 후보를 전부 훑으며 호출을 태운다** — 기각에 상한을 둔 것과
# 같은 이유이고, 그렇게 끝난 회차는 「실패」가 아니라 「아무 일 없음」처럼 보인다.
#
# [중요] **1 이 아니라 2 인 이유가 이 장치의 목적 자체다.** 1 이면 첫 후보를 미룬 순간
# 상한에 닿아 **다음 후보를 시도조차 못 하고**, 그러면 「출처를 못 갖추면 다른 주제로
# 넘어간다」가 성립하지 않는다 — 미루기만 하고 끝나는 것은 고치기 전과 다를 바 없다.
# 2 면 미룬 뒤 다른 후보를 «반드시 한 번은» 시도한다.
#
# 거기서 멈추는 것은 **연달아 두 후보가 출처를 못 갖추면 그것이 후보의 문제가 아닐**
# 가능성이 높기 때문이다 — 네트워크·게이트·에이전트 쪽 사정이면 후보를 바꿔도 같은 자리에 선다
MAX_DEFERRALS: Final = 2


class NoCandidateError(RuntimeError):
    """원장에 팔 후보가 없을 때."""


PROMPT: Final = """이 저장소의 `.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 수집

아래 후보 **하나**의 찬성 근거를 모읍니다. 다른 후보는 보지 마세요.

> {claim}

- 검색어를 **한국어와 영어로 각각** 갈아 끼우며 3회 이상 던지고, **던진 것을 전부** 적습니다
- 근거마다 **URL · 발행일 · 1차인지 2차인지**를 함께 적습니다
- **실제로 연 URL 만** 적습니다. 기억으로 URL 을 만들어 내지 마세요 —
  링크를 못 찾았으면 URL 을 비우고 `unverified` 에 적습니다
- **반증은 찾지 마세요.** 다른 단계의 일입니다
- 찬성 근거가 하나도 없으면 빈 목록으로 두세요. **「실체 없음」도 정상 결과입니다**
- 비용·세금·슬리피지는 적지 마세요

## 이 주장의 «파라미터 축»을 함께 냅니다

{axis_demand}

값이 비어 있는 말마다 **무엇을 얼마로 바꿀 수 있는지**를 `params` 에 적습니다 —
축 이름과 단위, 그리고 **서로 다른 숫자 후보값 2개 이상**입니다.

- 「짧은 기간 내 동시 매수」 → `{{"name": "동시 매수 판정 창", "unit": "거래일", "candidates": [5, 10, 20]}}`
- 「전저점 대비」 → `{{"name": "전저점 산정 일수", "unit": "거래일", "candidates": [20, 60]}}`

**축을 못 정하겠으면 빈 목록으로 두세요.** 「옥석을 가려」처럼 무엇을 채울지조차 없는 말과,
「(미래) 저점에서 산다」처럼 판정 시점에 알 수 없는 값이 여기 걸립니다.
그 후보는 잴 수 없는 것으로 판정되어 사유와 함께 기록되며, **그것도 정상 결과입니다** —
임의로 값 하나를 채우면 어떤 값을 넣느냐가 결론을 만듭니다.

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"claim": "받은 한 줄 주장 그대로", "identifier": "짧은-영문-이름", "queries": ["던진 검색어 전부"], "params": [{{"name": "축 이름", "unit": "단위", "candidates": [숫자, 숫자]}}], "evidence": [{{"title": "", "url": "", "published": "YYYY-MM-DD 또는 unknown", "kind": "primary|secondary", "says": "이 출처가 주장을 어떻게 뒷받침하나"}}], "unverified": ["확인하지 못한 것"]}}
"""

# 출처가 실재하지 않아 «다시» 물을 때 지시문 뒤에 붙이는 말.
#
# [중요] 원래 지시문을 복제하지 않고 **덧붙인다.** 두 벌로 쓰면 규율을 고치는 날
# 한쪽만 고쳐지고, 그 갈림은 에러를 내지 않는다.
#
# [중요] 「다른 출처를 찾아라」만 적지 않는다. 그렇게만 말하면 **빈자리를 메우려고
# 주소를 지어내는** 유인이 생긴다 — 이 게이트가 막으려던 바로 그 행동이다.
# 그래서 「못 찾으면 빼고 미검증에 적으라」를 «같은 무게로» 함께 준다
RETRY_SUFFIX: Final = """

## 다시 냅니다 — 앞서 낸 출처에 문제가 있었습니다

{problem}

- **그 주소를 그대로 다시 내지 마세요.** 실제로 열어 본 다른 출처를 찾습니다
- **못 찾으면 그 근거를 빼세요.** 무엇을 확인하지 못했는지는 `unverified` 에 적습니다.
  빈자리를 메우려고 주소를 지어내면 같은 자리에서 또 막힙니다 — **근거가 줄어드는 것은
  정상 결과이고, 없는 출처를 적는 것은 아닙니다**
- 나머지 규율은 위와 같습니다. 다른 말 없이 **JSON 하나만** 출력하세요
"""


def build_prompt(claim: str, *, source_problem: str | None = None) -> str:
    """수집 지시문을 만든다.

    [중요] 걸린 표현을 **이름으로 짚어** 요구한다. 「값이 비어 있으면 적으라」고만 하면
    에이전트가 자기 문장에 그런 말이 있는지를 스스로 판정해야 하고, 실측에서 이미
    「이 주장은 값이 다 정해졌다」고 넘어가는 모양이 나왔다. 그러면 그 후보는 기각되는데,
    **탐색에서 한 번 통과했던 후보가 수집에서 죽는** 일이 된다.

    Args:
        claim: 팔 후보의 한 줄 주장
        source_problem: 앞선 시도에서 출처가 막힌 사유. 주면 그것을 짚어 다시 내라는
            말이 뒤에 붙는다. **어느 주소가 문제였는지 이름으로 실려 있어야** 고칠 수 있다

    Returns:
        에이전트에게 줄 지시문
    """
    terms = quantified.triggered_terms(claim)
    if terms:
        demand = (
            f"이 주장에는 값이 비어 있는 표현이 있습니다 — **{' · '.join(terms)}**.\n"
            f"**이 표현들은 반드시 축으로 풀어야 합니다.** 하나도 풀지 못하면 그 후보는 "
            f"잴 수 없는 것으로 판정되어 사유와 함께 기록됩니다."
        )
    else:
        demand = "이 주장은 값이 다 정해져 있습니다. 그래도 잴 때 갈릴 축이 있으면 적고, 없으면 `params` 는 빈 목록입니다."
    prompt = PROMPT.format(claim=claim, axis_demand=demand)
    if source_problem is None:
        return prompt
    return prompt + RETRY_SUFFIX.format(problem=source_problem)


def run(run_dir: Path, ledger_path: Path, ask: AgentCaller) -> None:
    """후보를 하나 골라 찬성 근거를 파일로 남기고, 그 회차의 후보로 박는다.

    잴 수 없다고 판정된 후보는 사유와 함께 기각하고 **다음 후보로 넘어간다.**
    기각은 실패가 아니라 판정의 결과이므로 그 회차가 멈추지 않는다.

    출처가 실재하지 않으면 그 주소를 짚어 **한 번 다시 묻고**, 그래도 안 되면 그 후보를
    미뤄 두고 다음 후보로 간다. 미룸은 원장에 표시하지 않는다 — 기각도 막힘도 그 사정이
    아니기 때문이며, 그 사실은 결정 로그가 소유한다.

    Args:
        run_dir: 그 회차의 실행 폴더
        ledger_path: 원장 경로
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Raises:
        NoCandidateError: 원장에 팔 후보가 처음부터 없을 때. 탐색이 먼저 돌아야 한다
        StepFailed: 응답이 약속한 모양이 아닐 때
        StepQualityFailed: 검색어 규율을 못 지켰을 때 · 자립성 게이트에 막혔을 때 ·
            **미룸이 상한에 닿았을 때**. 마지막 것은 그 폴더를 미완성으로 남겨
            다음 회차가 로그를 물려받게 하려는 것이다
    """
    # 단계가 자기 산출물 폴더를 만든다. 부르는 쪽이 만들어 줬을 것이라 가정하면
    # 호출 경로가 늘 때마다 같은 실수를 되풀이한다
    run_dir.mkdir(parents=True, exist_ok=True)

    # [중요] 기각 수를 «그 회차 전체»에서 센다. 지역 변수로만 세면 이 함수가 다시 불릴 때
    # 0 으로 돌아간다 — JSON 이 깨져 「그 외」로 재시도되는 회차는 이 함수가 최대 세 번
    # 불리므로 상한이 세 배가 되고, 그만큼 후보와 예산이 함께 탄다.
    # 그 회차의 결정 로그가 이미 기각을 기록하므로 새 상태를 만들지 않고 그것을 센다
    rejections = _rejections_so_far(run_dir)
    deferred = decision_log.deferred_claims(run_dir, steps.COLLECT)
    while True:
        if rejections >= MAX_REJECTIONS:
            # 상한에 닿았다. 그 회차의 수집은 여기서 끝나고 기각은 원장에 남으므로
            # 다음 회차가 그 뒤부터 이어간다. **부르기 «전»에 본다** — 뒤에서 보면
            # 이 단계가 다시 불릴 때마다 한 번씩 더 부르게 된다
            return

        if len(deferred) >= MAX_DEFERRALS:
            # [중요] 여기서만은 «정상 종료»가 아니라 실패로 끝낸다. 미룸은 원장에 아무
            # 표시도 남기지 않으므로, 조용히 끝내면 그 폴더가 완주로 닫히고 **결정 로그가
            # 폴더와 함께 사라진다** — 다음 회차는 새 폴더에서 미룬 사실을 모른 채 같은
            # 후보를 다시 집고, 회차마다 호출만 태우며 0장을 낸다. 그 상태는 「실패」가
            # 아니라 「아무 일 없음」처럼 보여 며칠 지나서야 드러난다.
            #
            # 실패로 끝내면 그 폴더가 미완성으로 남아 **다음 회차가 이어받아 로그를 물려받고**,
            # 그래도 계속 막히면 회차 사이의 상한이 그 후보를 원장에서 걷어낸다 —
            # 없애려던 무한 반복을 막는 장치가 이미 거기 있다
            raise StepQualityFailed(
                f"출처를 갖춘 후보를 찾지 못했습니다 — {len(deferred)}개 후보가 실재하는 URL 을 내지 못했습니다. "
                "다음 회차가 이어받습니다."
            )

        candidate = ledger.next_unexplored(ledger_path, skip=deferred)
        if candidate is None:
            if rejections == 0 and not deferred:
                raise NoCandidateError("원장에 아직 안 판 후보가 없습니다. 탐색이 먼저 돌아야 합니다.")
            # 꺼낼 수 있던 후보를 모두 기각했거나 미뤄 두었다. 그 회차의 수집은 여기서 끝나고
            # 뒤따르는 단계는 「그 회차의 후보 없음」으로 건너뛰어진다 — 정상 결과다
            return

        payload = _ask_about(run_dir, candidate.claim, ask)

        shortfall = quantified.shortfall_reason(candidate.claim, payload.get("params"))
        if shortfall is not None:
            ledger.mark_rejected(ledger_path, candidate.claim, shortfall)
            decision_log.record(
                run_dir,
                steps.COLLECT,
                decision_log.EVENT_DISCARDED,
                claim=candidate.claim,
                reason=shortfall,
            )
            rejections += 1
            continue

        settled = _settle_sources(run_dir, candidate.claim, payload, ask)
        if settled is not None:
            _store(run_dir, ledger_path, candidate, settled)
            return

        # 출처를 끝내 못 갖췄다. **원장은 건드리지 않는다** — 기각은 「잴 수 없다」는
        # 판정이고 막힘은 「회차마다 같은 자리에서 실패해 접었다」는 뜻이라, 둘 중 어느 것도
        # 이 사정이 아니다. 적어 버리면 멀쩡한 후보가 사람이 손대기 전까지 영영 다시 안 파진다
        decision_log.record(
            run_dir,
            steps.COLLECT,
            decision_log.EVENT_DEFERRED,
            claim=candidate.claim,
            reason="출처가 실재하지 않습니다 — 다시 물어도 고쳐지지 않았습니다",
        )
        deferred.add(candidate.claim)


def _settle_sources(run_dir: Path, claim: str, payload: dict[str, Any], ask: AgentCaller) -> dict[str, Any] | None:
    """출처가 실재할 때까지 상한만큼 다시 묻는다.

    [중요] 자리가 «정성 표현 게이트 뒤 · 저장 앞»이다. 앞에 두면 곧 기각될 후보의
    URL 까지 찌르고, 뒤에 두면 **죽은 URL 이 든 파일이 이미 쓰인 뒤**다.

    Args:
        run_dir: 그 회차의 실행 폴더
        claim: 팔 후보의 한 줄 주장
        payload: 방금 받은 산출물
        ask: 프롬프트를 받아 에이전트를 부르는 쪽

    Returns:
        출처가 실재하는 산출물. 상한까지 물어도 안 고쳐졌으면 None —
        **그때 그 후보를 미루는 것은 부르는 쪽의 판단이다**

    Raises:
        StepQualityFailed: 자립성 게이트에 막혔을 때. 그쪽은 다시 묻는 대상이 아니다
    """
    for attempt in range(MAX_SOURCE_RETRIES + 1):
        prose_check.assert_self_contained(run_dir, steps.COLLECT, payload, what="수집 산출물")

        problem = url_check.check_sources(run_dir, steps.COLLECT, payload.get("evidence"), what="수집 출처")
        if problem is None:
            return payload
        if attempt == MAX_SOURCE_RETRIES:
            return None

        # 사유를 그대로 실어 다시 묻는다. 어느 주소가 문제였는지 짚어 주지 않으면
        # **다음 답도 같은 것을 낸다** — 게이트가 미완성을 돌려줄 때 무엇이 왜 비었는지를
        # 함께 돌려주는 이유와 같다
        payload = _ask_about(run_dir, claim, ask, source_problem=problem)

    # 위 루프는 언제나 `return` 으로 끝난다 — 마지막 회차에서 상한 가지가 잡기 때문이다
    raise RuntimeError(f"내부 불변조건 위반: 출처 확인 루프가 값 없이 끝났습니다 — 상한={MAX_SOURCE_RETRIES}")


def _rejections_so_far(run_dir: Path) -> int:
    """그 회차가 지금까지 기각한 후보 수를 결정 로그에서 센다."""
    return sum(
        1
        for entry in decision_log.read(run_dir)
        if entry.get("step") == steps.COLLECT and entry.get("event") == decision_log.EVENT_DISCARDED
    )


def _ask_about(run_dir: Path, claim: str, ask: AgentCaller, *, source_problem: str | None = None) -> dict[str, Any]:
    """후보 하나를 두고 에이전트를 부르고, 무엇을 읽고 얼마를 썼는지 남긴다.

    기록을 «게이트 앞»에서 남긴다. 막혀서 끝나도 그 회차가 무엇을 했고 얼마를 태웠는지는
    남아야 한다 — 없으면 회차 예산을 정할 때 그만큼이 통째로 빠진 값으로 계산된다.
    **다시 묻는 호출도 같다** — 두 번째 호출의 비용이 빠지면 그 회차의 합이 조용히 작아진다.

    Raises:
        StepQualityFailed: 검색어가 모자랄 때
    """
    result = ask(build_prompt(claim, source_problem=source_problem))
    payload = invoke.parse_json_answer(result, what="수집")

    queries = payload_helpers.as_strings(payload.get("queries"))

    decision_log.record(run_dir, steps.COLLECT, decision_log.EVENT_READ, queries=queries, query_count=len(queries))
    decision_log.record_cost(run_dir, steps.COLLECT, result)

    shortfall = query_gate.shortfall_reason(queries)
    if shortfall is not None:
        decision_log.record(run_dir, steps.COLLECT, decision_log.EVENT_FAILED, gate="queries", reason=shortfall)
        raise StepQualityFailed(f"수집 검색어 부족 — {shortfall}")

    return payload


def _store(run_dir: Path, ledger_path: Path, candidate: ledger.Entry, payload: dict[str, Any]) -> None:
    """찬성 근거를 파일로 남기고 그 후보를 그 회차의 후보로 박는다."""
    identifier = candidate.identifier
    if identifier is None:
        # 예전에 담긴 후보에는 식별자가 없다. 그 후보를 두고 에이전트를 어차피 불렀으므로
        # 여기서 박으면 «별도 호출이 들지 않는다» — 이것이 이미 쌓인 후보도
        # 짧은 폴더명을 얻는 경로다
        supplied = payload_helpers.as_text(payload.get("identifier"))
        if supplied:
            identifier = ledger.assign_identifier(ledger_path, candidate.claim, supplied) or None

    evidence = payload_helpers.as_list(payload.get("evidence"))
    unverified = payload_helpers.as_list(payload.get("unverified"))
    params = payload_helpers.as_list(payload.get("params"))
    queries = payload_helpers.as_strings(payload.get("queries"))

    # [중요] 산출물은 «후보별 폴더»에 넣는다. 실행 폴더 바로 아래에 고정 이름으로 쓰면
    # 한 회차가 후보 둘을 파는 순간 뒤엣것이 앞엣것을 덮어쓴다.
    # 경로를 만드는 곳은 `naming` 하나여야 한다는 계층 계약이 여기서 지켜진다
    output_dir = run_dir / naming.folder_name(candidate.claim, identifier)

    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남는다
    with atomic_write(output_dir / PRO_EVIDENCE_FILENAME) as file:
        json.dump(
            {"claim": candidate.claim, "params": params, "evidence": evidence, "unverified": unverified},
            file,
            ensure_ascii=False,
            indent=2,
        )
    with atomic_write(output_dir / SEARCH_QUERIES_FILENAME) as file:
        json.dump({"claim": candidate.claim, "queries": queries}, file, ensure_ascii=False, indent=2)

    decision_log.record(
        run_dir,
        steps.COLLECT,
        decision_log.EVENT_JUDGED,
        claim=candidate.claim,
        identifier=identifier,
        evidence_count=len(evidence),
        unverified_count=len(unverified),
        # 「찬성 근거 0건」은 고장이 아니라 **실체 없음이라는 정상 결과**다.
        # 그 판정을 나중에 기계가 골라낼 수 있게 이름을 붙여 둔다
        verdict="실체 없음" if not evidence else "근거 있음",
    )

    # 파일을 쓴 «뒤에» 박는다. 순서가 반대면 산출물 없이 후보만 박혀,
    # 뒤따르는 반증·계보가 있지도 않은 근거 위에서 돈다
    state.pin_candidate(run_dir, state.Candidate(claim=candidate.claim, identifier=identifier))

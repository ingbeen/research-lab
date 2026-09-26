"""실현가능성 단계 — dossier 의 4번 칸(데이터)과 5번 칸(집행)을 채운다.

채우는 순서가 `계보 → 찬성 → 반증 → 데이터 → 집행` 이라 4·5번 칸이 출처 쪽 칸들 뒤에 온다.

[중요] **이 단계는 회차의 마지막이 «아니다».** 뒤에 메커니즘(3·9번 칸) · 측정 설계(10번 칸) ·
판정(2번 칸)이 붙었으므로 「판 것」 표시는 여기서 하지 않는다. 여기서 표시하면 그 뒤 세
단계가 실패할 때 **후보가 그 칸들 없이 「판 것」으로 남아 영영 다시 안 파진다** —
수집이 표시하던 때와 똑같은 고장이고, 계층 계약 §4 가 「단계를 뒤에 더할 때마다 표시가
함께 옮겨간다」를 규칙으로 박아 둔 이유가 이것이다.

[중요] **그래서 이 단계는 원장을 받지 않는다.** 안 쓰는 인자를 두면 「실현가능성도 원장을
고친다」로 읽힌다 — 반증과 계보가 같은 이유로 안 받는다.

[중요] **러너가 데이터 카탈로그 본문을 읽어 프롬프트에 싣는다.** 경로만 가리키면 읽혔는지
확인할 길이 없고, 안 읽어도 **에러 없이 「이미 있음」만 조용히 안 나온다.** 이 저장소는
프롬프트 지시가 형식적으로만 지켜진 것을 세 번 확인했다.

[중요] **이 단계는 후보를 «기각하지 않는다».** 4·5번 칸은 묻는 자리이고 기각은 판정(2번 칸)이다.
설계 §7 이 「기각 신호」를 적어 둔 것은 **사람이 나중에 읽을 단서**이지 여기서 내릴 판정이
아니다 — 내리려 들면 이 단계가 또 하나의 판단자가 된다.

[중요] **검색어 게이트를 걸지 않는다.** 카탈로그가 답을 주는 후보는 검색이 필요 없고,
그때 검색어 하한을 요구하면 **억지 검색을 시키게 된다.** 계보 단계에 검색어 게이트가
없는 것과 같은 이유다. 던졌으면 기록만 한다.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from research_lab.agent import invoke
from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import DATA_CATALOG_PATH, FEASIBILITY_FILENAME
from research_lab.gate import feasibility as feasibility_gate
from research_lab.runner import decision_log, naming, prose_check, state, url_check
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

AgentCaller = Callable[[str], AgentResult]

STEP_NAME: Final = "feasibility"

# 카탈로그 항목 이름을 뽑는 자리. 제목 줄의 백틱 안에 있다.
#
# 글자 집합을 원장의 식별자와 같게 둔다 — 둘 다 사람과 에이전트가 손으로 쓰는 짧은 이름이고,
# 규칙이 갈리면 「카탈로그에는 있는데 못 찾는」 상태가 조용히 생긴다
CATALOG_ID_PATTERN: Final = re.compile(r"^#{2,}\s+`([a-z0-9][a-z0-9-]*)`", re.MULTILINE)

PROMPT: Final = """`.claude/skills/dossier-research/SKILL.md` 를 먼저 읽고 그 규율을 그대로 따르세요.

## 할 일 — 실현가능성

아래 주장을 **잰다면 무엇이 필요한가**와 **개인이 집행할 수 있는가**를 채웁니다.

> {claim}

**이 후보를 기각하거나 채택하지 마세요.** 판정은 다른 자리의 일입니다.
여기서는 **묻는 것에 답만** 합니다 — 「신호가 연 1회」처럼 걸리는 답이 나오면 그대로 적으면 됩니다.

## 무엇을 묻나

**4번 칸 — 데이터**

- `needs`: 어떤 데이터가 필요한가 (일봉? 분봉? 수급? 재무?)
- `availability`: **`이미 있음` · `받을 수 있음` · `막힘` 중 하나** — 다른 말로 적지 마세요
- `how_to_get`: 무엇으로 어떻게 받나
- `point_in_time`: **그 시점에 실제로 알 수 있었나** (재무는 발표가 늦습니다)
- `survivorship`: 상장폐지·합병 종목이 빠지지 않나
- `fallback`: 막히면 무엇으로 대체하나 — 대체 데이터 → 대상 축소 → 기간 축소 순으로 봅니다

**5번 칸 — 집행**

- `instrument`: 개인이 살 수 있는 상품이 있나 (없으면 그 사실과 이유)
- `signal_frequency`: 신호가 얼마나 자주 오나
- `leverage`: 배수를 걸 수 있나
- `waking_hours`: **사람이 깨어 있는 시간에** 집행 가능한가
- `intraday_precision`: 분·초 단위 집행이 필요한가

**`market`**: 대상 시장을 반드시 적습니다. 배수 상한이 시장마다 달라서, 시장 없이 적은
「1배뿐이다」는 나중에 되짚을 수 없습니다.

**[중요] 비용 · 세금 · 슬리피지는 적지 마세요.** 증권사·계좌·이벤트에 따라 자릿수가 달라지고
그 폭이 기대값과 같은 크기라 **어떤 값을 넣느냐가 결론을 만듭니다.**

**물을 것이 없는 자리는 「해당 없음」과 그 이유를 적습니다.** 빈 채로 두는 것과 다릅니다.

## 이미 밝혀진 것 — 아래에서 먼저 찾습니다

여기 있는 것을 새로 알아내면 낭비이고, **더 나쁘게는 틀리게 알아냅니다.**
쓴 항목의 이름(백틱 안의 짧은 영문)을 `catalog_hit` 에 적습니다.

**[중요] 답이 아래를 가리키게 쓰지 마세요** — 「그 문서를 보라」처럼 적지 않습니다. 이 산출물은 저장소 밖으로
나가므로 그 순간 **판단이 불가능한 종이**가 됩니다. 아래의 「자립 서술」은 그대로 옮겨도
읽히게 쓰여 있으니 **그 내용을 답 안에 풀어 적습니다.**

**아래에 없는 축은 「없는 데이터」가 아니라 「실측이 아직 없다」는 뜻입니다.**
그때는 웹에서 확인하고, 확인 못 하면 `unverified` 에 적습니다. 연 URL 은 `sources` 에
적고 **실제로 연 것만** 적습니다. 답에는 어디에 없는지가 아니라
「이 파이프라인이 실측한 기록 없음」처럼 **사실만** 적습니다.

----- 데이터 카탈로그 시작 -----
{catalog}
----- 데이터 카탈로그 끝 -----

## 낼 것

다른 말 없이 **JSON 하나만** 출력하세요.

{{"claim": "받은 한 줄 주장 그대로", "market": "국내|미국|둘 다", "data": {{"needs": ["필요한 데이터"], "availability": "이미 있음|받을 수 있음|막힘", "how_to_get": "", "point_in_time": "", "survivorship": "", "fallback": ""}}, "execution": {{"instrument": "", "signal_frequency": "", "leverage": "", "waking_hours": "", "intraday_precision": ""}}, "catalog_hit": ["쓴 카탈로그 항목 이름"], "queries": ["웹에서 확인했다면 던진 검색어"], "sources": [{{"title": "", "url": ""}}], "unverified": ["확인하지 못한 것"]}}
"""

# 카탈로그를 못 읽었을 때 프롬프트에 들어갈 말.
#
# 빈 문자열을 그대로 끼우면 에이전트가 「이미 밝혀진 것이 하나도 없다」로 읽어
# **받을 수 있는 데이터까지 「없다」로 적는다** — 설계 §7.0 이 경고한 오판이다
CATALOG_MISSING_NOTE: Final = (
    "(이번에는 이 자리에 실을 내용을 읽지 못했습니다. 「없는 데이터」라는 뜻이 «아닙니다» — 필요한 것을 웹에서 확인하고, 확인 못 한 것은 `unverified` 에 적으세요.)"
)


def build_prompt(claim: str, catalog: str) -> str:
    """실현가능성 지시문을 만든다.

    Args:
        claim: 그 회차의 한 줄 주장
        catalog: 데이터 카탈로그 본문. 못 읽었으면 빈 문자열

    Returns:
        에이전트에게 줄 지시문
    """
    return PROMPT.format(claim=claim, catalog=catalog.strip() or CATALOG_MISSING_NOTE)


def load_catalog(path: Path = DATA_CATALOG_PATH) -> str:
    """데이터 카탈로그 본문을 읽는다.

    [중요] 읽기에 실패하면 빈 문자열을 돌린다. 카탈로그는 검사기가 아니라 «입력»이고,
    입력이 없다고 회차를 세우면 **문서 한 장이 파이프라인을 멈추는** 구조가 된다 —
    무인 실행에는 고칠 사람이 없다. 못 읽은 사실은 결정 로그에 남는다.

    Args:
        path: 카탈로그 경로

    Returns:
        본문, 못 읽었으면 빈 문자열
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # [중요] 인코딩 오류도 함께 잡는다. `UnicodeDecodeError` 는 `OSError` 가 아니라
        # `ValueError` 라서, 안 잡으면 「카탈로그가 없어도 회차는 돈다」는 계약이 깨진다 —
        # WSL 과 mac 을 오가는 한글 문서라 편집기 한 번이 이 갈래를 만들 수 있고,
        # 그러면 그 단계가 매 회차 실패하며 상한까지 재시도한다
        return ""


def catalog_ids(catalog: str) -> frozenset[str]:
    """카탈로그에 실재하는 항목 이름을 뽑는다.

    이것이 있어야 에이전트가 낸 적중 이름이 실재하는지 대조할 수 있다.
    **막는 데 쓰지 않는다** — 계측의 진실성을 지키는 데만 쓴다.

    Args:
        catalog: 카탈로그 본문

    Returns:
        항목 이름들
    """
    return frozenset(CATALOG_ID_PATTERN.findall(catalog))


def run(
    run_dir: Path,
    ask: AgentCaller,
    *,
    catalog_path: Path = DATA_CATALOG_PATH,
) -> None:
    """4·5번 칸을 파일로 남긴다.

    Args:
        run_dir: 그 회차의 실행 폴더
        ask: 프롬프트를 받아 에이전트를 부르는 쪽
        catalog_path: 데이터 카탈로그 경로. 없으면 카탈로그 없이 진행한다

    Raises:
        RuntimeError: 그 회차의 후보가 상태에 없을 때 — 러너가 건너뛰었어야 하는 자리다
        StepFailed: 응답이 약속한 모양이 아닐 때
        StepQualityFailed: 4·5번 칸의 자리가 비었거나 출처가 실재하지 않을 때
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate = state.pinned_candidate(run_dir)
    if candidate is None:
        raise RuntimeError(f"내부 불변조건 위반: 그 회차의 후보가 상태에 없습니다 — {run_dir}")

    catalog = load_catalog(catalog_path)
    result = ask(build_prompt(candidate.claim, catalog))
    payload = invoke.parse_json_answer(result, what="실현가능성")

    known = catalog_ids(catalog)
    claimed = payload_helpers.as_strings(payload.get("catalog_hit"))
    # [중요] 실재하는 적중을 **한 번만 골라** 로그와 산출물이 같은 값을 쓰게 한다.
    # 두 곳에서 따로 고르면 고르는 규칙이 바뀔 때 한쪽만 고쳐지고, 그때
    # **로그와 산출물이 어긋나는데 에러가 안 난다** — 이 계측이 막으려던 것과 같은 고장이다
    hit = [name for name in claimed if name in known]

    # 무엇을 놓고 판단했고 얼마를 썼는지는 «게이트 앞»에서 남긴다.
    # 막혀서 끝나도 그 회차가 무엇을 했고 얼마를 태웠는지는 기록에 남아야 한다
    decision_log.record(
        run_dir,
        STEP_NAME,
        decision_log.EVENT_READ,
        catalog_items=len(known),
        catalog_read=bool(catalog.strip()),
        # [중요] 「썼다고 한 이름」과 「실재하는 이름」을 갈라 적는다. 지어낸 이름이 섞이면
        # 이 계측이 「카탈로그를 썼다」로 **거짓 긍정**을 내고 그 고장은 에러를 내지 않는다.
        # **막지는 않는다** — 판정이 아니라 계측의 진실성이고, 게이트를 세우면
        # 항목명을 못 옮겨 적은 회차가 통째로 죽는다
        catalog_hit=hit,
        catalog_hit_unknown=[name for name in claimed if name not in known],
        # [중요] 이 값도 «계측이지 판정이 아니다». 5번 칸에 비용이 섞이는 것을 막으면
        # 금지어 = 기각 구조가 되어 멀쩡한 후보가 죽는다. 분포를 보고 나중에 정한다
        cost_terms=list(feasibility_gate.cost_terms_in(payload.get("execution"))),
        # 검색어는 «게이트 없이» 기록만 한다. 카탈로그가 답을 주는 후보에 하한을 요구하면
        # 억지 검색을 시키게 된다
        queries=payload_helpers.as_strings(payload.get("queries")),
    )
    decision_log.record_cost(run_dir, STEP_NAME, result)

    shortfall = feasibility_gate.shortfall_reason(payload)
    if shortfall is not None:
        decision_log.record(run_dir, STEP_NAME, decision_log.EVENT_FAILED, gate=STEP_NAME, reason=shortfall)
        raise StepQualityFailed(f"실현가능성 칸 미달 — {shortfall}")

    # [중요] 값싼 게이트가 «전부 통과한 뒤»에 부른다. 이 검사만 네트워크를 쓰므로,
    # 어차피 막힐 단계에서 URL 을 찌르는 것은 순 낭비다
    prose_check.assert_self_contained(run_dir, STEP_NAME, payload, what="실현가능성 산출물")
    url_check.assert_sources_exist(run_dir, STEP_NAME, payload.get("sources"), what="실현가능성 출처")

    _store(run_dir, candidate, payload, hit=hit)


def _store(run_dir: Path, candidate: state.Candidate, payload: dict[str, Any], *, hit: list[str]) -> None:
    """4·5번 칸을 파일로 남기고 무엇을 판단했는지 기록한다.

    Args:
        hit: 카탈로그에 «실재하는» 적중 이름만. 지어낸 이름을 산출물에 남기면
            저장소 밖에서 그것을 찾으러 가게 되고, 그 문서는 어디에도 없다
    """
    output_dir = run_dir / naming.folder_name(candidate.claim, candidate.identifier)
    data: Any = payload[feasibility_gate.KEY_DATA]
    execution: Any = payload[feasibility_gate.KEY_EXECUTION]

    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 파일이 남는다
    with atomic_write(output_dir / FEASIBILITY_FILENAME) as file:
        json.dump(
            {
                "claim": candidate.claim,
                "market": payload.get(feasibility_gate.KEY_MARKET),
                "data": dict(data),
                "execution": dict(execution),
                "catalog_hit": hit,
                "sources": payload_helpers.as_list(payload.get("sources")),
                "unverified": payload_helpers.as_list(payload.get("unverified")),
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    decision_log.record(
        run_dir,
        STEP_NAME,
        decision_log.EVENT_JUDGED,
        claim=candidate.claim,
        market=payload.get(feasibility_gate.KEY_MARKET),
        # 이 값이 로그에 있어야 나중에 「데이터가 이미 있던 후보가 몇이었나」를 셀 수 있고,
        # 이 Phase 의 완료 조건(「이미 있음」이 나온다)도 그 자리에서 확인된다
        availability=data.get(feasibility_gate.KEY_AVAILABILITY),
        unverified_count=len(payload_helpers.as_list(payload.get("unverified"))),
    )

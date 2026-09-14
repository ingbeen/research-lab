"""실현가능성 단계가 남기는 것의 계약을 고정한다 — 4·5번 칸과 「판 것」 표시.

이 단계가 **밤의 마지막**이라 「판 것」 표시가 여기로 옮겨왔다. 계보가 끝나며 표시하면
그 뒤 실현가능성이 실패할 때 **후보가 4·5번 칸 없이 「판 것」으로 남아 영영 다시 안 파진다**
— 수집이 표시하던 때와 똑같은 고장이고, 계층 계약 §4 의 「마지막 단계가 표시한다」가
그것을 막으려고 있는 규칙이다.

[중요] **카탈로그를 러너가 읽어 프롬프트에 싣는다.** 경로만 가리키면 읽혔는지 확인할 길이
없고, 안 읽어도 **에러가 안 나면서 「이미 있음」만 조용히 안 나온다.** 이 저장소는
프롬프트 지시가 형식적으로만 지켜진 것을 세 번 확인했다.

[중요] **카탈로그가 없어도 그 밤은 돈다.** 카탈로그는 검사기가 아니라 «입력»이고,
입력이 없다고 밤을 멈추면 검사기가 파이프라인을 세우는 구조가 된다 — 계층 계약 §3 의
「판정을 못 하는 것과 실패로 판정하는 것은 다르다」가 여기에도 걸린다.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from research_lab.agent.invoke import AgentResult
from research_lab.common_constants import FEASIBILITY_FILENAME
from research_lab.runner import decision_log, feasibility, ledger, naming, state
from research_lab.runner.steps import StepQualityFailed

CLAIM = "미국 주가지수 ETF 를 옵션 만기주 첫 거래일에 사서 만기일 종가에 판다"
IDENTIFIER = "opex-us"

CATALOG = """# 데이터 카탈로그

### `us-etf-daily` — 미국 시세 (일봉)

미국 ETF 일봉은 yfinance 계열로 받을 수 있다.

### `expiry-calendar` — 만기 달력

만기일은 외부에서 받는 데이터가 아니라 달력 규칙이다.
"""


def _answer(payload: object) -> AgentResult:
    """에이전트가 그 JSON 을 돌려줬다고 치는 응답."""
    text = json.dumps(payload, ensure_ascii=False)
    return AgentResult(text=text, raw=text, cost_usd=0.4, tokens=90, elapsed_seconds=1.0, session_id="세션")


def _filled(**overrides: Any) -> dict[str, Any]:
    """게이트를 통과하는 산출물."""
    payload: dict[str, Any] = {
        "claim": CLAIM,
        "market": "미국",
        "data": {
            "needs": ["미국 주가지수 ETF 일봉", "옵션 만기일 달력"],
            "availability": "이미 있음",
            "how_to_get": "미국 ETF 일봉은 yfinance 계열로 받을 수 있고 이 기계에 받아둔 것이 있다",
            "point_in_time": "일봉 종가만 쓰므로 그날 장 마감 뒤에 알 수 있다",
            "survivorship": "지수 추종 ETF 한 종목이라 편향이 들어올 자리가 없다",
            "fallback": "막히면 지수 일봉으로 대체하되 집행 불가로 표시한다",
        },
        "execution": {
            "instrument": "국내 증권사로 직접 매수 가능한 미국 상장 ETF 가 있다",
            "signal_frequency": "월 1회 — 연 12건",
            "leverage": "미국은 3배 ETF 가 있다",
            "waking_hours": "미국장이라 한국시간 야간이다",
            "intraday_precision": "종가 기준이라 분·초 집행이 필요 없다",
        },
        "catalog_hit": ["us-etf-daily", "expiry-calendar"],
        "unverified": ["위클리 옵션 이후 월물 만기의 특별함이 희석됐는지"],
    }
    payload.update(overrides)
    return payload


def _pin(run_dir: Path, ledger_path: Path) -> Path:
    """그 밤의 후보를 원장과 상태에 박고 후보 폴더를 돌려준다."""
    ledger.append(ledger_path, CLAIM, identifier=IDENTIFIER)
    state.pin_candidate(run_dir, state.Candidate(claim=CLAIM, identifier=IDENTIFIER))
    return run_dir / naming.folder_name(CLAIM, IDENTIFIER)


def _catalog(tmp_path: Path, text: str = CATALOG) -> Path:
    """카탈로그 파일을 만든다."""
    path = tmp_path / "DATA_CATALOG.md"
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# 카탈로그를 «실어» 보낸다
# --------------------------------------------------------------------------


def test_prompt_carries_the_catalog_body() -> None:
    """
    목적: [중요] 카탈로그 «본문»이 프롬프트에 실리는 계약을 고정한다.

    경로만 가리키면 읽혔는지 확인할 길이 없다. 스킬(규율)은 못 읽어도 「문서는 그럴듯하고
    규율만 빠지는」 정도지만, 카탈로그를 못 읽으면 **「이미 있음」이 조용히 안 나온다** —
    그것이 이 단계의 완료 조건이다.

    Given: 한 줄 주장과 카탈로그 본문
    When: 지시문을 만든다
    Then: 둘 다 들어 있다
    """
    prompt = feasibility.build_prompt(CLAIM, CATALOG)

    assert CLAIM in prompt
    assert "us-etf-daily" in prompt
    assert "만기일은 외부에서 받는 데이터가 아니라 달력 규칙이다" in prompt


def test_prompt_demands_self_standing_prose() -> None:
    """
    목적: 4번 칸을 «자립 서술»로 적으라는 요구가 프롬프트에 있는 계약을 고정한다.

    이 저장소의 1순위 제약이다 — dossier 는 저장소 밖으로 나가므로 「카탈로그에 있다」로
    적히면 그 순간 **판단이 불가능한 종이**가 된다. 게이트는 이것을 못 막는다(내용 판정이
    된다). 막을 수 없는 것은 프롬프트와 계측이 전부이므로, 그 요구가 사라지지 않게 박는다.

    Given: 지시문
    When: 만든다
    Then: 「카탈로그에 있다」로 적지 말라는 요구가 들어 있다
    """
    prompt = feasibility.build_prompt(CLAIM, CATALOG)

    assert "카탈로그에 있다" in prompt


def test_missing_catalog_does_not_stop_the_night(tmp_path: Path) -> None:
    """
    목적: [중요] 카탈로그를 못 읽어도 그 밤이 «멈추지 않는» 계약을 고정한다.

    카탈로그는 검사기가 아니라 입력이다. 없다고 밤을 세우면 **문서 한 장이 파이프라인을
    멈추는** 구조가 되고, 무인 실행에는 고칠 사람이 없다. 대신 그 사실을 로그에 남긴다 —
    「판정을 못 하는 것은 로그에 남기고 통과시킨다」가 계층 계약 §3 이다.

    Given: 있지도 않은 카탈로그 경로
    When: 카탈로그를 읽는다
    Then: 예외 없이 빈 본문이 돌아온다
    """
    assert feasibility.load_catalog(tmp_path / "없는파일.md") == ""


def test_catalog_ids_are_extracted(tmp_path: Path) -> None:
    """
    목적: 카탈로그에서 «항목 이름»을 뽑는 계약을 고정한다.

    이 이름들이 있어야 에이전트가 낸 적중 이름이 실재하는지 대조할 수 있다.

    Given: 항목 둘이 든 카탈로그
    When: 이름을 뽑는다
    Then: 둘 다 나온다
    """
    assert feasibility.catalog_ids(CATALOG) == frozenset({"us-etf-daily", "expiry-calendar"})


def test_run_carries_the_catalog_into_the_prompt(tmp_path: Path) -> None:
    """
    목적: 단계가 실제로 카탈로그를 읽어 실어 보내는 계약을 고정한다.

    `build_prompt` 가 받기만 하고 아무도 안 넘겨주면 **프롬프트 테스트는 초록인데
    밤에는 카탈로그가 빠진다.** 그 구멍은 실측 전까지 드러나지 않는다.

    Given: 카탈로그 파일
    When: 단계를 돈다
    Then: 에이전트가 받은 지시문에 카탈로그가 들어 있다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)
    seen: list[str] = []

    def ask(prompt: str) -> AgentResult:
        seen.append(prompt)
        return _answer(_filled())

    feasibility.run(run_dir, ledger_path, ask, catalog_path=_catalog(tmp_path))

    assert "us-etf-daily" in seen[0]


# --------------------------------------------------------------------------
# 산출물과 「판 것」 표시
# --------------------------------------------------------------------------


def test_writes_its_own_file(tmp_path: Path) -> None:
    """
    목적: 4·5번 칸을 «파일»로 남기는 계약을 고정한다.

    아무도 보지 않는 시간에 도는 실행이라 화면에 쓴 것은 사라진다.

    Given: 채워진 산출물을 내놓는 응답
    When: 단계를 돈다
    Then: 후보 폴더에 파일이 생기고 4·5번 칸이 들어 있다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    output_dir = _pin(run_dir, ledger_path)

    feasibility.run(run_dir, ledger_path, lambda _: _answer(_filled()), catalog_path=_catalog(tmp_path))

    written = json.loads((output_dir / FEASIBILITY_FILENAME).read_text(encoding="utf-8"))
    assert written["claim"] == CLAIM
    assert written["market"] == "미국"
    assert written["data"]["availability"] == "이미 있음"
    assert written["execution"]["signal_frequency"] == "월 1회 — 연 12건"


def test_marks_the_candidate_explored(tmp_path: Path) -> None:
    """
    목적: [중요] 「판 것」 표시를 «이 단계»가 하는 계약을 고정한다.

    이 단계가 밤의 마지막이다. 계보가 끝나며 표시하면 그 뒤 이 단계가 실패할 때
    **후보가 4·5번 칸 없이 「판 것」으로 남아 영영 다시 안 파진다.**

    Given: 후보 하나가 든 원장
    When: 이 단계까지 끝난다
    Then: 그 후보가 판 것으로 표시돼 다음 후보가 없다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)

    assert ledger.next_unexplored(ledger_path) is not None

    feasibility.run(run_dir, ledger_path, lambda _: _answer(_filled()), catalog_path=_catalog(tmp_path))

    assert ledger.next_unexplored(ledger_path) is None


def test_writes_the_file_before_marking(tmp_path: Path) -> None:
    """
    목적: 파일을 쓴 «뒤»에 표시하는 계약을 고정한다.

    순서가 반대면 산출물 없이 후보만 「판 것」으로 남는다 — 그 후보는 다시 안 파지므로
    4·5번 칸이 영영 비어 있게 되고, **아침에는 완주한 밤처럼 보인다.**

    Given: 게이트에 막히는 산출물
    When: 단계를 돈다
    Then: 막히고, 파일도 없고, 후보는 «안 판 것»으로 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    output_dir = _pin(run_dir, ledger_path)
    blocked = _filled()
    blocked["execution"]["signal_frequency"] = ""

    with pytest.raises(StepQualityFailed):
        feasibility.run(run_dir, ledger_path, lambda _: _answer(blocked), catalog_path=_catalog(tmp_path))

    assert not (output_dir / FEASIBILITY_FILENAME).exists()
    assert ledger.next_unexplored(ledger_path) is not None


def test_without_a_pinned_candidate_it_is_an_invariant_violation(tmp_path: Path) -> None:
    """
    목적: 그 밤의 후보가 없으면 «고장»으로 터지는 계약을 고정한다.

    러너가 건너뛰었어야 하는 자리다(`steps.CANDIDATE_STEPS`). 조용히 넘어가면
    후보 없이 돌아 상한까지 헛돈 뒤 「다음 밤이 이어받습니다」로 보고된다.

    Given: 후보가 안 박힌 실행 폴더
    When: 단계를 돈다
    Then: 내부 불변조건 위반으로 터진다
    """
    run_dir = tmp_path / "run"

    with pytest.raises(RuntimeError):
        feasibility.run(run_dir, tmp_path / "원장.md", lambda _: _answer(_filled()), catalog_path=_catalog(tmp_path))


# --------------------------------------------------------------------------
# URL 실재 검사
# --------------------------------------------------------------------------


def test_is_blocked_when_a_source_url_does_not_exist(tmp_path: Path, probing: Any) -> None:
    """
    목적: 적어 낸 출처가 실재하지 않으면 막는 계약을 고정한다.

    카탈로그에 없는 축(예: 미국 쪽 새 항목)은 웹에서 확인하게 되어 있고,
    그러면 **없는 출처를 지어낼 자리가 이 단계에도 생긴다.**

    Given: 죽은 URL 이 든 출처
    When: 단계를 돈다
    Then: 「질」 실패가 오르고 후보는 안 판 것으로 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)
    probing(dead={"https://example.com/없는문서"})

    payload = _filled(sources=[{"title": "지어낸 문서", "url": "https://example.com/없는문서"}])

    with pytest.raises(StepQualityFailed):
        feasibility.run(run_dir, ledger_path, lambda _: _answer(payload), catalog_path=_catalog(tmp_path))

    assert ledger.next_unexplored(ledger_path) is not None


def test_does_not_probe_when_a_cheaper_gate_already_blocked(tmp_path: Path, probing: Any) -> None:
    """
    목적: 값싼 게이트가 막았으면 «바깥을 두드리지 않는» 계약을 고정한다.

    어차피 막힐 단계에서 남의 서버를 두드리는 것은 순 낭비이고 예의도 아니다 —
    계층 계약 §6 이다.

    Given: 4·5번 칸 게이트에 막히는 산출물과 출처 URL
    When: 단계를 돈다
    Then: 막히고, 아무 URL 도 찔리지 않는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)
    probed = probing()

    blocked = _filled(sources=[{"url": "https://example.com/찌르면안된다"}])
    blocked["market"] = ""

    with pytest.raises(StepQualityFailed):
        feasibility.run(run_dir, ledger_path, lambda _: _answer(blocked), catalog_path=_catalog(tmp_path))

    assert probed == []


# --------------------------------------------------------------------------
# 계측 — 막혀서 끝나도 남는다
# --------------------------------------------------------------------------


def _entries(run_dir: Path, event: str) -> list[dict[str, Any]]:
    """그 단계가 남긴 결정 로그 줄을 고른다."""
    return [
        entry
        for entry in decision_log.read(run_dir)
        if entry.get("step") == "feasibility" and entry.get("event") == event
    ]


def test_cost_and_measurements_survive_a_block(tmp_path: Path) -> None:
    """
    목적: 게이트에 막혀 끝나도 «무엇을 썼고 무엇을 봤는지»가 남는 계약을 고정한다.

    막힌 밤의 비용이 안 남으면 밤 예산을 정할 때 그만큼이 통째로 빠진 값으로 계산된다.

    Given: 게이트에 막히는 산출물
    When: 단계를 돈다
    Then: 비용과 계측이 결정 로그에 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)
    blocked = _filled()
    blocked["data"]["fallback"] = ""

    with pytest.raises(StepQualityFailed):
        feasibility.run(run_dir, ledger_path, lambda _: _answer(blocked), catalog_path=_catalog(tmp_path))

    assert _entries(run_dir, decision_log.EVENT_COST)
    assert _entries(run_dir, decision_log.EVENT_READ)
    assert _entries(run_dir, decision_log.EVENT_FAILED)


def test_catalog_hits_are_recorded(tmp_path: Path) -> None:
    """
    목적: 에이전트가 카탈로그의 «무엇»을 근거로 삼았는지 계측하는 계약을 고정한다.

    이 값이 늘 비어 있으면 **카탈로그를 실어도 안 쓴 것**이고, 그때 고쳐야 하는 것은
    카탈로그가 아니라 프롬프트다. 계측이 없으면 그 구별이 안 된다.

    Given: 카탈로그 항목 둘을 짚은 산출물
    When: 단계를 돈다
    Then: 짚은 이름들이 결정 로그에 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)

    feasibility.run(run_dir, ledger_path, lambda _: _answer(_filled()), catalog_path=_catalog(tmp_path))

    read = _entries(run_dir, decision_log.EVENT_READ)[0]
    assert sorted(read["catalog_hit"]) == ["expiry-calendar", "us-etf-daily"]
    assert read["catalog_hit_unknown"] == []


def test_unknown_catalog_hits_are_counted_separately(tmp_path: Path) -> None:
    """
    목적: [중요] 카탈로그에 «없는» 이름을 따로 세는 계약을 고정한다.

    지어낸 이름이 섞이면 위 계측이 「카탈로그를 썼다」로 **거짓 긍정**을 내고,
    그 고장은 에러를 내지 않는다. **막지는 않는다** — 이것은 판정이 아니라
    계측의 진실성이고, 게이트를 세우면 항목명을 못 옮겨 적은 밤이 통째로 죽는다.

    Given: 카탈로그에 없는 이름이 섞인 산출물
    When: 단계를 돈다
    Then: 막히지 않고, 없는 이름이 따로 기록된다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)

    payload = _filled(catalog_hit=["us-etf-daily", "지어낸-항목"])
    feasibility.run(run_dir, ledger_path, lambda _: _answer(payload), catalog_path=_catalog(tmp_path))

    read = _entries(run_dir, decision_log.EVENT_READ)[0]
    assert read["catalog_hit"] == ["us-etf-daily"]
    assert read["catalog_hit_unknown"] == ["지어낸-항목"]


def test_cost_terms_in_execution_are_recorded_but_do_not_block(tmp_path: Path) -> None:
    """
    목적: 5번 칸의 비용 표현이 «기록되고 막지는 않는» 계약을 고정한다 (설계 §2 · §10.1 A).

    Given: 5번 칸에 수수료가 섞인 산출물
    When: 단계를 돈다
    Then: 완주하고, 걸린 표현이 결정 로그에 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)

    payload = _filled()
    payload["execution"]["leverage"] = "미국은 3배까지 있으나 왕복 수수료가 크다"
    feasibility.run(run_dir, ledger_path, lambda _: _answer(payload), catalog_path=_catalog(tmp_path))

    read = _entries(run_dir, decision_log.EVENT_READ)[0]
    assert read["cost_terms"] == ["수수료"]


def test_judgement_records_the_availability(tmp_path: Path) -> None:
    """
    목적: 데이터 판정을 «기계가 읽을 수 있게» 남기는 계약을 고정한다.

    이 값이 로그에 있어야 나중에 「데이터가 이미 있던 후보가 몇이었나」를 셀 수 있고,
    이 Phase 의 완료 조건(「이미 있음」이 나온다)도 그 자리에서 확인된다.

    Given: 「이미 있음」으로 판정한 산출물
    When: 단계를 돈다
    Then: 그 값과 시장이 결정 로그에 남는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)

    feasibility.run(run_dir, ledger_path, lambda _: _answer(_filled()), catalog_path=_catalog(tmp_path))

    judged = _entries(run_dir, decision_log.EVENT_JUDGED)[0]
    assert judged["availability"] == "이미 있음"
    assert judged["market"] == "미국"

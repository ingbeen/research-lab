"""반증·계보 두 단계가 남기는 것의 계약을 고정한다.

**반증을 별도 세션으로 떼는 이유**는 하나다 — 같은 세션에서 찬성 근거를 잔뜩 모은 다음
「이제 반증을 찾아라」라고 하면, 자기가 방금 지지한 것을 스스로 무너뜨리라는 요구가 되고
**사람도 잘 못 한다.** 그래서 이 세션은 **한 줄 주장만** 받는다.

[중요] 세션이 갈리는 것은 구조가 보장하지만 **파일을 일부러 찾아 읽는 것까지는 못 막는다.**
스킬을 읽히려면 `Read` 도구가 필요해 도구를 뺄 수 없고, 실행 디렉터리가 저장소라 그 회차의
폴더가 보인다. 그래서 판정 대신 **계측을 심는다** — 반증 URL 과 찬성 URL 이 얼마나 겹쳤나를
로그에 적되, 그것으로 막지는 않는다. 겹치는 것 자체는 정상일 수도 있다(같은 논문을 양쪽이 인용).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from research_lab.agent.invoke import AgentResult, new_session_id
from research_lab.common_constants import (
    LINEAGE_FILENAME,
    PRO_EVIDENCE_FILENAME,
    REBUTTAL_FILENAME,
    REBUTTAL_QUERIES_FILENAME,
)
from research_lab.runner import decision_log, ledger, lineage, naming, rebut, state
from research_lab.runner.steps import StepQualityFailed

CLAIM = "11월 첫 거래일에 사서 4월 마지막 거래일에 판다"
QUERIES = ["Sell in May 비판", "sell in may debunked", "할로윈 효과 재현 실패"]


def _answer(payload: object) -> AgentResult:
    """에이전트가 그 JSON 을 돌려줬다고 치는 응답."""
    text = json.dumps(payload, ensure_ascii=False)
    return AgentResult(
        text=text, raw=text, cost_usd=0.5, tokens=100, usage=None, elapsed_seconds=1.0, session_id=new_session_id()
    )


def _pin(run_dir: Path, ledger_path: Path) -> Path:
    """그 회차의 후보를 원장과 상태에 박고 후보 폴더를 돌려준다."""
    ledger.append(ledger_path, CLAIM, identifier="sell-in-may")
    state.pin_candidate(run_dir, state.Candidate(claim=CLAIM, identifier="sell-in-may"))
    return run_dir / naming.folder_name(CLAIM, "sell-in-may")


def _write_pro_evidence(output_dir: Path, urls: list[str]) -> None:
    """수집이 남겼을 찬성 근거 파일을 만든다."""
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"claim": CLAIM, "evidence": [{"url": url} for url in urls], "unverified": []}
    (output_dir / PRO_EVIDENCE_FILENAME).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------
# 반증
# --------------------------------------------------------------------------


def test_rebut_prompt_carries_only_the_claim() -> None:
    """
    목적: 반증 세션이 «한 줄 주장만» 받는 계약을 고정한다.

    찬성 근거가 프롬프트에 실리면 별도 세션으로 뗀 의미가 사라진다 — 맥락을 끊으려고
    나눈 것인데 그 맥락을 손으로 다시 실어 주는 셈이 된다.

    Given: 한 줄 주장
    When: 지시문을 만든다
    Then: 주장은 들어 있고, 「이 주장을 깨라」가 임무로 적혀 있다
    """
    prompt = rebut.build_prompt(CLAIM)

    assert CLAIM in prompt
    assert "반증" in prompt


def test_rebut_writes_its_own_file(tmp_path: Path) -> None:
    """
    목적: 반증이 산출물을 «파일»로 남기는 계약을 고정한다.

    아무도 보지 않는 시간에 도는 실행이라 화면에 쓴 것은 사라진다.

    Given: 반증 하나를 내놓는 응답
    When: 반증을 돈다
    Then: 후보 폴더에 반증 파일이 생기고 내용이 들어 있다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")

    rebut.run(
        run_dir,
        lambda _: _answer(
            {
                "claim": CLAIM,
                "queries": QUERIES,
                "rebuttals": [{"title": "재현 실패", "url": "https://example.com/반박", "kind": "primary"}],
                "unverified": [],
            }
        ),
    )

    written = json.loads((output_dir / REBUTTAL_FILENAME).read_text(encoding="utf-8"))
    assert written["claim"] == CLAIM
    assert written["rebuttals"][0]["url"] == "https://example.com/반박"

    # 검색어도 «후보 폴더»에 남는다. 결정 로그에만 두면 그 후보의 산출물만 모아 볼 때
    # 「반대편으로 갈아 끼웠나」를 확인할 길이 사라진다
    queries = json.loads((output_dir / REBUTTAL_QUERIES_FILENAME).read_text(encoding="utf-8"))
    assert queries["queries"] == QUERIES


def test_rebut_records_overlap_with_pro_evidence(tmp_path: Path) -> None:
    """
    목적: 반증이 찬성 근거와 «얼마나 겹쳤나»를 계측해 남기는 계약을 고정한다.

    이 단계가 찬성 근거 파일을 몰래 읽는 것은 기계로 못 막는다. 그래서 막는 대신
    **재서 남긴다** — 높으면 의심 신호다. [중요] **이 값으로 판정하지 않는다.**
    같은 논문을 찬성·반증이 함께 인용하는 것은 정상이기 때문이다.

    Given: 찬성 근거와 URL 하나가 겹치는 반증
    When: 반증을 돈다
    Then: 겹친 수가 결정 로그에 남는다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    _write_pro_evidence(output_dir, ["https://example.com/같은글", "https://example.com/찬성만"])

    rebut.run(
        run_dir,
        lambda _: _answer(
            {
                "queries": QUERIES,
                "rebuttals": [{"url": "https://example.com/같은글"}, {"url": "https://example.com/반증만"}],
            }
        ),
    )

    judged = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_JUDGED]
    assert judged[0]["overlap_with_pro_evidence"] == 1


def test_rebut_survives_a_pro_evidence_file_with_broken_encoding(tmp_path: Path) -> None:
    """
    목적: [중요] 앞 단계 파일의 «인코딩»이 깨져도 이 단계가 죽지 않는 계약을 고정한다.

    이 값은 계측이라 「못 재면 0」이 계약인데, `UnicodeDecodeError` 는 `OSError` 가 아니라
    `ValueError` 라서 「파일 없음」과 「JSON 깨짐」만 잡으면 **그대로 빠져나간다.**

    터지는 자리가 나쁘다 — 계측은 **에이전트를 이미 부른 뒤**라, 그 회차는 돈을 다 쓰고
    산출물은 못 남긴다. 그리고 파일이 그대로 남으므로 **다음 회차도 같은 자리에서 죽는다.**

    Given: 한글 중간에서 끊겨 UTF-8 로 못 읽는 찬성 근거 파일
    When: 반증을 돈다
    Then: 예외 없이 끝나고, 겹친 수가 0 으로 남는다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    output_dir.mkdir(parents=True, exist_ok=True)
    broken = ('{"evidence": [{"says": "한 문장"'.encode())[:-2]
    (output_dir / PRO_EVIDENCE_FILENAME).write_bytes(broken)

    rebut.run(
        run_dir,
        lambda _: _answer({"queries": QUERIES, "rebuttals": [{"url": "https://example.com/반증만"}]}),
    )

    judged = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_JUDGED]
    assert judged[0]["overlap_with_pro_evidence"] == 0


def test_a_null_not_found_reason_is_not_stored_as_the_word_none(tmp_path: Path) -> None:
    """
    목적: [중요] 반증 사유가 «`null`» 이어도 `"None"` 으로 저장되지 않는 계약을 고정한다.

    이 값은 문서의 반증 칸으로 그대로 나간다. `str(None)` = `"None"` 이 저장되면
    「0건」 옆에 사유랍시고 `None` 이 붙고, **받는 사람은 그것이 무슨 뜻인지 알 길이 없다.**

    Given: 반증이 있고 사유 열쇠가 `null` 인 응답
    When: 반증을 돈다
    Then: 저장된 사유가 빈 문자열이다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")

    rebut.run(
        run_dir,
        lambda _: _answer(
            {"queries": QUERIES, "rebuttals": [{"url": "https://example.com/반증"}], "not_found_reason": None}
        ),
    )

    written = json.loads((output_dir / REBUTTAL_FILENAME).read_text(encoding="utf-8"))
    assert written["not_found_reason"] == ""


def test_lineage_survives_a_source_file_with_broken_encoding(tmp_path: Path) -> None:
    """
    목적: [중요] 앞 단계 파일의 «인코딩»이 깨져도 계보가 그 파일만 건너뛰는 계약을 고정한다.

    위 반증과 같은 갈래다. 이쪽은 「앞 단계가 실체 없음으로 끝나 파일이 비거나 없을 수
    있고 그것은 정상 결과」가 계약인데, 인코딩 갈래만 그 계약 밖으로 샌다.

    Given: 찬성 근거 파일의 인코딩이 깨지고 반증 파일은 멀쩡한 회차
    When: 계보를 돈다
    Then: 예외 없이 끝나고, 모은 출처가 반증 쪽 하나뿐이다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    output_dir.mkdir(parents=True, exist_ok=True)
    broken = ('{"evidence": [{"url": "https://example.com/한글"'.encode())[:-2]
    (output_dir / PRO_EVIDENCE_FILENAME).write_bytes(broken)
    (output_dir / REBUTTAL_FILENAME).write_text(
        json.dumps({"rebuttals": [{"url": "https://example.com/반증"}]}, ensure_ascii=False), encoding="utf-8"
    )

    lineage.run(
        run_dir,
        lambda _: _answer(
            {
                "groups": [{"origin": {"url": "https://example.com/반증"}, "copies": [], "why": "하나뿐이다"}],
                "independent_source_count": 1,
            }
        ),
    )

    judged = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_JUDGED]
    assert judged[0]["collected_sources"] == 1


def test_rebut_is_blocked_when_the_field_is_missing(tmp_path: Path) -> None:
    """
    목적: 반증 칸이 없는 응답이 그 회차를 «미완성»으로 만드는 계약을 고정한다.

    이것이 게이트 1차의 본체다. 재시도 대상이 아닌 「질」 갈래로 올라가야
    같은 회차에 full 예산으로 세 번 더 부르지 않는다.

    Given: 반증 칸이 없는 응답
    When: 반증을 돈다
    Then: 「질」 실패가 오르고 사유가 실려 있다
    """
    run_dir = tmp_path / "run"
    _pin(run_dir, tmp_path / "원장.md")

    with pytest.raises(StepQualityFailed):
        rebut.run(run_dir, lambda _: _answer({"queries": QUERIES}))


def test_rebut_is_blocked_when_queries_are_too_few(tmp_path: Path) -> None:
    """
    목적: 반증 검색어에도 하한이 걸리는 계약을 고정한다.

    반증은 「X 비판」·「X debunked」처럼 **찾는 말 자체를 갈아 끼워야** 나온다.
    한 번 던지고 「없다」고 적으면 조사한 것처럼 보이지만 조사가 아니다.

    Given: 검색어 하나뿐인 응답
    When: 반증을 돈다
    Then: 「질」 실패가 오른다
    """
    run_dir = tmp_path / "run"
    _pin(run_dir, tmp_path / "원장.md")

    with pytest.raises(StepQualityFailed):
        rebut.run(run_dir, lambda _: _answer({"queries": ["하나뿐"], "rebuttals": []}))


def test_rebut_is_blocked_when_zero_findings_have_no_reason(tmp_path: Path) -> None:
    """
    목적: 반증 0건인데 «왜 못 찾았는지»가 없으면 막는 계약을 고정한다.

    0건 자체는 정상 결과다. 다만 적어 두지 않으면 **「찾아봤는데 없었다」와 「안 찾았다」가
    구별되지 않는다** — 게이트가 결과 대신 «행위»를 검사한다는 말의 실체가 이것이다.

    Given: 검색어는 충분하지만 0건이고 사유가 빈 응답
    When: 반증을 돈다
    Then: 「질」 실패가 오른다
    """
    run_dir = tmp_path / "run"
    _pin(run_dir, tmp_path / "원장.md")

    with pytest.raises(StepQualityFailed):
        rebut.run(run_dir, lambda _: _answer({"queries": QUERIES, "rebuttals": [], "not_found_reason": "   "}))


def test_rebut_passes_with_zero_findings_and_a_reason(tmp_path: Path) -> None:
    """
    목적: 「없음 + 사유」가 그대로 «통과»하는 계약을 고정한다.

    [중요] 0건을 실패로 만들면 에이전트에게 **반증을 지어낼 압력**이 생긴다.
    백테스트가 없어 부풀릴 점수가 없는 이 저장소에서 **유일하게 남는 위조 위험이
    「없는 출처」**이고, 게이트가 그 압력을 만들면 안 된다.

    Given: 검색어가 충분하고 0건이며 사유가 적힌 응답
    When: 반증을 돈다
    Then: 예외 없이 끝나고 판정이 「반증 없음」으로 남는다
    """
    run_dir = tmp_path / "run"
    _pin(run_dir, tmp_path / "원장.md")

    rebut.run(
        run_dir,
        lambda _: _answer({"queries": QUERIES, "rebuttals": [], "not_found_reason": "한국어·영어로 여섯 번 던졌으나 반대 주장이 없었다"}),
    )

    judged = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_JUDGED]
    assert judged[0]["verdict"] == "반증 없음"


def test_rebut_cost_is_recorded_even_when_blocked(tmp_path: Path) -> None:
    """
    목적: 막혀서 끝난 반증도 «얼마를 썼는지»는 남기는 계약을 고정한다.

    게이트에 걸렸어도 그 호출은 이미 토큰을 썼다. 기록이 없으면 회차 예산을 정할 때
    그만큼이 통째로 빠진 값으로 계산된다.

    Given: 게이트에 걸리는 응답
    When: 반증을 돈다
    Then: 비용이 결정 로그에 남아 있다
    """
    run_dir = tmp_path / "run"
    _pin(run_dir, tmp_path / "원장.md")

    with pytest.raises(StepQualityFailed):
        rebut.run(run_dir, lambda _: _answer({"queries": ["하나뿐"], "rebuttals": []}))

    costs = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_COST]
    assert costs and costs[0]["cost_usd"] == 0.5


def test_rebut_is_blocked_when_a_url_does_not_exist(tmp_path: Path, probing: Any) -> None:
    """
    목적: 지어낸 URL 이 든 반증이 «파일로 남지 않는» 계약을 고정한다.

    반증 세션은 「많이 찾을수록 잘한 것」이라 **지어낼 압력이 가장 큰 자리**다.
    게이트가 결과의 수를 판정하지 않는 대신, 적어 낸 출처가 실재하는지는 반드시 본다.

    Given: 실재하지 않는 URL 이 든 반증
    When: 반증을 돈다
    Then: 막히고 반증 파일이 안 쓰인다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    dead_url = "https://example.com/지어낸-반증"
    probing(dead={dead_url})
    answer = _answer({"queries": QUERIES, "rebuttals": [{"title": "없는 글", "url": dead_url, "kind": "primary"}]})

    with pytest.raises(StepQualityFailed):
        rebut.run(run_dir, lambda _: answer)

    assert not (output_dir / REBUTTAL_FILENAME).exists()


def test_rebut_does_not_probe_when_a_cheaper_gate_already_blocked(tmp_path: Path, probing: Any) -> None:
    """
    목적: 값싼 게이트가 이미 막은 단계에서 «URL 을 찌르지 않는» 계약을 고정한다.

    URL 검사만 네트워크를 쓴다. 어차피 막힐 단계에서 찌르는 것은 순 낭비이고,
    남의 서버를 두드리는 일이기도 하다.

    Given: 검색어가 모자라고 URL 도 든 반증
    When: 반증을 돈다
    Then: 막히고, 아무 URL 도 찌르지 않았다
    """
    run_dir = tmp_path / "run"
    _pin(run_dir, tmp_path / "원장.md")
    probed = probing()
    answer = _answer({"queries": ["하나뿐"], "rebuttals": [{"title": "글", "url": "https://example.com/a"}]})

    with pytest.raises(StepQualityFailed):
        rebut.run(run_dir, lambda _: answer)

    assert probed == []


# --------------------------------------------------------------------------
# 계보
# --------------------------------------------------------------------------


def test_lineage_prompt_carries_both_sides(tmp_path: Path) -> None:
    """
    목적: 계보 지시문에 찬성·반증의 출처가 «함께» 실리는 계약을 고정한다.

    계보는 「누가 원본이고 누가 베꼈나」를 묻는 단계다. 한쪽만 주면 그 판정이
    반쪽이 되고, 반증 쪽 출처가 원본인 경우를 통째로 놓친다.

    Given: 양쪽 출처
    When: 지시문을 만든다
    Then: 둘 다 들어 있다
    """
    prompt = lineage.build_prompt(CLAIM, [{"url": "https://example.com/찬성"}, {"url": "https://example.com/반증"}])

    assert "https://example.com/찬성" in prompt
    assert "https://example.com/반증" in prompt


def test_lineage_writes_its_own_file(tmp_path: Path) -> None:
    """
    목적: 계보가 산출물을 «파일»로 남기는 계약을 고정한다.

    Given: 원본 하나와 복제 하나를 묶어 낸 응답
    When: 계보를 돈다
    Then: 후보 폴더에 계보 파일이 생기고 독립 소스 수가 들어 있다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    output_dir = _pin(run_dir, ledger_path)
    _write_pro_evidence(output_dir, ["https://example.com/원본", "https://example.com/복제"])

    lineage.run(
        run_dir,
        lambda _: _answer(
            {
                "groups": [
                    {
                        "origin": {"url": "https://example.com/원본"},
                        "copies": [{"url": "https://example.com/복제"}],
                        "why": "같은 숫자가 반복된다",
                    }
                ],
                "independent_source_count": 1,
            }
        ),
    )

    written = json.loads((output_dir / LINEAGE_FILENAME).read_text(encoding="utf-8"))
    assert written["independent_source_count"] == 1


def test_the_runner_counts_the_independent_sources(tmp_path: Path) -> None:
    """
    목적: [중요] 독립 소스 수를 에이전트가 아니라 «러너가 덩어리 수로» 세는 계약을 고정한다.

    정의상 자기 혼자인 덩어리가 독립 1 이라 그 수는 덩어리 수와 같다. 에이전트가 적으면
    틀려도 에러가 없고, 그 숫자가 6번 칸의 맨 앞에 실린다.

    Given: 덩어리 둘과 모양이 어긋난 항목 하나를 내면서 독립 소스 수를 5 로 적은 응답
    When: 계보를 돈다
    Then: 저장된 수와 로그의 수가 둘 다 2 다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    _write_pro_evidence(output_dir, ["https://example.com/원본", "https://example.com/복제", "https://example.com/독립"])

    lineage.run(
        run_dir,
        lambda _: _answer(
            {
                "groups": [
                    {
                        "origin": {"url": "https://example.com/원본"},
                        "copies": [{"url": "https://example.com/복제"}],
                        "why": "같은 숫자가 반복된다",
                    },
                    {"origin": {"url": "https://example.com/독립"}, "copies": [], "why": "혼자인 덩어리"},
                    "모양이 어긋난 덩어리",
                ],
                "independent_source_count": 5,
            }
        ),
    )

    written = json.loads((output_dir / LINEAGE_FILENAME).read_text(encoding="utf-8"))
    judged = [e for e in decision_log.read(run_dir) if e["event"] == decision_log.EVENT_JUDGED]
    assert written["independent_source_count"] == 2
    assert judged[-1]["independent_source_count"] == 2


def test_a_group_without_any_url_is_not_counted(tmp_path: Path) -> None:
    """
    목적: 주소가 하나도 없는 덩어리는 독립 소스로 «세지 않는» 계약을 고정한다.

    모은 출처가 없을 때 에이전트가 지시문의 JSON 틀을 그대로 되돌려 쓰면 빈 덩어리가 하나
    생긴다. 그것을 세면 출처가 0건인 문서의 6번 칸 맨 앞에 「독립 소스 수: 1」이 찍힌다.

    Given: 모은 출처가 없는 회차와, 주소가 빈 틀 덩어리 · 빈 절 덩어리를 낸 응답
    When: 계보를 돈다
    Then: 저장된 독립 소스 수가 0 이다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")

    lineage.run(
        run_dir,
        lambda _: _answer(
            {"groups": [{"origin": {"title": "", "url": "", "published": ""}, "copies": [], "why": ""}, {}]}
        ),
    )

    written = json.loads((output_dir / LINEAGE_FILENAME).read_text(encoding="utf-8"))
    assert written["independent_source_count"] == 0


def test_the_lineage_prompt_does_not_ask_for_the_count() -> None:
    """
    목적: 지시문이 독립 소스 수를 «적게 하지 않는» 계약을 고정한다.

    러너가 세는 값을 에이전트에게도 물으면 두 값이 갈릴 수 있고, 어느 쪽이 맞는지를
    매번 판별해야 한다.

    Given: 계보 지시문
    When: 내용을 본다
    Then: 그 열쇠가 없다
    """
    assert "independent_source_count" not in lineage.build_prompt(CLAIM, [{"url": "https://example.com/원본"}])


def test_lineage_does_not_mark_the_candidate_explored(tmp_path: Path) -> None:
    """
    목적: [중요] 계보가 후보를 「판 것」으로 표시하지 «않는» 계약을 고정한다.

    표시는 회차의 «마지막» 단계의 일이고 그 자리는 실현가능성이다. 계보가 표시하면
    그 뒤 4·5번 칸이 실패할 때 **후보가 그 칸들 없이 「판 것」으로 남아 영영 다시
    안 파진다** — 수집이 표시하던 때와 똑같은 고장이다.

    그래서 이 단계는 **원장을 아예 받지 않는다.** 안 쓰는 인자를 두면
    「계보도 원장을 고친다」로 읽힌다.

    Given: 후보 하나가 든 원장
    When: 계보가 끝난다
    Then: 그 후보가 «아직 안 판 것»으로 남아 있다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    _pin(run_dir, ledger_path)

    lineage.run(run_dir, lambda _: _answer({"groups": [], "independent_source_count": 0}))

    assert ledger.next_unexplored(ledger_path) is not None


def test_lineage_is_blocked_when_a_source_is_dropped(tmp_path: Path) -> None:
    """
    목적: 모았던 출처를 빠뜨린 계보표가 막히는 계약을 고정한다.

    Given: 찬성 근거 둘 중 하나만 다룬 계보표
    When: 계보를 돈다
    Then: 「질」 실패가 오르고, 계보 파일이 생기지 않는다
    """
    run_dir = tmp_path / "run"
    ledger_path = tmp_path / "원장.md"
    output_dir = _pin(run_dir, ledger_path)
    _write_pro_evidence(output_dir, ["https://example.com/원본", "https://example.com/빠뜨린"])

    with pytest.raises(StepQualityFailed):
        lineage.run(
            run_dir,
            lambda _: _answer(
                {"groups": [{"origin": {"url": "https://example.com/원본"}, "copies": []}], "independent_source_count": 1}
            ),
        )

    assert not (output_dir / LINEAGE_FILENAME).exists()


def test_lineage_is_blocked_when_a_url_does_not_exist(tmp_path: Path, probing: Any) -> None:
    """
    목적: [중요] 계보가 낸 URL 도 «실제로 찔러 보는» 계약을 고정한다.

    근거 문서의 머리말은 「아래에 적힌 URL 은 실제로 호출해 살아 있는지 확인했습니다」라고
    **보증**한다. 그런데 계보 단계만 그 검사를 안 지나면 6번 칸의 주소는 그 보증이 거짓이다.

    [중요] **계보는 앞 단계가 안 낸 주소를 새로 들 수 있다** — 「이건 저 글을 베낀 것」이라며
    복제를 하나 더 적는 자리가 그것이고, 거기가 **없는 출처를 지어낼 수 있는 입구**다.
    없는 출처를 지어내는 것은 이 범위에서 유일하게 남은 위조 경로이고,
    **읽어서는 구별되지 않아** 기계로 막기로 한 것이다.

    Given: 모았던 출처를 다 덮으면서 «새 복제 하나»를 지어낸 계보 응답
    When: 계보를 돈다
    Then: 막히고 계보 파일이 안 쓰인다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    _write_pro_evidence(output_dir, ["https://example.com/원본"])
    fabricated = "https://example.com/지어낸-복제"
    probing(dead={fabricated})

    with pytest.raises(StepQualityFailed):
        lineage.run(
            run_dir,
            lambda _: _answer(
                {
                    "groups": [
                        {
                            "origin": {"url": "https://example.com/원본"},
                            "copies": [{"url": fabricated}],
                            "why": "같은 숫자가 반복된다",
                        }
                    ],
                    "independent_source_count": 1,
                }
            ),
        )

    assert not (output_dir / LINEAGE_FILENAME).exists()


def test_lineage_probes_both_the_origin_and_its_copies(tmp_path: Path, probing: Any) -> None:
    """
    목적: 원본과 복제를 «둘 다» 찌르는 계약을 고정한다.

    복제 쪽을 빼면 「저 글을 베꼈다」는 주장 자체의 근거가 안 찔러진다 —
    그 자리가 비면 계보표는 검증되지 않은 주장을 담은 표가 된다.

    Given: 원본 하나와 복제 하나를 묶은 계보 응답
    When: 계보를 돈다
    Then: 두 주소를 다 찔렀다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    _write_pro_evidence(output_dir, ["https://example.com/원본", "https://example.com/복제"])
    probed = probing()

    lineage.run(
        run_dir,
        lambda _: _answer(
            {
                "groups": [
                    {
                        "origin": {"url": "https://example.com/원본"},
                        "copies": [{"url": "https://example.com/복제"}],
                        "why": "같은 숫자가 반복된다",
                    }
                ],
                "independent_source_count": 1,
            }
        ),
    )

    assert sorted(probed) == sorted(["https://example.com/원본", "https://example.com/복제"])


def test_lineage_does_not_probe_when_a_cheaper_gate_already_blocked(tmp_path: Path, probing: Any) -> None:
    """
    목적: 값싼 게이트가 이미 막은 계보 단계에서 «URL 을 찌르지 않는» 계약을 고정한다.

    URL 검사만 네트워크를 쓴다. 어차피 막힐 단계에서 찌르는 것은 순 낭비이고,
    남의 서버를 두드리는 일이기도 하다 — 수집·반증이 같은 순서를 지킨다.

    Given: 모았던 출처 하나를 빠뜨린 계보 응답
    When: 계보를 돈다
    Then: 막히고, 아무 URL 도 찌르지 않았다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    _write_pro_evidence(output_dir, ["https://example.com/원본", "https://example.com/빠뜨린-것"])
    probed = probing()

    with pytest.raises(StepQualityFailed):
        lineage.run(
            run_dir,
            lambda _: _answer({"groups": [{"origin": {"url": "https://example.com/원본"}, "copies": []}]}),
        )

    assert probed == []


def test_a_step_is_blocked_when_its_prose_points_outside(tmp_path: Path) -> None:
    """
    목적: [중요] 자립성 검사를 «단계»가 실제로 부르는 계약을 고정한다.

    게이트를 만들어 두고 부르는 쪽이 안 부르면 **그 검사는 한 번도 돌지 않고, 그 사실이
    드러나지 않는다** — 「기계가 본다」고 적어 두고 실제로는 안 보는 고장과 같은 모양이라
    게이트 단위 테스트만으로는 모자라다.

    [중요] 자리가 «단계»인 것이 핵심이다. 조립부(회차의 마지막 단계)에서 막으면
    **이미 굳은 앞 단계 산출물**을 두고 실패하고, 다음 회차는 마지막 단계만 다시 도므로
    **같은 자리에서 똑같이 실패한다** — 세 번이면 후보가 원장에서 걷힌다.
    단계에서 막으면 다음 회차가 «그 단계»를 다시 돌아 고칠 수 있다.

    Given: 함께 가지 않는 문서를 가리키는 말이 든 계보 응답
    When: 계보를 돈다
    Then: 막히고 계보 파일이 안 쓰인다
    """
    run_dir = tmp_path / "run"
    output_dir = _pin(run_dir, tmp_path / "원장.md")
    _write_pro_evidence(output_dir, ["https://example.com/원본"])

    with pytest.raises(StepQualityFailed):
        lineage.run(
            run_dir,
            lambda _: _answer(
                {
                    "groups": [
                        {
                            "origin": {"url": "https://example.com/원본"},
                            "copies": [],
                            "why": "이 스킬이 예로 든 것과 같은 모양이다",
                        }
                    ],
                    "independent_source_count": 1,
                }
            ),
        )

    assert not (output_dir / LINEAGE_FILENAME).exists()

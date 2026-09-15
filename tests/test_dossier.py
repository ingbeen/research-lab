"""근거 문서 조립의 계약을 고정한다 — 11칸이 전부 나오고, 다른 문서를 가리키지 않는다.

**이 문서가 이 파이프라인의 제품이다.** 그리고 저장소 «밖»으로 나간다 — 어느 프로젝트에든,
아직 없는 신규 프로젝트에든 그대로 넘어간다. 그래서 1순위 제약이 하나다.

> **다른 문서를 한 장도 열지 않고 판단할 수 있어야 한다.**

포인터를 쓰면 링크가 깨지는 것이 아니라 **판단이 불가능해진다.** 옮겨간 자리에는
그 저장소도, 그 규약도, 그 번호도 없기 때문이다.

[중요] **조립은 러너가 한다.** 에이전트에게 「전부 모아 마크다운으로 내라」고 시키면
앞 단계의 값을 **옮겨 적다 틀리고, 그 고장은 에러를 내지 않는다.**
"""

import json
from pathlib import Path
from typing import Any

import pytest

from research_lab.common_constants import (
    LINEAGE_FILENAME,
    MEASUREMENT_FILENAME,
    PRO_EVIDENCE_FILENAME,
    REBUTTAL_FILENAME,
)
from research_lab.gate import measurement as measurement_gate
from research_lab.runner import dossier, state
from research_lab.runner.steps import StepQualityFailed

# 경로 계산만 보는 테스트의 후보. 앞 단계 산출물이 필요 없으므로 준비물 픽스처를 안 쓴다
CANDIDATE = state.Candidate(claim="소형주는 1월에 더 오른다", identifier="january-kr")

# 러너가 만드는 «고정 문구»에 들어 있으면 안 되는 것들.
#
# [중요] 포인터는 형태가 여럿이라 하나만 막으면 나머지로 샌다 — 저장소 이름 · 폴더 경로 ·
# 문서 파일명 · 규약 번호. 이 문서는 그 어느 것도 열 수 없는 곳에서 읽힌다
FORBIDDEN_POINTERS = (
    "research-lab",
    "verify-lab",
    "CLAUDE.md",
    "DESIGN.md",
    "SKILL.md",
    "docs/",
    "runs/",
    "ledger/",
    "원장",
    "카탈로그",
    "원칙 ",
    "규약",
)

VERDICT_PAYLOAD: dict[str, Any] = {
    "verdict": "보류",
    "reason": "경제적 근거는 있으나 표본이 20건이라 시기를 둘로 쪼개면 칸당 10건이다",
    "criteria": "칸당 10건 미만이면 우연과 구별되지 않으므로 「어느 시기가 만든 값인가」를 물을 수 없다",
    "unverified_extra": ["판정 단계에서 새로 드러난 것"],
}


def _assembled(ready: Any) -> str:
    """조립한 문서의 본문."""
    written = dossier.assemble(ready.run_dir, ready.candidate, VERDICT_PAYLOAD, dossier_dir=ready.dossier_dir)
    return written.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 어디에 어떤 이름으로 쓰이나
# --------------------------------------------------------------------------


def test_the_file_is_named_by_date_and_identifier(tmp_path: Path) -> None:
    """
    목적: 파일명이 «날짜 + 짧은 식별자»인 계약을 고정한다.

    한 줄 주장을 파일명으로 쓰면 길이 한도에서 잘리고, **잘린 자리가 문장 중간이라
    무슨 후보인지 이름만으로 안 드러난다.** 날짜에 구분자를 넣지 않는 것은
    이 저장소의 추출물 이름 관용이다.

    Given: 회차 폴더 이름이 `20260914_1720`
    When: 문서 경로를 묻는다
    Then: `20260914_january-kr.md` 이다
    """
    path = dossier.path_for(tmp_path / "runs" / "20260914_1720", CANDIDATE)

    assert path.name == "20260914_january-kr.md"


def test_the_date_comes_from_the_run_folder_not_today(tmp_path: Path) -> None:
    """
    목적: [중요] 날짜를 «그 실행 폴더»에서 뽑는 계약을 고정한다.

    회차는 날을 넘겨 이어받을 수 있다. 「오늘」로 만들면 **이어받은 회차가 같은 후보의
    문서를 두 장 만들고**, 어느 것이 완성본인지 읽는 사람이 판별해야 한다.

    Given: 지난 날짜의 실행 폴더
    When: 문서 경로를 묻는다
    Then: 그 폴더의 날짜가 쓰인다
    """
    path = dossier.path_for(tmp_path / "runs" / "20251231_2359", CANDIDATE)

    assert path.name.startswith("20251231_")


def test_an_unparsable_run_folder_still_yields_a_path(tmp_path: Path) -> None:
    """
    목적: 폴더 이름이 형식에 안 맞아도 «멈추지 않는» 계약을 고정한다.

    사람이 `--run-dir` 로 아무 폴더나 지목할 수 있다. 거기서 예외를 올리면
    산출물을 다 만들어 놓고 마지막에 회차가 깨진다.

    Given: 형식에 안 맞는 폴더 이름
    When: 문서 경로를 묻는다
    Then: 예외 없이 식별자가 든 경로가 돌아온다
    """
    path = dossier.path_for(tmp_path / "손으로만든폴더", CANDIDATE)

    assert path.name.endswith("_january-kr.md")


# --------------------------------------------------------------------------
# 11칸
# --------------------------------------------------------------------------


def test_every_one_of_the_eleven_slots_is_present(prepared: Any) -> None:
    """
    목적: **11칸이 하나도 빠짐없이** 나오는 계약을 고정한다.

    자유 서술로 두면 찾은 것만 쓰고 안 찾은 것은 언급조차 안 한다. 칸이 정해져 있으면
    **안 물을 수가 없다** — 설계의 채워 본 예시에서 문제를 잡아낸 것이 5번 칸이었고,
    그것은 칸이 있어서 나온 항목이다.

    Given: 앞 여섯 단계가 끝난 후보 폴더
    When: 조립한다
    Then: 1번부터 11번까지의 제목이 모두 들어 있다
    """
    written = _assembled(prepared())

    for ordinal in range(1, 12):
        assert f"## {ordinal}." in written, ordinal


def test_the_content_of_each_slot_is_carried_over(prepared: Any) -> None:
    """
    목적: 각 칸의 «내용»이 실제로 실리는 계약을 고정한다.

    제목만 있고 내용이 비면 11칸이 다 있는 것처럼 보이면서 아무것도 말하지 않는다.

    Given: 앞 여섯 단계가 끝난 후보 폴더
    When: 조립한다
    Then: 각 단계가 낸 값들이 문서에 들어 있다
    """
    ready = prepared()
    written = _assembled(ready)

    for expected in (
        ready.candidate.claim,
        "보류",
        "윈도드레싱",
        "pykrx",
        "코스닥150",
        "1월 효과 원논문",
        "발표 후 소멸했다",
        "받아쓴 블로그",
        "12월 23일",
        "연 1회 x 20년 = 20건",
    ):
        assert expected in written, expected


def test_the_verdict_carries_its_own_criteria(prepared: Any) -> None:
    """
    목적: [중요] 판정 칸이 «적용한 기준 자체»를 담는 계약을 고정한다.

    「원칙 12 에 걸린다」로 적히면 그 번호는 저장소 밖에서 죽고, 받는 사람은
    「왜 보류지?」에 답을 얻지 못한다. 이 문서가 자립한다는 말의 실체가 이 자리다.

    Given: 기준이 적힌 판정
    When: 조립한다
    Then: 이유와 기준이 «둘 다» 문서에 들어 있다
    """
    written = _assembled(prepared())

    assert "표본이 20건이라" in written
    assert "우연과 구별되지 않으므로" in written


def test_unverified_is_gathered_from_every_step(prepared: Any) -> None:
    """
    목적: [중요] 11번 칸을 «러너가 모으는» 계약을 고정한다.

    에이전트에게 다시 옮겨 적게 하면 **옮기다 빠뜨리고, 그 고장은 에러를 내지 않는다.**
    그리고 11번 칸은 **비는 게 오히려 의심스러운** 칸이라 빠져도 티가 안 난다.

    Given: 단계마다 다른 미검증을 남긴 후보 폴더
    When: 조립한다
    Then: 모든 단계의 미검증과 판정이 덧붙인 것이 함께 들어 있다
    """
    written = _assembled(prepared())

    for expected in (
        "국내 절세 매도 유인의 크기",
        "최근 5년 국내 재현 여부",
        "ETF 상장 이전 구간의 대체 방법",
        "윈도드레싱의 국내 실증",
        "2000년 이전 코스닥 데이터 품질",
        "판정 단계에서 새로 드러난 것",
    ):
        assert expected in written, expected


# --------------------------------------------------------------------------
# 자립성 — 1순위 제약
# --------------------------------------------------------------------------


def test_the_fixed_wording_points_nowhere(prepared: Any) -> None:
    """
    목적: [중요] 러너가 만드는 «고정 문구»에 포인터가 없는 계약을 고정한다.

    이 문서는 저장소 밖으로 나가므로 저장소 이름 · 폴더 경로 · 문서 파일명 · 규약 번호가
    그 자리에서 전부 죽는다. **링크가 깨지는 것이 아니라 판단이 불가능해진다.**

    에이전트가 «쓴 문장» 안의 포인터는 여기서 못 막는다 — 그것은 내용 판정이고,
    판정하려 들면 게이트가 또 하나의 판단자가 된다. 그 자리는 사람이 나중에 본다.

    Given: 포인터가 없는 단계 산출물
    When: 조립한다
    Then: 문서 어디에도 포인터가 없다
    """
    written = _assembled(prepared())

    for pointer in FORBIDDEN_POINTERS:
        assert pointer not in written, pointer


def test_lists_are_written_as_prose_not_as_code(prepared: Any) -> None:
    """
    목적: [중요] 목록 자리에 «파이썬 표기»가 새지 않는 계약을 고정한다.

    필요한 데이터도, 진입·보유 격자도 목록으로 온다 — 이 문서에서 가장 자주 읽히는
    자리들이다. 그대로 문자열로 찍으면 `['국내 ETF 일봉']` · `[20, 40, 60]` 이 되어
    **사람이 읽는 산출물에 코드 조각이 실린다.** 읽는 사람은 이 저장소를 열 수 없고,
    그에게는 그것이 그냥 이상한 문서다.

    이 결함은 **테스트로는 안 나왔다** — 칸도 내용도 다 들어 있었기 때문이다.
    문서를 한 장 뽑아 눈으로 보고서야 드러났다.

    Given: 목록이 든 산출물
    When: 조립한다
    Then: 대괄호로 묶인 파이썬 목록 표기가 없고, 값은 그대로 읽힌다
    """
    written = _assembled(prepared())

    assert "['" not in written
    assert "[20," not in written
    assert "국내 ETF 일봉" in written
    assert "12월 20일 · 12월 23일" in written


def test_the_header_says_how_the_document_was_made(prepared: Any) -> None:
    """
    목적: 문서의 «신뢰도를 판단할 재료»가 문서 안에 있는 계약을 고정한다.

    밖에서는 이 파이프라인을 열 수 없다. 반증을 별도 세션이 모았다는 것, URL 을 실제로
    호출해 확인했다는 것, 비용·세금·슬리피지를 일부러 안 담았다는 것 — 읽는 사람이
    「이 문서를 얼마나 믿을까」를 정하는 데 필요한 것들이라 문서 «안»에 있어야 한다.

    Given: 조립된 문서
    When: 머리말을 본다
    Then: 그 셋이 적혀 있다
    """
    written = _assembled(prepared())

    assert "서로 다른 세션" in written
    assert "실제로 호출" in written
    assert "슬리피지" in written


# --------------------------------------------------------------------------
# 입력이 모자랄 때
# --------------------------------------------------------------------------


def test_a_missing_input_blocks_the_step(prepared: Any) -> None:
    """
    목적: [중요] 앞 단계의 파일이 하나라도 없으면 «막는» 계약을 고정한다.

    「한 칸이라도 비면 미완성」이 이 산출물의 규정이다. 다른 모듈의 「읽기 실패 시 빈 목록」
    관용을 여기서는 쓰지 않는다 — 그 관용은 **빈 것이 정상 결과일 수 있는 자리**의 것이고,
    여기서 쓰면 **칸이 빈 문서가 완성본으로 나간다.**

    Given: 계보 파일이 없는 후보 폴더
    When: 조립한다
    Then: 「질」 실패가 오르고 문서가 안 생긴다
    """
    ready = prepared()
    (ready.output_dir / LINEAGE_FILENAME).unlink()

    with pytest.raises(StepQualityFailed):
        dossier.assemble(ready.run_dir, ready.candidate, VERDICT_PAYLOAD, dossier_dir=ready.dossier_dir)

    assert not dossier.path_for(ready.run_dir, ready.candidate, dossier_dir=ready.dossier_dir).exists()


def test_a_broken_input_blocks_the_step(prepared: Any) -> None:
    """
    목적: 파일이 있어도 «읽히지 않으면» 막는 계약을 고정한다.

    반쯤 쓰다 끊긴 파일은 존재하면서 열리지 않는다. 그것을 빈 값으로 넘기면
    그 칸만 조용히 빈 문서가 나간다.

    Given: 깨진 JSON 이 든 파일
    When: 조립한다
    Then: 「질」 실패가 오른다
    """
    ready = prepared()
    (ready.output_dir / MEASUREMENT_FILENAME).write_text("{절반만 쓰다 끊", encoding="utf-8")

    with pytest.raises(StepQualityFailed):
        dossier.assemble(ready.run_dir, ready.candidate, VERDICT_PAYLOAD, dossier_dir=ready.dossier_dir)


def test_an_empty_finding_is_not_a_missing_input(prepared: Any) -> None:
    """
    목적: [중요] 「실체 없음」이 «정상 결과»로 통과하는 계약을 고정한다.

    찬성 근거 0건과 반증 0건은 이 파이프라인의 정상 결과다 — 억지로 채우게 만들면
    **없는 출처를 지어내게 되고, 그것이 여기서 가장 나쁜 고장이다.**
    보는 것은 「파일이 있나」이지 「내용이 비었나」가 아니다.

    Given: 반증이 0건이고 사유만 적힌 후보 폴더
    When: 조립한다
    Then: 막히지 않고, 그 사유가 문서에 실린다
    """
    ready = prepared()
    (ready.output_dir / REBUTTAL_FILENAME).write_text(
        json.dumps(
            {
                "claim": ready.candidate.claim,
                "rebuttals": [],
                "not_found_reason": "반대편 검색어를 다섯 가지로 갈아 끼웠으나 반박 문헌이 나오지 않았다",
                "unverified": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    written = _assembled(ready)

    assert "반박 문헌이 나오지 않았다" in written


def test_a_null_reason_is_not_printed_as_the_word_none(prepared: Any) -> None:
    """
    목적: [중요] JSON 의 `null` 이 «"None"» 이라는 글자로 문서에 실리지 않는 계약을 고정한다.

    `str(None)` 은 `"None"` 이라는 **내용이 있는 문자열**이다. 비었는지 보는 검사를 통과하고
    그대로 찍히므로, 「반증 0건」 옆에 사유랍시고 `None` 이 붙는다. 이 문서를 받는 사람은
    그것이 무슨 뜻인지 알 길이 없다.

    Given: 반증 0건이고 사유가 `null` 인 산출물
    When: 조립한다
    Then: 「0건」만 적히고 `None` 이라는 글자가 그 자리에 없다
    """
    ready = prepared()
    (ready.output_dir / REBUTTAL_FILENAME).write_text(
        json.dumps(
            {"claim": ready.candidate.claim, "rebuttals": [], "not_found_reason": None, "unverified": []},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    written = _assembled(ready)

    assert "**0건.**" in written
    assert "None" not in written


def test_a_dict_value_is_written_as_prose(prepared: Any) -> None:
    """
    목적: 절이 든 자리도 «파이썬 표기»로 새지 않는 계약을 고정한다.

    게이트의 「채워졌나」는 비어 있지 않은 절을 통과시킨다. 그대로 찍으면
    `{'kr': '원화 기준'}` 이 되어 목록이 새던 것과 **똑같은 고장**이 난다.

    Given: 기준선 자리에 절이 든 산출물
    When: 조립한다
    Then: 중괄호와 작은따옴표 없이 값이 읽힌다
    """
    ready = prepared()
    plan = json.loads((ready.output_dir / MEASUREMENT_FILENAME).read_text(encoding="utf-8"))
    plan["baseline"] = {"국내": "코스피 동일가중", "미국": "달러 기준 러셀3000"}
    (ready.output_dir / MEASUREMENT_FILENAME).write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    written = _assembled(ready)

    assert "{'" not in written
    assert "코스피 동일가중" in written
    assert "달러 기준 러셀3000" in written


def test_table_cells_are_written_as_prose_not_as_code(prepared: Any) -> None:
    """
    목적: [중요] 표 «한 칸»에도 파이썬 표기가 새지 않는 계약을 고정한다.

    바로 위 두 테스트가 막는 것은 «절»의 자리이고, 7·8번 칸은 **표**라 다른 함수를 탄다.
    그 함수만 `str()` 을 쓰고 있어, 같은 고장이 **출처 표에서만** 났다.
    에이전트가 `says` 를 한 문장이 아니라 여러 개로 내는 것은 흔하다.

    Given: `says` 와 `published` 가 목록인 찬성 근거
    When: 조립한다
    Then: 대괄호 표기가 없고, 값이 사람이 읽는 문장으로 이어져 있다
    """
    ready = prepared()
    path = ready.output_dir / PRO_EVIDENCE_FILENAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence"][0]["says"] = ["소형주 초과수익", "1월에 집중"]
    payload["evidence"][0]["published"] = [1976, 1]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    written = _assembled(ready)

    assert "['" not in written
    assert "[1976," not in written
    assert "소형주 초과수익 · 1월에 집중" in written


def test_a_table_cell_keeps_its_own_empty_mark_and_escaping() -> None:
    """
    목적: 표 한 칸이 «빈 값 표기»와 이스케이프를 그대로 유지하는 계약을 고정한다.

    [중요] 절의 빈 자리는 「적히지 않았습니다」이고 표의 빈 칸은 `-` 다. **둘은 달라야 한다** —
    표 안에 긴 문장이 들어가면 칸 폭이 무너진다. 그래서 펴는 방식을 공유하되 빈 값 표기는
    각자 둔다. 세로선을 안 막으면 **그 아래 표가 통째로 깨지면서 에러는 나지 않는다.**

    Given: 빈 값 · `None` · 세로선과 줄바꿈이 든 값
    When: 표 한 칸으로 만든다
    Then: 빈 것은 `-` 이고, 세로선은 이스케이프되고 줄바꿈은 공백이 된다
    """
    assert dossier._cell(None) == "-"
    assert dossier._cell("") == "-"
    assert dossier._cell([]) == "-"
    assert dossier._cell("가|나") == "가\\|나"
    assert dossier._cell("가\n나") == "가 나"


def test_nested_values_are_flattened_all_the_way_down() -> None:
    """
    목적: [중요] 펴기가 «한 겹»에서 멈추지 않는 계약을 고정한다.

    격자의 항목 타입을 일부러 안 묶어 두었다 — 진입은 날짜 문자열, 보유는 숫자로 오는 것이
    자연스럽기 때문이다. 그래서 **날짜 «구간»이 목록의 목록으로, 필요한 데이터가 사전의
    목록으로 오는 것이 정상**이고, 게이트도 그것을 막지 않는다.

    한 겹만 펴면 안쪽이 `str()` 을 타서 **이 함수가 막으려던 표기가 그대로 나온다.**
    겉보기에는 고쳐진 것처럼 보이므로 이 자리를 따로 고정한다.

    Given: 목록 안의 목록 · 목록 안의 사전
    When: 문서에 실을 문장으로 만든다
    Then: 어느 깊이에도 파이썬 표기가 없다
    """
    assert dossier._text([["12월 20일", "12월 24일"], ["12월 26일"]]) == "12월 20일 · 12월 24일 · 12월 26일"
    assert dossier._text([{"name": "국내 ETF 일봉", "source": "pykrx"}]) == "name: 국내 ETF 일봉 · source: pykrx"
    assert "[" not in dossier._text([[1, 2], [3]])
    assert "{" not in dossier._text([{"k": "v"}])


def test_the_header_date_matches_the_file_name(prepared: Any) -> None:
    """
    목적: 파일명의 날짜와 «문서 안의 날짜»가 같은 계약을 고정한다.

    「오늘」로 찍으면 날을 넘겨 이어받은 회차에서 둘이 하루 어긋나고, 읽는 사람은
    어느 쪽이 그 회차의 날짜인지 알 길이 없다. 같은 회차를 다시 조립하면 본문도 달라진다.

    Given: 지난 날짜의 실행 폴더
    When: 조립한다
    Then: 머리말의 날짜가 파일명의 날짜와 같다
    """
    ready = prepared()
    written = dossier.assemble(ready.run_dir, ready.candidate, VERDICT_PAYLOAD, dossier_dir=ready.dossier_dir)

    stamped = written.name[:8]
    assert f"{stamped[:4]}-{stamped[4:6]}-{stamped[6:]}" in written.read_text(encoding="utf-8")


def test_every_measurement_slot_the_gate_demands_is_rendered() -> None:
    """
    목적: [중요] 게이트가 요구하는 10번 칸 자리가 «문서에도» 전부 나오는 계약을 고정한다.

    자리 목록이 게이트와 문서에 두 벌로 있다 — 제목이 읽는 사람의 것이라 합칠 수 없다.
    그래서 게이트에만 자리를 더하면 **게이트도 스키마도 러너도 있다고 믿는 값이
    문서에서만 조용히 빠진다.** 이 테스트가 그 어긋남을 잡는다.

    Given: 게이트가 요구하는 자리 목록
    When: 문서가 펼치는 자리 목록과 견준다
    Then: 하나도 빠지지 않는다
    """
    demanded = {key for key, _ in measurement_gate.TEXT_FIELDS} | {key for key, _ in measurement_gate.GRID_FIELDS}
    rendered = {key for key, _ in dossier._MEASUREMENT_SLOTS}

    assert demanded <= rendered


# --------------------------------------------------------------------------
# 판정 못 한 주소 — 게이트가 «막지 않고» 사람이 볼 자리를 만든다
# --------------------------------------------------------------------------

# 실측에서 실제로 걸린 모양. 학술지·정부·언론이 봇을 막아 두 표본 연속 21% 가 여기 떨어졌다
BLOCKED_URL = "https://ssrn.example/abstract=1"


def test_unjudged_urls_land_in_the_unverified_slot(prepared: Any) -> None:
    """
    목적: 실재를 «확인하지 못한» 주소가 11번 칸에 실리는 계약을 고정한다.

    봇 차단(403)과 이름 해석 실패는 「판정 못 함」으로 통과한다 — 죽음으로 보면
    **멀쩡한 출처가 든 회차가 매번 죽기** 때문이다. 그런데 그 사실이 문서에 안 남으면
    받는 쪽은 표에 적힌 주소 중 무엇이 확인됐는지 **읽어서 구별할 수 없다.**

    Given: 판정 못 한 주소가 하나 있는 회차
    When: 조립한다
    Then: 11번 칸에 그 주소가 든다
    """
    ready = prepared()
    written = dossier.assemble(
        ready.run_dir,
        ready.candidate,
        VERDICT_PAYLOAD,
        dossier_dir=ready.dossier_dir,
        unverified_urls=[BLOCKED_URL],
    ).read_text(encoding="utf-8")

    slot = written.split("## 11.")[-1]

    assert BLOCKED_URL in slot


def test_the_unjudged_url_line_stands_on_its_own(prepared: Any) -> None:
    """
    목적: [중요] 그 줄이 «자립 서술»인 계약을 고정한다 — 1순위 제약.

    「URL 게이트에서 unknown 으로 판정됨」처럼 적으면 이 저장소를 열 수 없는 곳에서
    **아무 뜻이 없는 종이**가 된다. 읽는 사람이 그 자리에서 「왜 확인이 안 됐고 그래서
    무엇을 조심해야 하는가」를 알 수 있어야 한다.

    Given: 판정 못 한 주소가 있는 회차
    When: 조립한다
    Then: 그 줄에 포인터가 하나도 없고, 확인하지 못했다는 사실이 말로 적혀 있다
    """
    ready = prepared()
    written = dossier.assemble(
        ready.run_dir,
        ready.candidate,
        VERDICT_PAYLOAD,
        dossier_dir=ready.dossier_dir,
        unverified_urls=[BLOCKED_URL],
    ).read_text(encoding="utf-8")

    line = next(row for row in written.splitlines() if BLOCKED_URL in row)

    for pointer in FORBIDDEN_POINTERS:
        assert pointer not in line, f"판정 못 한 주소 줄이 「{pointer}」 를 가리킨다"
    assert "확인" in line, "확인하지 못했다는 사실이 말로 적혀야 한다"


def test_no_unjudged_urls_adds_nothing(prepared: Any) -> None:
    """
    목적: 판정 못 한 주소가 «없으면 아무것도 더하지 않는» 계약을 고정한다.

    없는 사실을 채워 넣으면 확인된 출처가 「확인 못 했다」로 읽힌다.

    Given: 전부 판정된 회차
    When: 조립한다
    Then: 11번 칸이 앞 단계들이 낸 미검증 그대로다
    """
    ready = prepared()
    without = _assembled(ready)
    with_empty = dossier.assemble(
        ready.run_dir, ready.candidate, VERDICT_PAYLOAD, dossier_dir=ready.dossier_dir, unverified_urls=[]
    ).read_text(encoding="utf-8")

    assert without == with_empty


def test_the_same_unjudged_url_is_listed_once(prepared: Any) -> None:
    """
    목적: 같은 주소가 «한 번만» 실리는 계약을 고정한다.

    수집과 반증이 각각 자기 출처를 찌르므로, 양쪽이 같은 논문을 인용하면 같은 주소가
    두 번 올라온다 — 겹침 자체는 정상이라는 것이 이미 실측으로 확인됐다.

    Given: 같은 주소가 두 번 들어온 회차
    When: 조립한다
    Then: 문서에 한 번만 나온다
    """
    ready = prepared()
    written = dossier.assemble(
        ready.run_dir,
        ready.candidate,
        VERDICT_PAYLOAD,
        dossier_dir=ready.dossier_dir,
        unverified_urls=[BLOCKED_URL, BLOCKED_URL],
    ).read_text(encoding="utf-8")

    assert written.count(BLOCKED_URL) == 1


def test_unjudged_urls_do_not_replace_the_steps_own_unverified(prepared: Any) -> None:
    """
    목적: [중요] 기계가 못 판정한 주소가 «에이전트가 밝힌 미검증»을 밀어내지 않는 계약을 고정한다.

    섞이거나 덮이면 「에이전트가 밝힌 것」과 「기계가 못 판정한 것」을 나중에 못 가른다.
    둘은 성질이 다르다 — 앞은 조사가 닿지 못한 자리이고, 뒤는 검사기가 판정을 못 한 자리다.

    Given: 단계마다 미검증을 남긴 회차와 판정 못 한 주소
    When: 조립한다
    Then: 둘 다 들어 있다
    """
    ready = prepared()
    written = dossier.assemble(
        ready.run_dir,
        ready.candidate,
        VERDICT_PAYLOAD,
        dossier_dir=ready.dossier_dir,
        unverified_urls=[BLOCKED_URL],
    ).read_text(encoding="utf-8")

    assert BLOCKED_URL in written
    assert "국내 절세 매도 유인의 크기" in written
    assert "판정 단계에서 새로 드러난 것" in written


def test_the_same_gap_written_with_different_spacing_is_folded(prepared: Any) -> None:
    """
    목적: 표기만 다른 같은 미검증을 «한 줄로» 접는 계약을 고정한다.

    [실측 2026-09-15] 11번 칸이 완전일치로만 접혀 같은 공백이 여러 번 실렸다.
    그 칸은 **가장 꼼꼼히 읽히는 자리**인데, 중복이 섞이면 «열린 공백이 몇 개인가»가
    읽히지 않는다.

    Given: 앞뒤 공백 · 내부 연속 공백 · 끝 마침표만 다른 같은 문장을 낸 두 단계
    When: 조립한다
    Then: 그 줄이 한 번만 나온다
    """
    ready = prepared()
    _rewrite(ready, PRO_EVIDENCE_FILENAME, unverified=["원논문 본문의 수치는 확인하지 못했다"])
    _rewrite(ready, REBUTTAL_FILENAME, unverified=["  원논문 본문의   수치는 확인하지 못했다.  "])

    written = _assembled(ready)

    # 본문을 그대로 세면 «접혔는지»가 아니라 「표기가 달라 서로 안 겹쳤는지」를 세게 된다.
    # 이 두 줄에만 있는 낱말로 센다
    assert written.count("수치는") == 1


def test_a_paraphrase_is_not_folded(prepared: Any) -> None:
    """
    목적: [중요] 뜻이 비슷할 뿐인 두 문장을 «접지 않는» 계약을 고정한다.

    접기를 의미 비교로 키우면 게이트가 아니라 판단자가 된다. 그리고 **서로 다른 공백
    둘을 하나로 접는 쪽이 중복을 남기는 쪽보다 나쁘다** — 사라진 쪽은 아무 흔적도
    남기지 않는다. 그래서 접기는 «표기 수준»에서 멈춘다.

    Given: 같은 논문을 두고 서로 다르게 쓴 두 미검증
    When: 조립한다
    Then: 둘 다 남는다
    """
    ready = prepared()
    _rewrite(ready, PRO_EVIDENCE_FILENAME, unverified=["Cusatis(1993) 수치는 PDF 추출 실패로 확인하지 못했다"])
    _rewrite(ready, REBUTTAL_FILENAME, unverified=["Cusatis, Miles, Woolridge(1993) 본문의 초과수익률은 미확인이다"])

    written = _assembled(ready)

    assert "PDF 추출 실패로 확인하지 못했다" in written
    assert "본문의 초과수익률은 미확인이다" in written


def _rewrite(ready: Any, filename: str, **fields: Any) -> None:
    """앞 단계가 남긴 산출물의 일부를 갈아 끼운다."""
    path = ready.output_dir / filename
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    payload.update(fields)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_an_object_shaped_unverified_entry_is_rendered_not_dropped(prepared: Any) -> None:
    """
    목적: [중요] 문자열이 아닌 미검증 항목을 «버리지 않고» 사람이 읽는 줄로 펴는 계약을 고정한다.

    앞 단계 넷은 응답 모양이 스키마로 강제되지 않아 미검증이 사전 모양으로 올 수 있다.
    그것을 버리면 **이 칸이 조용히 비고**, 「비어 있습니다 — 이 칸이 빈 것 자체를
    의심해 보세요」가 찍힌다. 그 문장은 그때 **거짓말**이 된다.

    Given: 사전 모양으로 적힌 미검증 항목
    When: 조립한다
    Then: 그 내용이 읽히는 한 줄로 실린다
    """
    ready = prepared()
    _rewrite(ready, PRO_EVIDENCE_FILENAME, unverified=[{"항목": "원논문 수치", "왜": "PDF 추출 실패"}])

    written = _assembled(ready)

    assert "원논문 수치" in written
    assert "PDF 추출 실패" in written
    assert "{" not in written.split("## 11.")[1], "파이썬·JSON 표기가 그대로 실리면 안 된다"

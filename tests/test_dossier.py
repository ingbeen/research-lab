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

from research_lab.common_constants import LINEAGE_FILENAME, MEASUREMENT_FILENAME, REBUTTAL_FILENAME
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

"""원장이 append-only 이고 같은 후보를 다시 담지 않는 계약을 고정한다.

원장은 「지금까지 본 후보」의 목록이고 **중복 방지의 전부**다. 없으면 같은 후보를 회차마다 다시
판다. 이 저장소가 만드는 누적 상태 중 하나인 이유는 「하루를 걸러도 그 회차가 없었을 뿐
영구 손상이 아니기」 때문이다 — 완주율·점수 같은 집계와 갈리는 지점이 여기다.

[중요] 사람도 손으로 고치는 파일이다. 그래서 프로그램이 통째로 다시 쓰지 않는다 —
다시 쓰는 순간 사람이 적어 둔 메모가 사라지고, **사라진 줄도 모른다.**
"""

from pathlib import Path

import pytest

from research_lab.runner import ledger, naming


def test_missing_ledger_reads_as_empty(tmp_path: Path) -> None:
    """
    목적: 원장이 아직 없는 첫 회차를 「빈 목록」으로 다루는 계약을 고정한다.

    Given: 없는 원장 경로
    When: 읽는다
    Then: 빈 목록이 돌아온다 (예외가 아니다)
    """
    assert ledger.load(tmp_path / "원장.md") == []


def test_appended_candidate_is_readable(tmp_path: Path) -> None:
    """
    목적: 담은 후보를 다시 읽어 오는 계약을 고정한다.

    Given: 빈 원장
    When: 후보 하나를 담고 읽는다
    Then: 그 후보가 들어 있다
    """
    path = tmp_path / "원장.md"

    ledger.append(path, "소형주는 1월에 더 오른다")

    assert "소형주는 1월에 더 오른다" in [entry.claim for entry in ledger.load(path)]


def test_append_keeps_existing_entries(tmp_path: Path) -> None:
    """
    목적: 담기가 «덧붙이기»이지 다시 쓰기가 아닌 계약을 고정한다.

    탐색 회차는 한 번에 여러 줄을 담는다. 통째로 다시 쓰면 직전 회차가 담은 것이 사라지고,
    **예외가 나지 않으므로 아무도 모른다.**

    Given: 후보가 하나 든 원장
    When: 다른 후보를 담는다
    Then: 둘 다 들어 있고 순서가 유지된다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    ledger.append(path, "둘째 후보")

    assert [entry.claim for entry in ledger.load(path)] == ["첫 후보", "둘째 후보"]


def test_human_written_lines_survive_append(tmp_path: Path) -> None:
    """
    목적: 사람이 손으로 적어 둔 내용이 살아남는 계약을 고정한다.

    이 파일은 사람도 고친다. 프로그램이 자기 형식으로 다시 쓰면 사람의 메모가 날아간다.

    Given: 사람이 머리말과 메모를 적어 둔 원장
    When: 후보를 담는다
    Then: 그 머리말이 그대로 남아 있다
    """
    path = tmp_path / "원장.md"
    preamble = "# 원장\n\n> 사람이 손으로 고칩니다. 프로그램은 줄을 덧붙이기만 합니다.\n"
    path.write_text(preamble, encoding="utf-8")

    ledger.append(path, "첫 후보")

    assert preamble in path.read_text(encoding="utf-8")


def test_duplicate_candidate_is_not_appended(tmp_path: Path) -> None:
    """
    목적: 같은 후보가 두 번 담기지 않는 계약을 고정한다.

    중복이 쌓이면 「아직 안 판 것」을 고를 때 같은 후보를 또 꺼낸다.

    Given: 후보가 이미 든 원장
    When: 같은 후보를 다시 담는다
    Then: 담기지 않고, 담지 않았다고 알려준다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    appended = ledger.append(path, "첫 후보")

    assert appended is False
    assert len(ledger.load(path)) == 1


def test_duplicate_check_ignores_surrounding_whitespace(tmp_path: Path) -> None:
    """
    목적: 공백 차이만으로 «다른 후보»가 되지 않는 계약을 고정한다.

    후보 문구는 에이전트가 매번 새로 낸다. 앞뒤 공백이 하나 다르다고 중복 판정을 빠져나가면
    중복 방지가 사실상 없는 것과 같다.

    Given: 후보가 든 원장
    When: 앞뒤 공백만 다른 같은 문구를 담는다
    Then: 담기지 않는다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    assert ledger.append(path, "  첫 후보  ") is False


def test_next_unexplored_returns_the_oldest_first(tmp_path: Path) -> None:
    """
    목적: 「쌓인 순서대로」 꺼내는 계약을 고정한다.

    고르는 규칙은 지금 이것 하나다. 「그럴듯함 순」은 아직 판 적 없는 후보를 판정해야 하므로
    근거가 없고, 그 판정 자체가 또 하나의 판단자가 된다.

    Given: 후보가 둘 든 원장
    When: 다음에 팔 후보를 묻는다
    Then: 먼저 담긴 것이 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.append(path, "둘째 후보")

    candidate = ledger.next_unexplored(path)

    assert candidate is not None
    assert candidate.claim == "첫 후보"


def test_next_unexplored_skips_finished_candidates(tmp_path: Path) -> None:
    """
    목적: 이미 판 후보를 다시 꺼내지 않는 계약을 고정한다.

    Given: 첫 후보를 판 것으로 표시한 원장
    When: 다음에 팔 후보를 묻는다
    Then: 둘째 후보가 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.append(path, "둘째 후보")
    ledger.mark_explored(path, "첫 후보")

    candidate = ledger.next_unexplored(path)

    assert candidate is not None
    assert candidate.claim == "둘째 후보"


def test_next_unexplored_returns_none_when_exhausted(tmp_path: Path) -> None:
    """
    목적: 재고가 떨어진 상태를 「없음」으로 알리는 계약을 고정한다.

    이 신호를 받으면 회차는 수집 대신 **탐색으로 전환**한다. 예외로 올리면 그 전환이
    「실패 처리」와 섞인다.

    Given: 모든 후보를 판 원장
    When: 다음에 팔 후보를 묻는다
    Then: None 이 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.mark_explored(path, "첫 후보")

    assert ledger.next_unexplored(path) is None


def test_next_unexplored_can_be_told_to_pass_over_a_candidate(tmp_path: Path) -> None:
    """
    목적: 부르는 쪽이 「이번엔 이 후보 말고」를 말할 수 있는 계약을 고정한다.

    수집은 출처를 못 갖춘 후보를 **원장에 표시하지 않고** 미룬다 — 기각도 막힘도 그
    상황의 뜻이 아니기 때문이다. 표시가 없으니 그 후보는 여전히 첫 번째이고,
    건너뛸 길이 없으면 **같은 후보를 영원히 다시 꺼낸다.**

    Given: 후보가 둘 든 원장
    When: 첫 후보를 건너뛰라고 말하며 묻는다
    Then: 둘째 후보가 돌아오고, 원장의 표시는 «하나도» 바뀌지 않는다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.append(path, "둘째 후보")

    candidate = ledger.next_unexplored(path, skip={"첫 후보"})

    assert candidate is not None
    assert candidate.claim == "둘째 후보"
    assert ledger.status_of(path, "첫 후보") is ledger.Status.UNEXPLORED


def test_next_unexplored_passes_over_by_the_canonical_claim(tmp_path: Path) -> None:
    """
    목적: 건너뛸 후보를 «정규 형태»로 맞춰 보는 계약을 고정한다.

    [중요] 원장은 사람이 손으로 고치는 파일이고 한 줄 주장은 에이전트가 낸 값이다.
    앞뒤 공백이나 앞머리 백틱 하나로 같은 후보가 다르게 보이면, 건너뛰라고 말해도
    **에러 없이 그냥 안 건너뛰어진다** — 그 고장은 무한 반복으로만 드러난다.

    Given: 후보가 둘 든 원장
    When: 앞뒤 공백이 붙은 주장으로 건너뛰라고 말한다
    Then: 그래도 건너뛰어진다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.append(path, "둘째 후보")

    candidate = ledger.next_unexplored(path, skip={"  첫 후보  "})

    assert candidate is not None
    assert candidate.claim == "둘째 후보"


def test_next_unexplored_passes_over_a_row_that_carries_a_backtick(tmp_path: Path) -> None:
    """
    목적: [중요] 원장 «쪽»에 백틱이 붙어 있어도 지나쳐지는 계약을 고정한다.

    원장을 읽는 쪽은 앞뒤 공백만 떼고, 정규 형태는 앞머리 백틱까지 뗀다. 한쪽만
    정규화하면 백틱이 붙은 줄에서 비교가 어긋나는데, 그 고장은 예외가 아니라
    **지나치라고 말한 후보를 그대로 다시 집는** 모양으로 나타난다 — 사람이 손으로
    고치는 파일이라 이런 줄이 실제로 들어온다.

    Given: 앞머리에 백틱이 붙은 줄이 든 원장
    When: 그 후보를 지나치라고 말한다
    Then: 다음 후보가 돌아온다
    """
    path = tmp_path / "원장.md"
    path.write_text(
        "- [ ] `Halloween` 11월 첫 거래일에 사서 4월 말에 판다\n- [ ] 둘째 후보\n",
        encoding="utf-8",
    )
    first = ledger.load(path)[0]

    candidate = ledger.next_unexplored(path, skip={first.claim})

    assert candidate is not None
    assert candidate.claim == "둘째 후보"


def test_next_unexplored_without_skip_behaves_as_before(tmp_path: Path) -> None:
    """
    목적: 건너뛸 후보를 «안 넘기는» 기존 호출이 그대로인 계약을 고정한다.

    이 함수의 호출처는 수집 말고도 둘 더 있다(회차가 재고를 묻는 자리 · 막힌 후보를
    되짚는 자리). 기본값이 없으면 그 자리들이 조용히 달라진다.

    Given: 후보가 둘 든 원장
    When: 건너뛸 후보 없이 묻는다
    Then: 먼저 담긴 것이 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.append(path, "둘째 후보")

    candidate = ledger.next_unexplored(path)

    assert candidate is not None
    assert candidate.claim == "첫 후보"


def test_marking_unknown_candidate_is_rejected(tmp_path: Path) -> None:
    """
    목적: 원장에 없는 후보를 표시하려는 시도가 «조용히» 넘어가지 않는 계약을 고정한다.

    표시가 조용히 무시되면 그 후보는 영원히 「안 판 것」으로 남아 회차마다 다시 팔린다.

    Given: 그 후보가 없는 원장
    When: 판 것으로 표시한다
    Then: 예외가 오른다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    with pytest.raises(ledger.UnknownCandidateError):
        ledger.mark_explored(path, "원장에 없는 후보")


def test_append_to_a_file_without_trailing_newline(tmp_path: Path) -> None:
    """
    목적: 마지막 줄에 개행이 없는 원장에 덧붙여도 줄이 «붙지 않는» 계약을 고정한다.

    이 파일은 사람이 손으로 고치라고 만든 것이고, 많은 편집기가 마지막 개행 없이 저장한다.
    그대로 덧붙이면 사람이 적은 후보와 새 후보가 **한 줄로 붙어** 사람의 후보는 망가지고
    새 후보는 통째로 사라진다. 예외도 안 나고 `append` 는 True 를 돌려준다.

    Given: 개행 없이 끝나는 원장
    When: 후보를 담는다
    Then: 두 후보가 각각 읽힌다
    """
    path = tmp_path / "원장.md"
    path.write_text("# 원장\n\n- [ ] 사람이 손으로 적은 후보", encoding="utf-8")

    ledger.append(path, "새 후보")

    assert [entry.claim for entry in ledger.load(path)] == ["사람이 손으로 적은 후보", "새 후보"]


# --------------------------------------------------------------------------
# 짧은 식별자
#
# 한 줄 주장이 통째로 폴더명이 되면 120바이트에서 잘리고, 잘린 자리가 문장 중간이라
# **무슨 후보인지 이름만으로 안 드러난다.** 주장은 파일 «안»에 이미 있으므로 폴더명이
# 그것을 반복할 이유가 없다.
# --------------------------------------------------------------------------


def test_identifier_round_trips(tmp_path: Path) -> None:
    """
    목적: 후보의 짧은 식별자가 원장에 남고 다시 읽히는 계약을 고정한다.

    Given: 식별자와 함께 담은 후보
    When: 읽는다
    Then: 식별자가 그대로 돌아온다
    """
    path = tmp_path / "원장.md"

    ledger.append(path, "분기 실적이 컨센서스를 10% 이상 상회한 종목을 산다", identifier="pead-us")

    assert ledger.load(path)[0].identifier == "pead-us"


def test_entry_without_an_identifier_is_still_read(tmp_path: Path) -> None:
    """
    목적: 식별자가 «없는» 예전 줄을 계속 읽는 계약을 고정한다.

    원장은 **중복 방지의 전부**라, 못 읽는 줄이 생기면 그 후보를 회차마다 다시 판다.
    사람이 손으로 넣을 때 식별자를 빼먹는 것도 정상 입력이다.

    Given: 식별자 없이 적힌 예전 형식의 줄
    When: 읽는다
    Then: 주장이 읽히고 식별자는 없음으로 나온다
    """
    path = tmp_path / "원장.md"
    path.write_text("- [ ] 식별자 없는 예전 후보\n", encoding="utf-8")

    entry = ledger.load(path)[0]

    assert entry.claim == "식별자 없는 예전 후보"
    assert entry.identifier is None


def test_duplicate_identifier_gets_a_different_one(tmp_path: Path) -> None:
    """
    목적: 식별자가 겹치지 않는 계약을 고정한다.

    식별자가 곧 산출물 폴더명이다. 겹치면 **두 후보의 근거가 한 폴더에 섞여 덮어쓰인다** —
    앞 후보는 이미 「판 것」으로 표시돼 다시 파이지도 않으므로 근거가 영영 사라진다.

    Given: 같은 식별자를 쓰려는 두 후보
    When: 둘 다 담는다
    Then: 식별자가 서로 다르다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보", identifier="pead")
    ledger.append(path, "둘째 후보", identifier="pead")

    identifiers = [entry.identifier for entry in ledger.load(path)]

    assert identifiers[0] != identifiers[1]
    assert all(identifiers)


def test_identifier_can_be_filled_in_later(tmp_path: Path) -> None:
    """
    목적: 예전 줄에 식별자를 «나중에» 박는 계약을 고정한다.

    이미 쌓인 후보도 짧은 폴더명을 갖게 하는 경로다. 수집이 그 후보를 꺼낼 때
    에이전트가 식별자를 함께 내므로 **별도 호출이 들지 않는다.**

    [중요] 통째로 다시 쓰지 않고 그 줄만 바꾼다 — 사람이 적어 둔 메모가 사라지면 안 된다.

    Given: 식별자 없는 후보와 사람이 적은 메모가 든 원장
    When: 식별자를 박는다
    Then: 식별자가 붙고 메모는 그대로 남는다
    """
    path = tmp_path / "원장.md"
    path.write_text("- [ ] 예전 후보\n\n> 사람이 적은 메모\n", encoding="utf-8")

    assigned = ledger.assign_identifier(path, "예전 후보", "old-one")

    assert assigned == "old-one"
    assert ledger.load(path)[0].identifier == "old-one"
    assert "사람이 적은 메모" in path.read_text(encoding="utf-8")


def test_assigning_an_identifier_keeps_the_claim_unchanged(tmp_path: Path) -> None:
    """
    목적: 식별자를 박아도 한 줄 주장 문자열이 «안 바뀌는» 계약을 고정한다.

    중복 판정이 주장 문자열로 이뤄지므로, 한 글자라도 달라지면 같은 후보가
    다음 탐색에서 **새 후보로 다시 담긴다.**

    Given: 후보가 든 원장
    When: 식별자를 박는다
    Then: 주장이 그대로다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "주장은 그대로여야 한다")

    ledger.assign_identifier(path, "주장은 그대로여야 한다", "keep")

    assert ledger.load(path)[0].claim == "주장은 그대로여야 한다"


# --------------------------------------------------------------------------
# 기각
#
# 파라미터로 해명되지 않은 후보는 «실패»가 아니라 판정의 결과다. 그 회차는 멈추지 않고
# 다음 후보로 간다. 사유를 남기는 것은 **다음에 같은 후보를 또 파지 않게** 하려는 것이다.
# --------------------------------------------------------------------------


def test_rejected_candidate_is_not_dug_again(tmp_path: Path) -> None:
    """
    목적: 기각된 후보를 다시 꺼내지 않는 계약을 고정한다.

    Given: 후보 둘 중 첫째를 기각한 원장
    When: 다음에 팔 후보를 묻는다
    Then: 둘째가 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.append(path, "둘째 후보")

    ledger.mark_rejected(path, "첫 후보", "「옥석을 가려」의 판정 축을 못 냈다")

    candidate = ledger.next_unexplored(path)
    assert candidate is not None
    assert candidate.claim == "둘째 후보"


def test_rejection_reason_is_written_next_to_the_entry(tmp_path: Path) -> None:
    """
    목적: 기각 사유가 원장에 «사람이 읽을 수 있게» 남는 계약을 고정한다.

    「기각됨」만 남으면 다음에 같은 후보가 다시 나왔을 때 왜 버렸는지 알 수 없어
    **같은 것을 또 판다.**

    Given: 사유와 함께 기각한 후보
    When: 원장을 읽는다
    Then: 사유가 파일에 들어 있다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    ledger.mark_rejected(path, "첫 후보", "「저점」의 관측 시점을 못 냈다")

    assert "「저점」의 관측 시점을 못 냈다" in path.read_text(encoding="utf-8")


def test_rejection_reason_line_is_not_read_as_a_candidate(tmp_path: Path) -> None:
    """
    목적: 사유 줄이 «후보로» 읽히지 않는 계약을 고정한다.

    사유가 후보로 읽히면 그 문장을 다음 회차가 파러 간다. 형식으로 구별돼야 한다.

    Given: 사유와 함께 기각한 후보
    When: 원장을 읽는다
    Then: 후보는 하나뿐이다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    ledger.mark_rejected(path, "첫 후보", "축을 못 냈다")

    assert len(ledger.load(path)) == 1


def test_rejected_entry_keeps_blocking_duplicates(tmp_path: Path) -> None:
    """
    목적: 기각된 후보가 «중복 방지»로 계속 작동하는 계약을 고정한다.

    기각 줄이 중복 판정에서 빠지면 다음 탐색이 같은 후보를 새로 담고, 그 회차가
    다시 기각하며 호출을 태운다. **기각은 「본 적 없다」가 아니다.**

    Given: 기각된 후보
    When: 같은 주장을 다시 담으려 한다
    Then: 담기지 않는다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.mark_rejected(path, "첫 후보", "축을 못 냈다")

    assert ledger.append(path, "첫 후보") is False


def test_rejecting_an_unknown_candidate_is_rejected(tmp_path: Path) -> None:
    """
    목적: 원장에 없는 후보를 기각하려는 시도가 «조용히» 넘어가지 않는 계약을 고정한다.

    조용히 넘어가면 그 후보는 「안 판 것」으로 남아 회차마다 다시 팔리고, 매번 기각된다.

    Given: 그 후보가 없는 원장
    When: 기각한다
    Then: 예외가 오른다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    with pytest.raises(ledger.UnknownCandidateError):
        ledger.mark_rejected(path, "원장에 없는 후보", "사유")


def test_claim_that_looks_like_an_identifier_prefix_is_not_misread(tmp_path: Path) -> None:
    """
    목적: 한 줄 주장이 «식별자 자리처럼 생겼어도» 잘리지 않는 계약을 고정한다.

    [중요] 주장이 `` `abc` — `` 로 시작하면 그 줄을 다시 읽을 때 앞부분이 식별자로 읽히고
    주장은 잘린 채 돌아온다. 그러면 **중복 판정이 통째로 깨져** 같은 후보가 회차마다 새로
    담기고, 표시를 바꾸려는 호출은 「원장에 없는 후보」로 예외를 낸다. 그 예외는 「그 외」로
    분류돼 세 번 재시도되며, **재시도마다 중복 줄이 하나씩 더 쌓인다.**
    에러 메시지가 아니라 **조용한 중복**으로 나타나는 고장이다.

    Given: 백틱과 대시로 시작하는 한 줄 주장
    When: 담고 · 다시 담고 · 기각한다
    Then: 중복이 막히고 기각이 성공한다
    """
    path = tmp_path / "원장.md"
    tricky = "`spy` — 20일 이동평균을 상향 돌파하면 매수한다"

    assert ledger.append(path, tricky) is True
    assert ledger.append(path, tricky) is False

    ledger.mark_rejected(path, tricky, "사유")

    assert len(ledger.load(path)) == 1
    assert ledger.next_unexplored(path) is None


# --------------------------------------------------------------------------
# 막힘
#
# 기각과 «성질이 다르다». 기각은 「잴 수 없다」는 **판정의 결과**이고, 막힘은 그 후보를
# 두고 같은 단계가 회차마다 실패해 **더 해봐야 소용없다**고 접는 것이다.
# 원장 머리말이 `- [-]` 를 「잴 수 없다고 판정한 것」이라 명시하므로 거기 합치면
# 그 설명이 거짓이 된다. 상태로 갈라 두면 나중에 「막힌 것만 다시 풀자」를 골라낼 수 있다.
# --------------------------------------------------------------------------


def test_blocked_candidate_is_not_dug_again(tmp_path: Path) -> None:
    """
    목적: 막힌 후보를 다시 꺼내지 않는 계약을 고정한다.

    이것이 §10.1 E 의 본체다. 다시 꺼내면 다음 회차가 같은 자리에서 또 막히고,
    **탐색도 수집도 영영 다시 돌지 않은 채 회차마다 호출만 탄다.**

    Given: 후보 둘 중 첫째가 막힌 원장
    When: 다음에 팔 후보를 묻는다
    Then: 둘째가 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.append(path, "둘째 후보")

    ledger.mark_blocked(path, "첫 후보", "반증 단계가 세 회차 연속 막혔다")

    candidate = ledger.next_unexplored(path)
    assert candidate is not None
    assert candidate.claim == "둘째 후보"


def test_blocked_is_a_different_state_from_rejected(tmp_path: Path) -> None:
    """
    목적: 막힘과 기각이 «상태로» 갈리는 계약을 고정한다.

    사유 문자열의 접두사로만 구분하면 파싱이 부서지기 쉽고, 사람이 사유를 손으로
    고치는 순간 구분이 사라진다.

    Given: 하나는 기각 · 하나는 막힘인 원장
    When: 읽는다
    Then: 두 상태가 서로 다르다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "기각될 후보")
    ledger.append(path, "막힐 후보")

    ledger.mark_rejected(path, "기각될 후보", "축을 못 냈다")
    ledger.mark_blocked(path, "막힐 후보", "세 회차 연속 막혔다")

    status_of = {entry.claim: entry.status for entry in ledger.load(path)}
    assert status_of["기각될 후보"] is ledger.Status.REJECTED
    assert status_of["막힐 후보"] is ledger.Status.BLOCKED


def test_block_reason_is_written_next_to_the_entry(tmp_path: Path) -> None:
    """
    목적: 막힌 사유가 사람이 읽을 수 있게 남는 계약을 고정한다.

    「막혔다」만 남으면 사람이 그 후보를 다시 풀어야 할지 판단할 근거가 없다.

    Given: 사유와 함께 막은 후보
    When: 원장을 읽는다
    Then: 사유가 파일에 있고, 후보로는 읽히지 않는다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    ledger.mark_blocked(path, "첫 후보", "계보 단계가 세 회차 연속 막혔다")

    assert "계보 단계가 세 회차 연속 막혔다" in path.read_text(encoding="utf-8")
    assert len(ledger.load(path)) == 1


def test_blocked_entry_keeps_blocking_duplicates(tmp_path: Path) -> None:
    """
    목적: 막힌 후보가 «중복 방지»로 계속 작동하는 계약을 고정한다.

    빠지면 다음 탐색이 같은 후보를 새 후보로 담고, 그 회차가 또 같은 자리에서 막힌다 —
    막은 의미가 통째로 사라진다.

    Given: 막힌 후보
    When: 같은 주장을 다시 담으려 한다
    Then: 담기지 않는다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.mark_blocked(path, "첫 후보", "세 회차 연속 막혔다")

    assert ledger.append(path, "첫 후보") is False


def test_blocking_an_unknown_candidate_is_rejected(tmp_path: Path) -> None:
    """
    목적: 원장에 없는 후보를 막으려는 시도가 «조용히» 넘어가지 않는 계약을 고정한다.

    Given: 그 후보가 없는 원장
    When: 막는다
    Then: 예외가 오른다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    with pytest.raises(ledger.UnknownCandidateError):
        ledger.mark_blocked(path, "원장에 없는 후보", "사유")


def test_existing_marks_still_read_after_adding_blocked(tmp_path: Path) -> None:
    """
    목적: 상태를 넷으로 늘려도 **기존 세 표시가 그대로 읽히는** 계약을 고정한다 (회귀).

    [중요] 줄을 읽는 정규식의 문자 클래스를 넓히는 변경이다. 잘못 넓히면 `-` 가 범위로
    읽혀 기존 원장이 통째로 안 읽히고, 원장은 **중복 방지의 전부**라 그 순간
    모든 후보가 회차마다 다시 팔린다.

    Given: 네 표시가 모두 든 원장
    When: 읽는다
    Then: 넷이 각각 제 상태로 읽힌다
    """
    path = tmp_path / "원장.md"
    path.write_text(
        "- [ ] 안 판 후보\n"
        "- [x] 판 후보\n"
        "- [-] 기각된 후보\n"
        "      기각: 축을 못 냈다\n"
        "- [!] 막힌 후보\n"
        "      막힘: 세 회차 연속 막혔다\n",
        encoding="utf-8",
    )

    status_of = {entry.claim: entry.status for entry in ledger.load(path)}

    assert status_of == {
        "안 판 후보": ledger.Status.UNEXPLORED,
        "판 후보": ledger.Status.EXPLORED,
        "기각된 후보": ledger.Status.REJECTED,
        "막힌 후보": ledger.Status.BLOCKED,
    }


def test_disambiguated_identifier_stays_within_the_length_cap(tmp_path: Path) -> None:
    """
    목적: 겹침을 피해 붙인 꼬리가 «길이 한도에 잘려 사라지지 않는» 계약을 고정한다.

    [중요] 한도를 넘긴 식별자를 돌려주면 경로를 만들 때 다시 잘려 꼬리가 없어지고,
    **두 후보가 같은 폴더에 쓰인다.** 앞 후보는 이미 판 것으로 표시돼 다시 파이지도
    않으므로 그 근거는 영영 사라진다 — 겹침 회피가 막으려던 바로 그 결과다.

    Given: 한도 길이만큼 긴 같은 식별자를 쓰려는 두 후보
    When: 둘 다 담는다
    Then: 폴더 이름이 서로 다르다
    """
    path = tmp_path / "원장.md"
    longest = "a" * naming.MAX_IDENTIFIER_LENGTH
    ledger.append(path, "첫 후보", identifier=longest)
    ledger.append(path, "둘째 후보", identifier=longest)

    folders = [naming.folder_name(entry.claim, entry.identifier) for entry in ledger.load(path)]

    assert folders[0] != folders[1]
    assert all(len(folder) <= naming.MAX_IDENTIFIER_LENGTH for folder in folders)


def test_a_new_reason_replaces_the_old_one(tmp_path: Path) -> None:
    """
    목적: [중요] 사유 줄이 «쌓이지 않는» 계약을 고정한다.

    표시를 바꿀 때 예전 사유를 안 지우면 `- [!]` 아래에 「기각: ...」이 남는다.
    머리말이 「사유가 바로 아래 줄에 있습니다」라고 약속하는데 그 약속이 거짓이 되고,
    **나중에 원장을 읽는 사람이 지금 사유와 옛 사유를 구별할 방법이 없다.**

    Given: 기각했다가 다시 막은 후보
    When: 원장을 읽는다
    Then: 막힘 사유만 남고 기각 사유는 사라진다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.mark_rejected(path, "첫 후보", "축을 못 냈다")

    ledger.mark_blocked(path, "첫 후보", "세 회차 연속 막혔다")

    written = path.read_text(encoding="utf-8")
    assert "세 회차 연속 막혔다" in written
    assert "축을 못 냈다" not in written


def test_reviving_a_candidate_clears_its_reason(tmp_path: Path) -> None:
    """
    목적: 다시 판 후보 아래에 예전 사유가 «안 남는» 계약을 고정한다.

    Given: 막혔다가 사람이 되살려 끝까지 판 후보
    When: 판 것으로 표시한다
    Then: 막힘 사유가 사라진다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.mark_blocked(path, "첫 후보", "세 회차 연속 막혔다")

    ledger.mark_explored(path, "첫 후보")

    assert "막힘" not in path.read_text(encoding="utf-8")


def test_a_human_memo_under_an_entry_survives(tmp_path: Path) -> None:
    """
    목적: [중요] 사람이 후보 «바로 아래»에 적은 메모가 살아남는 계약을 고정한다.

    예전 사유를 지우는 규칙이 들여쓰기만 보면 사람의 메모까지 같이 지운다.
    이 파일은 사람도 고치라고 만든 것이고, 지워진 사실은 예외로 드러나지 않는다.
    그래서 **프로그램이 쓰는 접두사까지** 보고 지운다.

    Given: 후보 바로 아래에 사람이 들여 쓴 메모
    When: 그 후보를 기각한다
    Then: 메모가 그대로 남는다
    """
    path = tmp_path / "원장.md"
    path.write_text("- [ ] 첫 후보\n      사람이 적어 둔 메모\n", encoding="utf-8")

    ledger.mark_rejected(path, "첫 후보", "축을 못 냈다")

    assert "사람이 적어 둔 메모" in path.read_text(encoding="utf-8")


def test_status_of_finds_a_candidate(tmp_path: Path) -> None:
    """
    목적: 후보 하나의 «현재 표시»를 물어볼 수 있는 계약을 고정한다.

    이것이 필요한 곳은 회차의 마지막 단계다 — 그 회차의 후보가 **이미 판 것이면**
    실현가능성을 물을 자리가 아니다. 그 판정을 부르는 쪽에서 하면
    「담긴 순서 그대로의 목록」을 직접 훑게 되고, 그때 **정규화를 빠뜨리면 조용히 안 맞는다.**

    Given: 표시가 서로 다른 후보들
    When: 각각의 표시를 묻는다
    Then: 그 표시가 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "안 판 후보")
    ledger.append(path, "판 후보")
    ledger.mark_explored(path, "판 후보")

    assert ledger.status_of(path, "안 판 후보") is ledger.Status.UNEXPLORED
    assert ledger.status_of(path, "판 후보") is ledger.Status.EXPLORED


def test_status_of_normalizes_the_claim(tmp_path: Path) -> None:
    """
    목적: [중요] 물어볼 때도 «정규화»를 지나는 계약을 고정한다.

    담는 쪽은 `canonical_claim` 을 지나는데 묻는 쪽이 안 지나면, 앞뒤 공백이나
    앞머리 백틱 하나 때문에 **같은 후보가 다르게 보인다.** 계보 게이트가 URL 을
    정규화하지 않아 겪은 것과 같은 갈래이고, **에러 없이 매번 어긋난다.**

    Given: 담긴 후보
    When: 앞뒤에 공백을 붙여 묻는다
    Then: 같은 표시가 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")

    assert ledger.status_of(path, "  첫 후보  ") is ledger.Status.UNEXPLORED


def test_status_of_an_unknown_candidate_is_none(tmp_path: Path) -> None:
    """
    목적: 원장에 없는 후보를 물으면 «없음»이 돌아오는 계약을 고정한다.

    사람이 손으로 줄을 지울 수 있는 파일이라 「없다」는 정상 상태다.
    여기서 예외를 올리면 부르는 쪽마다 감싸야 하고, 빠뜨린 곳에서 회차가 선다.

    Given: 빈 원장
    When: 아무 후보를 묻는다
    Then: None 이 돌아온다
    """
    assert ledger.status_of(tmp_path / "없는원장.md", "아무 후보") is None

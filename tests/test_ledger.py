"""원장이 append-only 이고 같은 후보를 다시 담지 않는 계약을 고정한다.

원장은 「지금까지 본 후보」의 목록이고 **중복 방지의 전부**다. 없으면 같은 후보를 매일 다시
판다. 이 저장소가 만드는 누적 상태 중 하나인 이유는 「하루를 걸러도 그날 밤이 없었을 뿐
영구 손상이 아니기」 때문이다 — 완주율·점수 같은 집계와 갈리는 지점이 여기다.

[중요] 사람도 손으로 고치는 파일이다. 그래서 프로그램이 통째로 다시 쓰지 않는다 —
다시 쓰는 순간 사람이 적어 둔 메모가 사라지고, **사라진 줄도 모른다.**
"""

from pathlib import Path

import pytest

from research_lab.runner import ledger


def test_missing_ledger_reads_as_empty(tmp_path: Path) -> None:
    """
    목적: 원장이 아직 없는 첫 밤을 「빈 목록」으로 다루는 계약을 고정한다.

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

    탐색 밤은 한 번에 여러 줄을 담는다. 통째로 다시 쓰면 직전 밤이 담은 것이 사라지고,
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

    이 신호를 받으면 밤은 수집 대신 **탐색으로 전환**한다. 예외로 올리면 그 전환이
    「실패 처리」와 섞인다.

    Given: 모든 후보를 판 원장
    When: 다음에 팔 후보를 묻는다
    Then: None 이 돌아온다
    """
    path = tmp_path / "원장.md"
    ledger.append(path, "첫 후보")
    ledger.mark_explored(path, "첫 후보")

    assert ledger.next_unexplored(path) is None


def test_marking_unknown_candidate_is_rejected(tmp_path: Path) -> None:
    """
    목적: 원장에 없는 후보를 표시하려는 시도가 «조용히» 넘어가지 않는 계약을 고정한다.

    표시가 조용히 무시되면 그 후보는 영원히 「안 판 것」으로 남아 매일 밤 다시 팔린다.

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

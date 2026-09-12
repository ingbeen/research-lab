"""후보 이름에서 파일명을 만드는 계약을 고정한다.

에이전트가 낸 한 줄 주장이 그대로 경로가 된다. 사람이 고른 이름이 아니므로
공백·슬래시·따옴표·괄호가 섞이고, 대상 시장에 미국이 들어오면 영문과 하이픈도 섞인다.

[중요] 경로를 만드는 곳은 이 모듈 하나여야 한다. 변환이 두 곳에 생기면 한쪽만 바뀌어도
예외가 나지 않고 **「파일 없음」으로만** 뜬다 — 무엇이 어긋났는지가 드러나지 않는다.
"""

import pytest

from research_lab.runner import naming


def test_spaces_become_underscores() -> None:
    """
    목적: 파일명에 공백을 넣지 않는 계약을 고정한다.

    공백이 든 경로는 셸에서 따옴표를 빠뜨리는 순간 두 인자로 갈라진다.

    Given: 공백이 든 후보 이름
    When: 파일명을 만든다
    Then: 공백이 밑줄로 바뀐다
    """
    assert naming.slug("월말 진입") == "월말_진입"


def test_korean_is_preserved() -> None:
    """
    목적: 한글을 버리지 않는 계약을 고정한다.

    한글을 떨어뜨리면 이름이 통째로 비거나 알아볼 수 없게 된다 —
    산출물을 읽는 사람이 파일 목록에서 무엇이 무엇인지 가릴 수 없다.

    Given: 한글 후보 이름
    When: 파일명을 만든다
    Then: 한글이 그대로 남는다
    """
    assert "월말" in naming.slug("월말 진입")


def test_path_separators_are_removed() -> None:
    """
    목적: 경로 구분자가 «디렉터리를 만들지 못하게» 하는 계약을 고정한다.

    이름에 슬래시가 있으면 파일 하나가 아니라 폴더 구조가 생긴다.
    상위로 올라가는 형태면 산출물이 저장소 밖에 쓰인다.

    Given: 슬래시와 상위 참조가 든 이름
    When: 파일명을 만든다
    Then: 결과에 경로 구분자가 없다
    """
    made = naming.slug("../../etc/passwd 를 노리는 이름")

    assert "/" not in made
    assert "\\" not in made
    assert not made.startswith(".")


def test_quotes_and_brackets_are_removed() -> None:
    """
    목적: 따옴표와 괄호를 떨어뜨리는 계약을 고정한다.

    에이전트는 한 줄 주장을 따옴표로 감싸거나 괄호로 단서를 달아 내놓는다.

    Given: 따옴표와 괄호가 든 이름
    When: 파일명을 만든다
    Then: 그 문자들이 남지 않는다
    """
    made = naming.slug('"1월 효과" (소형주)')

    assert '"' not in made
    assert "(" not in made
    assert ")" not in made


def test_english_candidate_survives() -> None:
    """
    목적: 미국 후보의 영문 이름이 깨지지 않는 계약을 고정한다.

    대상 시장에 미국이 들어오므로 영문·하이픈이 섞인 이름이 정상 입력이다.

    Given: 영문과 하이픈이 든 후보 이름
    When: 파일명을 만든다
    Then: 알아볼 수 있는 형태로 남는다
    """
    made = naming.slug("Post-Earnings Announcement Drift")

    assert "Earnings" in made or "earnings" in made
    assert " " not in made


def test_consecutive_separators_collapse() -> None:
    """
    목적: 구분자가 연달아 붙지 않는 계약을 고정한다.

    문자를 떨어뜨리고 나면 밑줄이 여러 개 남는다. 읽기 어렵고, 같은 후보가
    표기 차이로 다른 파일명을 얻는다.

    Given: 떨어뜨릴 문자가 연달아 있는 이름
    When: 파일명을 만든다
    Then: 밑줄이 이어지지 않고 앞뒤에도 붙지 않는다
    """
    made = naming.slug("  월말   (진입)  ")

    assert "__" not in made
    assert made == made.strip("_")


def test_length_is_capped_in_bytes() -> None:
    """
    목적: 길이를 «바이트»로 재는 계약을 고정한다.

    파일시스템의 이름 한도는 문자 수가 아니라 바이트다. 한글은 UTF-8 에서 한 자가 3바이트라,
    글자 수로 자르면 한글 이름만 한도를 넘겨 **저장이 실패한다.**
    [주의] 자른 자리가 문자 중간이면 깨진 바이트가 남으므로 문자 경계에서 잘라야 한다.

    Given: 아주 긴 한글 후보 이름
    When: 파일명을 만든다
    Then: 바이트 길이가 한도 안이고, 다시 디코딩된다
    """
    made = naming.slug("월말" * 200)

    encoded = made.encode("utf-8")
    assert len(encoded) <= naming.MAX_SLUG_BYTES
    assert encoded.decode("utf-8") == made


def test_empty_result_is_rejected() -> None:
    """
    목적: 이름을 못 만들면 «조용히» 빈 파일명을 쓰지 않는 계약을 고정한다.

    남는 문자가 하나도 없는데 빈 문자열을 돌려주면 산출물이 확장자만 가진 파일로 저장되고,
    다음 후보가 그것을 덮어쓴다. 무엇이 사라졌는지 아무도 모른다.

    Given: 떨어뜨릴 문자만 든 이름
    When: 파일명을 만든다
    Then: 예외가 오른다
    """
    with pytest.raises(naming.UnusableNameError):
        naming.slug("///   ***   ")


def test_same_name_gives_same_slug() -> None:
    """
    목적: 변환이 결정적인 계약을 고정한다.

    같은 후보가 밤마다 다른 파일명을 얻으면 이어받기가 «이미 판 것»을 못 찾는다.

    Given: 같은 후보 이름
    When: 두 번 변환한다
    Then: 결과가 같다
    """
    assert naming.slug("월말 진입") == naming.slug("월말 진입")

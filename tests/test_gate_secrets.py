"""자격증명 스캔의 탐지와 «범위» 계약을 고정한다.

이 저장소는 PUBLIC 이고, 에이전트가 아무도 안 볼 때 회차마다 파일을 쓴다.
자매 저장소에는 없던 위험이라 규칙이 아니라 기계가 막는다.

[중요] 이 파일 자체에 탐지 패턴이 «리터럴»로 들어 있다. 그래서 범위 계약이 탐지 계약만큼
중요하다 — 스캔 범위를 저장소 전체로 잡으면 검사기가 **자기 테스트와 자기 계획서에 걸려**
회차마다 실패로 만든다. 그 고장은 진짜 유출과 구별되지 않는다.
"""

from pathlib import Path

from research_lab import common_constants
from research_lab.gate import secrets

# 실제 값이 아니라 «모양»만 가진 예시다. 탐지는 접두사로 이뤄지므로 뒤는 아무 문자열이어도 된다
API_KEY_SHAPED = "sk-ant-api03-0000000000000000000000"
OAUTH_TOKEN_SHAPED = "sk-ant-oat01-0000000000000000000000"
PRIVATE_KEY_HEADER = "-----BEGIN PRIVATE KEY-----"


def test_api_key_shape_is_detected(tmp_path: Path) -> None:
    """
    목적: API 키 모양을 잡아내는 계약을 고정한다.

    Given: API 키 모양이 든 산출물
    When: 스캔한다
    Then: 발견된다
    """
    (tmp_path / "찬성근거.json").write_text(f'{{"메모": "{API_KEY_SHAPED}"}}', encoding="utf-8")

    assert secrets.scan([tmp_path])


def test_oauth_token_shape_is_detected(tmp_path: Path) -> None:
    """
    목적: 무인 실행용 장기 토큰 모양을 잡아내는 계약을 고정한다.

    이 토큰이 컨테이너에 들어가는 «유일한» 자격증명이라, 새어 나갈 수 있는 것도 이것뿐이다.

    Given: 장기 토큰 모양이 든 로그
    When: 스캔한다
    Then: 발견된다
    """
    (tmp_path / "decisions.jsonl").write_text(f'{{"raw": "{OAUTH_TOKEN_SHAPED}"}}', encoding="utf-8")

    assert secrets.scan([tmp_path])


def test_private_key_header_is_detected(tmp_path: Path) -> None:
    """
    목적: 개인키 머리말을 잡아내는 계약을 고정한다.

    Given: 개인키 머리말이 든 파일
    When: 스캔한다
    Then: 발견된다
    """
    (tmp_path / "메모.txt").write_text(PRIVATE_KEY_HEADER, encoding="utf-8")

    assert secrets.scan([tmp_path])


def test_clean_output_yields_nothing(tmp_path: Path) -> None:
    """
    목적: 정상 산출물이 통과하는 계약을 고정한다.

    오탐이 잦으면 사람이 결과를 안 믿게 되고, 그러면 진짜 유출도 넘긴다.

    Given: 자격증명이 없는 산출물
    When: 스캔한다
    Then: 발견이 없다
    """
    (tmp_path / "찬성근거.json").write_text('{"url": "https://example.com/논문"}', encoding="utf-8")

    assert secrets.scan([tmp_path]) == []


def test_finding_names_the_file(tmp_path: Path) -> None:
    """
    목적: 발견이 «어느 파일»인지 알려주는 계약을 고정한다.

    무인 실행에서 나중에 보는 것은 이 기록뿐이다. 경로가 없으면 무엇을 지워야 하는지 모른다.

    Given: 자격증명이 든 파일
    When: 스캔한다
    Then: 발견에 그 경로가 들어 있다
    """
    leaked = tmp_path / "찬성근거.json"
    leaked.write_text(API_KEY_SHAPED, encoding="utf-8")

    assert secrets.scan([tmp_path])[0].path == leaked


def test_finding_does_not_carry_the_secret_value(tmp_path: Path) -> None:
    """
    목적: 발견 기록이 «또 하나의 유출»이 되지 않는 계약을 고정한다.

    발견을 로그에 남기는데 그 로그가 값을 담으면, 자격증명이 산출물에서 로그로 옮겨갈 뿐이다.
    그리고 그 로그는 PUBLIC 저장소에 있다.

    Given: 자격증명이 든 파일
    When: 스캔한다
    Then: 발견의 어떤 필드에도 값 자체가 들어 있지 않다
    """
    (tmp_path / "찬성근거.json").write_text(API_KEY_SHAPED, encoding="utf-8")

    finding = secrets.scan([tmp_path])[0]

    assert API_KEY_SHAPED not in repr(finding)


def test_unreadable_file_does_not_stop_the_scan(tmp_path: Path) -> None:
    """
    목적: 못 읽는 파일이 검사기를 죽이지 않는 계약을 고정한다.

    판정을 «못 하는 것»과 «실패로 판정하는 것»은 다르다. 검사기가 죽어서 파이프라인을
    멈추게 해서는 안 된다 — 읽을 수 있었던 나머지 파일까지 함께 검사를 못 받는다.

    Given: 텍스트가 아닌 파일과 자격증명이 든 파일이 함께 있는 폴더
    When: 스캔한다
    Then: 예외 없이 진행되고 자격증명은 발견된다
    """
    (tmp_path / "이미지.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\xfd")
    (tmp_path / "찬성근거.json").write_text(API_KEY_SHAPED, encoding="utf-8")

    assert len(secrets.scan([tmp_path])) == 1


def test_missing_root_is_not_an_error(tmp_path: Path) -> None:
    """
    목적: 아직 안 생긴 폴더를 「발견 없음」으로 다루는 계약을 고정한다.

    `dossier/` 는 첫 dossier 가 나오기 전까지 없다. 이걸 실패로 보면 첫 회차가 무조건 실패한다.

    Given: 존재하지 않는 경로
    When: 스캔한다
    Then: 발견이 없고 예외도 없다
    """
    assert secrets.scan([tmp_path / "아직없는폴더"]) == []


def test_scan_scope_excludes_the_repository_root() -> None:
    """
    목적: 스캔 범위가 «러너가 쓴 것»으로 한정되는 계약을 고정한다.

    저장소 전체를 훑으면 이 테스트 파일과 계획서의 리터럴에 걸려 **회차마다 실패한다.**
    그 고장은 진짜 유출과 구별되지 않으므로, 사람이 결과를 믿지 않게 된다.

    Given: 그 회차의 검사 범위
    When: 목록을 본다
    Then: 저장소 루트·문서·테스트가 들어 있지 않다
    """
    roots = set(secrets.scan_roots(common_constants.RUNS_DIR / "20260101_0100", ledger_dir=common_constants.LEDGER_DIR))

    assert common_constants.BASE_DIR not in roots
    assert common_constants.DOCS_DIR not in roots
    assert common_constants.BASE_DIR / "tests" not in roots
    assert common_constants.BASE_DIR / "src" not in roots


def test_scan_scope_covers_everything_the_cycle_writes() -> None:
    """
    목적: 범위를 좁히다가 «써야 할 곳»을 빠뜨리지 않는 계약을 고정한다.

    좁히기의 반대 실패다. 러너가 쓰는 곳이 범위 밖이면 검사기는 통과를 알리면서
    아무것도 안 본다 — 이쪽도 에러가 나지 않는다.

    Given: 그 회차의 실행 폴더와 그 회차가 쓴 근거 문서
    When: 검사 범위를 만든다
    Then: 셋이 모두 들어 있다
    """
    run_dir = common_constants.RUNS_DIR / "20260101_0100"
    written = common_constants.DOSSIER_DIR / "20260101_pead-us.md"
    roots = set(secrets.scan_roots(run_dir, ledger_dir=common_constants.LEDGER_DIR, dossier_path=written))

    assert run_dir in roots
    assert written in roots
    assert common_constants.LEDGER_DIR in roots
    # 범위는 언제나 «러너가 쓰는 곳» 안에 있다. 러너가 새 자리에 쓰기 시작하면
    # 그 자리를 이 목록에 더해야 하고, 안 더하면 여기가 먼저 걸린다
    assert all(any(root == base or base in root.parents for base in common_constants.WRITABLE_ROOTS) for root in roots)


def test_scan_scope_does_not_include_past_cycles() -> None:
    """
    목적: 지난 회차들의 실행 폴더가 범위에 «안» 들어가는 계약을 고정한다.

    `runs/` 를 통째로 넘기면 과거 어느 회차에 한 번 걸린 파일이 **이후 모든 회차를 영구히
    실패시킨다.** 아무도 그 파일을 치우지 않고, 회차마다 검사 대상이 누적돼 시간까지 늘어난다.

    Given: 그 회차의 검사 범위
    When: 목록을 본다
    Then: `runs/` 전체가 아니라 그 회차의 폴더 하나만 들어 있다
    """
    roots = set(secrets.scan_roots(common_constants.RUNS_DIR / "20260102_0100", ledger_dir=common_constants.LEDGER_DIR))

    assert common_constants.RUNS_DIR not in roots


def test_scan_scope_does_not_include_past_dossiers() -> None:
    """
    목적: [중요] 지난 회차의 «근거 문서»도 범위에 안 들어가는 계약을 고정한다.

    근거 문서는 회차마다 한 장씩 쌓인다 — `runs/` 와 정확히 같은 모양이다.
    폴더를 통째로 넘기면 **한 장이 한 번 걸린 뒤 이후 모든 회차가 종료 코드 4 로 끝나고,
    무인 실행에는 그것을 치울 사람이 없다.** 이 검사기는 «그 회차가 새로 쓴 것»을
    막으려는 것이지 과거를 청소하려는 것이 아니다.

    Given: 그 회차가 쓴 문서 하나를 넘긴 검사 범위
    When: 목록을 본다
    Then: 그 문서만 들어 있고 문서 폴더 전체는 안 들어 있다
    """
    roots = set(
        secrets.scan_roots(
            common_constants.RUNS_DIR / "20260102_0100",
            ledger_dir=common_constants.LEDGER_DIR,
            dossier_path=common_constants.DOSSIER_DIR / "20260102_pead-us.md",
        )
    )

    assert common_constants.DOSSIER_DIR not in roots


def test_a_cycle_without_a_dossier_still_has_a_scope() -> None:
    """
    목적: 근거 문서가 안 나온 회차도 «나머지»는 검사받는 계약을 고정한다.

    게이트에 막혀 끝난 회차는 문서를 안 남긴다. 그때 범위가 통째로 비면
    **그 회차가 실행 폴더에 쓴 것들이 검사를 안 받는다.**

    Given: 문서를 안 넘긴 검사 범위
    When: 목록을 본다
    Then: 실행 폴더와 원장은 그대로 들어 있다
    """
    run_dir = common_constants.RUNS_DIR / "20260103_0100"
    roots = set(secrets.scan_roots(run_dir, ledger_dir=common_constants.LEDGER_DIR))

    assert run_dir in roots
    assert common_constants.LEDGER_DIR in roots


def test_the_scope_follows_the_ledger_it_is_given(tmp_path: Path) -> None:
    """
    목적: [중요] 검사 범위의 원장 폴더가 «넘겨받은 원장의 폴더»인 계약을 고정한다.

    기본 원장 자리를 상수로 박으면 다른 원장을 쓴 회차는 **실제로 쓴 원장을 검사하지 않고**
    기본 원장을 검사한다 — 통과를 알리면서 아무것도 안 본 것이다.

    Given: 기본이 아닌 자리의 원장 폴더
    When: 검사 범위를 만든다
    Then: 그 폴더가 들어 있고 기본 원장 폴더는 없다
    """
    used = tmp_path / "다른원장"
    roots = set(secrets.scan_roots(common_constants.RUNS_DIR / "20260104_0100", ledger_dir=used))

    assert used in roots
    assert common_constants.LEDGER_DIR not in roots


def test_a_leftover_temporary_ledger_file_is_scanned(tmp_path: Path) -> None:
    """
    목적: [중요] 원장 폴더에 남은 «임시 파일»도 검사받는 계약을 고정한다.

    원장은 임시 파일에 쓰고 바꿔 끼우는데, 강제 종료되면 그 임시 파일이 남아 그대로 커밋된다.
    원장 «파일»만 넘기면 그 파일이 검사에서 빠지고, **빠진 사실은 아무 소리도 내지 않는다.**

    Given: 원장 옆에 자격증명 모양이 든 임시 파일이 남은 원장 폴더
    When: 그 회차의 범위를 스캔한다
    Then: 임시 파일에서 발견된다
    """
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    (ledger_dir / "원장.md").write_text("- [ ] 멀쩡한 후보\n", encoding="utf-8")
    (ledger_dir / "원장.md.tmp").write_text(f"- [ ] {OAUTH_TOKEN_SHAPED}\n", encoding="utf-8")

    findings = secrets.scan(secrets.scan_roots(tmp_path / "run", ledger_dir=ledger_dir))

    assert [finding.path.name for finding in findings] == ["원장.md.tmp"]

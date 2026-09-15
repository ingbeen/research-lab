"""단계 산출물을 근거 문서 한 장으로 조립한다 — **이 파이프라인의 제품이다.**

이 문서는 저장소 «밖»으로 나간다. 어느 프로젝트에든, 아직 없는 신규 프로젝트에든
그대로 넘어간다. 그래서 제약이 하나이고 그것이 다른 모든 것보다 앞선다.

> **다른 문서를 한 장도 열지 않고 판단할 수 있어야 한다.**

포인터를 쓰면 링크가 깨지는 것이 아니라 **판단이 불가능해진다.** 옮겨간 자리에는
그 저장소도, 그 문서도, 그 번호도 없기 때문이다. 그래서 이 모듈이 만드는 고정 문구에는
저장소 이름 · 폴더 경로 · 문서 파일명 · 번호로 된 참조가 **하나도 없다.**
**그래서 문서가 길어진다. 의도한 것이다.**

[중요] **조립은 러너가 한다.** 에이전트에게 「전부 모아 마크다운으로 내라」고 시키면
앞 단계의 값을 옮겨 적다 틀리고, **그 고장은 에러를 내지 않는다.**

[중요] 에이전트가 «쓴 문장» 안의 포인터는 **여기서 보지 않는다.** 판정은 `runner/prose_check`
가 **단계마다** 한다 — 조립은 회차의 마지막 단계라, 여기서 막으면 이미 굳은 앞 단계
산출물을 두고 실패하고 **다음 회차도 같은 자리에서 똑같이 실패한다**([실측 2026-09-15]).
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Final

from research_lab.common_constants import (
    DOSSIER_DIR,
    DOSSIER_NAME_FORMAT,
    FEASIBILITY_FILENAME,
    KST,
    LINEAGE_FILENAME,
    MEASUREMENT_FILENAME,
    MECHANISM_FILENAME,
    PRO_EVIDENCE_FILENAME,
    REBUTTAL_FILENAME,
    RUN_DIR_DATE_LENGTH,
)
from research_lab.gate import measurement as measurement_gate
from research_lab.gate import mechanism as mechanism_gate
from research_lab.gate import verdict as verdict_gate
from research_lab.runner import naming, outputs, state
from research_lab.runner import payload as payload_helpers
from research_lab.runner.atomic import atomic_write
from research_lab.runner.steps import StepQualityFailed

# 조립에 반드시 있어야 하는 산출물. 괄호 안은 사유에 실을 사람이 읽는 이름이다.
#
# [중요] 하나라도 없으면 막는다. 「한 칸이라도 비면 미완성」이 이 산출물의 규정이고,
# 다른 모듈의 「읽기 실패 시 빈 값」 관용을 여기서 쓰면 **칸이 빈 문서가 완성본으로 나간다.**
# 그 관용은 «빈 것이 정상 결과일 수 있는 자리»의 것이다
REQUIRED_OUTPUTS: Final = (
    (PRO_EVIDENCE_FILENAME, "찬성 근거"),
    (REBUTTAL_FILENAME, "반증"),
    (LINEAGE_FILENAME, "출처 계보"),
    (FEASIBILITY_FILENAME, "데이터·집행"),
    (MECHANISM_FILENAME, "우위와 소멸"),
    (MEASUREMENT_FILENAME, "측정 설계"),
)

# 문서의 머리말. **여기 있는 것이 「이 문서를 얼마나 믿을까」의 재료**다.
#
# [중요] 밖에서는 이 파이프라인을 열 수 없으므로, 어떻게 만들어졌는지가 문서 «안»에
# 있어야 한다. 특히 마지막 둘은 **없는 것을 없다고 밝히는** 자리다 — 안 적으면
# 읽는 사람이 「비용을 빼먹었다」·「성적을 재고도 안 적었다」로 오해한다
HEADER: Final = """# {claim}

> **근거 문서** · 식별자 `{identifier}` · 작성 {date}
>
> 이 문서는 **다른 문서를 한 장도 열지 않고 판단할 수 있게** 쓰였습니다.
>
> **어떻게 만들어졌나**
>
> - 찬성 근거와 반증을 **서로 다른 세션**이 모았습니다. 반증을 모은 쪽은 찬성 근거가
>   무엇인지 모르는 채 「이 주장을 깨라」만 받았습니다 — 한 자리에서 둘 다 시키면
>   방금 지지한 것을 스스로 무너뜨리라는 요구가 되어 잘 되지 않습니다.
> - 아래에 적힌 URL 은 **실제로 호출해** 살아 있는지 확인했습니다. 다만 자동 접근을 막는
>   사이트와 이름이 해석되지 않는 주소는 확인할 수 없으므로, **그런 주소는 맨 끝의 미검증
>   목록에 따로 적어 두었습니다** — 거기 없는 주소는 확인된 것입니다.
> - **수수료 · 세금 · 슬리피지를 일부러 담지 않았습니다.** 증권사 · 계좌 · 이벤트에 따라
>   자릿수가 달라지고 그 폭이 기대값과 같은 크기라, 값을 하나 고르면 **그 값이 판정을
>   대신합니다.** 재는 쪽이 자기 조건으로 넣어야 합니다.
> - **수익률을 재지 않았습니다.** 이 문서는 「재 볼 가치가 있는가」의 근거이지 측정 결과가 아닙니다.
"""

EVIDENCE_TABLE_HEAD: Final = "| 제목 | 발행일 | 1차/2차 | 무엇을 말하나 | 주소 |\n| --- | --- | --- | --- | --- |"

EMPTY_SLOT: Final = "(적히지 않았습니다)"

# 실재를 확인하지 못한 주소를 11번 칸에 적는 문구.
#
# [중요] **한 줄 안에서 뜻이 닫혀야 한다.** 이 문서는 이 파이프라인을 열 수 없는 곳에서
# 읽히므로 「게이트에서 unknown 으로 판정됨」처럼 적으면 받는 사람에게 아무 뜻이 없다.
# 그리고 **「내용이 틀렸다」가 아니라 「확인이 안 됐다」**임을 그 자리에서 밝힌다 —
# 학술지·정부·언론 사이트가 자동 접근을 막는 것은 흔한 일이고, 두 표본 연속 21% 가 그랬다
UNJUDGED_URL_NOTE: Final = "자동 접근이 막히거나 주소가 해석되지 않아, 이 주소가 실제로 열리는지 확인하지 못했습니다: {url}"


def path_for(run_dir: Path, candidate: state.Candidate, *, dossier_dir: Path = DOSSIER_DIR) -> Path:
    """그 회차가 쓸 근거 문서의 경로를 정한다.

    [중요] 날짜를 «그 실행 폴더»에서 뽑는다. 회차는 날을 넘겨 이어받을 수 있고,
    「오늘」로 만들면 **이어받은 회차가 같은 후보의 문서를 두 장 만든다** —
    그때 어느 것이 완성본인지 읽는 사람이 판별해야 한다.

    Args:
        run_dir: 그 회차의 실행 폴더
        candidate: 그 회차의 후보
        dossier_dir: 문서를 쌓을 폴더. 기본값은 이 저장소의 자리이고,
            **인자로 받는 이유는 원장·카탈로그와 같다** — 상수를 코드에 박으면
            부르는 쪽이 어디에 쓰이는지 고를 수 없고, 시험 삼아 돌린 실행이
            **진짜 산출물 폴더에 문서를 남긴다**

    Returns:
        문서 경로. 폴더 이름이 형식에 안 맞으면 오늘 날짜를 쓴다
    """
    name = naming.folder_name(candidate.claim, candidate.identifier)
    return dossier_dir / DOSSIER_NAME_FORMAT.format(date=_run_date(run_dir), identifier=name)


def _run_date(run_dir: Path) -> str:
    """그 실행 폴더의 날짜(`YYYYMMDD`). 폴더 이름이 형식에 안 맞으면 오늘.

    **파일명과 문서 머리말이 같은 값을 쓰게 하려고 한 곳에 둔다** — 두 곳에서 따로 뽑으면
    날을 넘긴 회차에서 둘이 하루 어긋나고, 그 어긋남은 에러를 내지 않는다.
    """
    head = run_dir.name[:RUN_DIR_DATE_LENGTH]
    if len(head) == RUN_DIR_DATE_LENGTH and head.isdigit():
        return head
    return datetime.now(KST).strftime("%Y%m%d")


def load_required(output_dir: Path) -> dict[str, dict[str, Any]]:
    """조립에 필요한 산출물을 «전부» 읽는다. 하나라도 없으면 막는다.

    [중요] 판정 단계가 **에이전트를 부르기 전에** 이것을 먼저 부른다. 어차피 조립에서
    막힐 회차라면 호출을 사는 것이 순 낭비다 — 값싼 검사를 먼저 돌리는 것과 같은 이유다.

    Args:
        output_dir: 그 회차의 후보 폴더

    Returns:
        파일명으로 찾을 수 있는 산출물들

    Raises:
        StepQualityFailed: 하나라도 없거나 읽히지 않을 때
    """
    loaded: dict[str, dict[str, Any]] = {}
    for filename, label in REQUIRED_OUTPUTS:
        found = outputs.read(output_dir, filename)
        if found is None:
            raise StepQualityFailed(f"근거 문서를 조립할 수 없습니다 — 「{label}」 산출물이 없거나 읽히지 않습니다: {output_dir / filename}")
        loaded[filename] = found
    return loaded


def assemble(
    run_dir: Path,
    candidate: state.Candidate,
    decision: dict[str, Any],
    *,
    dossier_dir: Path = DOSSIER_DIR,
    unverified_urls: list[str] | None = None,
) -> Path:
    """단계 산출물을 읽어 11칸짜리 근거 문서를 쓴다.

    Args:
        run_dir: 그 회차의 실행 폴더
        candidate: 그 회차의 후보
        decision: 판정 단계가 낸 산출물
        dossier_dir: 문서를 쌓을 폴더
        unverified_urls: 실재를 확인하지 «못한» 주소들. **인자로 받는다** —
            이 모듈이 결정 로그를 직접 읽으면 조립부의 입력이 인자에 다 드러나지 않고,
            에이전트가 낸 미검증과 한 덩어리가 되어 **나중에 「사람이 밝힌 것」과
            「기계가 못 판정한 것」을 가를 수 없다**.
            [주의] 목록이어야 한다 — 문자열 하나를 넘기면 파이썬에서는 순회가 «글자 단위»로
            되어 **예외 없이** 주소 한 건이 글자 수만큼의 줄로 불어난다

    Returns:
        쓴 문서의 경로

    Raises:
        StepQualityFailed: 앞 단계의 산출물이 하나라도 없거나 읽히지 않을 때
    """
    output_dir = run_dir / naming.folder_name(candidate.claim, candidate.identifier)
    document = _render(run_dir, candidate, decision, load_required(output_dir), unverified_urls)

    path = path_for(run_dir, candidate, dossier_dir=dossier_dir)
    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 문서가 남는다
    with atomic_write(path) as file:
        file.write(document)
    return path


def _render(
    run_dir: Path,
    candidate: state.Candidate,
    decision: dict[str, Any],
    loaded: dict[str, dict[str, Any]],
    unverified_urls: list[str] | None,
) -> str:
    """11칸을 «문서 순서»로 펼친다 — 결론 먼저, 근거 뒤.

    나중에 읽는 사람이 위 다섯 칸만 보고 판단할 수 있어야 하고, 아래 여섯 칸은
    그 판단을 의심할 때 내려가는 자리다. **채우는 순서와 읽는 순서는 다르다.**
    """
    evidence = loaded[PRO_EVIDENCE_FILENAME]
    rebuttal = loaded[REBUTTAL_FILENAME]
    lineage = loaded[LINEAGE_FILENAME]
    feasible = loaded[FEASIBILITY_FILENAME]
    mechanism = loaded[MECHANISM_FILENAME]
    plan = loaded[MEASUREMENT_FILENAME]

    # [중요] 머리말의 날짜를 파일명과 «같은 자리»에서 뽑는다. `datetime.now()` 를 쓰면
    # 날을 넘겨 이어받은 회차에서 **파일명과 문서 안의 날짜가 하루 어긋나고**, 읽는 사람은
    # 어느 쪽이 그 회차의 날짜인지 알 길이 없다. 같은 회차를 다시 조립하면 본문도 달라진다
    stamped = _run_date(run_dir)

    sections = [
        HEADER.format(
            claim=candidate.claim,
            identifier=naming.folder_name(candidate.claim, candidate.identifier),
            date=f"{stamped[:4]}-{stamped[4:6]}-{stamped[6:]}",
        ),
        f"## 1. 한 줄 주장\n\n{candidate.claim}",
        _verdict_section(decision),
        _named_slots("## 3. 왜 우위가 있을 수 있나", mechanism.get(mechanism_gate.KEY_EDGE), mechanism_gate.EDGE_FIELDS),
        _feasibility_section("## 4. 데이터 실현가능성", feasible.get("data"), _DATA_FIELDS, feasible),
        _feasibility_section("## 5. 집행 현실성", feasible.get("execution"), _EXECUTION_FIELDS, None),
        _lineage_section(lineage),
        _evidence_section("## 7. 찬성 근거", payload_helpers.as_list(evidence.get("evidence")), None),
        _evidence_section(
            "## 8. 반증",
            payload_helpers.as_list(rebuttal.get("rebuttals")),
            payload_helpers.as_text(rebuttal.get("not_found_reason")),
        ),
        _named_slots("## 9. 왜 사라졌을 수 있나", mechanism.get(mechanism_gate.KEY_DECAY), mechanism_gate.DECAY_FIELDS),
        _measurement_section(plan),
        _unverified_section(decision, loaded, unverified_urls),
    ]

    # [중요] 자립성은 여기서 «보지 않는다». 조립은 회차의 마지막 단계라, 여기서 막으면
    # **이미 굳은 앞 단계 산출물**을 두고 실패한다 — 다음 회차는 마지막 단계만 다시 돌고
    # 그 산출물은 그대로이므로 같은 자리에서 똑같이 실패하고, 세 번이면 후보가 걷힌다.
    # 판정은 `runner/prose_check` 가 **단계마다** 한다 ([실측 2026-09-15])
    return "\n\n".join(sections).rstrip() + "\n"


# 4번 칸에서 펼칠 자리. 게이트의 목록을 그대로 쓰지 않는 이유는 **읽는 사람이 볼 제목**과
# **에이전트에게 물을 문구**가 다르기 때문이다 — 물을 때는 「안 적으면 생기는 일」이 붙어야
# 하지만, 읽을 때 그것이 붙어 있으면 문서가 지시서처럼 읽힌다
_DATA_FIELDS: Final = (
    ("needs", "필요한 데이터"),
    ("availability", "받을 수 있나"),
    ("how_to_get", "어떻게 받나"),
    ("point_in_time", "그 시점에 실제로 알 수 있었나"),
    ("survivorship", "상장폐지·합병 종목이 빠지지 않나"),
    ("fallback", "막히면 무엇으로"),
)

_EXECUTION_FIELDS: Final = (
    ("instrument", "살 수 있는 상품이 있나"),
    ("signal_frequency", "신호가 얼마나 자주 오나"),
    ("leverage", "배수를 걸 수 있나"),
    ("waking_hours", "사람이 깨어 있는 시간에 집행 가능한가"),
    ("intraday_precision", "분·초 단위 집행이 필요한가"),
)

# 10번 칸에서 펼칠 자리. 위 `_DATA_FIELDS` 와 같은 이유로 게이트의 목록을 그대로 쓰지 않는다 —
# 제목이 읽는 사람의 것이고 순서도 문서의 흐름을 따른다.
#
# [중요] 그래서 **게이트에 자리를 더하면 여기도 더해야 한다.** 안 더하면 게이트도 스키마도
# 러너도 있다고 믿는 값이 **문서에서만 조용히 빠진다.** 그 어긋남은 계약 테스트가 잡는다
_MEASUREMENT_SLOTS: Final = (
    ("instrument", "대상 — 실제로 살 수 있는 상품"),
    ("no_lookahead", "미래 참조가 없음"),
    ("entry_grid", "진입 시점 격자"),
    ("holding_grid", "보유 기간 격자"),
    ("single_value_reason", "격자가 한 값뿐인 이유"),
    ("baseline", "기준선 — 무엇과 견주나"),
    ("direction", "방향"),
    ("expected_samples", "예상 표본 수"),
)


def _verdict_section(decision: dict[str, Any]) -> str:
    """2번 칸 — 판정과 «적용한 기준 자체».

    [중요] 기준을 이유와 나란히 적는다. 번호로 된 참조는 이 문서가 옮겨간 자리에서
    죽으므로, **기준의 내용이 여기 있어야** 「왜 이 판정인가」에 답이 된다.
    """
    lines = [
        "## 2. 판정",
        "",
        f"**{_text(decision.get(verdict_gate.KEY_VERDICT))}**",
        "",
        "**왜 그렇게 판정했나**",
        "",
        _text(decision.get(verdict_gate.KEY_REASON)),
        "",
        "**적용한 기준**",
        "",
        _text(decision.get(verdict_gate.KEY_CRITERIA)),
    ]
    return "\n".join(lines)


def _named_slots(heading: str, section: Any, fields: tuple[tuple[str, str], ...]) -> str:
    """이름 붙은 자리들을 소제목으로 펼친다 (3번 칸 · 9번 칸).

    자리 이름을 그대로 보이는 이유는 **무엇을 물었는지가 답만큼 중요하기** 때문이다.
    「해당 없음」이 적힌 자리도 그 자체가 읽는 사람에게 신호다.
    """
    lines = [heading, ""]
    for key, label in fields:
        short = label.split(" — ")[0]
        value = section.get(key) if isinstance(section, dict) else None
        lines.extend([f"**{short}**", "", _text(value), ""])
    return "\n".join(lines).rstrip()


def _feasibility_section(heading: str, section: Any, fields: tuple[tuple[str, str], ...], extra: Any) -> str:
    """4번 칸과 5번 칸 — 물은 자리를 하나씩 펼친다."""
    lines = [heading, ""]
    market = payload_helpers.as_text(extra.get("market")) if isinstance(extra, dict) else ""
    if market:
        lines.extend([f"**대상 시장**: {market}", ""])
    for key, label in fields:
        value = section.get(key) if isinstance(section, dict) else None
        lines.extend([f"**{label}**", "", _text(value), ""])
    return "\n".join(lines).rstrip()


def _lineage_section(lineage: dict[str, Any]) -> str:
    """6번 칸 — 「세 곳에서 확인」이 아니라 「한 원본 · 복제 두 곳」.

    복제를 뺀 수를 맨 앞에 둔다. 그 수가 이 칸에서 읽는 사람이 가장 먼저 찾는 값이다.
    """
    groups = payload_helpers.as_list(lineage.get("groups"))
    lines = [
        "## 6. 출처 계보",
        "",
        f"**복제를 뺀 독립 소스 수: {_text(lineage.get('independent_source_count'))}**",
        "",
        "여러 곳이 같은 말을 하는 가장 흔한 이유는 서로 베꼈기 때문입니다. 아래는 그것을 걷어낸 결과입니다.",
        "",
    ]

    if not groups:
        lines.append(EMPTY_SLOT)
        return "\n".join(lines)

    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            # [중요] 이 자리도 «펴서» 적는다. 모양이 어긋난 덩어리는 대개 목록으로 오는데,
            # 계보 게이트는 URL 이 하나도 없으면 그런 덩어리를 그냥 지나치므로
            # **여기까지 도달한다.** `str()` 로 찍으면 6번 칸에 파이썬 표기가 실린다
            lines.extend([f"### 덩어리 {index}", "", _text(group), ""])
            continue

        # [주의] 한 번 꺼내 두고 판정한다. `group.get(...)` 를 그때그때 부르면
        # 「dict 인지 본 값」과 「쓰는 값」이 서로 다른 호출이 되어 보장이 사라진다
        found: Any = group.get("origin")
        origin: dict[str, Any] = found if isinstance(found, dict) else {}
        lines.extend(
            [
                f"### 덩어리 {index} — 원본: {_text(origin.get('title'))}",
                "",
                f"- 원본: {_text(origin.get('title'))} · {_text(origin.get('published'))} · {_text(origin.get('url'))}",
            ]
        )
        # [중요] «적힌 줄 수»로 판정한다. 「목록이 비었나」로 보면 객체가 아닌 값만 든 목록에서
        # 복제 줄도 「없음」 줄도 안 나와, **복제가 있었는지 없었는지가 문서에서 사라진다** —
        # 이 칸에서 읽는 사람이 가장 먼저 찾는 것이 그 수다
        written = 0
        for copy in payload_helpers.as_list(group.get("copies")):
            label = _text(copy.get("title")) if isinstance(copy, dict) else _text(copy)
            url = _text(copy.get("url")) if isinstance(copy, dict) else "-"
            lines.append(f"- 복제: {label} · {url}")
            written += 1
        if not written:
            lines.append("- 복제: 없음 (혼자인 덩어리)")
        lines.extend(["", f"왜 한 덩어리인가: {_text(group.get('why'))}", ""])

    return "\n".join(lines).rstrip()


def _evidence_section(heading: str, items: list[Any], not_found_reason: str | None) -> str:
    """7번 칸과 8번 칸 — 출처를 표로 편다.

    [중요] 0건은 **정상 결과**다. 억지로 채우게 만들면 없는 출처를 지어내게 되고,
    그것이 이 문서에서 가장 나쁜 고장이다. 그래서 0건일 때는 «왜 없었는지»를 싣는다.
    """
    lines = [heading, ""]
    if not items:
        reason = (not_found_reason or "").strip()
        lines.append(f"**0건.** {reason}" if reason else "**0건.**")
        return "\n".join(lines)

    lines.append(EVIDENCE_TABLE_HEAD)
    for item in items:
        if not isinstance(item, dict):
            # [중요] 이 자리도 이스케이프를 탄다. 세로선이 든 문자열이 그대로 들어가면
            # **칸 수가 어긋나 그 아래 표가 통째로 깨지고, 에러는 나지 않는다**
            lines.append(f"| {_cell(item)} | - | - | - | - |")
            continue
        lines.append(
            "| {title} | {published} | {kind} | {says} | {url} |".format(
                title=_cell(item.get("title")),
                published=_cell(item.get("published")),
                kind=_cell(item.get("kind")),
                says=_cell(item.get("says")),
                url=_cell(item.get("url")),
            )
        )
    return "\n".join(lines)


def _measurement_section(plan: dict[str, Any]) -> str:
    """10번 칸 — 받는 쪽이 그대로 잴 수 있는 형태.

    [중요] 이 칸이 문서에 박히는 순간 **사전등록**이 따라온다 — 재기 전에 방법이 고정되므로
    결과를 보고 기준을 고치는 일이 막힌다. 그것이 이 칸을 길게 두는 이유다.
    """
    lines = ["## 10. 측정 설계 초안", ""]
    for key, label in _MEASUREMENT_SLOTS:
        value = plan.get(key)
        if key == measurement_gate.KEY_SINGLE_VALUE_REASON and not str(value or "").strip():
            # 격자가 여럿이면 이 자리는 물을 것이 없다. 빈 칸을 남기면 읽는 사람이
            # 「빠뜨린 것인가」를 매번 판별해야 한다
            continue
        lines.extend([f"**{label}**", "", _text(value), ""])
    return "\n".join(lines).rstrip()


def _unverified_section(
    decision: dict[str, Any], loaded: dict[str, dict[str, Any]], unverified_urls: list[str] | None
) -> str:
    """11번 칸 — 모든 단계의 미검증을 «러너가» 모은다.

    [중요] 에이전트에게 다시 옮겨 적게 하면 옮기다 빠뜨리고, 이 칸은 **비는 게 오히려
    의심스러운** 칸이라 빠져도 티가 안 난다.

    같은 문장이 여러 단계에서 나올 수 있으므로 중복은 접되, **처음 나온 순서를 지킨다** —
    정렬하면 어느 단계가 낸 것인지의 흐름이 사라진다.

    [중요] 실재를 확인하지 «못한» 주소를 **맨 뒤에 붙인다.** 앞의 것들은 조사가 닿지 못한
    자리이고 이것은 검사기가 판정을 못 한 자리라 성질이 다른데, 섞어 놓으면 읽는 사람이
    그 둘을 가를 수 없다. 그리고 **덮어쓰지 않는다** — 하나가 다른 하나를 밀어내면
    사라진 쪽은 아무 흔적도 남기지 않는다.
    """
    # [중요] `as_strings` 를 쓰지 않는다. 그것은 문자열이 아닌 항목을 «버리는데**,
    # 이 칸은 「비는 게 오히려 의심스러운」 자리라 조용히 사라지면 문서가 거짓말을 한다 —
    # 사전 모양으로 낸 미검증이 통째로 빠지면 「(비어 있습니다)」가 찍힌다.
    # 문서에 값을 싣는 자리는 전부 `_flatten` 을 지난다
    gathered: list[str] = []
    for found in loaded.values():
        gathered.extend(_readable(found.get("unverified")))
    gathered.extend(_readable(decision.get("unverified_extra")))
    gathered.extend(UNJUDGED_URL_NOTE.format(url=url) for url in payload_helpers.as_strings(unverified_urls))

    lines = [
        "## 11. 미검증 목록",
        "",
        "확인하지 못한 것입니다. **「반증됨」과 다릅니다** — 못 찾은 것과 아니라고 확인한 것은 다릅니다.",
        "",
    ]

    seen: set[str] = set()
    unique: list[str] = []
    for item in gathered:
        key = _fold_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    if not unique:
        # [주의] 이 칸이 비는 것은 **오히려 의심스럽다.** 한 회차 조사에서 모르는 게
        # 하나도 없을 수 없으므로, 비었다는 사실 자체를 읽는 사람에게 보인다
        lines.append("(비어 있습니다. 한 차례 조사에서 모르는 것이 하나도 없기는 어려우므로, 이 칸이 빈 것 자체를 의심해 보세요.)")
        return "\n".join(lines)

    lines.extend(f"- {item}" for item in unique)
    return "\n".join(lines)


def _readable(value: Any) -> list[str]:
    """미검증 목록을 «사람이 읽는 줄»들로 편다. 빈 항목은 뺀다."""
    return [line for item in payload_helpers.as_list(value) if (line := _flatten(item))]


def _fold_key(item: str) -> str:
    """중복 판정에 쓸 열쇠 — «표기 수준»에서 멈춘다.

    완전일치로만 접으면 앞뒤 공백 하나, 끝 마침표 하나 때문에 같은 공백이 여러 줄로
    실린다. 11번 칸은 **가장 꼼꼼히 읽히는 자리**인데 중복이 섞이면
    「열린 공백이 몇 개인가」가 읽히지 않는다.

    [중요] **뜻으로 접지 않는다.** 뜻을 비교하기 시작하면 이 조립부가 또 하나의 판단자가
    되고, 무엇보다 **서로 다른 공백 둘을 하나로 접는 쪽이 중복을 남기는 쪽보다 나쁘다** —
    사라진 쪽은 아무 흔적도 남기지 않는다. 그래서 같은 말을 다르게 쓴 두 줄은 둘 다 남는다.
    """
    # [중요] 대소문자를 «내리지 않는다». 이 칸에는 판정 못 한 URL 이 함께 실리는데
    # 경로는 대소문자를 가리는 서버가 있어, 내리면 `/Paper.pdf` 와 `/paper.pdf` 가
    # 한 줄로 접히고 **사라진 쪽은 아무 흔적도 남기지 않는다**
    return " ".join(item.split()).rstrip(" .·。")


def _flatten(value: Any) -> str:
    """값을 «사람이 읽는 한 줄»로 편다. 비었으면 빈 문자열이다.

    [중요] 목록을 `str()` 로 바로 찍지 않는다. 그러면 `['국내 ETF 일봉']` 처럼
    **파이썬 표기가 그대로 문서에 실린다** — 필요한 데이터도 격자도 목록으로 오므로
    이 문서에서 가장 자주 읽히는 자리들이 코드 조각처럼 보인다. 여기는 사람이 읽는
    산출물이고, 그 사람은 이 저장소를 열 수 없다.

    [중요] **문서에 값을 싣는 자리는 전부 이 함수를 지난다.** 한 자리만 `str()` 을 쓰면
    그 자리에서만 같은 고장이 나고, 나머지가 멀쩡하니 **테스트도 눈도 그 한 곳을 놓친다** —
    실제로 표를 만드는 쪽이 그렇게 빠져 있었다.

    **빈 값을 여기서 표기하지 않는** 이유는 부르는 쪽마다 그 표기가 다르기 때문이다 —
    절은 「적히지 않았습니다」, 표 한 칸은 `-`. 여기서 정하면 둘 중 하나가 틀린다.
    """
    # [중요] **한 겹만 펴면 안 된다.** 격자의 `items` 타입을 일부러 안 묶어 두었으므로
    # 날짜 «구간»이 목록의 목록으로, 데이터 목록이 사전의 목록으로 오는 것이 정상이다.
    # 한 겹만 펴면 그 안쪽이 `str()` 을 타서 **바로 이 함수가 막으려던 표기가 그대로 나온다**
    if isinstance(value, list | tuple):
        return " · ".join(flattened for flattened in (_flatten(item) for item in value) if flattened)

    if isinstance(value, dict):
        # [중요] 절도 «비어 있지 않은 값»이라 게이트를 통과한다. 그대로 찍으면
        # `{'kr': '원화 기준'}` 이 되어 목록과 똑같은 고장이 난다
        pairs = ((key, _flatten(item)) for key, item in value.items())
        return " · ".join(f"{key}: {flattened}" for key, flattened in pairs if flattened)

    return payload_helpers.as_text(value)


def _text(value: Any) -> str:
    """절 한 자리에 실을 문장으로 만든다. 비었으면 그 사실을 «보이게» 적는다."""
    return _flatten(value) or EMPTY_SLOT


def _cell(value: Any) -> str:
    """표 한 칸으로 만든다.

    [중요] 세로선을 이스케이프한다. 제목이나 인용문에 세로선이 섞이면 **표가 통째로
    깨지면서 에러는 나지 않는다** — 읽는 사람에게는 그냥 이상한 문서로 보인다.

    [중요] 펴기는 `_flatten` 이 한다. 여기서 `str()` 을 따로 쓰면 목록이 든 칸에서만
    파이썬 표기가 새고, **출처 표는 이 문서에서 가장 많이 읽히는 자리다.**

    빈 칸이 「적히지 않았습니다」가 아니라 `-` 인 것은 **표의 폭** 때문이다 —
    한 칸에 긴 문장이 들어가면 그 줄 전체가 읽기 어려워진다.
    """
    written = _flatten(value).replace("|", "\\|").replace("\n", " ")
    return written or "-"

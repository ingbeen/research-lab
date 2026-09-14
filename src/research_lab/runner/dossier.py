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

[중요] 에이전트가 «쓴 문장» 안의 포인터는 여기서 못 막는다 — 그것은 내용 판정이고,
판정하려 들면 또 하나의 판단자가 된다. 그 자리는 사람이 나중에 본다.
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
>   사이트와 이름이 해석되지 않는 주소는 「판정 못 함」으로 통과하므로 완전하지는 않습니다.
> - **수수료 · 세금 · 슬리피지를 일부러 담지 않았습니다.** 증권사 · 계좌 · 이벤트에 따라
>   자릿수가 달라지고 그 폭이 기대값과 같은 크기라, 값을 하나 고르면 **그 값이 판정을
>   대신합니다.** 재는 쪽이 자기 조건으로 넣어야 합니다.
> - **수익률을 재지 않았습니다.** 이 문서는 「재 볼 가치가 있는가」의 근거이지 측정 결과가 아닙니다.
"""

EVIDENCE_TABLE_HEAD: Final = "| 제목 | 발행일 | 1차/2차 | 무엇을 말하나 | 주소 |\n| --- | --- | --- | --- | --- |"

EMPTY_SLOT: Final = "(적히지 않았습니다)"


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
) -> Path:
    """단계 산출물을 읽어 11칸짜리 근거 문서를 쓴다.

    Args:
        run_dir: 그 회차의 실행 폴더
        candidate: 그 회차의 후보
        decision: 판정 단계가 낸 산출물
        dossier_dir: 문서를 쌓을 폴더

    Returns:
        쓴 문서의 경로

    Raises:
        StepQualityFailed: 앞 단계의 산출물이 하나라도 없거나 읽히지 않을 때
    """
    output_dir = run_dir / naming.folder_name(candidate.claim, candidate.identifier)
    document = _render(run_dir, candidate, decision, load_required(output_dir))

    path = path_for(run_dir, candidate, dossier_dir=dossier_dir)
    # 반쯤 쓰다 끊기면 완성본 자리에 잘린 문서가 남는다
    with atomic_write(path) as file:
        file.write(document)
    return path


def _render(
    run_dir: Path, candidate: state.Candidate, decision: dict[str, Any], loaded: dict[str, dict[str, Any]]
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
            _plain(rebuttal.get("not_found_reason")),
        ),
        _named_slots("## 9. 왜 사라졌을 수 있나", mechanism.get(mechanism_gate.KEY_DECAY), mechanism_gate.DECAY_FIELDS),
        _measurement_section(plan),
        _unverified_section(decision, loaded),
    ]
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
    market = _plain(extra.get("market")) if isinstance(extra, dict) else ""
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
            lines.extend([f"### 덩어리 {index}", "", str(group), ""])
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


def _unverified_section(decision: dict[str, Any], loaded: dict[str, dict[str, Any]]) -> str:
    """11번 칸 — 모든 단계의 미검증을 «러너가» 모은다.

    [중요] 에이전트에게 다시 옮겨 적게 하면 옮기다 빠뜨리고, 이 칸은 **비는 게 오히려
    의심스러운** 칸이라 빠져도 티가 안 난다.

    같은 문장이 여러 단계에서 나올 수 있으므로 중복은 접되, **처음 나온 순서를 지킨다** —
    정렬하면 어느 단계가 낸 것인지의 흐름이 사라진다.
    """
    gathered: list[str] = []
    for found in loaded.values():
        gathered.extend(payload_helpers.as_strings(found.get("unverified")))
    gathered.extend(payload_helpers.as_strings(decision.get("unverified_extra")))

    lines = [
        "## 11. 미검증 목록",
        "",
        "확인하지 못한 것입니다. **「반증됨」과 다릅니다** — 못 찾은 것과 아니라고 확인한 것은 다릅니다.",
        "",
    ]

    seen: set[str] = set()
    unique = [item for item in gathered if not (item in seen or seen.add(item))]

    if not unique:
        # [주의] 이 칸이 비는 것은 **오히려 의심스럽다.** 한 회차 조사에서 모르는 게
        # 하나도 없을 수 없으므로, 비었다는 사실 자체를 읽는 사람에게 보인다
        lines.append("(비어 있습니다. 한 차례 조사에서 모르는 것이 하나도 없기는 어려우므로, 이 칸이 빈 것 자체를 의심해 보세요.)")
        return "\n".join(lines)

    lines.extend(f"- {item}" for item in unique)
    return "\n".join(lines)


def _text(value: Any) -> str:
    """값을 문서에 실을 문장으로 만든다. 비었으면 그 사실을 «보이게» 적는다.

    [중요] 목록을 `str()` 로 바로 찍지 않는다. 그러면 `['국내 ETF 일봉']` 처럼
    **파이썬 표기가 그대로 문서에 실린다** — 필요한 데이터도 격자도 목록으로 오므로
    이 문서에서 가장 자주 읽히는 자리들이 코드 조각처럼 보인다. 여기는 사람이 읽는
    산출물이고, 그 사람은 이 저장소를 열 수 없다.
    """
    if isinstance(value, list | tuple):
        joined = " · ".join(_plain(item) for item in value if _plain(item))
        return joined or EMPTY_SLOT

    if isinstance(value, dict):
        # [중요] 절도 «비어 있지 않은 값»이라 게이트를 통과한다. 그대로 찍으면
        # `{'kr': '원화 기준'}` 이 되어 목록과 똑같은 고장이 난다
        joined = " · ".join(f"{key}: {_plain(item)}" for key, item in value.items() if _plain(item))
        return joined or EMPTY_SLOT

    return _plain(value) or EMPTY_SLOT


def _plain(value: Any) -> str:
    """값을 «사람이 읽는» 문자열로 만든다. 없으면 빈 문자열이다.

    [중요] `str()` 을 바로 쓰지 않는다. JSON 의 `null` 은 파이썬에서 `None` 이 되고
    `str(None)` 은 **`"None"` 이라는 «내용이 있는» 문자열**이 된다 — 비었는지 보는 검사를
    통과하고, 그대로 문서에 찍힌다. 「반증 0건」 옆에 사유랍시고 `None` 이 붙는 식이다.
    """
    return "" if value is None else str(value).strip()


def _cell(value: Any) -> str:
    """표 한 칸으로 만든다.

    [중요] 세로선을 이스케이프한다. 제목이나 인용문에 세로선이 섞이면 **표가 통째로
    깨지면서 에러는 나지 않는다** — 읽는 사람에게는 그냥 이상한 문서로 보인다.
    """
    written = str(value).strip() if value is not None else ""
    return written.replace("|", "\\|").replace("\n", " ") or "-"

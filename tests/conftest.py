"""테스트가 «진짜 네트워크»를 쓰지 않게 만들고, 판정을 바꿔 끼울 자리를 하나로 둔다.

URL 실재 게이트가 수집·반증에 붙으면서, 그 단계를 도는 테스트가 산출물에 적힌 URL 을
실제로 찌를 수 있게 됐다. 그대로 두면 넷이 한꺼번에 나빠진다 —
① 오프라인에서 테스트가 깨지고 ② 남의 서버를 두드리고 ③ 느려지고
④ **결과가 그날 네트워크에 따라 달라져** 초록과 빨강이 코드와 무관해진다.

[중요] 각 테스트 파일이 알아서 막게 두지 않는다. 한 곳만 빠져도 **그 파일만 조용히
네트워크를 쓰고**, 그 사실은 오프라인에 가기 전까지 드러나지 않는다. 그래서 여기서 한 번 막는다.

뒤 단계들이 «앞 단계의 산출물»을 입력으로 먹으므로, 그 준비물도 여기 둔다.
테스트 파일끼리 import 하면 어느 파일이 준비물의 주인인지 흐려지고, pytest 의 경로 규칙에
기대게 된다.
"""

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from research_lab.common_constants import (
    FEASIBILITY_FILENAME,
    LINEAGE_FILENAME,
    MEASUREMENT_FILENAME,
    MECHANISM_FILENAME,
    PRO_EVIDENCE_FILENAME,
    REBUTTAL_FILENAME,
)
from research_lab.gate import urls as url_gate
from research_lab.runner import ledger, naming, state


def _alive(url: str) -> url_gate.Probe:
    """찔러 봤더니 살아 있었다."""
    return url_gate.Probe(liveness=url_gate.Liveness.ALIVE, detail="HEAD 200", status=200)


@pytest.fixture(autouse=True)
def _no_real_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """찌르는 쪽을 「전부 살아 있음」으로 바꾼다 — 아무 테스트도 밖으로 나가지 못한다.

    `real_prober` 표시가 붙은 테스트만 비켜 간다. **진짜 요청 경로에도 계약이 있고**
    (스킴 거르기·HEAD 거부 시 GET·4xx 를 판정으로 옮기기), 그것을 검사하려면 이 함수를
    실제로 지나야 한다. 그 테스트는 `urlopen` 을 직접 갈아 끼워 밖으로 나가지 않는 것을
    스스로 책임진다.
    """
    if request.node.get_closest_marker("real_prober") is not None:
        return
    monkeypatch.setattr(url_gate, "probe_url", _alive)


@pytest.fixture
def probing(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """URL 판정을 원하는 대로 바꿔 끼우고, 무엇을 찔렀는지 돌려준다.

    테스트마다 prober 를 손으로 흉내 내면 `Probe` 모양이 바뀔 때 그 수만큼 고쳐야 하고,
    **빠뜨린 곳은 「계약이 깨졌다」가 아니라 알쏭달쏭한 타입 오류로 터진다.**

    쓰는 법::

        probed = probing(dead={"https://example.com/없음"})
        ...
        assert probed == [...]        # 무엇을 찔렀나
    """
    calls: list[str] = []

    def install(*, dead: Iterable[str] = (), unknown: Mapping[str, str] | None = None) -> list[str]:
        dead_urls = set(dead)
        unknown_urls = dict(unknown or {})

        def probe(url: str) -> url_gate.Probe:
            calls.append(url)
            if url in dead_urls:
                return url_gate.Probe(liveness=url_gate.Liveness.DEAD, detail="HEAD 404", status=404)
            if url in unknown_urls:
                return url_gate.Probe(liveness=url_gate.Liveness.UNKNOWN, detail=unknown_urls[url])
            return _alive(url)

        monkeypatch.setattr(url_gate, "probe_url", probe)
        return calls

    return install


# --------------------------------------------------------------------------
# 뒤 단계들의 «입력» — 앞 단계가 남긴 산출물
# --------------------------------------------------------------------------

CLAIM = "소형주는 1월에 더 오른다. 12월 말에 사서 1월 말에 판다"
IDENTIFIER = "january-kr"

# 실행 폴더 이름의 날짜가 근거 문서의 파일명이 된다. 「오늘」이 아니라 이 값이 쓰이는지를
# 검사하려면 **오늘일 리 없는 날짜**여야 한다
RUN_FOLDER = "20240115_0900"


@dataclass(frozen=True)
class Prepared:
    """앞 단계들이 끝난 회차 하나.

    [중요] `dossier_dir` 이 여기 있는 이유는 **테스트가 진짜 산출물 폴더에 문서를 남기지
    않게** 하기 위해서다. 기본값이 저장소의 자리라, 안 넘기면 `pytest` 한 번에
    커밋 대상 폴더에 파일이 생긴다 — 그리고 그 사실은 `git status` 를 볼 때까지 안 드러난다.
    """

    run_dir: Path
    ledger_path: Path
    output_dir: Path
    dossier_dir: Path
    candidate: state.Candidate


def _write(output_dir: Path, filename: str, payload: dict[str, Any]) -> None:
    """산출물 하나를 만들어 둔다."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / filename).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _pro_evidence() -> dict[str, Any]:
    """수집이 남긴 것 — 찬성 근거와 파라미터 축."""
    return {
        "claim": CLAIM,
        "params": [{"name": "보유 기간", "unit": "거래일", "candidates": [20, 60]}],
        "evidence": [
            {
                "title": "1월 효과 원논문",
                "url": "https://example.com/jan-1976",
                "published": "1976-01-01",
                "kind": "primary",
                "says": "소형주의 1월 초과수익을 처음 보고했다",
            }
        ],
        "unverified": ["국내 절세 매도 유인의 크기"],
    }


def _rebuttal() -> dict[str, Any]:
    """반증이 남긴 것 — 별도 세션의 산출물."""
    return {
        "claim": CLAIM,
        "rebuttals": [
            {
                "title": "발표 후 소멸했다",
                "url": "https://example.com/decay",
                "published": "2011-05-01",
                "kind": "secondary",
                "says": "발표 이후 효과가 약해졌다",
            }
        ],
        "not_found_reason": "",
        "unverified": ["최근 5년 국내 재현 여부"],
    }


def _lineage() -> dict[str, Any]:
    """계보가 남긴 것 — 한 원본과 복제."""
    return {
        "claim": CLAIM,
        "groups": [
            {
                "origin": {
                    "title": "1월 효과 원논문",
                    "url": "https://example.com/jan-1976",
                    "published": "1976-01-01",
                },
                "copies": [{"title": "받아쓴 블로그", "url": "https://example.com/blog"}],
                "why": "같은 숫자와 같은 예시를 그대로 옮겼다",
            }
        ],
        "independent_source_count": 2,
        "unverified": [],
    }


def _feasibility() -> dict[str, Any]:
    """실현가능성이 남긴 것 — 4·5번 칸."""
    return {
        "claim": CLAIM,
        "market": "국내",
        "data": {
            "needs": ["국내 ETF 일봉"],
            "availability": "이미 있음",
            "how_to_get": "국내 ETF 일봉은 pykrx 로 받을 수 있다",
            "point_in_time": "일봉 종가만 쓴다",
            "survivorship": "지수 추종 ETF 한 종목이라 편향이 들어올 자리가 없다",
            "fallback": "막히면 지수 일봉으로 대체하되 집행 불가로 표시한다",
        },
        "execution": {
            "instrument": "코스닥150 을 추종하는 국내 상장 ETF",
            "signal_frequency": "연 1회",
            "leverage": "국내는 2배가 상한이다",
            "waking_hours": "국내장이라 낮에 집행된다",
            "intraday_precision": "종가 기준이라 분·초 집행이 필요 없다",
        },
        "catalog_hit": ["krx-daily"],
        "sources": [],
        "unverified": ["ETF 상장 이전 구간의 대체 방법"],
    }


def _mechanism() -> dict[str, Any]:
    """메커니즘이 남긴 것 — 3·9번 칸."""
    return {
        "claim": CLAIM,
        "edge": {
            "risk_premium": "해당 없음 — 위험을 더 지는 구조가 아니다",
            "behavioral": "연말 절세 매도 뒤 되사기와 기관 윈도드레싱",
            "structural": "1월 신규 자금 유입",
        },
        "decay": {
            "post_publication": "발표로 널리 알려져 선반영됐을 수 있다",
            "regulatory": "한국은 양도세 구조가 달라 절세 매도 유인이 작다",
            "market_structure": "패시브 비중 확대로 연말 매도 압력이 옅어졌다",
        },
        "sources": [{"title": "소멸 연구", "url": "https://example.com/decay"}],
        "unverified": ["윈도드레싱의 국내 실증"],
    }


def _measurement() -> dict[str, Any]:
    """측정 설계가 남긴 것 — 10번 칸."""
    return {
        "claim": CLAIM,
        "instrument": "코스닥150 을 추종하는 국내 상장 ETF",
        "no_lookahead": "진입·청산이 달력만 보면 정해진다",
        "entry_grid": ["12월 20일", "12월 23일", "12월 26일"],
        "holding_grid": [20, 40, 60],
        "single_value_reason": "",
        "baseline": "같은 보유 기간을 아무 날에나 시작했을 때의 전체 평균",
        "direction": "위·아래를 미리 정하지 않는다",
        "expected_samples": "연 1회 x 20년 = 20건",
        "unverified": ["2000년 이전 코스닥 데이터 품질"],
    }


# 앞 단계들의 산출물. 「어디까지 끝났나」를 테스트가 고를 수 있게 «순서대로» 둔다
EARLIER_OUTPUTS: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
    (PRO_EVIDENCE_FILENAME, _pro_evidence),
    (REBUTTAL_FILENAME, _rebuttal),
    (LINEAGE_FILENAME, _lineage),
    (FEASIBILITY_FILENAME, _feasibility),
    (MECHANISM_FILENAME, _mechanism),
    (MEASUREMENT_FILENAME, _measurement),
)


@pytest.fixture
def prepared(tmp_path: Path) -> Callable[..., Prepared]:
    """앞 단계가 끝난 회차 하나를 만든다.

    쓰는 법::

        state = prepared()              # 여섯 단계가 다 끝난 상태
        state = prepared(through=4)      # 실현가능성까지만 끝난 상태

    `through` 는 `EARLIER_OUTPUTS` 의 앞에서부터 몇 개를 만들지다. 뒤 단계일수록
    입력이 많으므로, 테스트가 «자기가 필요한 만큼만» 만들어야 준비물이 과해지지 않는다.
    """

    def build(*, through: int = len(EARLIER_OUTPUTS)) -> Prepared:
        run_dir = tmp_path / "runs" / RUN_FOLDER
        ledger_path = tmp_path / "원장.md"
        candidate = state.Candidate(claim=CLAIM, identifier=IDENTIFIER)

        ledger.append(ledger_path, CLAIM, identifier=IDENTIFIER)
        state.pin_candidate(run_dir, candidate)

        output_dir = run_dir / naming.folder_name(CLAIM, IDENTIFIER)
        for filename, make in EARLIER_OUTPUTS[:through]:
            _write(output_dir, filename, make())

        return Prepared(
            run_dir=run_dir,
            ledger_path=ledger_path,
            output_dir=output_dir,
            dossier_dir=tmp_path / "dossier",
            candidate=candidate,
        )

    return build

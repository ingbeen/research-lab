# 회차를 도는 컨테이너.
#
# [중요] 컨테이너는 «보안 샌드박스가 아니다». 리서치는 인터넷이 필수라 그 조건을 못 맞춘다.
# 여기가 막는 것은 파일 시스템이지 네트워크가 아니며, 그래서 안에 넣는 자격증명은
# Claude 토큰 «하나뿐»이다.

# 멀티아치 베이스만 쓴다. 개발은 WSL(amd64), 운용은 mac(arm64) 이라
# 아치 고정 이미지를 쓰면 옮기는 날 한쪽에서 안 뜬다
FROM python:3.12-slim

# Claude Code 설치 방식: **npm 패키지**.
#
# 탈락안은 네이티브 인스톨러다. 그쪽은 `$HOME/.local/share/claude/` 에 240MB 바이너리를 깔고
# 아치를 스스로 판별하지만, 이 컨테이너는 `--user 1000:1000` 으로 돌고 HOME 을 호스트 폴더로
# 마운트한다 — 빌드 시점의 HOME 과 실행 시점의 HOME 이 달라 설치본을 못 찾는다.
# npm 전역 설치는 `/usr/local/lib/node_modules` 에 들어가 **HOME 과 무관하고 모두가 읽을 수 있어**
# 그 문제가 없다. 대가는 Node 런타임이 얹히는 것이다.
#
# git 을 넣는 이유는 에이전트가 저장소 상태를 읽을 수 있어야 해서이고, ca-certificates 는
# 웹 조회에 필요하다
RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs npm ca-certificates git \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code \
 && npm cache clean --force

# 컨테이너 «안» 경로는 고정한다. 호스트 경로는 바깥에서 주입한다 —
# 코드에 박으면 `/home/...` 과 `/Users/...` 가 갈린다
WORKDIR /work

# 러너는 표준 라이브러리만 쓴다. 그래서 이 이미지에 poetry 도 가상환경도 없다.
# 있다면 호스트의 `.venv`(아치가 다를 수 있다)와 섞여 재현이 깨졌을 것이다
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 소스는 굽지 않고 bind mount 로 받는다. 산출물이 호스트 폴더에 그대로 생겨야
# VSCode 소스 컨트롤에 diff 로 뜨고, 컨테이너가 죽어도 남는다

ENTRYPOINT ["python3", "/work/scripts/run_cycle.py"]

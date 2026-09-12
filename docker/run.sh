#!/usr/bin/env bash
# 밤을 컨테이너에서 돌린다.
#
# 사용법과 옵션은 docs/COMMANDS.md 가 SoT다.
set -euo pipefail

IMAGE="${RESEARCH_LAB_IMAGE:-research-lab:latest}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# [중요] 컨테이너 안 claude 의 HOME 은 «저장소 밖»에 둔다.
#
# 세 자리 중 나머지 둘은 각각 다른 쪽으로 터진다.
#   - 저장소 «안»   : 인증 상태와 세션 로그가 bind mount 를 타고 저장소에 생긴다.
#                    이 저장소는 PUBLIC 이고 git 이력은 되돌아가지 않는다
#   - 컨테이너 휘발 : 컨테이너와 함께 죽어 세션 로그가 사라진다.
#                    폭주 감지 fallback(토큰 합산)과 되붙기가 둘 다 없어진다
# 저장소 밖 호스트 폴더는 둘 다 피한다. mac 과 공유되지 않지만 잃는 것이 없다 —
# 되짚을 로그는 러너가 runs/ 에 쓰고, 되붙기와 5시간 창 합산은 기계를 옮기면 어차피 못 쓴다.
AGENT_HOME="${RESEARCH_LAB_AGENT_HOME:-$HOME/.research-lab-agent-home}"

if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  echo "[중지] CLAUDE_CODE_OAUTH_TOKEN 이 없습니다." >&2
  echo "       무인 실행에는 장기 토큰이 필요합니다. 호스트에서 'claude setup-token' 을 먼저 실행하세요." >&2
  exit 3
fi

# [중요] 과금 경로를 여기서 한 번 더 막는다. 러너 안에도 같은 가드가 있지만,
# 이쪽이 «컨테이너에 넣기 전»이라 한 겹 앞이다
if [ -n "${ANTHROPIC_API_KEY+x}" ]; then
  echo "[중지] ANTHROPIC_API_KEY 가 설정돼 있습니다." >&2
  echo "       이 프로젝트는 구독 토큰만 씁니다. 그 변수가 있으면 구독 대신 API 로 과금됩니다." >&2
  echo "       값이 비어 있어도 거부합니다 — 지우려면 변수 자체를 unset 하세요." >&2
  exit 3
fi

mkdir -p "$AGENT_HOME"

# [중요] 환경을 «통째로» 물려주지 않는다.
# '--env-file' 이나 환경 상속을 쓰면 ANTHROPIC_API_KEY 가 조용히 딸려 들어간다.
# 넘길 것을 이름으로 하나씩 나열하는 것이 그 사고를 구조적으로 막는 방법이다.
#
# --user 1000:1000 이 없으면 root 소유 파일이 생겨 호스트에서 못 고친다.
exec docker run --rm \
  --user 1000:1000 \
  --volume "$REPO_DIR:/work" \
  --volume "$AGENT_HOME:/agent-home" \
  --env HOME=/agent-home \
  --env "CLAUDE_CODE_OAUTH_TOKEN=$CLAUDE_CODE_OAUTH_TOKEN" \
  --env TZ=Asia/Seoul \
  --workdir /work \
  "$IMAGE" "$@"

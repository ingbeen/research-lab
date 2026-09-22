#!/usr/bin/env bash
# 예약 회차 트리거를 끄고 · 켜고 · 상태를 본다.
#
# 사용법은 docs/COMMANDS.md 가 SoT다.
#
# [중요] 끄기가 «두 동작»인 이유 — launchctl 이 둘을 따로 관리한다.
#   disable : 다음 부팅에서 올라오지 않게 한다 (/var/db/com.apple.xpc.launchd 에 기록된다)
#   bootout : 지금 세션에서 내린다
# 하나만 하면 절반만 꺼지고, 그 절반은 «에러를 내지 않는다».
# [실측] 2026-09-21 — disable 만 걸린 서비스는 그대로 실행됐고(kickstart rc=0),
# bootout 만 건 예약은 재부팅에서 되살아나 사흘간 회차를 돌렸다.
#
# [중요] launchctl list 로 상태를 판정하지 않는다 — disabled 인 서비스도 그대로 보여준다.
# 그래서 로드 여부는 print, 재부팅 후 여부는 print-disabled 로 «따로» 본다.
#
# 절전 해제 예약(pmset)은 sudo 가 필요해 이 스크립트가 건드리지 않는다. 보여주기만 한다.
set -euo pipefail

LABEL="local.research-lab.cycle"

# [중요] 외부 명령(cat)을 쓰지 않는다 — printf 는 bash 내장이라 PATH 가 망가져도 나온다.
# 사용법은 «무엇이 잘못됐는지 모를 때» 읽는 글이라, 그 자리에서 또 실패하면 안 된다
usage() {
  printf '%s\n' \
    "예약 회차 트리거를 제어합니다." \
    "" \
    "  off      예약을 끕니다 — 재부팅해도 꺼진 채로 유지됩니다" \
    "  on       예약을 켭니다" \
    "  status   지금 도는지 · 재부팅 후에도 도는지 봅니다" \
    "" \
    "사용법: ./scripts/trigger.sh {off|on|status}" >&2
}

# [중요] 인자 검증이 launchctl 보다 «앞»이다. 순서가 반대면 잘못된 인자로 불렀을 때
# 기계마다 다른 답이 나온다 — launchctl 이 없는 곳에서는 플랫폼 오류로, 있는 곳에서는 사용법으로.
if [ $# -ne 1 ]; then
  usage
  exit 2
fi

case "$1" in
  off | on | status) ACTION="$1" ;;
  *)
    usage
    exit 2
    ;;
esac

if ! command -v launchctl >/dev/null 2>&1; then
  echo "[중지] launchctl 을 찾을 수 없습니다 — 이 스크립트는 mac 전용입니다." >&2
  echo "       운용기는 mac 입니다. 다른 기계의 트리거는 docs/OPERATIONS.md 7절을 보세요." >&2
  exit 3
fi

DOMAIN="gui/$(id -u)"
SERVICE="$DOMAIN/$LABEL"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

# --------------------------------------------------------------------------
# 조회 — 답을 «셋»으로 낸다: yes · no · unknown
#
# [중요] 조회 «실패»를 「아니오」로 접지 않는다. 접으면 이 스크립트가 막으려는 바로 그
# 오판을 스스로 저지른다 — 살아 있는 예약을 「안 돕니다」로 보고하고 사람을 안심시킨다.
# --------------------------------------------------------------------------

# 지금 이 부팅 세션에 올라와 있나. 올라와 있으면 disabled 여도 «돈다»
#
# [실측 2026-09-21] launchctl print 의 종료 코드는 갈린다 —
#   0   올라와 있다
#   113 그런 서비스가 없다 (= 확실히 안 올라와 있다)
#   112 그런 «도메인»이 없다. 비-GUI 세션(ssh 등)에서 난다 — 이때는 «알 수 없다»
loaded_state() {
  local rc=0
  launchctl print "$SERVICE" >/dev/null 2>&1 || rc=$?
  case "$rc" in
    0) echo "yes" ;;
    113) echo "no" ;;
    *) echo "unknown" ;;
  esac
}

# 다음 부팅에서 올라오지 못하게 막혀 있나
#
# grep -F 를 쓴다 — 라벨에 든 '.' 이 정규식에서는 아무 글자나 되므로 다른 라벨을 물 수 있다.
# 파이프 대신 변수에 담는 것도 같은 이유다: pipefail 아래에서 grep -q 가 먼저 끝나면
# launchctl 이 SIGPIPE 로 죽어 «막혀 있는데 아니라고» 답할 수 있다
disabled_state() {
  local listing rc=0
  listing="$(launchctl print-disabled "$DOMAIN" 2>/dev/null)" || rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "unknown"
    return 0
  fi
  # 파이프도 grep 도 쓰지 않는다. case 의 패턴은 «리터럴»이라 라벨의 '.' 이 아무 글자나
  # 되는 일이 없고, pipefail 아래에서 grep 이 먼저 끝나 launchctl 이 SIGPIPE 로 죽는
  # 경로도 애초에 생기지 않는다
  case "$listing" in
    *"\"$LABEL\" => disabled"*) echo "yes" ;;
    *) echo "no" ;;
  esac
}

# 도는 중인 회차가 있으면 알린다. 막지는 않는다 — 끄겠다는 지시를 거부하면 안 된다.
#
# [중요] 이미지 «이름으로 거르지 않는다». docs/OPERATIONS.md 6절이 그 이유를 적어 두었다 —
# 실행 스크립트가 RESEARCH_LAB_IMAGE 로 이름을 덮어쓸 수 있어서, 이름을 박아 거르면
# 덮어쓴 날 조용히 「안 돌고 있음」으로 보인다. 그래서 목록을 «그대로 보여주고» 사람이 본다.
#
# 엔진이 내려가 있거나 docker 가 없으면 조회 자체가 실패한다. 그 실패도 「없음」과 가른다.
warn_if_cycle_running() {
  local listing rc=0
  listing="$(docker ps --format '{{.Image}}  {{.Status}}  {{.Names}}' 2>/dev/null)" || rc=$?

  if [ "$rc" -ne 0 ]; then
    echo "[확인 불가] 도는 중인 회차가 있는지 확인하지 못했습니다 — 엔진이 내려가 있거나" >&2
    echo "            docker 를 찾을 수 없습니다. 도는 회차가 있었다면 끊길 수 있습니다." >&2
    return 0
  fi

  if [ -n "$listing" ]; then
    echo "[주의] 지금 떠 있는 컨테이너가 있습니다. 이 중에 회차가 있으면 끊깁니다 —" >&2
    echo "       끊긴 회차는 다음 회차가 이어받지만, runs/cycles.jsonl 에 종료 줄이 남지" >&2
    echo "       않아 나중에 보면 전원 차단과 구별되지 않습니다 (docs/OPERATIONS.md 5.1)." >&2
    printf '%s\n' "$listing" | sed 's/^/         /' >&2
  fi
}

# 예약 시각과 장수.
#
# [중요] «올라온 정의»와 «파일의 정의»는 다를 수 있다 — 파일만 고치고 다시 안 올리면
# 갈린다(docs/OPERATIONS.md 8.3). 파일 쪽만 읽으면 지금 01:00 에 도는 예약을 03:00 이라고
# 적게 되므로, 올라와 있으면 «올라온 쪽»을 읽고 어느 쪽인지 밝힌다.
print_schedule() {
  # [중요] 로드 여부를 «인자로 받는다». 여기서 다시 물으면 부르는 쪽이 「확인 불가」라고
  # 적은 직후에 「아직 안 올라왔습니다」라고 단언하는 모순이 한 화면에 찍힌다
  local loaded="$1"
  local printed hour minute dossiers schedule origin

  if [ "$loaded" = "yes" ] && printed="$(launchctl print "$SERVICE" 2>/dev/null)"; then
    origin="지금 올라온 정의"
    hour="$(printf '%s' "$printed" | grep -o '"Hour" => [0-9]*' | head -1 || true)"
    minute="$(printf '%s' "$printed" | grep -o '"Minute" => [0-9]*' | head -1 || true)"
    dossiers="$(printf '%s' "$printed" | grep -o 'cycle-dossiers [0-9]*' | head -1 || true)"
    # 「"Hour" => 1」 에서 마지막 칸만 남긴다 (bash 내장이라 외부 명령이 늘지 않는다)
    hour="${hour##* }"
    minute="${minute##* }"
    dossiers="${dossiers##* }"
  else
    case "$loaded" in
      unknown) origin="정의 파일 (올라왔는지 확인하지 못했습니다)" ;;
      *) origin="정의 파일 (아직 안 올라왔습니다)" ;;
    esac
    hour="$(plutil -extract StartCalendarInterval.Hour raw "$PLIST" 2>/dev/null || true)"
    minute="$(plutil -extract StartCalendarInterval.Minute raw "$PLIST" 2>/dev/null || true)"
    dossiers="$(grep -o 'cycle-dossiers [0-9]*' "$PLIST" 2>/dev/null | head -1 || true)"
    dossiers="${dossiers##* }"
  fi

  # [중요] 숫자인지 먼저 본다. printf '%02d' 는 「08」을 8진수로 읽어 터지고,
  # set -e 아래에서는 그 자리에서 스크립트가 통째로 끝난다 — 성공한 on 이 exit 1 이 된다.
  # plist 의 시각이 <string>08</string> 으로 적혀 있으면 실제로 그렇게 된다
  if [[ "$hour" =~ ^[0-9]+$ ]] && [[ "$minute" =~ ^[0-9]+$ ]]; then
    schedule="$(printf '매일 %02d:%02d' "$((10#$hour))" "$((10#$minute))")"
  else
    schedule="읽을 수 없음"
  fi

  echo "  예약 시각   : $schedule"
  # 접미사를 실패 문구에 붙이면 「읽을 수 없음장」이 된다 — 성공했을 때만 붙인다
  if [ -n "$dossiers" ]; then
    echo "  장수        : ${dossiers}장"
  else
    echo "  장수        : 읽을 수 없음"
  fi
  echo "  읽은 곳     : $origin"
}

# --------------------------------------------------------------------------
# 동작 — 건 다음 «상태를 다시 읽어» 검증한다. 셸 스크립트는 품질 검증을 받지 않으므로
# 「명령은 성공했는데 안 꺼진」 상태를 여기서 막는 수밖에 없다
# --------------------------------------------------------------------------

do_off() {
  # [중요] 조건문으로 감싼다. 맨몸으로 부르면 실패했을 때 set -e 가 «여기서» 끝내
  # 아래 검증과 한글 안내가 통째로 건너뛰어진다 — 예약이 살아 있는데 영문 에러만 남는다
  if ! launchctl disable "$SERVICE"; then
    echo "[실패] disable 을 걸지 못했습니다. 예약이 «재부팅 후에도» 살아 있습니다." >&2
    echo "       GUI 세션이 아닌 곳(ssh 등)에서는 걸리지 않습니다 — 로그인한 세션에서 다시 시도하세요." >&2
    exit 1
  fi

  # [중요] 경고는 disable «뒤»에 둔다. 이 조회는 docker 소켓을 타는데, 엔진이 먹통이면
  # 시간제한 없이 멈춘다 — 앞에 두면 「급히 꺼야 할 때」 끄기 자체가 시작도 못 한다.
  # 막는 경고가 아니므로 뒤로 미뤄도 잃는 것이 없고, 실제로 회차를 끊는 것은 아래 bootout 이다
  warn_if_cycle_running

  if [ "$(loaded_state)" != "no" ]; then
    # 실패해도 넘어간다 — 결과는 아래 검증이 판정한다
    launchctl bootout "$SERVICE" || true
  fi

  # [중요] bootout 은 «비동기»다. launchd 가 SIGTERM 을 보낸 뒤 ExitTimeOut(기본 20초)까지
  # 기다렸다가 SIGKILL 하므로, 도는 회차를 내릴 때는 caffeinate -> sh -> docker 가 정리되는
  # 동안 서비스가 남아 있다. 10초만 기다리면 «성공한 조작을 실패로 보고»한다 — 그 기본값보다
  # 넉넉히 둔다. 안 도는 평소에는 한 번도 안 자고 빠져나간다
  local waited=0
  while [ "$(loaded_state)" = "yes" ] && [ "$waited" -lt 30 ]; do
    sleep 1
    waited=$((waited + 1))
  done

  # [중요] «재부팅 후»부터 검증한다. 그쪽이 이 스크립트의 핵심 약속이라, 로드 상태로 먼저
  # 빠져나가면 「disable 은 걸렸습니다」를 종료 코드만 보고 «확인 없이» 단언하게 된다
  local disabled loaded
  disabled="$(disabled_state)"
  loaded="$(loaded_state)"

  if [ "$disabled" != "yes" ]; then
    if [ "$disabled" = "unknown" ]; then
      echo "[실패] disabled 기록을 «확인하지 못했습니다» — 꺼졌다고 믿으면 안 됩니다." >&2
    else
      echo "[실패] disabled 기록이 남지 않았습니다 — 재부팅하면 다시 올라와 돕니다." >&2
    fi
    echo "       직접 걸려면: launchctl disable $SERVICE" >&2
    echo "       상태를 보려면: ./scripts/trigger.sh status" >&2
    exit 1
  fi

  if [ "$loaded" != "no" ]; then
    if [ "$loaded" = "unknown" ]; then
      echo "[실패] 지금 올라와 있는지 «확인하지 못했습니다». 오늘 밤 돌 수 있습니다." >&2
    else
      echo "[실패] 예약이 여전히 올라와 있습니다. 지금 이 부팅 세션에서는 계속 돕니다." >&2
    fi
    echo "       재부팅 후에는 안 돕니다 — disabled 기록은 확인했습니다." >&2
    echo "       직접 내리려면: launchctl bootout $SERVICE" >&2
    exit 1
  fi

  echo "예약을 껐습니다. 재부팅해도 꺼진 채로 유지됩니다."
  echo "  다시 켤 때 : ./scripts/trigger.sh on"
}

do_on() {
  if [ ! -f "$PLIST" ]; then
    echo "[중지] 작업 정의 파일이 없습니다: $PLIST" >&2
    echo "       먼저 만들어야 합니다. 절차는 docs/OPERATIONS.md 3절에 있습니다." >&2
    exit 1
  fi

  # [중요] enable 이 «먼저»다. disabled 인 채로 bootstrap 하면 Input/output error 로 거부된다.
  # 조건문으로 감싸는 이유는 do_off 와 같다 — 맨몸으로 부르면 아래 검증이 건너뛰어진다
  if ! launchctl enable "$SERVICE"; then
    echo "[실패] enable 을 풀지 못했습니다. disabled 기록이 남아 있어 재부팅해도 안 돕니다." >&2
    echo "       GUI 세션이 아닌 곳(ssh 등)에서는 걸리지 않습니다 — 로그인한 세션에서 다시 시도하세요." >&2
    exit 1
  fi

  if [ "$(loaded_state)" != "yes" ]; then
    launchctl bootstrap "$DOMAIN" "$PLIST" || true
  fi

  # [중요] 올라오는 것도 즉시가 아니다. do_off 가 기다리는 것과 같은 이유이며,
  # 비대칭으로 두면 여기서만 「성공했는데 실패로 보고」가 난다 — 그것도 하필
  # 「껐다가 다시 켜는」 왕복의 마지막 단계에서
  local waited=0
  while [ "$(loaded_state)" != "yes" ] && [ "$waited" -lt 10 ]; do
    sleep 1
    waited=$((waited + 1))
  done

  local loaded disabled
  loaded="$(loaded_state)"
  disabled="$(disabled_state)"

  if [ "$loaded" != "yes" ]; then
    if [ "$loaded" = "unknown" ]; then
      echo "[실패] 예약이 올라왔는지 «확인하지 못했습니다»." >&2
    else
      echo "[실패] 예약이 올라오지 않았습니다 — 지금은 돌지 않습니다." >&2
    fi
    # [중요] enable 은 이미 걸렸다. 그래서 지금 이 기계는 «로드 안 됨 + disabled 아님»,
    # 곧 2026-09-16 의 그 상태다. 여기서 안 알리면 사람은 「그냥 꺼져 있다」고 믿고 떠난다
    echo "       [주의] 다만 disabled 는 풀렸으므로 «재부팅하면 돕니다»." >&2
    echo "              정의 파일이 잘못됐다면 고쳐서 다시 켜고, 계속 끄려면: ./scripts/trigger.sh off" >&2
    echo "       직접 올리려면: launchctl bootstrap $DOMAIN $PLIST" >&2
    echo "       지금 상태를 보려면: ./scripts/trigger.sh status" >&2
    exit 1
  fi

  if [ "$disabled" != "no" ]; then
    if [ "$disabled" = "unknown" ]; then
      echo "[실패] disabled 기록을 «확인하지 못했습니다» — 재부팅 후를 장담할 수 없습니다." >&2
    else
      echo "[실패] disabled 기록이 남아 있습니다 — 재부팅하면 올라오지 않습니다." >&2
    fi
    echo "       직접 풀려면: launchctl enable $SERVICE" >&2
    exit 1
  fi

  echo "예약을 켰습니다."
  print_schedule "$loaded"
}

do_status() {
  local loaded disabled now_verdict future_verdict now_detail future_detail

  # 한 번만 묻고 그 값을 계속 쓴다 — 다시 물으면 그 사이 상태가 바뀌었을 때
  # 한 보고서 안에 서로 모순되는 문장이 나란히 찍힌다
  loaded="$(loaded_state)"
  disabled="$(disabled_state)"

  case "$loaded" in
    yes) now_verdict="돕니다" now_detail="올라와 있음" ;;
    no) now_verdict="안 돕니다" now_detail="올라와 있지 않음" ;;
    *) now_verdict="확인 불가" now_detail="조회가 실패했습니다 (GUI 세션이 아닐 수 있습니다)" ;;
  esac

  if [ "$disabled" = "unknown" ]; then
    future_verdict="확인 불가"
    future_detail="disabled 조회가 실패했습니다"
  elif [ "$disabled" = "yes" ]; then
    future_verdict="안 돕니다"
    future_detail="disabled 로 막혀 있음"
  elif [ ! -f "$PLIST" ]; then
    future_verdict="안 돕니다"
    future_detail="작업 정의 파일이 없음"
  else
    future_verdict="돕니다"
    future_detail="disabled 아님 · 정의 파일 있음"
  fi

  echo "예약 회차 트리거 ($LABEL)"
  echo "  지금        : $now_verdict ($now_detail)"
  echo "  재부팅 후   : $future_verdict ($future_detail)"

  # [중요] 경고는 «표시 문자열이 아니라 상태»로 판정한다. 위 문구를 고치면 경고가
  # 조용히 사라지는 연결을 만들지 않는다 — 사라져도 출력은 멀쩡해 보인다.
  #
  # 실측 표의 두 함정에 각각 하나씩 단다. 한쪽만 달면 나머지 한쪽을 밟은 사람은
  # 평범한 두 줄만 보고 지나간다
  if [ "$loaded" = "no" ] && [ "$disabled" = "no" ] && [ -f "$PLIST" ]; then
    # 2026-09-16 의 상태. 껐다고 믿은 예약이 재부팅에서 되살아나 사흘을 돌았다
    echo "  [주의] 지금은 안 돌지만 «재부팅하면 돕니다». 계속 끄려면: ./scripts/trigger.sh off"
  fi
  if [ "$loaded" = "yes" ] && [ "$disabled" = "yes" ]; then
    # disable 만 건 상태. 재부팅 후는 안전하지만 «오늘 밤»에 그대로 돈다
    echo "  [주의] 재부팅 후엔 안 돌지만 «오늘 밤에는 돕니다». 지금 내리려면: ./scripts/trigger.sh off"
  fi
  if [ "$loaded" = "unknown" ] || [ "$disabled" = "unknown" ]; then
    echo "  [주의] 조회가 실패한 항목이 있습니다 — «꺼졌다고 믿지 마세요»."
    echo "         로그인한 GUI 세션에서 다시 보세요 (ssh 로는 판정할 수 없습니다)."
  fi

  echo
  print_schedule "$loaded"
  echo "  정의 파일   : $PLIST"

  echo
  echo "  절전 해제 예약 (sudo 가 필요해 이 스크립트는 건드리지 않습니다):"
  # [주의] 빈 출력을 「기계가 안 깨어난다」로 읽지 않는다 — 깨우는 수단은 반복 예약 말고도
  # 있다. 그 오판을 한 번 거둔 적이 있다 (docs/OPERATIONS.md 3.3). 원문만 보여준다.
  #
  # [중요] 조회 «실패»와 「예약 없음」을 가른다. 둘 다 빈 문자열이라 종료 코드로만 갈린다 —
  # 합쳐 버리면 확인하지 못한 것을 「없다」고 단정하게 되고, 그것이 위 3.3 의 오판이다
  local wake
  if ! wake="$(pmset -g sched 2>/dev/null)"; then
    echo "    (확인 불가 — pmset 조회가 실패했습니다. 「예약 없음」과 다릅니다)"
  elif [ -n "$wake" ]; then
    echo "$wake" | sed 's/^/    /'
  else
    echo "    (반복 예약 없음 — 다만 이것만으로 「안 깨어난다」고 판정하지 않습니다)"
  fi
}

case "$ACTION" in
  off) do_off ;;
  on) do_on ;;
  status) do_status ;;
esac

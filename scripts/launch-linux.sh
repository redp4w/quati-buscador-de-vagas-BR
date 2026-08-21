#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
DATA_DIR="$PROJECT_ROOT/data"
PID_FILE="$DATA_DIR/quati.pid"
SHUTDOWN_REQUEST="$DATA_DIR/shutdown.request"
LOG_FILE="$DATA_DIR/runtime.log"
PORT=8501
APP_URL="http://127.0.0.1:${PORT}/"
HEALTH_URL="http://127.0.0.1:${PORT}/_stcore/health"

notify_error() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send --urgency=critical 'Q.U.A.T.I.' "$1"
  else
    printf '%s\n' "$1" >&2
  fi
}

open_app() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$APP_URL" >/dev/null 2>&1 &
  elif command -v gio >/dev/null 2>&1; then
    gio open "$APP_URL" >/dev/null 2>&1 &
  else
    printf 'Abra %s no navegador.\n' "$APP_URL"
  fi
}

has_client_connection() {
  ss -Htn state established "( sport = :$PORT )" 2>/dev/null | grep -q .
}

is_own_process() {
  local process_id="$1"
  [[ "$process_id" =~ ^[0-9]+$ ]] || return 1
  [[ -r "/proc/$process_id/cmdline" ]] || return 1
  local command_line
  command_line="$(tr '\0' ' ' < "/proc/$process_id/cmdline")"
  [[ "$command_line" == *"$PROJECT_ROOT"* ]] &&
    [[ "$command_line" == *streamlit* ]] &&
    [[ "$command_line" == *app.py* ]]
}

if [[ ! -x "$PYTHON_BIN" ]]; then
  notify_error 'O Q.U.A.T.I. ainda não foi instalado. Execute install-linux.sh primeiro.'
  exit 1
fi

if [[ -L "$DATA_DIR" ]] || [[ -L "$PID_FILE" ]] || [[ -L "$SHUTDOWN_REQUEST" ]] || [[ -L "$LOG_FILE" ]]; then
  notify_error 'A pasta data ou um arquivo de controle é um link e não pode ser usado com segurança.'
  exit 1
fi

if [[ -r "$PID_FILE" ]]; then
  RUNNING_PID="$(tr -d '[:space:]' < "$PID_FILE")"
  if is_own_process "$RUNNING_PID"; then
    open_app
    exit 0
  fi
  rm -f -- "$PID_FILE"
fi

if ! command -v ss >/dev/null 2>&1 || ! command -v setsid >/dev/null 2>&1; then
  notify_error 'Os componentes locais de rede não foram encontrados. Execute install-linux.sh novamente.'
  exit 1
fi

if ss -ltnH "sport = :$PORT" | grep -q .; then
  notify_error "A porta local $PORT está ocupada por outro programa."
  exit 1
fi

mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"
rm -f -- "$SHUTDOWN_REQUEST"
cd "$PROJECT_ROOT"
export QUATI_SHUTDOWN_REQUEST="$SHUTDOWN_REQUEST"
nohup setsid "$PYTHON_BIN" -m streamlit run "$PROJECT_ROOT/app.py" \
  --server.address 127.0.0.1 \
  --server.port "$PORT" \
  --server.headless true \
  --server.enableXsrfProtection true \
  --server.enableCORS true \
  --server.maxUploadSize 10 \
  --client.showErrorDetails none > "$LOG_FILE" 2>&1 &
APP_PID=$!
PID_TEMP="$(mktemp "$DATA_DIR/.quati.pid.XXXXXX")"
printf '%s\n' "$APP_PID" > "$PID_TEMP"
mv -f -- "$PID_TEMP" "$PID_FILE"

cleanup_app() {
  if is_own_process "$APP_PID"; then
    kill -TERM -- "-$APP_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$APP_PID" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$APP_PID" 2>/dev/null; then
      kill -KILL -- "-$APP_PID" 2>/dev/null || true
    fi
  fi
  rm -f -- "$PID_FILE"
  rm -f -- "$SHUTDOWN_REQUEST"
}
trap cleanup_app EXIT INT TERM HUP

READY=false
for _ in $(seq 1 30); do
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    notify_error "A aplicação encerrou durante a inicialização. Consulte $LOG_FILE."
    exit 1
  fi
  if curl -fsS --max-time 1 "$HEALTH_URL" >/dev/null 2>&1; then
    READY=true
    break
  fi
  sleep 0.5
done

if [[ "$READY" != true ]]; then
  notify_error "A aplicação não respondeu no tempo esperado. Consulte $LOG_FILE."
  exit 1
fi

open_app
CLIENT_WAS_SEEN=false
IDLE_TICKS=0
WAIT_TICKS=0
while kill -0 "$APP_PID" 2>/dev/null; do
  if [[ -f "$SHUTDOWN_REQUEST" ]]; then
    exit 0
  fi
  if has_client_connection; then
    CLIENT_WAS_SEEN=true
    IDLE_TICKS=0
  elif [[ "$CLIENT_WAS_SEEN" == true ]]; then
    IDLE_TICKS=$((IDLE_TICKS + 1))
    if (( IDLE_TICKS >= 20 )); then
      exit 0
    fi
  else
    WAIT_TICKS=$((WAIT_TICKS + 1))
    if (( WAIT_TICKS >= 180 )); then
      notify_error 'Nenhuma aba se conectou ao Q.U.A.T.I.'
      exit 1
    fi
  fi
  sleep 0.5
done

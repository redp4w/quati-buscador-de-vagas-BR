#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/data/quati.pid"

notify_user() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send 'Q.U.A.T.I.' "$1"
  else
    printf '%s\n' "$1"
  fi
}

if [[ -L "$PROJECT_ROOT/data" ]] || [[ -L "$PID_FILE" ]]; then
  notify_user 'A pasta data ou o arquivo de controle é um link e não será acessado.'
  exit 1
fi

if [[ ! -r "$PID_FILE" ]]; then
  notify_user 'O Q.U.A.T.I. já estava encerrado.'
  exit 0
fi

APP_PID="$(tr -d '[:space:]' < "$PID_FILE")"
if [[ ! "$APP_PID" =~ ^[0-9]+$ ]] || [[ ! -r "/proc/$APP_PID/cmdline" ]]; then
  rm -f -- "$PID_FILE"
  notify_user 'O Q.U.A.T.I. já estava encerrado.'
  exit 0
fi

COMMAND_LINE="$(tr '\0' ' ' < "/proc/$APP_PID/cmdline")"
if [[ "$COMMAND_LINE" != *"$PROJECT_ROOT"* ]] ||
   [[ "$COMMAND_LINE" != *streamlit* ]] ||
   [[ "$COMMAND_LINE" != *app.py* ]]; then
  notify_user 'O identificador salvo pertence a outro programa e não foi encerrado.'
  exit 1
fi

kill "$APP_PID"
for _ in $(seq 1 20); do
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    rm -f -- "$PID_FILE"
    notify_user 'Q.U.A.T.I. encerrado.'
    exit 0
  fi
  sleep 0.25
done

notify_user 'O processo ainda está encerrando. Tente novamente em alguns segundos.'
exit 1

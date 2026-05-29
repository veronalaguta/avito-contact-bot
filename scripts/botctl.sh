#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/Users/veronikalagutkina/Documents/Avito/avito_contact_bot"
PID_FILE="$APP_DIR/run/bot.pid"
LOG_FILE="$APP_DIR/logs/bot.log"

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  return 1
}

start_bot() {
  if is_running; then
    echo "Bot already running (pid $(cat "$PID_FILE"))."
    return 0
  fi

  mkdir -p "$APP_DIR/logs" "$APP_DIR/run"
  touch "$LOG_FILE"

  nohup /bin/zsh -lc "cd '$APP_DIR' && source .venv/bin/activate && avito-contact-bot" >> "$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  sleep 2

  if is_running; then
    echo "Bot started (pid $pid)."
  else
    echo "Bot failed to start. Last log lines:"
    tail -n 40 "$LOG_FILE" || true
    return 1
  fi
}

stop_bot() {
  if ! is_running; then
    echo "Bot is not running."
    rm -f "$PID_FILE"
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid" 2>/dev/null || true

  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      break
    fi
    sleep 0.2
  done

  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi

  rm -f "$PID_FILE"
  echo "Bot stopped."
}

status_bot() {
  if is_running; then
    echo "Bot is running (pid $(cat "$PID_FILE"))."
  else
    echo "Bot is not running."
    return 1
  fi
}

show_logs() {
  local lines="${1:-80}"
  tail -n "$lines" "$LOG_FILE"
}

case "${1:-}" in
  start)
    start_bot
    ;;
  stop)
    stop_bot
    ;;
  restart)
    stop_bot || true
    start_bot
    ;;
  status)
    status_bot
    ;;
  logs)
    show_logs "${2:-80}"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs [N]}"
    exit 2
    ;;
esac

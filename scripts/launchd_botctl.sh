#!/usr/bin/env bash
set -euo pipefail

LABEL="com.veronalaguta.avito-contact-bot"
UID_CUR="$(id -u)"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/$LABEL.plist"
APP_DIR="/Users/veronikalagutkina/Documents/Avito/avito_contact_bot"
RUN_SCRIPT="$APP_DIR/scripts/run_bot.sh"
LOG_DIR="$APP_DIR/logs"
OUT_LOG="$LOG_DIR/launchd.out.log"
ERR_LOG="$LOG_DIR/launchd.err.log"

write_plist() {
  mkdir -p "$PLIST_DIR" "$LOG_DIR"
  cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$LABEL</string>

    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>$RUN_SCRIPT</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$APP_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$OUT_LOG</string>

    <key>StandardErrorPath</key>
    <string>$ERR_LOG</string>

    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
  </dict>
</plist>
PLIST
}

is_loaded() {
  launchctl print "gui/$UID_CUR/$LABEL" >/dev/null 2>&1
}

install_agent() {
  write_plist
  launchctl bootout "gui/$UID_CUR/$LABEL" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$UID_CUR" "$PLIST_PATH"
  launchctl enable "gui/$UID_CUR/$LABEL" || true
  launchctl kickstart -k "gui/$UID_CUR/$LABEL"
  echo "Installed and started: $LABEL"
}

start_agent() {
  if ! is_loaded; then
    launchctl bootstrap "gui/$UID_CUR" "$PLIST_PATH"
  fi
  launchctl enable "gui/$UID_CUR/$LABEL" || true
  launchctl kickstart -k "gui/$UID_CUR/$LABEL"
  echo "Started: $LABEL"
}

stop_agent() {
  launchctl bootout "gui/$UID_CUR/$LABEL"
  echo "Stopped: $LABEL"
}

restart_agent() {
  if is_loaded; then
    launchctl kickstart -k "gui/$UID_CUR/$LABEL"
    echo "Restarted: $LABEL"
  else
    start_agent
  fi
}

status_agent() {
  if is_loaded; then
    echo "Loaded: $LABEL"
    launchctl print "gui/$UID_CUR/$LABEL" | rg -n "state =|pid =|last exit code =" || true
  else
    echo "Not loaded: $LABEL"
    return 1
  fi
}

uninstall_agent() {
  launchctl bootout "gui/$UID_CUR/$LABEL" >/dev/null 2>&1 || true
  rm -f "$PLIST_PATH"
  echo "Uninstalled: $LABEL"
}

logs_agent() {
  local lines="${1:-80}"
  echo "--- STDOUT ($OUT_LOG) ---"
  tail -n "$lines" "$OUT_LOG" 2>/dev/null || true
  echo "--- STDERR ($ERR_LOG) ---"
  tail -n "$lines" "$ERR_LOG" 2>/dev/null || true
}

case "${1:-}" in
  install)
    install_agent
    ;;
  start)
    start_agent
    ;;
  stop)
    stop_agent
    ;;
  restart)
    restart_agent
    ;;
  status)
    status_agent
    ;;
  uninstall)
    uninstall_agent
    ;;
  logs)
    logs_agent "${2:-80}"
    ;;
  *)
    echo "Usage: $0 {install|start|stop|restart|status|logs [N]|uninstall}"
    exit 2
    ;;
esac

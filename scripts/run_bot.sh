#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/Users/veronikalagutkina/Documents/Avito/avito_contact_bot"
cd "$APP_DIR"
source .venv/bin/activate
exec avito-contact-bot

#!/bin/bash
# Instala serviços systemd para bot + dashboard (correr na VPS como root).
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Este script corre apenas na VPS Linux." >&2
  exit 1
fi

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Correr como root: sudo bash scripts/install_services.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [[ ! -f "$PROJECT_DIR/venv/bin/python" ]]; then
  echo "venv não encontrado. Correr primeiro: bash scripts/setup_vps.sh" >&2
  exit 1
fi

echo "📂 Projeto: $PROJECT_DIR"

echo "🗄️  A aplicar migrações Django..."
"$PROJECT_DIR/venv/bin/python" manage.py migrate --noinput

echo "📋 A instalar unit files systemd..."
for unit in forexbot forexbot-dashboard; do
  sed "s|@PROJECT_DIR@|$PROJECT_DIR|g" \
    "$SCRIPT_DIR/systemd/${unit}.service" \
    > "/etc/systemd/system/${unit}.service"
done

systemctl daemon-reload
systemctl enable forexbot forexbot-dashboard

echo "🔥 A abrir porta do dashboard (9999) no firewall..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 9999/tcp || true
fi

echo "🚀 A arrancar serviços..."
systemctl restart forexbot forexbot-dashboard

echo ""
echo "✅ Serviços instalados!"
echo ""
echo "  Bot:        systemctl status forexbot"
echo "  Dashboard:  systemctl status forexbot-dashboard"
echo "  Logs bot:   journalctl -u forexbot -f"
echo "  Logs dash:  journalctl -u forexbot-dashboard -f"
echo ""
echo "  Dashboard:  http://$(hostname -I | awk '{print $1}'):9999"
echo ""
echo "Parar bot manual (se ainda a correr): Ctrl+C no terminal antigo"
echo "Nota: DRY_RUN=true no .env — ordens simuladas até mudares para false"

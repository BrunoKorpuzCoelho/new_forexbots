#!/bin/bash
set -euo pipefail

# Setup ForexBot v2 — correr apenas na VPS Linux (Ubuntu/Debian)

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Este script corre apenas na VPS Linux." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "📦 A instalar dependências do sistema..."
apt update
apt install -y python3 python3-pip python3-venv git curl

echo "🐍 A criar ambiente virtual..."
python3 -m venv venv
source venv/bin/activate

echo "📚 A instalar dependências Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🔍 A verificar ctrader-open-api..."
python -c "from ctrader_open_api import Client; print('✅ ctrader-open-api instalado')"

echo ""
echo "✅ Setup concluído!"
echo "Próximos passos:"
echo "  cp .env.example .env   # preencher credenciais"
echo "  source venv/bin/activate"
echo "  python forexbot/config.py"

"""Testa notificações Telegram. Correr: python scripts/test_telegram.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

from forexbot import config


def main() -> None:
    token = config.TELEGRAM_BOT_TOKEN.strip()
    chat_id = config.TELEGRAM_CHAT_ID.strip()
    if not token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID em falta no .env")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/getMe"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        print(f"❌ Token inválido (HTTP {r.status_code}): {r.text}")
        print("   Cria um bot novo em @BotFather e atualiza TELEGRAM_BOT_TOKEN")
        sys.exit(1)
    bot_name = r.json().get("result", {}).get("username", "?")
    print(f"✅ Bot OK: @{bot_name}")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": chat_id, "text": "✅ ForexBot v2 — teste Telegram OK"},
        timeout=10,
    )
    if r.status_code != 200:
        print(f"❌ Falha ao enviar (HTTP {r.status_code}): {r.text}")
        print("   Obtém chat_id: envia mensagem ao bot e abre")
        print(f"   https://api.telegram.org/bot{token[:8]}.../getUpdates")
        sys.exit(1)
    print("✅ Mensagem enviada com sucesso")


if __name__ == "__main__":
    main()

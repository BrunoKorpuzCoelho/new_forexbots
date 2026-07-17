import os
from dotenv import load_dotenv

load_dotenv()

# ── cTrader ──────────────────────────────────────────────
CTRADER_CLIENT_ID     = os.getenv("CTRADER_CLIENT_ID", "")
CTRADER_CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET", "")
CTRADER_ACCOUNT_ID    = int(os.getenv("CTRADER_ACCOUNT_ID", "0"))
CTRADER_ACCESS_TOKEN  = os.getenv("CTRADER_ACCESS_TOKEN", "")
CTRADER_REFRESH_TOKEN = os.getenv("CTRADER_REFRESH_TOKEN", "")
CTRADER_HOST          = os.getenv("CTRADER_HOST", "demo.ctraderapi.com")
CTRADER_PORT          = int(os.getenv("CTRADER_PORT", "5035"))
CTRADER_REDIRECT_URI  = os.getenv(
    "CTRADER_REDIRECT_URI", "http://localhost:8080/callback"
)

# ── Telegram ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Bot ──────────────────────────────────────────────────
DRY_RUN   = os.getenv("DRY_RUN", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── Risco ────────────────────────────────────────────────
RISK_PCT = float(os.getenv("RISK_PCT", "1.0"))
# 0 ou vazio = sem limite; default 1.0 = máximo 1 lote por ordem
_max_lot = os.getenv("MAX_LOT", "1.0").strip()
MAX_LOT = float(_max_lot) if _max_lot and float(_max_lot) > 0 else None

# ── Django ───────────────────────────────────────────────
DJANGO_SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DJANGO_DEBUG      = os.getenv("DJANGO_DEBUG", "True") == "True"
DJANGO_PORT       = int(os.getenv("DJANGO_PORT", "9999"))

# ── Estratégias ──────────────────────────────────────────
STRATEGY_A_ENABLED = os.getenv("STRATEGY_A_ENABLED", "true").lower() == "true"
STRATEGY_B_ENABLED = os.getenv("STRATEGY_B_ENABLED", "true").lower() == "true"
STRATEGY_C_ENABLED = os.getenv("STRATEGY_C_ENABLED", "true").lower() == "true"
# Inverte LONG↔SHORT na Estratégia B (mesmas condições de entrada)
STRATEGY_B_INVERT = os.getenv("STRATEGY_B_INVERT", "false").lower() == "true"

# ── Trailing SL ──────────────────────────────────────────
# A 50% do TP → move SL para 10% do TP; a 70% → SL para 40% do TP
TRAIL_SL_ENABLED = os.getenv("TRAIL_SL_ENABLED", "true").lower() == "true"
TRAIL_CHECK_SECONDS = int(os.getenv("TRAIL_CHECK_SECONDS", "60"))

# ── Pares ────────────────────────────────────────────────
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "EURUSD,XAUUSD").split(",")]


def validate():
    errors = []
    if not CTRADER_CLIENT_ID:
        errors.append("CTRADER_CLIENT_ID em falta no .env")
    if not CTRADER_CLIENT_SECRET:
        errors.append("CTRADER_CLIENT_SECRET em falta no .env")
    if not CTRADER_ACCOUNT_ID:
        errors.append("CTRADER_ACCOUNT_ID em falta no .env")
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN em falta no .env")
    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID em falta no .env")
    if errors:
        raise EnvironmentError(
            "Erros de configuração no .env:\n" + "\n".join(f"  ❌ {e}" for e in errors)
        )
    print("✅ Configuração validada com sucesso")


if __name__ == "__main__":
    validate()

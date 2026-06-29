"""
Gera e renova tokens OAuth2 para o cTrader Open API.
Correr manualmente na VPS: python -m forexbot.broker.ctrader_auth
"""
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv, set_key

from forexbot.config import CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET

load_dotenv()

log = logging.getLogger(__name__)

REDIRECT_URI = os.getenv(
    "CTRADER_REDIRECT_URI", "http://localhost:8080/callback"
)
AUTH_URL = "https://connect.spotware.com/apps/auth"
TOKEN_URL = "https://connect.spotware.com/apps/token"
ENV_FILE = ".env"

_auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params = parse_qs(urlparse(self.path).query)
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Autenticado! Podes fechar esta janela.</h2>")

    def log_message(self, format, *args):
        pass


def get_auth_url() -> str:
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={CTRADER_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=trading"
    )


def exchange_code_for_tokens(code: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CTRADER_CLIENT_ID,
            "client_secret": CTRADER_CLIENT_SECRET,
        },
    )
    resp.raise_for_status()
    return resp.json()


def _save_tokens(access_token: str, refresh_token: str) -> None:
    set_key(ENV_FILE, "CTRADER_ACCESS_TOKEN", access_token)
    set_key(ENV_FILE, "CTRADER_REFRESH_TOKEN", refresh_token)
    os.environ["CTRADER_ACCESS_TOKEN"] = access_token
    os.environ["CTRADER_REFRESH_TOKEN"] = refresh_token


def refresh_token_if_needed() -> str:
    """Renova o access token usando o refresh token e guarda no .env."""
    refresh = os.getenv("CTRADER_REFRESH_TOKEN", "")
    if not refresh:
        raise RuntimeError("Sem refresh token. Correr: python -m forexbot.broker.ctrader_auth")

    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": CTRADER_CLIENT_ID,
                "client_secret": CTRADER_CLIENT_SECRET,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        _save_tokens(data["access_token"], data["refresh_token"])
        log.info("Token renovado com sucesso")
        return data["access_token"]
    except Exception as e:
        try:
            from forexbot.core import decision_logger as dl
            from forexbot.notifications.telegram import get_notifier

            get_notifier().send_error(context="OAuth Token Refresh", error=e)
            dl.log_error(
                context="OAuth Token Refresh",
                message=str(e),
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    log.info("Abre este URL no browser:")
    log.info("%s", get_auth_url())
    log.info("A aguardar callback em %s ...", REDIRECT_URI)
    server = HTTPServer(("0.0.0.0", 8080), CallbackHandler)
    server.handle_request()

    if not _auth_code:
        log.error("Não foi recebido código de autenticação")
        raise SystemExit(1)

    log.info("Código recebido: %s...", _auth_code[:10])
    tokens = exchange_code_for_tokens(_auth_code)
    _save_tokens(tokens["access_token"], tokens["refresh_token"])
    log.info("Tokens guardados no .env com sucesso")

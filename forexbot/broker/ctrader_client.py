"""
Cliente TCP síncrono para o cTrader Open API via Twisted.
Gere a ligação, autenticação da app, e pedidos de dados.
"""
import logging
import threading
import time

from ctrader_open_api import Client, Protobuf, TcpProtocol
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAAccountAuthRes,
    ProtoOAApplicationAuthReq,
    ProtoOAApplicationAuthRes,
    ProtoOAGetSymbolsReq,
    ProtoOAGetSymbolsRes,
    ProtoOAGetTrendbarsReq,
    ProtoOAGetTrendbarsRes,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
from twisted.internet import reactor

from forexbot import config

log = logging.getLogger(__name__)

PERIOD_MAP = {
    "M1": ProtoOATrendbarPeriod.M1,
    "M5": ProtoOATrendbarPeriod.M5,
    "M15": ProtoOATrendbarPeriod.M15,
    "H1": ProtoOATrendbarPeriod.H1,
    "H4": ProtoOATrendbarPeriod.H4,
    "D1": ProtoOATrendbarPeriod.D1,
}


class CTraderClient:
    """Wrapper síncrono sobre o cliente Twisted assíncrono do cTrader."""

    def __init__(self, access_token: str):
        self._token = access_token
        self._connected = False
        self._authed = False
        self._symbols: dict[str, int] = {}
        self._pending: dict = {}
        self._lock = threading.Event()

        self._client = Client(
            config.CTRADER_HOST,
            config.CTRADER_PORT,
            TcpProtocol,
        )
        self._client.setConnectedCallback(self._on_connected)
        self._client.setDisconnectedCallback(self._on_disconnected)
        self._client.setMessageReceivedCallback(self._on_message)

    def start(self) -> None:
        """Arranca o reactor em thread daemon e aguarda autenticação."""
        self._client.startService()
        thread = threading.Thread(
            target=reactor.run,
            kwargs={"installSignalHandlers": False},
            daemon=True,
        )
        thread.start()

        if not self._lock.wait(timeout=30):
            raise TimeoutError("cTrader: timeout na autenticação (30s)")
        log.info("cTrader client pronto")

    def _on_connected(self, client):
        log.info("TCP ligado — a autenticar app...")
        req = ProtoOAApplicationAuthReq()
        req.clientId = config.CTRADER_CLIENT_ID
        req.clientSecret = config.CTRADER_CLIENT_SECRET
        client.send(req)

    def _on_disconnected(self, client, reason):
        log.warning("cTrader desligado: %s", reason)
        self._connected = False
        self._authed = False

    def _on_message(self, client, message):
        msg_type = message.payloadType

        if msg_type == ProtoOAApplicationAuthRes().payloadType:
            log.info("App autenticada — a autenticar conta...")
            req = ProtoOAAccountAuthReq()
            req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
            req.accessToken = self._token
            client.send(req)

        elif msg_type == ProtoOAAccountAuthRes().payloadType:
            log.info("Conta %s autenticada", config.CTRADER_ACCOUNT_ID)
            self._connected = True
            self._authed = True
            self._lock.set()

        elif msg_type == ProtoOAGetSymbolsRes().payloadType:
            res = Protobuf.extract(message, ProtoOAGetSymbolsRes)
            for sym in res.symbol:
                self._symbols[sym.symbolName] = sym.symbolId
            log.info("%s símbolos carregados", len(self._symbols))
            if "symbols" in self._pending:
                self._pending["symbols"] = self._symbols.copy()

        elif msg_type == ProtoOAGetTrendbarsRes().payloadType:
            res = Protobuf.extract(message, ProtoOAGetTrendbarsRes)
            key = f"bars_{res.symbolId}"
            if key in self._pending:
                self._pending[key] = list(res.trendbar)

    def get_symbol_id(self, symbol: str) -> int | None:
        return self._symbols.get(symbol)

    def load_symbols(self) -> dict[str, int]:
        """Carrega todos os símbolos disponíveis na conta."""
        req = ProtoOAGetSymbolsReq()
        req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
        key = "symbols"
        self._pending[key] = None
        self._client.send(req)

        for _ in range(100):
            if self._pending.get(key) is not None:
                return self._pending.pop(key)
            time.sleep(0.1)

        raise TimeoutError("Timeout ao carregar símbolos")

    def get_candles(self, symbol: str, timeframe: str = "M15", count: int = 200) -> list:
        """Obtém velas históricas para o símbolo e timeframe indicados."""
        sym_id = self.get_symbol_id(symbol)
        if sym_id is None:
            log.warning("Símbolo não encontrado: %s", symbol)
            return []

        period = PERIOD_MAP.get(timeframe, ProtoOATrendbarPeriod.M15)
        req = ProtoOAGetTrendbarsReq()
        req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
        req.symbolId = sym_id
        req.period = period
        req.count = count

        key = f"bars_{sym_id}"
        self._pending[key] = None
        self._client.send(req)

        for _ in range(100):
            if self._pending.get(key) is not None:
                return self._pending.pop(key)
            time.sleep(0.1)

        log.warning("Timeout ao obter velas para %s", symbol)
        return []

"""
Broker de ordens cTrader — abrir/fechar posições e consultar equity.
Estende CTraderClient via subclasse sem modificar o ficheiro base.
"""
import logging
import time
import uuid

from ctrader_open_api import Protobuf
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAClosePositionReq,
    ProtoOAExecutionEvent,
    ProtoOANewOrderReq,
    ProtoOAReconcileReq,
    ProtoOAReconcileRes,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
    ProtoOAOrderType,
    ProtoOATradeSide,
)

from forexbot import config
from forexbot.broker.ctrader_client import CTraderClient
from forexbot.core.signal import Direction, TradeSignal

log = logging.getLogger(__name__)

DEFAULT_EQUITY = 10000.0
VOLUME_SCALE = 100  # cTrader: volume em 0.01 de unidade (1.00 lot = 100)
PRICE_SCALE = 100000  # relative SL/TP em 1/100000 de unidade de preço


class TradingCTraderClient(CTraderClient):
    """CTraderClient com suporte a execução de ordens e reconcile."""

    def _on_message(self, client, message) -> None:
        msg_type = message.payloadType

        if msg_type == ProtoOAExecutionEvent().payloadType:
            res = Protobuf.extract(message, ProtoOAExecutionEvent)
            self._pending["exec_pending"] = res
            if res.HasField("order") and res.order.orderId:
                self._pending[f"exec_{res.order.orderId}"] = res
            if res.HasField("position") and res.position.positionId:
                self._pending[f"exec_pos_{res.position.positionId}"] = res
            return

        if msg_type == ProtoOAReconcileRes().payloadType:
            res = Protobuf.extract(message, ProtoOAReconcileRes)
            self._pending["reconcile"] = res
            return

        super()._on_message(client, message)

    def wait_pending(self, key: str, timeout: float = 10.0):
        """Aguarda valor em _pending ou None se timeout."""
        for _ in range(int(timeout * 10)):
            if self._pending.get(key) is not None:
                return self._pending.pop(key)
            time.sleep(0.1)
        return None

    def send_and_wait(self, request, pending_key: str, timeout: float = 10.0):
        """Envia pedido e aguarda resposta associada."""
        self._pending[pending_key] = None
        self._client.send(request)
        return self.wait_pending(pending_key, timeout)


class CTraderBroker:
    """Operações de trading sobre o cliente cTrader estendido."""

    def __init__(self, client: TradingCTraderClient) -> None:
        self._client = client

    def get_equity(self) -> float:
        """Obtém balance/equity da conta via reconcile."""
        try:
            req = ProtoOAReconcileReq()
            req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
            res = self._client.send_and_wait(req, "reconcile", timeout=10)
            if res is None:
                log.warning("Timeout ao obter equity — a usar fallback demo")
                return DEFAULT_EQUITY

            if hasattr(res, "balance") and res.balance:
                equity = res.balance / 100.0
                log.debug("Equity obtido: %.2f", equity)
                return float(equity)

            log.warning("Reconcile sem balance — a usar fallback demo")
            return DEFAULT_EQUITY
        except Exception as e:
            log.error("Erro ao obter equity: %s", e)
            return DEFAULT_EQUITY

    def open_trade(self, signal: TradeSignal, lot: float) -> str:
        """Abre ordem MARKET. Em DRY_RUN retorna ticket simulado."""
        if config.DRY_RUN:
            ticket = f"dry-{signal.id}"
            log.info("[DRY_RUN] Ordem simulada: %s %s lot=%.2f", signal.symbol, ticket, lot)
            return ticket

        sym_id = self._client.get_symbol_id(signal.symbol)
        if sym_id is None:
            log.error("Símbolo não encontrado para ordem: %s", signal.symbol)
            return ""

        try:
            req = ProtoOANewOrderReq()
            req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
            req.symbolId = sym_id
            req.orderType = ProtoOAOrderType.MARKET
            req.tradeSide = (
                ProtoOATradeSide.BUY
                if signal.direction == Direction.LONG
                else ProtoOATradeSide.SELL
            )
            req.volume = int(round(lot * VOLUME_SCALE))
            req.relativeStopLoss = int(abs(signal.entry - signal.sl) * PRICE_SCALE)
            req.relativeTakeProfit = int(abs(signal.tp - signal.entry) * PRICE_SCALE)
            req.clientOrderId = str(uuid.uuid4())[:16]

            exec_event = self._client.send_and_wait(req, "exec_pending", timeout=10)
            if exec_event is None:
                log.error("Timeout ao abrir ordem para %s", signal.symbol)
                return ""

            ticket = self._extract_ticket(exec_event)
            if ticket:
                log.info("Ordem aberta: %s ticket=%s lot=%.2f", signal.symbol, ticket, lot)
            return ticket
        except Exception as e:
            log.error("Erro ao abrir ordem [%s]: %s", signal.symbol, e)
            return ""

    def close_position(self, ticket: str, symbol: str) -> bool:
        """Fecha posição pelo positionId."""
        if config.DRY_RUN:
            log.info("[DRY_RUN] Fecho simulado: %s %s", symbol, ticket)
            return True

        try:
            req = ProtoOAClosePositionReq()
            req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
            req.positionId = int(ticket)

            exec_event = self._client.send_and_wait(req, "exec_pending", timeout=10)
            if exec_event is None:
                log.error("Timeout ao fechar posição %s", ticket)
                return False

            log.info("Posição fechada: %s (%s)", symbol, ticket)
            return True
        except Exception as e:
            log.error("Erro ao fechar posição %s: %s", ticket, e)
            return False

    def get_open_positions(self) -> list[dict]:
        """Lista posições abertas via reconcile."""
        try:
            req = ProtoOAReconcileReq()
            req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
            res = self._client.send_and_wait(req, "reconcile", timeout=10)
            if res is None:
                return []

            positions = []
            for pos in res.position:
                if not pos.tradeData.volume:
                    continue
                td = pos.tradeData
                direction = "LONG" if td.tradeSide == ProtoOATradeSide.BUY else "SHORT"
                entry = td.price if hasattr(td, "price") else 0.0
                positions.append({
                    "ticket": str(pos.positionId),
                    "symbol_id": td.symbolId,
                    "direction": direction,
                    "volume": td.volume / VOLUME_SCALE,
                    "entry": entry,
                    "sl": pos.stopLoss if pos.HasField("stopLoss") else 0.0,
                    "tp": pos.takeProfit if pos.HasField("takeProfit") else 0.0,
                })
            return positions
        except Exception as e:
            log.error("Erro ao listar posições: %s", e)
            return []

    @staticmethod
    def _extract_ticket(exec_event: ProtoOAExecutionEvent) -> str:
        """Extrai ticket (positionId ou orderId) do evento de execução."""
        if exec_event.HasField("position") and exec_event.position.positionId:
            return str(exec_event.position.positionId)
        if exec_event.HasField("order") and exec_event.order.orderId:
            return str(exec_event.order.orderId)
        if exec_event.HasField("deal") and exec_event.deal.dealId:
            return str(exec_event.deal.dealId)
        return ""

"""
Broker de ordens cTrader — abrir/fechar posições e consultar equity.
Estende CTraderClient via subclasse sem modificar o ficheiro base.
"""
import logging
import threading
import time
import uuid
from dataclasses import dataclass

from ctrader_open_api import Protobuf
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAClosePositionReq,
    ProtoOADealListByPositionIdReq,
    ProtoOADealListByPositionIdRes,
    ProtoOAExecutionEvent,
    ProtoOANewOrderReq,
    ProtoOAOrderErrorEvent,
    ProtoOAReconcileReq,
    ProtoOAReconcileRes,
    ProtoOASymbolByIdReq,
    ProtoOASymbolByIdRes,
    ProtoOATraderReq,
    ProtoOATraderRes,
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
PRICE_SCALE = 100000  # relative SL/TP em 1/100000 de unidade de preço
PRICE_SCALE_DIGITS = 5
# cTrader Open API: volume/minVolume/stepVolume/lotSize estão na mesma unidade
# (inteiros ×100 vs UI). volume_protocol = lots × lotSize (ProtoOASymbol.lotSize).
# Ref: help.ctrader.com/open-api + forum Spotware (0.01 lot = 100_000 se lotSize=10M).


@dataclass(frozen=True)
class SymbolInfo:
    symbol_id: int
    name: str
    digits: int
    pip_position: int
    lot_size: int
    min_volume: int
    step_volume: int
    max_volume: int
    sl_distance: int
    tp_distance: int

    @classmethod
    def from_proto(cls, sym, name: str = "") -> "SymbolInfo | None":
        lot_size = sym.lotSize if sym.HasField("lotSize") else 0
        if lot_size <= 0:
            return None
        pip_pos = sym.pipPosition if sym.HasField("pipPosition") else max(sym.digits - 1, 0)
        return cls(
            symbol_id=sym.symbolId,
            name=name or (sym.symbolName if sym.HasField("symbolName") else ""),
            digits=sym.digits,
            pip_position=pip_pos,
            lot_size=lot_size,
            min_volume=sym.minVolume if sym.HasField("minVolume") else lot_size // 100,
            step_volume=sym.stepVolume if sym.HasField("stepVolume") else 1,
            max_volume=sym.maxVolume if sym.HasField("maxVolume") else 0,
            sl_distance=sym.slDistance if sym.HasField("slDistance") else 0,
            tp_distance=sym.tpDistance if sym.HasField("tpDistance") else 0,
        )


def pip_size_from_info(info: SymbolInfo) -> float:
    return 10 ** (-info.pip_position)


def _volume_from_lot(lot: float, info: SymbolInfo, *, strict: bool) -> int | None:
    """Converte lote para volume protocolo respeitando min/step/max."""
    raw = lots_to_protocol_volume(lot, info.lot_size)
    min_v = max(info.min_volume, 1)
    step_v = max(info.step_volume, 1)
    max_v = info.max_volume or raw

    if raw < min_v:
        if strict:
            log.warning(
                "Volume %.4f lot (%d) < minVolume %.4f lot (%d) — rejeitado",
                lot,
                raw,
                protocol_volume_to_lots(min_v, info.lot_size),
                min_v,
            )
            return None
        log.info(
            "Volume %.4f lot (%d) < minVolume %.4f lot (%d) — a usar mínimo",
            lot,
            raw,
            protocol_volume_to_lots(min_v, info.lot_size),
            min_v,
        )
        raw = min_v

    steps = (raw - min_v + step_v - 1) // step_v
    volume = min_v + steps * step_v
    if volume > max_v:
        log.warning(
            "Volume normalizado %d (%.4f lot) > maxVolume %d (%.4f lot)",
            volume,
            protocol_volume_to_lots(volume, info.lot_size),
            max_v,
            protocol_volume_to_lots(max_v, info.lot_size),
        )
        return None
    return volume


def round_lot_to_specs(
    lot: float,
    info: SymbolInfo,
    *,
    strict: bool = True,
) -> float | None:
    """Arredonda lote ao step do broker; None se inválido em modo strict."""
    volume = _volume_from_lot(lot, info, strict=strict)
    if volume is None:
        return None
    return protocol_volume_to_lots(volume, info.lot_size)


def normalize_volume(lot: float, info: SymbolInfo, *, strict: bool = False) -> int | None:
    """Converte lote para volume protocolo respeitando min/step/max do símbolo."""
    return _volume_from_lot(lot, info, strict=strict)


def compute_close_pnl(deal, default_money_digits: int) -> tuple[float, float, int] | None:
    """Extrai PnL líquido, preço de fecho e timestamp de um deal de fecho."""
    if not deal.HasField("closePositionDetail"):
        return None
    cpd = deal.closePositionDetail
    digits = (
        cpd.moneyDigits
        if cpd.HasField("moneyDigits")
        else (
            deal.moneyDigits
            if deal.HasField("moneyDigits")
            else default_money_digits
        )
    )
    scale = 10 ** digits
    gross = cpd.grossProfit / scale
    swap = cpd.swap / scale
    comm = cpd.commission / scale
    net = gross + swap + comm
    close_price = cpd.entryPrice if cpd.HasField("entryPrice") else 0.0
    if deal.HasField("executionPrice"):
        close_price = deal.executionPrice
    ts = deal.executionTimestamp if deal.HasField("executionTimestamp") else 0
    if not ts and deal.HasField("utcLastUpdateTimestamp"):
        ts = deal.utcLastUpdateTimestamp
    return net, close_price, ts


def lots_to_protocol_volume(lot: float, lot_size: int) -> int:
    return int(round(lot * lot_size))


def protocol_volume_to_lots(volume: int, lot_size: int) -> float:
    return volume / lot_size


def to_relative_price_delta(
    price_delta: float,
    digits: int,
    min_points: int = 0,
) -> int:
    """Converte distância de preço para relativeStopLoss/TakeProfit (1/100000)."""
    tick_rel = 10 ** max(0, PRICE_SCALE_DIGITS - digits)
    rel = int(round(abs(price_delta) * PRICE_SCALE))
    rel = max(tick_rel, rel)
    rel = ((rel + tick_rel // 2) // tick_rel) * tick_rel
    if min_points > 0:
        min_rel = min_points * tick_rel
        rel = max(rel, min_rel)
    return rel


class TradingCTraderClient(CTraderClient):
    """CTraderClient com suporte a execução de ordens e reconcile."""

    def __init__(self, access_token: str):
        super().__init__(access_token)
        self._money_digits = 2
        self._is_limited_risk = False
        self._trader_loaded = False
        self._pending_lock = threading.Lock()
        self._symbol_cache: dict[int, SymbolInfo] = {}
        self._symbol_specs: dict[str, SymbolInfo] = {}

    def _set_pending(self, key: str, value) -> None:
        with self._pending_lock:
            self._pending[key] = value

    def load_trader_info(self) -> bool:
        """Obtém balance, moneyDigits e flags da conta."""
        req = ProtoOATraderReq()
        req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
        res = self.send_and_wait(req, "trader", timeout=10)
        if res is None:
            return False

        trader = res.trader
        self._money_digits = trader.moneyDigits if trader.HasField("moneyDigits") else 2
        self._is_limited_risk = bool(
            trader.isLimitedRisk if trader.HasField("isLimitedRisk") else False
        )
        self._trader_loaded = True
        log.info(
            "Conta carregada: balance=%.2f limitedRisk=%s",
            trader.balance / (10 ** self._money_digits),
            self._is_limited_risk,
        )
        return True

    def fire_request(self, request) -> None:
        """Envia pedido imediatamente (fora da fila rate-limited de 5 msg/s)."""

        def _send(protocol):
            protocol.send(request, instant=True)
            log.debug("Pedido enviado (instant) payloadType=%s", request.payloadType)

        deferred = self._client.whenConnected(failAfterFailures=1)
        deferred.addCallback(_send)
        deferred.addErrback(
            lambda failure: log.error("fire_request falhou: %s", failure)
        )

    def _on_message(self, client, message) -> None:
        msg_type = message.payloadType

        if msg_type == ProtoOAExecutionEvent().payloadType:
            res = Protobuf.extract(message)
            exec_type = res.executionType if res.HasField("executionType") else "?"
            log.info("ExecutionEvent recebido: type=%s account=%s", exec_type, res.ctidTraderAccountId)
            self._set_pending("exec_pending", res)
            if res.HasField("order") and res.order.orderId:
                self._set_pending(f"exec_{res.order.orderId}", res)
            if res.HasField("position") and res.position.positionId:
                self._set_pending(f"exec_pos_{res.position.positionId}", res)
            return

        if msg_type == ProtoOAOrderErrorEvent().payloadType:
            res = Protobuf.extract(message)
            self._set_pending("order_error", res)
            self._set_pending("exec_pending", res)
            log.error(
                "Erro de ordem cTrader: %s — %s",
                res.errorCode,
                res.description if res.HasField("description") else "",
            )
            return

        if msg_type == ProtoOATraderRes().payloadType:
            res = Protobuf.extract(message)
            self._set_pending("trader", res)
            return

        if msg_type == ProtoOAReconcileRes().payloadType:
            res = Protobuf.extract(message)
            self._set_pending("reconcile", res)
            return

        if msg_type == ProtoOASymbolByIdRes().payloadType:
            res = Protobuf.extract(message)
            self._set_pending("symbol_by_id", res)
            return

        if msg_type == ProtoOADealListByPositionIdRes().payloadType:
            res = Protobuf.extract(message)
            pos_id = res.deal[0].positionId if res.deal else None
            key = f"deals_pos_{pos_id}" if pos_id else "deals_by_position"
            self._set_pending(key, res)
            return

        super()._on_message(client, message)

    def _cache_symbol_info(self, name: str, info: SymbolInfo) -> None:
        self._symbol_cache[info.symbol_id] = info
        if name:
            self._symbol_specs[name] = info

    def preload_symbol_specs(self, symbols: list[str]) -> int:
        """Carrega metadados completos para todos os símbolos do bot."""
        ids: list[int] = []
        id_to_name: dict[int, str] = {}
        for name in symbols:
            sym_id = self.get_symbol_id(name)
            if sym_id is None:
                log.warning("Símbolo não encontrado no broker: %s", name)
                continue
            ids.append(sym_id)
            id_to_name[sym_id] = name

        if not ids:
            return 0

        req = ProtoOASymbolByIdReq()
        req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
        for sym_id in ids:
            req.symbolId.append(sym_id)
        res = self.send_and_wait(req, "symbol_by_id", timeout=15)
        if res is None or not res.symbol:
            log.error("Falha ao pré-carregar specs de símbolos")
            return 0

        loaded = 0
        for sym in res.symbol:
            name = id_to_name.get(sym.symbolId, "")
            info = SymbolInfo.from_proto(sym, name=name)
            if info is None:
                log.error("lotSize em falta para símbolo id=%s", sym.symbolId)
                continue
            self._cache_symbol_info(name, info)
            loaded += 1
            log.debug(
                "%s: pipPos=%d lotSize=%d minVol=%.4f lot stepVol=%.4f lot",
                name,
                info.pip_position,
                info.lot_size,
                protocol_volume_to_lots(info.min_volume, info.lot_size),
                protocol_volume_to_lots(info.step_volume, info.lot_size),
            )
        log.info("Specs carregados para %d/%d símbolos", loaded, len(symbols))
        return loaded

    def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        """Obtém metadados do símbolo (min/step volume, digits, pipPosition)."""
        if symbol in self._symbol_specs:
            return self._symbol_specs[symbol]

        sym_id = self.get_symbol_id(symbol)
        if sym_id is None:
            return None
        if sym_id in self._symbol_cache:
            return self._symbol_cache[sym_id]

        req = ProtoOASymbolByIdReq()
        req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
        req.symbolId.append(sym_id)
        res = self.send_and_wait(req, "symbol_by_id", timeout=10)
        if res is None or not res.symbol:
            log.error("Sem metadados para símbolo %s (id=%s)", symbol, sym_id)
            return None

        info = SymbolInfo.from_proto(res.symbol[0], name=symbol)
        if info is None:
            log.error("lotSize em falta para %s (id=%s)", symbol, sym_id)
            return None
        self._cache_symbol_info(symbol, info)
        log.debug(
            "%s: digits=%d pipPos=%d lotSize=%d minVol=%d (%.4f lot) stepVol=%d",
            symbol,
            info.digits,
            info.pip_position,
            info.lot_size,
            info.min_volume,
            protocol_volume_to_lots(info.min_volume, info.lot_size),
            info.step_volume,
        )
        return info

    def wait_pending(self, key: str, timeout: float = 10.0):
        """Aguarda valor em _pending ou None se timeout."""
        for _ in range(int(timeout * 10)):
            with self._pending_lock:
                if self._pending.get(key) is not None:
                    return self._pending.pop(key)
            time.sleep(0.1)
        return None

    def send_and_wait(self, request, pending_key: str, timeout: float = 10.0):
        """Envia pedido e aguarda resposta associada."""
        self._set_pending(pending_key, None)
        deferred = self._client.send(request, responseTimeoutInSeconds=timeout)
        deferred.addErrback(lambda failure: None)
        return self.wait_pending(pending_key, timeout)


class CTraderBroker:
    """Operações de trading sobre o cliente cTrader estendido."""

    def __init__(self, client: TradingCTraderClient) -> None:
        self._client = client

    def get_equity(self) -> float:
        """Obtém balance da conta via ProtoOATraderReq."""
        try:
            if not self._client._trader_loaded:
                if not self._client.load_trader_info():
                    log.warning("Timeout ao obter trader info — a usar fallback demo")
                    return DEFAULT_EQUITY

            req = ProtoOATraderReq()
            req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
            res = self._client.send_and_wait(req, "trader", timeout=10)
            if res is None:
                log.warning("Timeout ao obter equity — a usar fallback demo")
                return DEFAULT_EQUITY

            trader = res.trader
            digits = trader.moneyDigits if trader.HasField("moneyDigits") else 2
            equity = trader.balance / (10 ** digits)
            self._client._money_digits = digits
            self._client._is_limited_risk = bool(
                trader.isLimitedRisk if trader.HasField("isLimitedRisk") else False
            )
            self._client._trader_loaded = True
            log.info("Equity obtido: $%.2f", equity)
            return float(equity)
        except Exception as e:
            log.error("Erro ao obter equity: %s", e)
            return DEFAULT_EQUITY

    def open_trade(self, signal: TradeSignal, lot: float) -> str:
        """Abre ordem MARKET. Em DRY_RUN retorna ticket simulado."""
        if config.DRY_RUN:
            ticket = f"dry-{signal.id}"
            log.info("[DRY_RUN] Ordem simulada: %s %s lot=%.2f", signal.symbol, ticket, lot)
            return ticket

        sym_info = self._client.get_symbol_info(signal.symbol)
        if sym_info is None:
            log.error("Símbolo não encontrado para ordem: %s", signal.symbol)
            return ""

        try:
            volume = normalize_volume(lot, sym_info, strict=True)
            if volume is None:
                log.error(
                    "Volume inválido para %s: lot=%.2f min=%.4f step=%.4f",
                    signal.symbol,
                    lot,
                    protocol_volume_to_lots(sym_info.min_volume, sym_info.lot_size),
                    protocol_volume_to_lots(sym_info.step_volume, sym_info.lot_size),
                )
                return ""

            rel_sl = to_relative_price_delta(
                signal.entry - signal.sl,
                sym_info.digits,
                sym_info.sl_distance,
            )
            rel_tp = to_relative_price_delta(
                signal.tp - signal.entry,
                sym_info.digits,
                sym_info.tp_distance,
            )
            if rel_sl <= 0 or rel_tp <= 0:
                log.error(
                    "SL/TP relativo inválido para %s: sl=%s tp=%s",
                    signal.symbol,
                    rel_sl,
                    rel_tp,
                )
                return ""

            req = ProtoOANewOrderReq()
            req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
            req.symbolId = sym_info.symbol_id
            req.orderType = ProtoOAOrderType.MARKET
            req.tradeSide = (
                ProtoOATradeSide.BUY
                if signal.direction == Direction.LONG
                else ProtoOATradeSide.SELL
            )
            req.relativeStopLoss = rel_sl
            req.relativeTakeProfit = rel_tp
            req.clientOrderId = str(uuid.uuid4())[:16]
            if self._client._is_limited_risk:
                req.guaranteedStopLoss = True
            req.volume = volume

            exec_lots = protocol_volume_to_lots(volume, sym_info.lot_size)
            log.info(
                "A enviar ordem %s %s lot=%.4f vol=%d sl=%s tp=%s",
                signal.symbol,
                signal.direction.value,
                exec_lots,
                volume,
                rel_sl,
                rel_tp,
            )

            self._client._set_pending("exec_pending", None)
            self._client._set_pending("order_error", None)
            self._client.fire_request(req)

            exec_event = self._client.wait_pending("exec_pending", timeout=20)
            if exec_event is None:
                log.error("Timeout ao abrir ordem para %s", signal.symbol)
                return ""

            if isinstance(exec_event, ProtoOAOrderErrorEvent):
                log.error(
                    "Ordem rejeitada [%s]: %s — %s",
                    signal.symbol,
                    exec_event.errorCode,
                    exec_event.description if exec_event.HasField("description") else "",
                )
                return ""

            if exec_event.HasField("errorCode") and exec_event.errorCode:
                log.error(
                    "Execução com erro [%s]: %s",
                    signal.symbol,
                    exec_event.errorCode,
                )
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

            self._client._set_pending("exec_pending", None)
            self._client.fire_request(req)

            exec_event = self._client.wait_pending("exec_pending", timeout=20)
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
                sym_info = self._client._symbol_cache.get(td.symbolId)
                lot_size = sym_info.lot_size if sym_info else 1
                symbol_name = sym_info.name if sym_info else ""
                positions.append({
                    "ticket": str(pos.positionId),
                    "symbol": symbol_name,
                    "symbol_id": td.symbolId,
                    "direction": direction,
                    "volume": td.volume / lot_size if lot_size else td.volume,
                    "entry": entry,
                    "sl": pos.stopLoss if pos.HasField("stopLoss") else 0.0,
                    "tp": pos.takeProfit if pos.HasField("takeProfit") else 0.0,
                })
            return positions
        except Exception as e:
            log.error("Erro ao listar posições: %s", e)
            return []

    def get_deals_by_position(
        self,
        position_id: int,
        from_ts_ms: int | None = None,
        to_ts_ms: int | None = None,
    ) -> list:
        """Obtém deals de uma posição (inclui fecho com PnL)."""
        try:
            now_ms = int(time.time() * 1000)
            req = ProtoOADealListByPositionIdReq()
            req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
            req.positionId = position_id
            req.fromTimestamp = from_ts_ms if from_ts_ms is not None else 0
            req.toTimestamp = to_ts_ms if to_ts_ms is not None else now_ms
            pending_key = f"deals_pos_{position_id}"
            res = self._client.send_and_wait(req, pending_key, timeout=10)
            if res is None:
                return []
            return list(res.deal)
        except Exception as e:
            log.error("Erro ao obter deals da posição %s: %s", position_id, e)
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

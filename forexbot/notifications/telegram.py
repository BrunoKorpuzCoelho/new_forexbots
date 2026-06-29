"""Notificações Telegram para sinais e trades."""
import logging
from datetime import datetime, timezone
from typing import Protocol

import requests

from forexbot import config
from forexbot.core.signal import Direction, TradeSignal

log = logging.getLogger(__name__)


class NotifierProtocol(Protocol):
    def send(self, text: str) -> None: ...
    def send_signal(self, signal: TradeSignal, lot: float, ticket: str) -> None: ...
    def send_close(
        self,
        ticket: str,
        symbol: str,
        strategy: str,
        pnl: float,
        pips: float,
        exit_reason: str,
    ) -> None: ...
    def send_daily_summary(self, stats: dict) -> None: ...
    def send_error(self, context: str, error: Exception, details: str = "") -> None: ...
    def send_warning(self, context: str, message: str) -> None: ...


class NullNotifier:
    """Notifier silencioso quando Telegram não está configurado."""

    def send(self, text: str) -> None:
        log.debug("Telegram (desativado): %s", text)

    def send_signal(self, signal: TradeSignal, lot: float, ticket: str) -> None:
        log.debug("Telegram (desativado) sinal: %s lot=%s ticket=%s", signal, lot, ticket)

    def send_close(
        self,
        ticket: str,
        symbol: str,
        strategy: str,
        pnl: float,
        pips: float,
        exit_reason: str,
    ) -> None:
        log.debug(
            "Telegram (desativado) fecho: %s %s pnl=%.2f",
            symbol,
            ticket,
            pnl,
        )

    def send_daily_summary(self, stats: dict) -> None:
        log.debug("Telegram (desativado) resumo: %s", stats)

    def send_error(self, context: str, error: Exception, details: str = "") -> None:
        log.debug(
            "Telegram (desativado) erro: [%s] %s: %s",
            context,
            type(error).__name__,
            error,
        )

    def send_warning(self, context: str, message: str) -> None:
        log.debug("Telegram (desativado) aviso: [%s] %s", context, message)


class TelegramNotifier:
    """Envia mensagens via Bot API do Telegram."""

    def __init__(self) -> None:
        self._token = config.TELEGRAM_BOT_TOKEN
        self._chat_id = config.TELEGRAM_CHAT_ID
        self._base = f"https://api.telegram.org/bot{self._token}/sendMessage"

    def send(self, text: str, timeout: int = 10) -> None:
        if not self._token or not self._chat_id:
            return
        try:
            requests.post(
                self._base,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=timeout,
            )
        except Exception as e:
            log.warning("Telegram erro: %s", e)

    def send_signal(self, signal: TradeSignal, lot: float, ticket: str) -> None:
        emoji = "🟢" if signal.direction == Direction.LONG else "🔴"
        direction_label = "LONG" if signal.direction == Direction.LONG else "SHORT"
        dry = " [DRY RUN]" if config.DRY_RUN else ""
        msg = (
            f"{emoji} <b>OPEN {direction_label}{dry}</b> — Estratégia {signal.strategy}\n"
            f"Par: <b>{signal.symbol}</b> · {signal.direction.value}\n"
            f"Entrada: <code>{signal.entry:.5f}</code>\n"
            f"SL: <code>{signal.sl:.5f}</code> · TP: <code>{signal.tp:.5f}</code>\n"
            f"RR: <b>1:{signal.rr_ratio}</b> · Lot: <code>{lot}</code>\n"
            f"📋 {signal.reason}\n"
            f"🎫 Ticket: <code>{ticket}</code>"
        )
        self.send(msg)

    def send_close(
        self,
        ticket: str,
        symbol: str,
        strategy: str,
        pnl: float,
        pips: float,
        exit_reason: str,
    ) -> None:
        emoji = "✅" if pnl >= 0 else "❌"
        msg = (
            f"{emoji} <b>CLOSE TRADE</b> — Estratégia {strategy}\n"
            f"Par: <b>{symbol}</b>\n"
            f"P&L: <code>{pnl:+.2f}$</code> ({pips:+.1f} pips)\n"
            f"Saída: {exit_reason}\n"
            f"🎫 Ticket: <code>{ticket}</code>"
        )
        self.send(msg)

    def send_daily_summary(self, stats: dict) -> None:
        msg = (
            f"📊 <b>Resumo Diário</b>\n"
            f"Trades: {stats.get('total', 0)}\n"
            f"Wins: {stats.get('wins', 0)} · Losses: {stats.get('losses', 0)}\n"
            f"P&L: <code>{stats.get('pnl', 0):+.2f}$</code>\n"
            f"Win rate: {stats.get('win_rate', 0):.1f}%"
        )
        self.send(msg)

    def send_error(self, context: str, error: Exception, details: str = "") -> None:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            msg = (
                f"🚨 <b>ERRO — ForexBot v2</b>\n"
                f"📍 Contexto: {context}\n"
                f"❌ Erro: {type(error).__name__}: {error}"
            )
            if details:
                msg += f"\n📋 Detalhe: {details}"
            msg += f"\n🕐 {ts} UTC"
            self.send(msg, timeout=5)
        except Exception as e:
            log.warning("Falha ao enviar erro Telegram: %s", e)

    def send_warning(self, context: str, message: str) -> None:
        try:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            msg = (
                f"⚠️ <b>AVISO — ForexBot v2</b>\n"
                f"📍 Contexto: {context}\n"
                f"💬 {message}\n"
                f"🕐 {ts} UTC"
            )
            self.send(msg, timeout=5)
        except Exception as e:
            log.warning("Falha ao enviar aviso Telegram: %s", e)


def get_notifier() -> TelegramNotifier | NullNotifier:
    """Retorna notifier real ou nulo conforme configuração."""
    if config.TELEGRAM_BOT_TOKEN:
        return TelegramNotifier()
    return NullNotifier()

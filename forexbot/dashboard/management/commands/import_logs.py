"""Importa logs JSONL de logs/decisions/ para a base de dados."""
import json
import logging
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from forexbot.dashboard.models import DecisionLog, Trade

log = logging.getLogger(__name__)

LOGS_DIR = Path("logs/decisions")


class Command(BaseCommand):
    help = "Importa ficheiros JSONL de logs/decisions/ para Trade e DecisionLog"

    def handle(self, *args, **options) -> None:
        if not LOGS_DIR.exists():
            log.warning("Diretório %s não encontrado", LOGS_DIR)
            return

        trades_imported = 0
        logs_imported = 0
        files = sorted(LOGS_DIR.glob("*.jsonl"))

        for filepath in files:
            log.info("A processar %s", filepath.name)
            with open(filepath, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        result = record.get("result", "")
                        if result == "TRADE_OPEN":
                            if self._import_trade_open(record):
                                trades_imported += 1
                        elif result == "TRADE_CLOSE":
                            if self._import_trade_close(record):
                                trades_imported += 1
                        elif result in ("SIGNAL", "NO_SIGNAL"):
                            if self._import_decision_log(record):
                                logs_imported += 1
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        log.warning(
                            "Erro na linha %d de %s: %s",
                            line_num,
                            filepath.name,
                            e,
                        )

        log.info(
            "Importação concluída: %d trades processados, %d decision logs importados",
            trades_imported,
            logs_imported,
        )

    def _parse_ts(self, ts_str: str) -> datetime:
        dt = datetime.fromisoformat(ts_str)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.utc)
        return dt

    def _import_trade_open(self, record: dict) -> bool:
        ticket = record.get("ticket", "")
        if not ticket:
            return False

        ts = self._parse_ts(record["ts"])
        _, created = Trade.objects.update_or_create(
            ticket=ticket,
            defaults={
                "strategy": record.get("strategy", ""),
                "symbol": record.get("symbol", ""),
                "direction": record.get("direction", ""),
                "entry": float(record.get("entry", 0)),
                "sl": float(record.get("sl", 0)),
                "tp": float(record.get("tp", 0)),
                "lot": float(record.get("lot", 0)),
                "reason": record.get("reason", ""),
                "opened_at": ts,
            },
        )
        return created

    def _import_trade_close(self, record: dict) -> bool:
        ticket = record.get("ticket", "")
        if not ticket:
            return False

        ts = self._parse_ts(record["ts"])
        updated = Trade.objects.filter(ticket=ticket).update(
            closed_at=ts,
            pnl=float(record.get("pnl", 0)),
            pips=float(record.get("pips", 0)),
            exit_reason=record.get("exit_reason", ""),
        )
        return updated > 0

    def _import_decision_log(self, record: dict) -> bool:
        ts = self._parse_ts(record["ts"])
        _, created = DecisionLog.objects.get_or_create(
            ts=ts,
            strategy=record.get("strategy", ""),
            symbol=record.get("symbol", ""),
            result=record.get("result", ""),
            defaults={
                "reason": record.get("reason", ""),
                "indicators": record.get("indicators", {}),
            },
        )
        return created

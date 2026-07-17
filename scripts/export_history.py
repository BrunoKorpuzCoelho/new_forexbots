"""
Exporta histórico de trades e estado da conta para análise.
Correr na VPS (parar forexbot se usar --live):

  cd /var/www/new_forexbots
  source venv/bin/activate
  python scripts/export_history.py
  python scripts/export_history.py --live   # balance + posições abertas (cTrader)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_project.settings")

import django

django.setup()

from django.db.models import Sum

from forexbot import config
from forexbot.dashboard.models import Trade

LOGS_DIR = ROOT / "logs" / "decisions"


def _section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def print_config() -> None:
    _section("CONFIG (.env)")
    print(f"DRY_RUN={config.DRY_RUN}")
    print(f"RISK_PCT={config.RISK_PCT}")
    print(f"MAX_LOT={getattr(config, 'MAX_LOT', 'n/a')}")
    print(f"CTRADER_ACCOUNT_ID={config.CTRADER_ACCOUNT_ID}")


def print_jsonl_trades() -> None:
    _section("LOGS JSONL (TRADE_OPEN / TRADE_CLOSE)")
    if not LOGS_DIR.exists():
        print("(sem pasta logs/decisions)")
        return

    events: list[dict] = []
    for path in sorted(LOGS_DIR.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("result") in ("TRADE_OPEN", "TRADE_CLOSE"):
                    events.append(rec)

    if not events:
        print("(nenhum trade nos JSONL)")
        return

    for rec in sorted(events, key=lambda r: r.get("ts", "")):
        print(json.dumps(rec, ensure_ascii=False))


def print_db_trades() -> None:
    _section("BASE DE DADOS (Trade)")
    qs = Trade.objects.all().order_by("opened_at")
    if not qs.exists():
        print("(vazio — correr: python manage.py import_logs)")
        return

    for t in qs:
        pnl = f"{t.pnl:.2f}" if t.pnl is not None else "ABERTO"
        closed = t.closed_at.strftime("%Y-%m-%d %H:%M") if t.closed_at else "—"
        print(
            f"{t.opened_at:%Y-%m-%d %H:%M} | {t.strategy} | {t.symbol} | "
            f"{t.direction} | lot={t.lot} | entry={t.entry} | sl={t.sl} | tp={t.tp} | "
            f"ticket={t.ticket} | pnl={pnl} | fechado={closed} | {t.exit_reason or ''}"
        )

    closed = qs.filter(closed_at__isnull=False)
    open_count = qs.filter(closed_at__isnull=True).count()
    total_pnl = closed.aggregate(s=Sum("pnl"))["s"] or 0.0
    print()
    print(f"Resumo DB: {qs.count()} trades | {open_count} abertos | "
          f"{closed.count()} fechados | P&L fechados=${total_pnl:.2f}")


def print_live() -> None:
    _section("CONTA cTrader (ao vivo)")
    print("A ligar... (parar forexbot se der conflito de ligação)")
    from forexbot.core.main_loop import connect_bot

    client, broker, _strategies, _notifier = connect_bot()
    try:
        equity = broker.get_equity()
        print(f"Balance: ${equity:.2f}")

        positions = broker.get_open_positions()
        if not positions:
            print("Posições abertas: nenhuma")
        else:
            print(f"Posições abertas: {len(positions)}")
            id_to_name = {v: k for k, v in client._symbols.items()}
            for p in positions:
                sym = id_to_name.get(p.get("symbol_id"), f"id={p.get('symbol_id')}")
                print(
                    f"  {sym} {p.get('direction')} lot={p.get('volume')} "
                    f"entry={p.get('entry')} sl={p.get('sl')} tp={p.get('tp')} "
                    f"ticket={p.get('ticket')}"
                )
    finally:
        stop = getattr(client, "stop", None)
        if callable(stop):
            stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta histórico de trades")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Consulta balance e posições abertas no cTrader",
    )
    args = parser.parse_args()

    print_config()
    print_jsonl_trades()
    print_db_trades()
    if args.live:
        print_live()

    _section("FIM — cola este output no chat para análise")


if __name__ == "__main__":
    main()

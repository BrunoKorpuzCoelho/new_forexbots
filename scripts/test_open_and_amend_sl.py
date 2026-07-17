"""
Teste em produção: abre 1 posição por par e altera o SL (amend).

IMPORTANTE
----------
1. Para o bot antes:  sudo systemctl stop forexbot
2. Corre com --confirm (senão só mostra o plano)
3. Usa lote mínimo do broker (não o MAX_LOT de 1.0)
4. Depois fecha as posições no cTrader e limpa a BD

Uso (VPS):
  cd /var/www/new_forexbots
  source venv/bin/activate
  sudo systemctl stop forexbot
  python -u scripts/test_open_and_amend_sl.py              # dry plan
  python -u scripts/test_open_and_amend_sl.py --confirm    # todos os SYMBOLS
  python -u scripts/test_open_and_amend_sl.py --confirm --limit 3
  python -u scripts/test_open_and_amend_sl.py --confirm --symbol EURUSD
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Output imediato no terminal (sem buffer)
os.environ.setdefault("PYTHONUNBUFFERED", "1")
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_project.settings")

from forexbot import config
from forexbot.broker.ctrader_broker import (
    protocol_volume_to_lots,
    round_lot_to_specs,
)
from forexbot.core.main_loop import bars_to_candles, connect_bot
from forexbot.core.signal import Direction, TradeSignal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger("test_open_amend")


def p(msg: str = "") -> None:
    """Print com flush para aparecer logo no terminal."""
    print(msg, flush=True)


def _min_lot(sym_info) -> float | None:
    """Lote mínimo do símbolo, arredondado às specs."""
    raw = protocol_volume_to_lots(sym_info.min_volume, sym_info.lot_size)
    return round_lot_to_specs(raw, sym_info, strict=True)


def _atr_risk(candles, fallback: float) -> float:
    if len(candles) < 15:
        return fallback
    trs = []
    for i in range(1, len(candles)):
        c, prev = candles[i], candles[i - 1]
        tr = max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
        trs.append(tr)
    window = trs[-14:]
    return sum(window) / len(window) if window else fallback


def _build_signal(symbol: str, candles, direction: Direction) -> TradeSignal | None:
    if not candles:
        return None
    entry = candles[-1].close
    risk = _atr_risk(candles, entry * 0.001)
    if risk <= 0:
        return None
    if direction == Direction.LONG:
        sl, tp = entry - risk, entry + risk
    else:
        sl, tp = entry + risk, entry - risk
    return TradeSignal(
        strategy="TEST",
        symbol=symbol,
        direction=direction,
        entry=entry,
        sl=sl,
        tp=tp,
        reason="test_open_and_amend_sl",
        timestamp=datetime.now(timezone.utc),
    )


def _tighten_sl(direction: str, entry: float, sl: float, factor: float = 0.5) -> float:
    """Aproxima o SL da entrada (50% da distância) — amend válido sem o preço ter andado."""
    dist = abs(entry - sl)
    new_dist = dist * factor
    if direction == "LONG":
        return entry - new_dist
    return entry + new_dist


def _print_running_score(results: list[dict]) -> None:
    ok_open = sum(1 for r in results if r["open"])
    ok_amend = sum(1 for r in results if r["amend"])
    fail = sum(1 for r in results if r["error"])
    p(
        f"  📊 Progresso parcial: abertos={ok_open} | amend OK={ok_amend} | "
        f"falhas={fail} | feitos={len(results)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Abre 1 posição por par e testa amend do SL"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Executa de verdade (sem isto só mostra o plano)",
    )
    parser.add_argument("--symbol", type=str, default="", help="Só este par (ex: EURUSD)")
    parser.add_argument("--limit", type=int, default=0, help="Máximo de pares a testar")
    parser.add_argument(
        "--side",
        choices=("LONG", "SHORT"),
        default="LONG",
        help="Direção das ordens de teste (default LONG)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=2.0,
        help="Segundos entre abrir e alterar SL (default 2)",
    )
    args = parser.parse_args()

    symbols = [args.symbol.upper()] if args.symbol else list(config.SYMBOLS)
    if args.limit > 0:
        symbols = symbols[: args.limit]
    direction = Direction.LONG if args.side == "LONG" else Direction.SHORT

    p("=" * 60)
    p("TEST OPEN + AMEND SL")
    p("=" * 60)
    p(f"Conta:     {config.CTRADER_ACCOUNT_ID}")
    p(f"DRY_RUN:   {config.DRY_RUN}")
    p(f"Pares:     {len(symbols)} → {symbols}")
    p(f"Direção:   {direction.value}")
    p(f"Confirm:   {args.confirm}")
    p()
    p("NOTA: o SL é apertado para 50% da distância original (teste de amend).")
    p("      Não precisa do preço estar a 50%/70% do TP.")
    p("      Para o bot: sudo systemctl stop forexbot")
    p()

    if config.DRY_RUN:
        p("⚠️  DRY_RUN=true no .env — ordens serão simuladas.")
        p()

    if not args.confirm:
        p("Modo plano (sem ordens). Corre de novo com --confirm para executar.")
        p("Exemplo: python -u scripts/test_open_and_amend_sl.py --confirm --symbol EURUSD")
        return 0

    p("[1/3] A ligar ao cTrader...")
    client, broker, _strategies, _notifier = connect_bot()
    p("[1/3] ✅ Ligado")
    p(f"[2/3] A testar {len(symbols)} par(es)...")
    results: list[dict] = []

    try:
        for i, symbol in enumerate(symbols, 1):
            p()
            p(f"{'─' * 60}")
            p(f"[{i}/{len(symbols)}] {symbol}")
            p(f"{'─' * 60}")
            row = {
                "symbol": symbol,
                "ticket": "",
                "open": False,
                "amend": False,
                "error": "",
            }

            try:
                p(f"  → A obter specs de {symbol}...")
                sym_info = client.get_symbol_info(symbol)
                if sym_info is None:
                    row["error"] = "specs indisponíveis"
                    p(f"  ❌ FALHOU: {row['error']}")
                    results.append(row)
                    _print_running_score(results)
                    continue
                p(f"  ✓ Specs OK (digits={sym_info.digits})")

                p("  → A calcular lote mínimo...")
                lot = _min_lot(sym_info)
                if lot is None or lot <= 0:
                    row["error"] = "lote mínimo inválido"
                    p(f"  ❌ FALHOU: {row['error']}")
                    results.append(row)
                    _print_running_score(results)
                    continue
                p(f"  ✓ Lote mínimo = {lot}")

                p("  → A obter velas M15...")
                bars = client.get_candles(symbol, "M15", count=50)
                candles = bars_to_candles(bars)
                p(f"  ✓ {len(candles)} velas recebidas")

                signal = _build_signal(symbol, candles, direction)
                if signal is None:
                    row["error"] = "sem velas / risco inválido"
                    p(f"  ❌ FALHOU: {row['error']}")
                    results.append(row)
                    _print_running_score(results)
                    continue

                p(
                    f"  → A abrir {direction.value} lot={lot} "
                    f"entry≈{signal.entry:.5f} sl={signal.sl:.5f} tp={signal.tp:.5f} ..."
                )
                ticket = broker.open_trade(signal, lot)
                if not ticket:
                    row["error"] = "open_trade falhou"
                    p(f"  ❌ FALHOU: {row['error']}")
                    results.append(row)
                    _print_running_score(results)
                    continue

                row["ticket"] = ticket
                row["open"] = True
                p(f"  ✅ ABERTO ticket={ticket}")

                p(f"  → A aguardar {args.pause:.1f}s antes do amend...")
                time.sleep(args.pause)

                p("  → A ler posição no broker...")
                positions = broker.get_open_positions()
                pos = next((x for x in positions if x["ticket"] == ticket), None)
                if pos:
                    p(
                        f"  ✓ Posição encontrada: entry={pos.get('entry')} "
                        f"sl={pos.get('sl')} tp={pos.get('tp')}"
                    )
                else:
                    p("  ⚠️ Posição não listada no reconcile — uso valores do sinal")

                entry = float(pos["entry"]) if pos and pos.get("entry") else signal.entry
                cur_sl = float(pos["sl"]) if pos and pos.get("sl") else signal.sl
                cur_tp = float(pos["tp"]) if pos and pos.get("tp") else signal.tp
                side = pos["direction"] if pos else direction.value

                new_sl = round(_tighten_sl(side, entry, cur_sl, factor=0.5), sym_info.digits)
                p(f"  → A alterar SL {cur_sl:.5f} → {new_sl:.5f} (TP={cur_tp:.5f})...")
                ok = broker.amend_position_sltp(ticket, symbol, new_sl, cur_tp)
                row["amend"] = bool(ok)
                if ok:
                    p(f"  ✅ AMEND OK — SL agora {new_sl:.5f}")
                    p(f"  ✅ [{i}/{len(symbols)}] {symbol} PASSOU")
                else:
                    row["error"] = "amend falhou"
                    p(f"  ❌ FALHOU: amend SL")
                    p(f"  ❌ [{i}/{len(symbols)}] {symbol} FALHOU no amend")

            except Exception as e:
                row["error"] = str(e)
                p(f"  ❌ EXCEÇÃO: {e}")
                log.exception("%s falhou", symbol)

            results.append(row)
            _print_running_score(results)
            time.sleep(0.5)

    finally:
        p()
        p("[3/3] A terminar ligação...")
        stop = getattr(client, "stop", None)
        if callable(stop):
            stop()
        p("[3/3] ✅ Feito")

    opened = sum(1 for r in results if r["open"])
    amended = sum(1 for r in results if r["amend"])
    failed = [r for r in results if r["error"]]
    passed = [r for r in results if r["open"] and r["amend"] and not r["error"]]

    p()
    p("=" * 60)
    p("RESUMO FINAL")
    p("=" * 60)
    p(f"Total pares:     {len(results)}")
    p(f"Abertas OK:      {opened}")
    p(f"Amend SL OK:     {amended}")
    p(f"Passaram (ambos):{len(passed)}")
    p(f"Falharam:        {len(failed)}")
    p()

    if passed:
        p("✅ Passaram:")
        for r in passed:
            p(f"   • {r['symbol']} ticket={r['ticket']}")
    if failed:
        p("❌ Falharam:")
        for r in failed:
            p(f"   • {r['symbol']}: {r['error']} (ticket={r['ticket'] or '—'})")

    p()
    if amended == opened and opened > 0 and not failed:
        p("🎉 TUDO CORREU BEM — open + amend OK em todos os pares testados.")
    elif amended > 0:
        p("⚠️  PARCIAL — alguns pares OK, outros falharam (ver lista acima).")
    else:
        p("❌ NADA PASSOU — verifica logs e se o forexbot está parado.")

    p()
    p("Próximos passos:")
    p("  1. Fecha as posições no cTrader")
    p("  2. Limpa a BD (com bot parado)")
    p("  3. sudo systemctl start forexbot")
    return 0 if amended == opened and opened > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

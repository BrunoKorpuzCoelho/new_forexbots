"""Cálculo de tamanho de lote baseado em risco percentual e specs do broker."""
import logging

from forexbot import config
from forexbot.broker.ctrader_broker import SymbolInfo, round_lot_to_specs

log = logging.getLogger(__name__)


def pip_size(info: SymbolInfo) -> float:
    """Tamanho de 1 pip em unidades de preço."""
    return 10 ** (-info.pip_position)


def contract_units(info: SymbolInfo) -> float:
    """Unidades do ativo base por 1 lote (lotSize cTrader em cents)."""
    return info.lot_size / 100


def quote_to_usd_rate(
    symbol: str,
    entry: float,
    usdjpy_rate: float | None = None,
) -> float:
    """
    Fator para converter valor em moeda de cotação para USD.
    Pares USD* assumem cotação USD. Pares *JPY dividem pelo USDJPY.
    """
    if not symbol.endswith("JPY"):
        return 1.0
    rate = usdjpy_rate if usdjpy_rate and usdjpy_rate > 0 else entry
    if rate <= 0:
        return 1.0
    return 1.0 / rate


def pip_value_per_lot_usd(
    info: SymbolInfo,
    entry: float,
    usdjpy_rate: float | None = None,
) -> float:
    """Valor em USD de 1 pip para 1 lote."""
    ps = pip_size(info)
    pv_quote = ps * contract_units(info)
    return pv_quote * quote_to_usd_rate(info.name, entry, usdjpy_rate)


def lot_size(
    equity: float,
    entry: float,
    sl: float,
    info: SymbolInfo,
    usdjpy_rate: float | None = None,
) -> float | None:
    """
    Calcula lote baseado em equity, RISK_PCT e distância ao SL.
    Usa pipPosition/lotSize do broker. Retorna None se fora de min/max/step.
    """
    risk_amount = equity * (config.RISK_PCT / 100)
    sl_distance = abs(entry - sl)
    ps = pip_size(info)
    sl_pips = sl_distance / ps if ps > 0 else 0.0

    if sl_pips < 0.1:
        log.warning(
            "SL demasiado pequeno (%.2f pips) para %s — ordem rejeitada",
            sl_pips,
            info.name,
        )
        return None

    pv = pip_value_per_lot_usd(info, entry, usdjpy_rate)
    if pv <= 0:
        log.warning("pip_value inválido para %s", info.name)
        return None

    lot_raw = risk_amount / (sl_pips * pv)
    lot_uncapped = lot_raw
    if config.MAX_LOT is not None:
        lot_raw = min(config.MAX_LOT, lot_raw)

    lot_final = round_lot_to_specs(lot_raw, info, strict=True)
    if lot_uncapped > lot_raw and config.MAX_LOT is not None:
        log.info(
            "Lote limitado por MAX_LOT=%.2f: %s calculado=%.4f → %.4f",
            config.MAX_LOT,
            info.name,
            lot_uncapped,
            lot_raw,
        )
    log.debug(
        "lot_size: symbol=%s equity=%.2f risk_amount=%.2f sl_distance=%.6f "
        "sl_pips=%.2f pip_value=%.4f lot_calculado=%.4f lot_final=%s",
        info.name,
        equity,
        risk_amount,
        sl_distance,
        sl_pips,
        pv,
        lot_raw,
        f"{lot_final:.4f}" if lot_final is not None else "REJEITADO",
    )
    return lot_final

"""
Testa a ligação ao cTrader.
Correr na VPS: python scripts/connect_check.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from forexbot import config
from forexbot.broker.ctrader_client import CTraderClient


def main():
    print("A ligar ao cTrader...")
    client = CTraderClient(config.CTRADER_ACCESS_TOKEN)
    client.start()
    print("Ligado.")

    print("A carregar simbolos...")
    symbols = client.load_symbols()
    print(f"{len(symbols)} simbolos disponiveis")

    print("\nVerificacao de simbolos do .env:")
    for sym in config.SYMBOLS:
        sym_id = client.get_symbol_id(sym)
        if sym_id:
            print(f"   {sym}: ✅ ID={sym_id}")
        else:
            print(f"   {sym}: ❌ NÃO ENCONTRADO")

    print("\nA obter 5 velas M15 de EURUSD...")
    candles = client.get_candles("EURUSD", "M15", count=5)
    if candles:
        for c in candles[-5:]:
            print(
                f"   Open={c.low + c.deltaOpen / 100000:.5f} "
                f"High={c.low + c.deltaHigh / 100000:.5f} "
                f"Low={c.low / 100000:.5f} "
                f"Close={c.low + c.deltaClose / 100000:.5f} "
                f"Vol={c.volume}"
            )
    else:
        raise RuntimeError("Sem velas recebidas — verificar simbolo ou token")

    print("\n✅ Teste concluído com sucesso!")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

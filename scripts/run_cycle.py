"""
Executa um ciclo M15 imediatamente (sem esperar pelo fecho da vela).
Correr na VPS: python scripts/run_cycle.py

Nota: não correr em paralelo com o serviço forexbot (systemctl).
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from forexbot.core.main_loop import _configure_logging, connect_bot, run_cycle


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _configure_logging()

    client, broker, strategies, notifier = connect_bot()
    log.info("Ciclo manual a iniciar...")
    run_cycle(client, broker, strategies, notifier)
    print("✅ Ciclo M15 concluído — ver logs acima")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

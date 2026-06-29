"""Ponto de entrada principal do ForexBot v2."""
import logging

from forexbot.core.main_loop import run

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run()

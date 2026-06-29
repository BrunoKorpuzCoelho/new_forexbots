#!/usr/bin/env python
"""Utilitário de linha de comandos Django."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar Django. Instala-o e tenta novamente."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

"""Ponto de entrada do dashboard Django."""
import os

from django.core.management import execute_from_command_line

from forexbot import config

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_project.settings")
    port = config.DJANGO_PORT
    execute_from_command_line(["manage.py", "runserver", f"0.0.0.0:{port}"])

"""Configuração da app Django do dashboard."""
from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "forexbot.dashboard"
    verbose_name = "ForexBot Dashboard"

"""Admin Django para modelos do dashboard."""
from django.contrib import admin

from forexbot.dashboard.models import DecisionLog, ErrorLog, Trade


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("ticket", "strategy", "symbol", "direction", "opened_at", "pnl")
    list_filter = ("strategy", "symbol", "direction")
    search_fields = ("ticket", "symbol")


@admin.register(DecisionLog)
class DecisionLogAdmin(admin.ModelAdmin):
    list_display = ("ts", "strategy", "symbol", "result")
    list_filter = ("strategy", "symbol", "result")
    search_fields = ("symbol", "reason")


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ("ts", "level", "context", "message")
    list_filter = ("level",)
    search_fields = ("context", "message")

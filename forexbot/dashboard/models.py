"""Modelos de dados do dashboard."""
from django.db import models


class Trade(models.Model):
    ticket = models.CharField(max_length=50, unique=True)
    strategy = models.CharField(max_length=5)
    symbol = models.CharField(max_length=20)
    direction = models.CharField(max_length=5)
    entry = models.FloatField()
    sl = models.FloatField()
    tp = models.FloatField()
    lot = models.FloatField()
    reason = models.TextField()
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    pnl = models.FloatField(null=True, blank=True)
    pips = models.FloatField(null=True, blank=True)
    exit_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        return f"{self.strategy} {self.symbol} {self.direction} {self.opened_at}"

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @property
    def is_winner(self) -> bool:
        return self.pnl is not None and self.pnl > 0


class DecisionLog(models.Model):
    ts = models.DateTimeField()
    strategy = models.CharField(max_length=5)
    symbol = models.CharField(max_length=20)
    result = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    indicators = models.JSONField(default=dict)

    class Meta:
        ordering = ["-ts"]

    def __str__(self) -> str:
        return f"{self.ts} {self.strategy} {self.symbol} {self.result}"


class ErrorLog(models.Model):
    ts = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10)
    context = models.CharField(max_length=200)
    message = models.TextField()
    traceback = models.TextField(blank=True)

    class Meta:
        ordering = ["-ts"]
        verbose_name = "Erro"

    def __str__(self) -> str:
        return f"{self.ts} [{self.level}] {self.context}"

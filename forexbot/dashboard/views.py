"""Views do dashboard ForexBot v2."""
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from forexbot.dashboard.models import DecisionLog, ErrorLog, Trade

VALID_STRATEGIES = ("A", "B", "C")


def _win_rate(wins: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(wins / total * 100, 1)


def _closed_trades_qs():
    return Trade.objects.filter(closed_at__isnull=False)


def _trade_stats(qs) -> dict:
    closed = qs.filter(closed_at__isnull=False)
    total = closed.count()
    wins = closed.filter(pnl__gt=0).count()
    losses = closed.filter(pnl__lte=0, pnl__isnull=False).count()
    pnl = closed.aggregate(total=Sum("pnl"))["total"] or 0.0
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": _win_rate(wins, total),
        "pnl": round(pnl, 2),
    }


def _recent_errors_count() -> int:
    try:
        return ErrorLog.objects.filter(
            level="ERROR",
            ts__gte=timezone.now() - timedelta(hours=24),
        ).count()
    except Exception:
        return 0


@login_required
def index(request: HttpRequest) -> HttpResponse:
    """Página principal com resumo geral."""
    closed = _closed_trades_qs()
    total_trades = closed.count()
    wins = closed.filter(pnl__gt=0).count()
    losses = closed.filter(pnl__lte=0, pnl__isnull=False).count()
    total_pnl = closed.aggregate(total=Sum("pnl"))["total"] or 0.0
    open_count = Trade.objects.filter(closed_at__isnull=True).count()

    by_strategy = []
    for strat in VALID_STRATEGIES:
        stats = _trade_stats(Trade.objects.filter(strategy=strat))
        stats["strategy"] = strat
        by_strategy.append(stats)

    by_symbol = list(
        Trade.objects.filter(closed_at__isnull=False)
        .values("symbol")
        .annotate(
            total=Count("id", filter=Q(pnl__isnull=False)),
            wins=Count("id", filter=Q(pnl__gt=0)),
            losses=Count("id", filter=Q(pnl__lte=0, pnl__isnull=False)),
            pnl=Coalesce(Sum("pnl"), 0.0),
        )
        .filter(total__gt=0)
        .order_by("-total", "-pnl")[:10]
    )
    for row in by_symbol:
        row["win_rate"] = _win_rate(row["wins"], row["total"])
        row["pnl"] = round(float(row["pnl"]), 2)

    context = {
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": _win_rate(wins, total_trades),
        "total_pnl": round(total_pnl, 2),
        "open_count": open_count,
        "by_strategy": by_strategy,
        "by_symbol": by_symbol,
        "recent_trades": Trade.objects.all()[:20],
        "open_trades": Trade.objects.filter(closed_at__isnull=True),
        "recent_errors_count": _recent_errors_count(),
    }
    return render(request, "dashboard/index.html", context)


@login_required
def strategy_detail(request: HttpRequest, strategy: str) -> HttpResponse:
    """Detalhe de uma estratégia."""
    strategy = strategy.upper()
    if strategy not in VALID_STRATEGIES:
        raise Http404("Estratégia inválida")

    qs = Trade.objects.filter(strategy=strategy)
    closed = qs.filter(closed_at__isnull=False)
    stats = _trade_stats(qs)
    avg_pnl = closed.aggregate(avg=Avg("pnl"))["avg"] or 0.0
    best = closed.order_by("-pnl").first()
    worst = closed.order_by("pnl").first()

    context = {
        "strategy": strategy,
        "stats": stats,
        "avg_pnl": round(avg_pnl, 2),
        "best_trade": best,
        "worst_trade": worst,
        "trades": qs,
        "recent_errors_count": _recent_errors_count(),
    }
    return render(request, "dashboard/strategy.html", context)


@login_required
def logs_view(request: HttpRequest) -> HttpResponse:
    """Lista de decision logs com filtros."""
    qs = DecisionLog.objects.all()

    strategy = request.GET.get("strategy", "").upper()
    symbol = request.GET.get("symbol", "").upper()
    result = request.GET.get("result", "")
    date_str = request.GET.get("date", "")

    if strategy:
        qs = qs.filter(strategy=strategy)
    if symbol:
        qs = qs.filter(symbol=symbol)
    if result:
        qs = qs.filter(result=result)
    if date_str:
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
            qs = qs.filter(ts__date=day)
        except ValueError:
            pass

    paginator = Paginator(qs, 100)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page": page,
        "filters": {
            "strategy": strategy,
            "symbol": symbol,
            "result": result,
            "date": date_str,
        },
        "result_choices": ["SIGNAL", "NO_SIGNAL", "TRADE_OPEN", "TRADE_CLOSE"],
        "recent_errors_count": _recent_errors_count(),
    }
    return render(request, "dashboard/logs.html", context)


@login_required
def errors_view(request: HttpRequest) -> HttpResponse:
    """Lista de erros e avisos com filtros."""
    qs = ErrorLog.objects.all()

    level = request.GET.get("level", "").upper()
    context_filter = request.GET.get("context", "")
    date_str = request.GET.get("date", "")

    if level:
        qs = qs.filter(level=level)
    if context_filter:
        qs = qs.filter(context__icontains=context_filter)
    if date_str:
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
            qs = qs.filter(ts__date=day)
        except ValueError:
            pass

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page": page,
        "total_count": paginator.count,
        "filters": {
            "level": level,
            "context": context_filter,
            "date": date_str,
        },
        "level_choices": ["ERROR", "WARNING"],
        "recent_errors_count": _recent_errors_count(),
    }
    return render(request, "dashboard/errors.html", context)

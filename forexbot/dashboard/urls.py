"""URLs da app dashboard."""
from django.urls import path

from forexbot.dashboard import views

urlpatterns = [
    path("", views.index, name="index"),
    path("strategy/<str:strategy>/", views.strategy_detail, name="strategy_detail"),
    path("logs/", views.logs_view, name="logs"),
    path("errors/", views.errors_view, name="errors"),
]

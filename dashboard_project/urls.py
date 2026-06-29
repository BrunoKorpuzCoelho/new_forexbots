"""URLs do projeto Django."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("forexbot.dashboard.urls")),
    path("admin/", admin.site.urls),
]

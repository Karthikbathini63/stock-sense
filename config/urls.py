"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path
from inventory import views


urlpatterns = [
    path("admin/", admin.site.urls),

    # Team dashboard and stock log pages
    path("stockdash/", views.stockdash, name="stockdash"),
    path("stocklog/", views.stocklog, name="stocklog"),

    # Main dashboard
    path("", views.dashboard, name="dashboard"),
]
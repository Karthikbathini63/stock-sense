"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path
from inventory import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('stockdash/', views.stockdash, name='stockdash'),
    path('stocklog/', views.stocklog, name='stocklog'),
]

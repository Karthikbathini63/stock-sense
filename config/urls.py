"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path
from inventory import views


urlpatterns = [
    path("admin/", admin.site.urls),

    path("stockdash/", views.stockdash, name="stockdash"),
    path("stocklog/", views.stocklog, name="stocklog"),
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.add_product, name="add_product"),
    path("products/edit/<int:product_id>/", views.edit_product, name="edit_product"),
    path("products/delete/<int:product_id>/", views.delete_product, name="delete_product"),
    path("", views.dashboard, name="dashboard"),
]
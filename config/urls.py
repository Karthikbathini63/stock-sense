from django.contrib import admin
from django.urls import path
from inventory import views


urlpatterns = [
    path("admin/", admin.site.urls),

    # Dashboard
    path("stockdash/", views.stockdash, name="stockdash"),
    path("stock-ledger/", views.stock_ledger, name="stock_ledger"),
    path("receipts/", views.receipts, name="receipts"),
    path("transfers/", views.transfers, name="transfers"),
    path("adjustments/", views.adjustments, name="adjustments"),
    path("deliveries/", views.deliveries, name="deliveries"),

    # Product Management
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.add_product, name="add_product"),
    path(
        "products/edit/<int:product_id>/",
        views.edit_product,
        name="edit_product"
    ),
    path(
        "products/delete/<int:product_id>/",
        views.delete_product,
        name="delete_product"
    ),

    # Registration
    path("register/", views.register, name="register"),
    path(
        "send-registration-otp/",
        views.send_registration_otp,
        name="send_registration_otp"
    ),
    # Login
    path("login/", views.login, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Default page
    path("", views.dashboard, name="dashboard"),
]
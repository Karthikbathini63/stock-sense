from django.contrib import admin
from django.urls import path
from inventory import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('stockdash/', views.stockdash, name='stockdash'),
    path('stocklog/', views.stocklog, name='stocklog'),

    path('register/', views.register, name='register'),
    path('send-registration-otp/', views.send_registration_otp, name='send_registration_otp'),
]
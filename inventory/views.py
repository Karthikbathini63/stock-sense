
from django.shortcuts import render


def dashboard(request):
    return render(request, "inventory/dashboard.html")


def stockdash(request):
    return render(request, "inventory/stockdash.html")


def stocklog(request):
    return render(request, "inventory/stocklog.html")
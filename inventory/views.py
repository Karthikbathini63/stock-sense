from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
import secrets


def stockdash(request):
    return render(request, "inventory/stockdash.html")


def stocklog(request):
    return render(request, "inventory/stocklog.html")


def register(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        otp = request.POST.get("otp")

        if password != confirm_password:
            return render(
                request,
                "inventory/register.html",
                {"error": "Passwords do not match."}
            )

        if User.objects.filter(username=username).exists():
            return render(
                request,
                "inventory/register.html",
                {"error": "Username already exists."}
            )

        if User.objects.filter(email=email).exists():
            return render(
                request,
                "inventory/register.html",
                {"error": "Email already exists."}
            )

        saved_otp = request.session.get("registration_otp")

        if not saved_otp or otp != saved_otp:
            return render(
                request,
                "inventory/register.html",
                {"error": "Invalid OTP."}
            )

        User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        request.session.pop("registration_otp", None)

        return redirect("login")

    return render(request, "inventory/register.html")


def send_registration_otp(request):
    if request.method == "POST":
        email = request.POST.get("email")

        if not email:
            return JsonResponse({
                "success": False,
                "message": "Please enter your email."
            })

        otp = str(secrets.randbelow(900000) + 100000)

        request.session["registration_otp"] = otp

        send_mail(
            "StockSense Registration OTP",
            f"Your StockSense OTP is: {otp}\n\n"
            "This OTP is valid for 5 minutes.",
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

        return JsonResponse({
            "success": True,
            "message": "OTP sent successfully."
        })

    return JsonResponse({
        "success": False,
        "message": "Invalid request."
    })
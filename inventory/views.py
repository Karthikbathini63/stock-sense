from django.shortcuts import render, redirect
<<<<<<< HEAD
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
import secrets
=======
from .models import Product, Stock


def dashboard(request):
    return render(request, "inventory/dashboard.html")
>>>>>>> origin/main


def stockdash(request):

    stocks = Stock.objects.select_related("product")

    total_stock = sum(
        stock.quantity
        for stock in stocks
    )

    low_stock = sum(
        1
        for stock in stocks
        if 0 < stock.quantity <= stock.product.reorder_level
    )

    out_of_stock = sum(
        1
        for stock in stocks
        if stock.quantity == 0
    )

    return render(
        request,
        "inventory/stockdash.html",
        {
            "total_stock": total_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
        }
    )



def stocklog(request):
    return render(request, "inventory/stocklog.html")


<<<<<<< HEAD
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
=======
def product_list(request):
    products = Product.objects.all().order_by("name")

    return render(
        request,
        "inventory/product_list.html",
        {"products": products}
    )


def add_product(request):

    if request.method == "POST":
        sku = request.POST.get("sku")
        name = request.POST.get("name")
        category_id = request.POST.get("category")
        unit_of_measure = request.POST.get("unit_of_measure")
        description = request.POST.get("description")
        reorder_level = request.POST.get("reorder_level")

        Product.objects.create(
            sku=sku,
            name=name,
            category_id=category_id,
            unit_of_measure=unit_of_measure,
            description=description,
            reorder_level=reorder_level,
        )

        return redirect("product_list")

    from .models import Category
    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "inventory/add_product.html",
        {"categories": categories}
    )
def edit_product(request, product_id):

    product = Product.objects.get(id=product_id)

    if request.method == "POST":
        product.sku = request.POST.get("sku")
        product.name = request.POST.get("name")
        product.category_id = request.POST.get("category")
        product.unit_of_measure = request.POST.get("unit_of_measure")
        product.description = request.POST.get("description")
        product.reorder_level = request.POST.get("reorder_level")

        product.save()

        return redirect("product_list")

    from .models import Category
    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "inventory/edit_product.html",
        {
            "product": product,
            "categories": categories,
        }
    )


def delete_product(request, product_id):

    product = Product.objects.get(id=product_id)

    if request.method == "POST":
        product.delete()
        return redirect("product_list")

    return render(
        request,
        "inventory/delete_product.html",
        {"product": product}
    )
>>>>>>> origin/main

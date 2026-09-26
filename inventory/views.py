from django.shortcuts import render, redirect
from .models import Product, Stock


def dashboard(request):
    return render(request, "inventory/dashboard.html")


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
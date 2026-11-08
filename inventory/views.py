
import logging
import logging
import secrets

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, F, Q, Sum
from django.utils import timezone
from django.utils.html import escape

from .models import (
    Product,
    Category,
    Stock,
    StockTransaction,
    Location,
)

logger = logging.getLogger(__name__)

# OTP configuration
OTP_TTL_SECONDS = 300          # OTP valid for 5 minutes
OTP_RESEND_COOLDOWN = 45       # seconds before a new OTP can be requested


# =========================
# HELPERS
# =========================

def _otp_payload_is_valid(payload):
    if not isinstance(payload, dict):
        return False
    created_at = payload.get("created_at")
    if not isinstance(created_at, (int, float)):
        return False
    return (timezone.now().timestamp() - created_at) <= OTP_TTL_SECONDS


def parse_quantity(value):
    """Return (quantity, error). Quantity must be a positive whole number."""
    try:
        quantity = int(str(value).strip())
        if quantity <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, "Quantity must be a positive whole number."
    return quantity, None


# =========================
# DASHBOARD
# =========================

def dashboard(request):
    return redirect("stockdash")


@login_required
def stockdash(request):

    stocks = Stock.objects.select_related("product", "location")

    total_stock = stocks.aggregate(total=Sum("quantity"))["total"] or 0

    low_stock_products = [
        stock
        for stock in stocks
        if 0 < stock.quantity <= stock.product.reorder_level
    ]

    out_of_stock_products = [
        stock
        for stock in stocks
        if stock.quantity == 0
    ]

    recent_transactions = (
        StockTransaction.objects
        .select_related("product", "location", "created_by")
        .order_by("-created_at")[:10]
    )

    available_stock = (
        Stock.objects.select_related("product")
        .filter(
            quantity__gt=F("product__reorder_level")
        )
        .count()
    )

    delivered_total = (
        StockTransaction.objects
        .filter(transaction_type="DELIVERY")
        .aggregate(total=Sum("quantity"))["total"] or 0
    )

    return render(
        request,
        "inventory/stockdash.html",
        {
            "total_stock": total_stock,
            "total_products": Product.objects.count(),
            "total_categories": Category.objects.count(),
            "total_warehouses": Location.objects.values("warehouse").distinct().count(),
            "total_locations": Location.objects.count(),
            "total_transactions": StockTransaction.objects.count(),
            "delivery_count": StockTransaction.objects.filter(
                transaction_type="DELIVERY"
            ).count(),
            "delivered_total": delivered_total,
            "low_stock": len(low_stock_products),
            "low_stock_items": low_stock_products,
            "out_of_stock": len(out_of_stock_products),
            "out_of_stock_items": out_of_stock_products,
            "available_stock": available_stock,
            "recent_transactions": recent_transactions,
        }
    )


@login_required
def stock_ledger(request):
    transactions = (
        StockTransaction.objects
        .select_related("product", "location", "created_by")
        .order_by("-created_at")
    )

    return render(
        request,
        "inventory/stock_ledger.html",
        {"transactions": transactions}
    )


# =========================
# RECEIPTS
# =========================

@login_required
def receipts(request):

    if request.method == "POST":

        product_id = request.POST.get("product")
        location_id = request.POST.get("location")
        quantity_value = request.POST.get("quantity", "").strip()
        reference = request.POST.get("reference", "").strip()
        notes = request.POST.get("notes", "").strip()

        product = get_object_or_404(
            Product,
            pk=product_id
        )

        location = get_object_or_404(
            Location,
            pk=location_id
        )

        try:
            quantity = int(quantity_value)

            if quantity <= 0:
                raise ValueError

        except (TypeError, ValueError):
            return render(
                request,
                "inventory/receipts.html",
                {
                    "products": Product.objects.order_by("name"),
                    "locations": Location.objects.select_related(
                        "warehouse"
                    ).order_by("warehouse__name", "name"),
                    "error": "Quantity must be a positive whole number.",
                    "selected_product": product_id,
                    "selected_location": location_id,
                    "reference": reference,
                    "notes": notes,
                },
            )

        with transaction.atomic():

            stock, created = Stock.objects.get_or_create(
                product=product,
                location=location,
                defaults={"quantity": 0},
            )

            stock = Stock.objects.select_for_update().get(
                pk=stock.pk
            )

            stock.quantity += quantity

            stock.save(
                update_fields=["quantity"]
            )

            StockTransaction.objects.create(
                product=product,
                location=location,
                transaction_type="RECEIPT",
                quantity=quantity,
                reference=reference,
                notes=notes,
                created_by=request.user,
            )

        messages.success(
            request,
            f"Receipt recorded: {quantity} "
            f"{product.unit_of_measure} of {product.name}.",
        )

        return redirect("receipts")

    return render(
        request,
        "inventory/receipts.html",
        {
            "products": Product.objects.order_by("name"),
            "locations": Location.objects.select_related(
                "warehouse"
            ).order_by("warehouse__name", "name"),
        },
    )

# =========================
# DELIVERIES
# =========================

@login_required
def deliveries(request):

    if request.method == "POST":

        product_id = request.POST.get("product")
        location_id = request.POST.get("location")
        quantity_value = request.POST.get("quantity", "").strip()
        reference = request.POST.get("reference", "").strip()
        notes = request.POST.get("notes", "").strip()

        product = get_object_or_404(
            Product,
            pk=product_id
        )

        location = get_object_or_404(
            Location,
            pk=location_id
        )

        try:
            quantity = int(quantity_value)

            if quantity <= 0:
                raise ValueError

        except (TypeError, ValueError):
            return render(
                request,
                "inventory/deliveries.html",
                {
                    "products": Product.objects.order_by("name"),
                    "locations": Location.objects.select_related(
                        "warehouse"
                    ).order_by("warehouse__name", "name"),
                    "error": "Quantity must be a positive whole number.",
                    "selected_product": product_id,
                    "selected_location": location_id,
                    "reference": reference,
                    "notes": notes,
                },
            )

        with transaction.atomic():

            stock = (
                Stock.objects
                .select_for_update()
                .filter(product=product, location=location)
                .first()
            )

            if stock is None or stock.quantity < quantity:
                return render(
                    request,
                    "inventory/deliveries.html",
                    {
                        "products": Product.objects.order_by("name"),
                        "locations": Location.objects.select_related(
                            "warehouse"
                        ).order_by("warehouse__name", "name"),
                        "error": "Insufficient stock for this delivery.",
                        "selected_product": product_id,
                        "selected_location": location_id,
                        "quantity": quantity,
                        "reference": reference,
                        "notes": notes,
                    },
                )

            stock.quantity -= quantity
            stock.save(update_fields=["quantity"])

            StockTransaction.objects.create(
                product=product,
                location=location,
                transaction_type="DELIVERY",
                quantity=quantity,
                reference=reference,
                notes=notes,
                created_by=request.user,
            )

        messages.success(
            request,
            f"Delivery recorded: {quantity} "
            f"{product.unit_of_measure} of {product.name}.",
        )

        return redirect("deliveries")

    return render(
        request,
        "inventory/deliveries.html",
        {
            "products": Product.objects.order_by("name"),
            "locations": Location.objects.select_related(
                "warehouse"
            ).order_by("warehouse__name", "name"),
        },
    )
    
# =========================
# STOCK TRANSFERS
# =========================

@login_required
def transfers(request):

    if request.method == "POST":
        product_id = request.POST.get("product")
        source_id = request.POST.get("source_location")
        destination_id = request.POST.get("destination_location")
        quantity_value = request.POST.get("quantity", "").strip()
        reference = request.POST.get("reference", "").strip()
        notes = request.POST.get("notes", "").strip()

        products = Product.objects.order_by("name")
        locations = Location.objects.select_related(
            "warehouse"
        ).order_by("warehouse__name", "name")

        def show_error(message):
            return render(
                request,
                "inventory/transfers.html",
                {
                    "products": products,
                    "locations": locations,
                    "error": message,
                    "selected_product": product_id,
                    "selected_source": source_id,
                    "selected_destination": destination_id,
                    "quantity": quantity_value,
                    "reference": reference,
                    "notes": notes,
                },
            )

        if not product_id or not source_id or not destination_id:
            return show_error("Please select a product and both locations.")

        if source_id == destination_id:
            return show_error(
                "Source and destination locations must be different."
            )

        try:
            quantity = int(quantity_value)
            if quantity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return show_error(
                "Quantity must be a positive whole number."
            )

        product = get_object_or_404(Product, pk=product_id)
        source = get_object_or_404(Location, pk=source_id)
        destination = get_object_or_404(Location, pk=destination_id)

        with transaction.atomic():
            source_stock = (
                Stock.objects.select_for_update()
                .filter(product=product, location=source)
                .first()
            )

            if source_stock is None or source_stock.quantity < quantity:
                return show_error(
                    "Insufficient stock at the source location."
                )

            destination_stock, created = Stock.objects.get_or_create(
                product=product,
                location=destination,
                defaults={"quantity": 0},
            )

            source_stock.quantity -= quantity
            source_stock.save(update_fields=["quantity"])

            destination_stock.quantity += quantity
            destination_stock.save(update_fields=["quantity"])

            StockTransaction.objects.create(
                product=product,
                location=source,
                transaction_type="TRANSFER_OUT",
                quantity=quantity,
                reference=reference,
                notes=notes,
                created_by=request.user,
            )

            StockTransaction.objects.create(
                product=product,
                location=destination,
                transaction_type="TRANSFER_IN",
                quantity=quantity,
                reference=reference,
                notes=notes,
                created_by=request.user,
            )

        messages.success(
            request,
            f"Transferred {quantity} {product.unit_of_measure} "
            f"of {product.name} successfully."
        )
        return redirect("transfers")

    return render(
        request,
        "inventory/transfers.html",
        {
            "products": Product.objects.order_by("name"),
            "locations": Location.objects.select_related(
                "warehouse"
            ).order_by("warehouse__name", "name"),
        },
    )

    
# =========================
# STOCK ADJUSTMENTS
# =========================

@login_required
def adjustments(request):

    if request.method == "POST":
        product_id = request.POST.get("product")
        location_id = request.POST.get("location")
        adjustment_value = request.POST.get("adjustment", "").strip()
        reference = request.POST.get("reference", "").strip()
        notes = request.POST.get("notes", "").strip()

        products = Product.objects.order_by("name")
        locations = Location.objects.select_related(
            "warehouse"
        ).order_by("warehouse__name", "name")

        def show_error(message):
            return render(
                request,
                "inventory/adjustments.html",
                {
                    "products": products,
                    "locations": locations,
                    "error": message,
                    "selected_product": product_id,
                    "selected_location": location_id,
                    "adjustment": adjustment_value,
                    "reference": reference,
                    "notes": notes,
                },
            )

        if not product_id or not location_id:
            return show_error("Please select a product and location.")

        try:
            adjustment = int(adjustment_value)
            if adjustment == 0:
                raise ValueError
        except (TypeError, ValueError):
            return show_error(
                "Adjustment must be a non-zero whole number."
            )

        product = get_object_or_404(Product, pk=product_id)
        location = get_object_or_404(Location, pk=location_id)

        with transaction.atomic():
            stock = (
                Stock.objects.select_for_update()
                .filter(product=product, location=location)
                .first()
            )

            current_quantity = stock.quantity if stock else 0
            new_quantity = current_quantity + adjustment

            if new_quantity < 0:
                return show_error(
                    f"Insufficient stock. Current quantity is "
                    f"{current_quantity}; this adjustment would make "
                    "stock negative."
                )

            if stock is None:
                stock = Stock.objects.create(
                    product=product,
                    location=location,
                    quantity=new_quantity,
                )
            else:
                stock.quantity = new_quantity
                stock.save(update_fields=["quantity"])

            StockTransaction.objects.create(
                product=product,
                location=location,
                transaction_type="ADJUSTMENT",
                quantity=adjustment,
                reference=reference,
                notes=notes,
                created_by=request.user,
            )

        messages.success(
            request,
            f"Stock adjusted for {product.name}: "
            f"{adjustment:+d} {product.unit_of_measure}. "
            f"New quantity: {new_quantity}.",
        )
        return redirect("adjustments")

    return render(
        request,
        "inventory/adjustments.html",
        {
            "products": Product.objects.order_by("name"),
            "locations": Location.objects.select_related(
                "warehouse"
            ).order_by("warehouse__name", "name"),
        },
    )

# =========================
# REGISTRATION
# =========================

def _send_otp_email(email, otp):
    send_mail(
        "StockSense Registration OTP",
        f"Your StockSense OTP is: {otp}\n\n"
        f"This OTP is valid for {OTP_TTL_SECONDS // 60} minutes.",
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )


def register(request):

    if request.method == "POST":

        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        confirm_password = request.POST.get("confirm_password") or ""
        otp = (request.POST.get("otp") or "").strip()

        def show_error(message):
            return render(
                request,
                "inventory/register.html",
                {
                    "error": message,
                    "username": username,
                    "email": email,
                },
            )

        if password != confirm_password:
            return show_error("Passwords do not match.")

        if User.objects.filter(username__iexact=username).exists():
            return show_error("Username already exists.")

        if User.objects.filter(email__iexact=email).exists():
            return show_error("Email already exists.")

        saved = request.session.get("registration_otp")

        if not _otp_payload_is_valid(saved):
            return show_error(
                "No valid OTP found for this session. "
                "Click 'Send OTP' and use the latest email you "
                "received within the next 5 minutes."
            )

        if otp != saved.get("code"):
            return show_error(
                "Invalid OTP. Click 'Send OTP' to get a fresh code "
                "and use the latest email you received."
            )

        User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        request.session.pop("registration_otp", None)

        messages.success(
            request,
            "Account created successfully. Please log in."
        )
        return redirect("login")

    return render(
        request,
        "inventory/register.html"
    )


def send_registration_otp(request):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "Invalid request."
        }, status=405)

    email = (request.POST.get("email") or "").strip()

    if not email:
        return JsonResponse({
            "success": False,
            "message": "Please enter your email."
        })

    saved = request.session.get("registration_otp")

    if isinstance(saved, dict) and saved.get("last_sent_at"):
        remaining = int(
            OTP_RESEND_COOLDOWN - (timezone.now().timestamp() - saved["last_sent_at"])
        )

        if remaining > 0:
            return JsonResponse({
                "success": False,
                "message": f"Please wait {remaining}s before "
                           "requesting another OTP."
            }, status=429)

    otp = str(secrets.randbelow(900000) + 100000)

    try:
        _send_otp_email(email, otp)
    except Exception:
        logger.exception(
            "Failed to send registration OTP email to %s", email
        )
        return JsonResponse({
            "success": False,
            "message": "Unable to send OTP right now. "
                       "Please try again in a moment."
        }, status=500)

    # Only store the OTP once the email has actually been sent,
    # and replace any previous code so old OTPs cannot be reused.
    now_ts = timezone.now().timestamp()
    request.session["registration_otp"] = {
        "code": otp,
        "email": email,
        "created_at": now_ts,
        "last_sent_at": now_ts,
    }

    return JsonResponse({
        "success": True,
        "message": "OTP sent successfully."
    })


# =========================
# LOGIN / LOGOUT
# =========================

def login(request):

    if request.method == "POST":

        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        user = authenticate(
            request,
            username=username,
            password=password
        )

        # Allow logging in with the email address too.
        if user is None and "@" in username:
            matched = (
                User.objects
                .filter(email__iexact=username)
                .first()
            )
            if matched is not None:
                user = authenticate(
                    request,
                    username=matched.username,
                    password=password
                )

        # Fall back to a case-insensitive username match.
        if user is None:
            matched = (
                User.objects
                .filter(username__iexact=username)
                .first()
            )
            if matched is not None:
                user = authenticate(
                    request,
                    username=matched.username,
                    password=password
                )

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("stockdash")

        return render(
            request,
            "inventory/stocklog.html",
            {"error": "Invalid username or password."}
        )

    if request.user.is_authenticated:
        return redirect("stockdash")

    return render(
        request,
        "inventory/stocklog.html"
    )


@login_required
def logout_view(request):

    if request.method == "POST":
        auth_logout(request)
        messages.success(request, "You have been logged out.")
        return redirect("login")

    return redirect("stockdash")


# =========================
# PRODUCT MANAGEMENT
# =========================

@login_required
def product_list(request):

    search_query = (request.GET.get("q") or "").strip()

    products = Product.objects.select_related("category").order_by("name")

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(sku__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    paginator = Paginator(products, 10)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "inventory/product_list.html",
        {
            "page_obj": page_obj,
            "products": page_obj.object_list,
            "search_query": search_query,
        }
    )


def _validate_product_payload(sku, name, category_id, unit_of_measure,
                              reorder_level, existing_product=None):
    """Return (cleaned, error). Minimal server-side validation for products."""

    sku = (sku or "").strip()
    name = (name or "").strip()
    unit_of_measure = (unit_of_measure or "").strip()

    if not sku:
        return None, "SKU is required."
    if not name:
        return None, "Product name is required."
    if not unit_of_measure:
        return None, "Unit of measure is required."
    if not category_id:
        return None, "Please select a category."

    if not Category.objects.filter(pk=category_id).exists():
        return None, "Selected category does not exist."

    try:
        reorder_level = int(reorder_level or 0)
        if reorder_level < 0:
            raise ValueError
    except (TypeError, ValueError):
        return None, "Reorder level must be a non-negative whole number."

    duplicate_sku = Product.objects.filter(sku__iexact=sku)
    if existing_product is not None:
        duplicate_sku = duplicate_sku.exclude(pk=existing_product.pk)
    if duplicate_sku.exists():
        return None, f"A product with SKU '{sku}' already exists."

    cleaned = {
        "sku": sku,
        "name": name,
        "category_id": int(category_id),
        "unit_of_measure": unit_of_measure,
        "reorder_level": reorder_level,
    }
    return cleaned, None


@login_required
def add_product(request):

    if request.method == "POST":

        sku = request.POST.get("sku")
        name = request.POST.get("name")
        category_id = request.POST.get("category")
        unit_of_measure = request.POST.get("unit_of_measure")
        description = request.POST.get("description")
        reorder_level = request.POST.get("reorder_level")

        cleaned, error = _validate_product_payload(
            sku, name, category_id, unit_of_measure, reorder_level
        )

        if error:
            categories = Category.objects.all().order_by("name")
            return render(
                request,
                "inventory/add_product.html",
                {
                    "categories": categories,
                    "error": error,
                    "form_data": request.POST,
                },
            )

        Product.objects.create(
            sku=cleaned["sku"],
            name=cleaned["name"],
            category_id=cleaned["category_id"],
            unit_of_measure=cleaned["unit_of_measure"],
            description=description or "",
            reorder_level=cleaned["reorder_level"],
        )

        messages.success(request, f"Product '{cleaned['name']}' created.")
        return redirect("product_list")

    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "inventory/add_product.html",
        {"categories": categories}
    )


@login_required
def edit_product(request, product_id):

    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":

        sku = request.POST.get("sku")
        name = request.POST.get("name")
        category_id = request.POST.get("category")
        unit_of_measure = request.POST.get("unit_of_measure")
        description = request.POST.get("description")
        reorder_level = request.POST.get("reorder_level")

        cleaned, error = _validate_product_payload(
            sku, name, category_id, unit_of_measure, reorder_level,
            existing_product=product,
        )

        if error:
            categories = Category.objects.all().order_by("name")
            return render(
                request,
                "inventory/edit_product.html",
                {
                    "product": Product(sku=sku, name=name,
                                       description=description),
                    "categories": categories,
                    "error": error,
                    "form_data": request.POST,
                },
            )

        product.sku = cleaned["sku"]
        product.name = cleaned["name"]
        product.category_id = cleaned["category_id"]
        product.unit_of_measure = cleaned["unit_of_measure"]
        product.description = description or ""
        product.reorder_level = cleaned["reorder_level"]
        product.save()

        messages.success(request, f"Product '{cleaned['name']}' updated.")
        return redirect("product_list")

    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "inventory/edit_product.html",
        {
            "product": product,
            "categories": categories,
        }
    )


@login_required
def delete_product(request, product_id):

    product = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        try:
            product.delete()
        except ProtectedError:
            messages.error(
                request,
                f"Cannot delete '{product.name}'. It has stock transaction "
                "history. Use stock adjustments to correct quantities or "
                "keep the product for audit purposes.",
            )
            return redirect("product_list")

        messages.success(request, f"Product '{product.name}' deleted.")
        return redirect("product_list")

    return render(
        request,
        "inventory/delete_product.html",
        {"product": product}
    )
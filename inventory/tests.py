"""
Automated tests for StockSense.

Covers: authentication (registration + OTP + login + logout), product
management, stock receipts, deliveries, transfers (incl. atomicity),
adjustments, dashboard calculations, transaction history and route
protection.

All tests run against isolated test data - never the real development
records.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.db.models import Sum
from django.test import TestCase, override_settings
from django.urls import reverse

from inventory.models import (
    Product,
    Category,
    Stock,
    StockTransaction,
    Warehouse,
    Location,
)


class BaseTestData(TestCase):
    """Creates an isolated warehouse/location/category/product set."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="TestPass!2026",
        )
        cls.category = Category.objects.create(name="Electronics")
        cls.warehouse_a = Warehouse.objects.create(
            name="WH Alpha", code="WHA"
        )
        cls.warehouse_b = Warehouse.objects.create(
            name="WH Beta", code="WHB"
        )
        cls.location_a = Location.objects.create(
            warehouse=cls.warehouse_a, name="Rack A1", code="A1"
        )
        cls.location_b = Location.objects.create(
            warehouse=cls.warehouse_b, name="Rack B1", code="B1"
        )
        cls.product = Product.objects.create(
            sku="SKU-001",
            name="Test Product",
            category=cls.category,
            unit_of_measure="pcs",
            reorder_level=5,
        )

    def login_user(self):
        self.client.login(username="tester", password="TestPass!2026")


class RegistrationTests(TestCase):
    """Registration + email OTP verification."""

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def request_otp(self):
        response = self.client.post(
            reverse("send_registration_otp"), {"email": "new@example.com"}
        )
        return response

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_otp_email_is_sent_and_stored(self):
        response = self.request_otp()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("StockSense OTP is:", mail.outbox[0].body)

        payload = self.client.session.get("registration_otp")
        self.assertIsNotNone(payload)
        self.assertTrue(
            payload["code"].isdigit() and len(payload["code"]) == 6
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_success_flow(self):
        self.request_otp()
        otp = self.client.session["registration_otp"]["code"]
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password": "StrongPass!2026",
                "confirm_password": "StrongPass!2026",
                "otp": otp,
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(username="newuser").exists())
        # OTP must not be reusable
        self.assertNotIn("registration_otp", self.client.session)

    def test_registration_password_mismatch(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password": "abc",
                "confirm_password": "xyz",
                "otp": "123456",
            },
        )
        self.assertContains(response, "Passwords do not match.")
        self.assertFalse(User.objects.filter(username="newuser").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_expired_otp_rejected(self):
        self.request_otp()
        from django.utils import timezone
        from datetime import timedelta

        session = self.client.session
        session["registration_otp"]["created_at"] = (
            timezone.now().timestamp() - timedelta(minutes=11).total_seconds()
        )
        session.save()

        response = self.client.post(
            reverse("register"),
            {
                "username": "expireuser",
                "email": "new@example.com",
                "password": "StrongPass!2026",
                "confirm_password": "StrongPass!2026",
                "otp": session["registration_otp"]["code"],
            },
        )
        self.assertContains(response, "No valid OTP")
        self.assertFalse(User.objects.filter(username="expireuser").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_wrong_otp_rejected(self):
        self.request_otp()
        response = self.client.post(
            reverse("register"),
            {
                "username": "wrongotp",
                "email": "new@example.com",
                "password": "StrongPass!2026",
                "confirm_password": "StrongPass!2026",
                "otp": "000000",
            },
        )
        self.assertContains(response, "Invalid OTP")
        self.assertFalse(User.objects.filter(username="wrongotp").exists())

    def test_duplicate_username_blocked(self):
        User.objects.create_user(username="dup", password="x")
        response = self.client.post(
            reverse("register"),
            {
                "username": "Dup",  # case-insensitive
                "email": "other@example.com",
                "password": "p",
                "confirm_password": "p",
                "otp": "123456",
            },
        )
        self.assertContains(response, "Username already exists.")

    def test_duplicate_email_blocked(self):
        User.objects.create_user(username="dup", email="dup@example.com",
                                 password="x")
        response = self.client.post(
            reverse("register"),
            {
                "username": "other",
                "email": "DUP@example.com",
                "password": "p",
                "confirm_password": "p",
                "otp": "123456",
            },
        )
        self.assertContains(response, "Email already exists.")


class LoginLogoutTests(BaseTestData):

    def test_login_success_and_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": "tester", "password": "TestPass!2026"},
        )
        self.assertRedirects(response, reverse("stockdash"))

    def test_login_with_email(self):
        response = self.client.post(
            reverse("login"),
            {"username": "tester@example.com", "password": "TestPass!2026"},
        )
        self.assertRedirects(response, reverse("stockdash"))

    def test_login_case_insensitive_username(self):
        response = self.client.post(
            reverse("login"),
            {"username": "TESTER", "password": "TestPass!2026"},
        )
        self.assertRedirects(response, reverse("stockdash"))

    def test_login_wrong_password(self):
        response = self.client.post(
            reverse("login"),
            {"username": "tester", "password": "nope"},
        )
        self.assertContains(response, "Invalid username or password.")

    def test_login_nonexistent_user(self):
        response = self.client.post(
            reverse("login"),
            {"username": "ghost", "password": "whatever1"},
        )
        self.assertContains(response, "Invalid username or password.")

    def test_logout_ends_session(self):
        self.login_user()
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        response = self.client.get(reverse("stockdash"))
        self.assertEqual(response.status_code, 302)


class RouteProtectionTests(TestCase):
    """Private pages must redirect anonymous users to /login/."""

    PROTECTED_ROUTES = [
        "stockdash",
        "stock_ledger",
        "receipts",
        "deliveries",
        "transfers",
        "adjustments",
        "product_list",
        "add_product",
        "logout",
    ]

    def test_anonymous_users_are_redirected(self):
        for name in self.PROTECTED_ROUTES:
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(
                    response.status_code,
                    302,
                    f"{name} should redirect",
                )
                self.assertTrue(
                    response.url.startswith("/login/"),
                    f"{name} should redirect to /login/",
                )

    def test_public_routes_are_open(self):
        for name in ["login", "register"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)

    def test_delete_product_requires_login(self):
        category = Category.objects.create(name="Tmp Cat")
        product = Product.objects.create(
            sku="T1",
            name="T",
            category=category,
        )
        response = self.client.get(
            reverse("delete_product", args=[product.id])
        )
        self.assertEqual(response.status_code, 302)


class ProductTests(BaseTestData):

    def setUp(self):
        self.login_user()

    def test_product_list_shows_products(self):
        response = self.client.get(reverse("product_list"))
        self.assertContains(response, "Test Product")

    def test_product_search(self):
        response = self.client.get(
            reverse("product_list"), {"q": "Test"}
        )
        self.assertContains(response, "Test Product")
        response = self.client.get(
            reverse("product_list"), {"q": "doesnotexist"}
        )
        self.assertContains(response, "No products match")

    def test_add_product_success(self):
        response = self.client.post(
            reverse("add_product"),
            {
                "sku": "SKU-002",
                "name": "Second Product",
                "category": self.category.id,
                "unit_of_measure": "kg",
                "description": "desc",
                "reorder_level": "3",
            },
        )
        self.assertRedirects(response, reverse("product_list"))
        self.assertTrue(Product.objects.filter(sku="SKU-002").exists())

    def test_add_product_duplicate_sku_rejected(self):
        response = self.client.post(
            reverse("add_product"),
            {
                "sku": "sku-001",  # case-insensitive duplicate
                "name": "CopyCat",
                "category": self.category.id,
                "unit_of_measure": "pcs",
                "reorder_level": "0",
            },
        )
        self.assertContains(response, "already exists")
        self.assertEqual(
            Product.objects.filter(name="CopyCat").count(), 0
        )

    def test_add_product_invalid_reorder_level(self):
        response = self.client.post(
            reverse("add_product"),
            {
                "sku": "SKU-003",
                "name": "Third",
                "category": self.category.id,
                "unit_of_measure": "pcs",
                "reorder_level": "-5",
            },
        )
        self.assertContains(response, "non-negative whole number")
        self.assertFalse(Product.objects.filter(sku="SKU-003").exists())

    def test_edit_product_success(self):
        response = self.client.post(
            reverse("edit_product", args=[self.product.id]),
            {
                "sku": self.product.sku,
                "name": "Renamed Product",
                "category": self.category.id,
                "unit_of_measure": "pcs",
                "description": "",
                "reorder_level": self.product.reorder_level,
            },
        )
        self.assertRedirects(response, reverse("product_list"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Renamed Product")

    def test_edit_product_keep_same_sku_allowed(self):
        response = self.client.post(
            reverse("edit_product", args=[self.product.id]),
            {
                "sku": "SKU-001",
                "name": "Same SKU Rename",
                "category": self.category.id,
                "unit_of_measure": "pcs",
                "description": "",
                "reorder_level": self.product.reorder_level,
            },
        )
        self.assertRedirects(response, reverse("product_list"))

    def test_delete_product_without_transactions(self):
        product = Product.objects.create(
            sku="SKU-DEL", name="Delete Me",
            category=self.category, unit_of_measure="pcs",
        )
        response = self.client.post(
            reverse("delete_product", args=[product.id])
        )
        self.assertRedirects(response, reverse("product_list"))
        self.assertFalse(Product.objects.filter(pk=product.id).exists())

    def test_delete_product_with_transactions_is_blocked_not_500(self):
        Stock.objects.create(
            product=self.product, location=self.location_a, quantity=10
        )
        StockTransaction.objects.create(
            product=self.product, location=self.location_a,
            transaction_type="RECEIPT", quantity=10, created_by=self.user,
        )
        response = self.client.post(
            reverse("delete_product", args=[self.product.id])
        )
        self.assertRedirects(response, reverse("product_list"))
        self.assertTrue(Product.objects.filter(pk=self.product.id).exists())


class StockOperationTests(BaseTestData):
    """Receipts, deliveries, transfers, adjustments + ledger."""

    def setUp(self):
        self.login_user()

    def stock(self, quantity):
        return Stock.objects.create(
            product=self.product, location=self.location_a, quantity=quantity
        )

    # ---------- RECEIPT ----------

    def test_receipt_increases_stock_and_creates_transaction(self):
        stock = self.stock(5)
        response = self.client.post(
            reverse("receipts"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "quantity": "10",
                "reference": "PO-1",
                "notes": "note",
            },
        )
        self.assertRedirects(response, reverse("receipts"))
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 15)
        self.assertTrue(
            StockTransaction.objects.filter(
                product=self.product,
                location=self.location_a,
                transaction_type="RECEIPT",
                quantity=10,
            ).exists()
        )

    def test_receipt_invalid_quantity(self):
        response = self.client.post(
            reverse("receipts"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "quantity": "-3",
            },
        )
        self.assertContains(response, "positive whole number")
        self.assertFalse(
            StockTransaction.objects.filter(transaction_type="RECEIPT",
                                            created_by=self.user).exists()
        )

    def test_receipt_creates_missing_stock_record(self):
        # no stock row yet: receipt must create it
        response = self.client.post(
            reverse("receipts"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "quantity": "4",
            },
        )
        self.assertRedirects(response, reverse("receipts"))
        self.assertEqual(
            Stock.objects.get(
                product=self.product, location=self.location_a
            ).quantity,
            4,
        )

    # ---------- DELIVERY ----------

    def test_delivery_decreases_stock(self):
        stock = self.stock(10)
        response = self.client.post(
            reverse("deliveries"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "quantity": "6",
                "reference": "SO-1",
            },
        )
        self.assertRedirects(response, reverse("deliveries"))
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 4)
        self.assertTrue(
            StockTransaction.objects.filter(
                transaction_type="DELIVERY", quantity=6
            ).exists()
        )

    def test_delivery_insufficient_stock_blocked(self):
        stock = self.stock(3)
        response = self.client.post(
            reverse("deliveries"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "quantity": "5",
            },
        )
        self.assertContains(response, "Insufficient stock")
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 3)
        self.assertFalse(
            StockTransaction.objects.filter(
                transaction_type="DELIVERY", created_by=self.user
            ).exists()
        )

    def test_delivery_on_missing_stock_record_blocked(self):
        response = self.client.post(
            reverse("deliveries"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "quantity": "1",
            },
        )
        self.assertContains(response, "Insufficient stock")
        self.assertFalse(
            Stock.objects.filter(
                product=self.product, location=self.location_a
            ).exists()
        )

    # ---------- TRANSFER ----------

    def test_transfer_moves_stock_and_logs_both_transactions(self):
        source = self.stock(10)
        response = self.client.post(
            reverse("transfers"),
            {
                "product": self.product.id,
                "source_location": self.location_a.id,
                "destination_location": self.location_b.id,
                "quantity": "7",
                "reference": "TR-1",
            },
        )
        self.assertRedirects(response, reverse("transfers"))

        source.refresh_from_db()
        destination = Stock.objects.get(
            product=self.product, location=self.location_b
        )
        self.assertEqual(source.quantity, 3)
        self.assertEqual(destination.quantity, 7)

        types = list(
            StockTransaction.objects.filter(created_by=self.user)
            .values_list("transaction_type", "quantity")
        )
        self.assertEqual(
            types, [("TRANSFER_OUT", 7), ("TRANSFER_IN", 7)]
        )

    def test_transfer_insufficient_source_blocked(self):
        source = self.stock(2)
        response = self.client.post(
            reverse("transfers"),
            {
                "product": self.product.id,
                "source_location": self.location_a.id,
                "destination_location": self.location_b.id,
                "quantity": "5",
            },
        )
        self.assertContains(response, "Insufficient stock")
        source.refresh_from_db()
        self.assertEqual(source.quantity, 2)
        self.assertFalse(
            StockTransaction.objects.filter(
                transaction_type__in=["TRANSFER_IN", "TRANSFER_OUT"],
                created_by=self.user,
            ).exists()
        )

    def test_transfer_same_location_blocked(self):
        self.stock(10)
        response = self.client.post(
            reverse("transfers"),
            {
                "product": self.product.id,
                "source_location": self.location_a.id,
                "destination_location": self.location_a.id,
                "quantity": "5",
            },
        )
        self.assertContains(response, "must be different")

    def test_transfer_zero_quantity_blocked(self):
        self.stock(10)
        response = self.client.post(
            reverse("transfers"),
            {
                "product": self.product.id,
                "source_location": self.location_a.id,
                "destination_location": self.location_b.id,
                "quantity": "0",
            },
        )
        self.assertContains(response, "positive whole number")

    def test_transfer_atomicity_no_partial_transfer(self):
        """If the destination write fails, the source must be untouched."""
        self.stock(10)
        original_create = StockTransaction.objects.create

        calls = {"n": 0}

        def flaky_create(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:  # fail on the second (TRANSFER_IN) write
                raise RuntimeError("simulated DB failure")
            return original_create(*args, **kwargs)

        with patch("inventory.views.StockTransaction.objects.create",
                   side_effect=flaky_create):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("transfers"),
                    {
                        "product": self.product.id,
                        "source_location": self.location_a.id,
                        "destination_location": self.location_b.id,
                        "quantity": "4",
                    },
                )

        source = Stock.objects.get(
            product=self.product, location=self.location_a
        )
        self.assertEqual(source.quantity, 10, "source must be restored")
        self.assertFalse(
            Stock.objects.filter(
                product=self.product, location=self.location_b
            ).exists()
        )
        self.assertEqual(
            StockTransaction.objects.filter(
                transaction_type__in=["TRANSFER_IN", "TRANSFER_OUT"],
                created_by=self.user,
            ).count(),
            0,
        )

    # ---------- ADJUSTMENT ----------

    def test_positive_adjustment(self):
        stock = self.stock(10)
        response = self.client.post(
            reverse("adjustments"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "adjustment": "+3",
                "reference": "AD-1",
                "notes": "cycle count",
            },
        )
        self.assertRedirects(response, reverse("adjustments"))
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 13)
        self.assertTrue(
            StockTransaction.objects.filter(
                transaction_type="ADJUSTMENT", quantity=3
            ).exists()
        )

    def test_negative_adjustment(self):
        stock = self.stock(10)
        response = self.client.post(
            reverse("adjustments"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "adjustment": "-4",
            },
        )
        self.assertRedirects(response, reverse("adjustments"))
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 6)

    def test_adjustment_prevents_negative_stock(self):
        stock = self.stock(2)
        response = self.client.post(
            reverse("adjustments"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "adjustment": "-10",
            },
        )
        self.assertContains(response, "would make stock negative")
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 2)

    def test_adjustment_creates_missing_stock_record(self):
        response = self.client.post(
            reverse("adjustments"),
            {
                "product": self.product.id,
                "location": self.location_a.id,
                "adjustment": "5",
            },
        )
        self.assertRedirects(response, reverse("adjustments"))
        self.assertEqual(
            Stock.objects.get(
                product=self.product, location=self.location_a
            ).quantity,
            5,
        )

    # ---------- LEDGER / DASHBOARD / HISTORY ----------

    def test_ledger_requires_login_and_renders(self):
        response = self.client.get(reverse("stock_ledger"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_counts_from_database(self):
        self.stock(10)
        Stock.objects.create(
            product=self.product, location=self.location_b, quantity=0
        )
        response = self.client.get(reverse("stockdash"))
        self.assertEqual(
            response.context["total_stock"], 10
        )
        self.assertEqual(response.context["out_of_stock"], 1)
        self.assertEqual(response.context["total_products"], 1)

    def test_dashboard_low_stock_detection(self):
        self.stock(3)  # reorder_level is 5 -> low stock
        response = self.client.get(reverse("stockdash"))
        self.assertEqual(response.context["low_stock"], 1)

    def test_transaction_history_consistency(self):
        self.stock(0)
        # receipt +10, delivery -4 => stock should be 6 and history readable
        self.client.post(
            reverse("receipts"),
            {"product": self.product.id, "location": self.location_a.id,
             "quantity": "10"},
        )
        self.client.post(
            reverse("deliveries"),
            {"product": self.product.id, "location": self.location_a.id,
             "quantity": "4"},
        )
        stock = Stock.objects.get(
            product=self.product, location=self.location_a
        )
        receipts = StockTransaction.objects.filter(
            product=self.product, transaction_type="RECEIPT"
        ).aggregate(total=Sum("quantity"))["total"] or 0
        deliveries = StockTransaction.objects.filter(
            product=self.product, transaction_type="DELIVERY"
        ).aggregate(total=Sum("quantity"))["total"] or 0
        self.assertEqual(stock.quantity, receipts - deliveries)

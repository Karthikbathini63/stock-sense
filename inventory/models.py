from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Warehouse(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Location(models.Model):
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="locations"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "code"],
                name="unique_location_code_per_warehouse",
            ),
        ]
        indexes = [
            models.Index(fields=["warehouse"]),
        ]

    def __str__(self):
        return f"{self.warehouse.name} - {self.name}"


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products"
    )
    unit_of_measure = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    reorder_level = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.sku} - {self.name}"


class Stock(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_records"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="stock_records"
    )
    quantity = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "location"],
                name="unique_product_location"
            ),
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name="stock_quantity_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["location"]),
        ]

    def __str__(self):
        return f"{self.product.sku} - {self.location.name}: {self.quantity}"
        
class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("RECEIPT", "Receipt"),
        ("DELIVERY", "Delivery"),
        ("TRANSFER_IN", "Transfer In"),
        ("TRANSFER_OUT", "Transfer Out"),
        ("ADJUSTMENT", "Adjustment"),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="transactions"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="transactions"
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    quantity = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.transaction_type} - "
            f"{self.product.sku} - {self.quantity}"
        )

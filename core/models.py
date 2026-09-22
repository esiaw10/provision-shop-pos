from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


# ============================================================
# STORE
# ============================================================

class Store(models.Model):

    name = models.CharField(
        max_length=150,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    address = models.CharField(
        max_length=255,
        blank=True,
    )

    active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# USER
# ============================================================

class User(AbstractUser):

    ROLE_CHOICES = [
        ("ADMIN", "Administrator"),
        ("MANAGER", "Store Manager"),
        ("ATTENDANT", "Attendant"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="ATTENDANT",
    )

    store = models.ForeignKey(
        Store,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="core_user_set",
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )

    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="core_user_permissions_set",
        blank=True,
        help_text="Specific user permissions.",
        verbose_name="user permissions",
    )

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.username


# ============================================================
# CATEGORY
# ============================================================

class Category(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================
# PRODUCT
# ============================================================

class Product(models.Model):

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="products",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    name = models.CharField(
        max_length=200,
    )

    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    stock = models.PositiveIntegerField(
        default=0,
    )

    low_stock_threshold = models.PositiveIntegerField(
        default=20,
    )

    barcode = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["name"]

        indexes = [
            models.Index(
                fields=["store", "active"],
            ),
            models.Index(
                fields=["store", "name"],
            ),
            models.Index(
                fields=["store", "barcode"],
            ),
        ]

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold

    def __str__(self):
        return self.name


# ============================================================
# SALE
# ============================================================

class Sale(models.Model):

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="sales",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sales",
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    sold_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="sales",
    )

    sold_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        ordering = ["-sold_at"]

        indexes = [
            models.Index(
                fields=["store", "sold_at"],
            ),
            models.Index(
                fields=["store", "product"],
            ),
        ]

    @property
    def total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.quantity} - "
            f"{self.total}"
        )


# ============================================================
# STOCK MOVEMENT
# ============================================================

class StockMovement(models.Model):

    MOVEMENT_TYPES = (
        ("SALE", "Sale"),
        ("RESTOCK", "Restock"),
        ("ADJUSTMENT", "Adjustment"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPES,
    )

    quantity = models.IntegerField()

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    note = models.CharField(
        max_length=255,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["store", "created_at"],
            ),
            models.Index(
                fields=["store", "movement_type"],
            ),
            models.Index(
                fields=["product", "created_at"],
            ),
        ]

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.movement_type} - "
            f"{self.quantity}"
        )

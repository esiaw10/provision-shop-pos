from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Store(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


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
    )

    # 🚀 Crucial fix to resolve the core database accessor clashes
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
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

    def __str__(self):
        return self.username


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=150)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
    )

    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    stock = models.PositiveIntegerField(default=0)

    low_stock_threshold = models.PositiveIntegerField(
        default=20,
    )

    barcode = models.CharField(
        max_length=100,
        blank=True,
    )

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold


class Sale(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    sold_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
    )

    sold_at = models.DateTimeField(
        default=timezone.now,
    )

    @property
    def total(self):
        return self.quantity * self.unit_price


class StockMovement(models.Model):
    MOVEMENT_TYPES = (
        ("SALE", "Sale"),
        ("RESTOCK", "Restock"),
        ("ADJUSTMENT", "Adjustment"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPES,
    )

    # IntegerField allows both stock additions and deductions.
    quantity = models.IntegerField()

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    note = models.CharField(
        max_length=255,
        blank=True,
    )

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.movement_type} - "
            f"{self.quantity}"
        )

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Category, Product, Sale, StockMovement, Store, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "store",
        "is_staff",
    )

    list_filter = (
        "role",
        "store",
        "is_staff",
        "is_superuser",
        "is_active",
    )

    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
    )

    ordering = ("username",)

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            _("Store Assignment & Roles"),
            {
                "fields": ("role", "store"),
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            _("Store Assignment & Roles"),
            {
                "classes": ("wide",),
                "fields": ("role", "store"),
            },
        ),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "product_count")
    search_fields = ("name",)

    @admin.display(description="Total Products")
    def product_count(self, obj):
        return obj.product_set.count()


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "active")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "store",
        "category",
        "stock",
        "selling_price",
        "low_stock_status",
    )

    list_filter = ("store", "category", "active")
    search_fields = ("name", "barcode")

    actions = ["reset_stock_to_hundred"]

    @admin.display(description="Stock Health")
    def low_stock_status(self, obj):
        if obj.stock <= obj.low_stock_threshold:
            return "⚠️ Low Stock Alert"

        return "✅ Healthy"

    @admin.action(description="Bulk restock selected items to 100 units")
    def reset_stock_to_hundred(self, request, queryset):
        queryset.update(stock=100)

        self.message_user(
            request,
            "Selected inventory profiles updated successfully.",
        )


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "store",
        "quantity",
        "unit_price",
        "calculated_total",
        "sold_at",
    )

    list_filter = (
        "store",
        "sold_at",
        "sold_by",
    )

    date_hierarchy = "sold_at"

    readonly_fields = ("sold_at",)

    @admin.display(description="Total (GH₵)")
    def calculated_total(self, obj):
        return f"GH₵ {obj.total:,.2f}"


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "store",
        "movement_type",
        "quantity",
        "user",
        "created_at",
    )

    list_filter = (
        "store",
        "movement_type",
        "created_at",
    )

    date_hierarchy = "created_at"

    readonly_fields = ("created_at",)

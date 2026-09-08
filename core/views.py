import datetime
import json
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Product, Sale, StockMovement


logger = logging.getLogger(__name__)


def get_current_store(request):
    """Return the signed-in user's store, or None if not assigned."""
    try:
        return request.user.store
    except ObjectDoesNotExist:
        return None


@login_required
def dashboard(request):
    """Dashboard summary with current week Sunday-Saturday sales."""
    store = get_current_store(request)

    if not store:
        return render(request, "core/no_store.html")

    active_products_count = Product.objects.filter(
        store=store,
        active=True
    ).count()

    total_sales = sum(
        (sale.total for sale in Sale.objects.filter(store=store)),
        Decimal("0.00")
    )

    # Current week: Sunday to Saturday
    today = timezone.localdate()

    # Python weekday(): Monday=0 ... Sunday=6
    days_since_sunday = (today.weekday() + 1) % 7

    week_start = today - datetime.timedelta(days=days_since_sunday)
    week_end = week_start + datetime.timedelta(days=6)

    # Get all sales for the current Sunday-Saturday week
    weekly_sales = Sale.objects.filter(
        store=store,
        sold_at__date__gte=week_start,
        sold_at__date__lte=week_end,
    )

    # Create seven rows: Sunday through Saturday
    weekly_sales_data = []

    for i in range(7):
        current_day = week_start + datetime.timedelta(days=i)

        day_sales = sum(
            (
                sale.total
                for sale in weekly_sales
                if timezone.localtime(sale.sold_at).date() == current_day
            ),
            Decimal("0.00")
        )

        weekly_sales_data.append({
            "day": current_day.strftime("%A"),
            "date": current_day.strftime("%Y-%m-%d"),
            "amount": day_sales,
        })

    return render(
        request,
        "core/dashboard.html",
        {
            "active_products_count": active_products_count,
            "total_sales": total_sales,
            "weekly_sales_data": weekly_sales_data,
            "week_start": week_start,
            "week_end": week_end,
        }
    )


@login_required
def daily_sales(request):
    """Show an itemized sales ledger for the selected date."""
    store = get_current_store(request)

    if not store:
        return render(request, "core/no_store.html")

    date_value = request.GET.get("date", "")

    try:
        selected_date = (
            datetime.datetime.strptime(date_value, "%Y-%m-%d").date()
            if date_value
            else timezone.localdate()
        )
    except ValueError:
        selected_date = timezone.localdate()

    sales = Sale.objects.filter(
        store=store,
        sold_at__date=selected_date,
    ).select_related(
        "product",
        "sold_by"
    ).order_by("-sold_at")

    daily_total = sum(
        (sale.total for sale in sales),
        Decimal("0.00")
    )

    return render(
        request,
        "core/daily_sales.html",
        {
            "sales": sales,
            "selected_date": selected_date,
            "daily_total": daily_total,
        }
    )


@login_required
def pos(request):
    store = get_current_store(request)

    if not store:
        return render(request, "core/no_store.html")

    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()

    products = Product.objects.filter(
        store=store,
        active=True
    ).select_related("category")

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(barcode__icontains=query)
        )

    if category:
        products = products.filter(category__name=category)

    categories = list(
        Product.objects.filter(
            store=store,
            active=True,
            category__name__isnull=False
        ).order_by(
            "category__name"
        ).values_list(
            "category__name",
            flat=True
        ).distinct()
    )

    return render(
        request,
        "core/pos.html",
        {
            "products": products.order_by("name"),
            "categories": categories,
            "selected_category": category,
            "query": query,
        }
    )


@login_required
@require_POST
def sell_one(request, product_id):
    store = get_current_store(request)

    if not store:
        return JsonResponse(
            {"ok": False, "error": "No store assigned."},
            status=400
        )

    with transaction.atomic():
        product = get_object_or_404(
            Product.objects.select_for_update(),
            pk=product_id,
            store=store,
            active=True,
        )

        if product.stock <= 0:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Out of stock",
                    "stock": 0
                },
                status=400
            )

        product.stock -= 1
        product.save(update_fields=["stock"])

        Sale.objects.create(
            store=store,
            product=product,
            quantity=1,
            unit_price=product.selling_price,
            sold_by=request.user,
        )

        StockMovement.objects.create(
            product=product,
            store=store,
            movement_type="SALE",
            quantity=-1,
            user=request.user,
            note="POS sale",
        )

    return JsonResponse(
        {
            "ok": True,
            "stock": product.stock,
            "low_stock": product.is_low_stock,
            "message": f"{product.name} sold",
        }
    )


@login_required
def restock(request):
    store = get_current_store(request)

    if not store:
        return render(request, "core/no_store.html")

    products = Product.objects.filter(
        store=store,
        active=True
    ).order_by("name")

    if request.method == "POST":
        product_id = request.POST.get("product")
        note = request.POST.get("note", "").strip()

        try:
            quantity = int(request.POST.get("quantity"))

            if quantity <= 0:
                raise ValueError

        except (TypeError, ValueError):
            messages.error(
                request,
                "Please enter a quantity greater than zero."
            )
            return redirect("restock")

        with transaction.atomic():
            product = get_object_or_404(
                Product.objects.select_for_update(),
                id=product_id,
                store=store,
                active=True
            )

            product.stock += quantity
            product.save(update_fields=["stock"])

            StockMovement.objects.create(
                product=product,
                store=store,
                movement_type="RESTOCK",
                quantity=quantity,
                user=request.user,
                note=note,
            )

        messages.success(
            request,
            f"{product.name} restocked by {quantity}. New stock: {product.stock}"
        )

        return redirect("restock")

    return render(
        request,
        "core/restock.html",
        {"products": products}
    )


@login_required
@require_POST
def process_cart_sale(request):
    """Validate the full cart, then deduct all items in one transaction."""

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"ok": False, "error": "Invalid sale data."},
            status=400
        )

    cart_items = payload.get("items") if isinstance(payload, dict) else None

    if not isinstance(cart_items, list) or not cart_items:
        return JsonResponse(
            {"ok": False, "error": "Your cart is empty."},
            status=400
        )

    quantities = {}

    try:
        for item in cart_items:
            product_id = int(item["id"])
            quantity = int(item["quantity"])

            if product_id <= 0 or quantity <= 0:
                raise ValueError

            quantities[product_id] = quantities.get(product_id, 0) + quantity

    except (KeyError, TypeError, ValueError):
        return JsonResponse(
            {
                "ok": False,
                "error": "Each cart item needs a valid product and quantity."
            },
            status=400
        )

    store = get_current_store(request)

    if not store:
        return JsonResponse(
            {"ok": False, "error": "No store assigned."},
            status=400
        )

    try:
        with transaction.atomic():
            product_ids = sorted(quantities)

            products = list(
                Product.objects.select_for_update().filter(
                    id__in=product_ids,
                    store=store,
                    active=True
                ).order_by("id")
            )

            products_by_id = {
                product.id: product
                for product in products
            }

            if set(product_ids) != set(products_by_id):
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "One or more products are unavailable."
                    },
                    status=404
                )

            # Check every item before changing any stock.
            for product_id in product_ids:
                product = products_by_id[product_id]

                if product.stock < quantities[product_id]:
                    return JsonResponse(
                        {
                            "ok": False,
                            "error": f"Insufficient inventory for {product.name}."
                        },
                        status=400
                    )

            updates = []

            for product_id in product_ids:
                product = products_by_id[product_id]
                quantity = quantities[product_id]

                product.stock -= quantity
                product.save(update_fields=["stock"])

                Sale.objects.create(
                    store=store,
                    product=product,
                    quantity=quantity,
                    unit_price=product.selling_price,
                    sold_by=request.user,
                )

                StockMovement.objects.create(
                    product=product,
                    store=store,
                    movement_type="SALE",
                    quantity=-quantity,
                    user=request.user,
                    note="POS cart sale",
                )

                updates.append(
                    {
                        "id": product.id,
                        "new_stock": product.stock,
                        "is_low": product.stock <= product.low_stock_threshold,
                    }
                )

        return JsonResponse(
            {
                "ok": True,
                "updates": updates
            }
        )

    except Exception:
        logger.exception("POS cart sale failed")

        return JsonResponse(
            {
                "ok": False,
                "error": "The sale could not be completed. Please try again."
            },
            status=500
        )


def custom_logout_view(request):
    auth_logout(request)
    return redirect("login")

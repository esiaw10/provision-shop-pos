import datetime
import json
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    logout as auth_logout,
)
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password

from .forms import ProductForm
from .models import (
    Product,
    Sale,
    StockMovement,
    Store,
    User,
    Category,
)
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

logger = logging.getLogger(__name__)

User = get_user_model()


def signup(request):

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":

        store_name = request.POST.get("store_name", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        # -----------------------------
        # VALIDATION
        # -----------------------------

        if not store_name:
            messages.error(request, "Please enter your shop name.")
            return redirect("signup")

        if not first_name:
            messages.error(request, "Please enter your first name.")
            return redirect("signup")

        if not username:
            messages.error(request, "Please enter a username.")
            return redirect("signup")

        if not password:
            messages.error(request, "Please enter a password.")
            return redirect("signup")

        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return redirect("signup")

        if len(password) < 8:
            messages.error(
                request,
                "Password must contain at least 8 characters."
            )
            return redirect("signup")

        if User.objects.filter(username__iexact=username).exists():
            messages.error(
                request,
                "That username is already in use. Please choose another."
            )
            return redirect("signup")

        # -----------------------------
        # PASSWORD VALIDATION
        # -----------------------------

        temp_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )

        try:
            validate_password(password, temp_user)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)

            return redirect("signup")

        # -----------------------------
        # CREATE STORE + USER
        # -----------------------------

        with transaction.atomic():

            store = Store.objects.create(
                name=store_name,
                active=True,
            )

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

            user.role = "ADMIN"
            user.store = store
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            user.save(
                update_fields=[
                    "role",
                    "store",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ]
            )

        # -----------------------------
        # LOG USER IN
        # -----------------------------

        login(request, user)

        messages.success(
            request,
            f"Welcome to {store.name}! Your shop account has been created."
        )

        return redirect("dashboard")

    return render(request, "core/signup.html")

# ============================================================
# ROLE HELPERS
# ============================================================


def is_main_admin(user):
    """
    The main Super Admin of the entire POS system.
    """
    return user.is_authenticated and user.is_superuser


def is_store_admin(user):
    """
    Store ADMIN role.
    """
    return (
        user.is_authenticated
        and not user.is_superuser
        and user.role == "ADMIN"
    )


def is_manager(user):
    """
    Store Manager role.
    """
    return (
        user.is_authenticated
        and not user.is_superuser
        and user.role == "MANAGER"
    )


def is_attendant(user):
    """
    Store Attendant role.
    """
    return (
        user.is_authenticated
        and not user.is_superuser
        and user.role == "ATTENDANT"
    )


def can_manage_products(user):
    """
    Users allowed to add/delete/reset products.
    """
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.role in ["ADMIN", "MANAGER"]
        )
    )


def can_manage_stock(user):
    """
    Users allowed to restock products.
    """
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.role in ["ADMIN", "MANAGER"]
        )
    )


def can_reset_data(user):
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.role in ["ADMIN", "MANAGER"]
        )
    )


def can_manage_users(user):
    """
    Only the main Super Admin manages users across stores.
    """
    return user.is_authenticated and user.is_superuser


def can_manage_stores(user):
    """
    Only the main Super Admin manages stores.
    """
    return user.is_authenticated and user.is_superuser


# ============================================================
# STORE HELPER
# ============================================================

def get_current_store(request):
    """
    Returns the logged-in user's active store.

    Super Admin may not have a store because the Super Admin
    manages the whole POS system.
    """

    try:
        store = request.user.store
    except ObjectDoesNotExist:
        return None

    if store is None:
        return None

    if not store.active:
        return None

    return store


# ============================================================
# USER MANAGEMENT
# ============================================================

@login_required
def manage_users(request):

    if not can_manage_users(request.user):
        messages.error(
            request,
            "You do not have permission to access user management."
        )
        return redirect("dashboard")

    users = (
        User.objects
        .select_related("store")
        .exclude(id=request.user.id)
        .order_by("store__name", "username")
    )

    return render(
        request,
        "core/manage_users.html",
        {
            "users": users,
        },
    )


@login_required
def add_user(request):

    # Only Super Admin can create users
    if not can_manage_users(request.user):
        messages.error(
            request,
            "You do not have permission to add users."
        )
        return redirect("dashboard")

    # Only active stores can be assigned
    stores = Store.objects.filter(
        active=True
    ).order_by("name")

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        first_name = request.POST.get(
            "first_name",
            ""
        ).strip()

        last_name = request.POST.get(
            "last_name",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        role = request.POST.get(
            "role",
            ""
        ).strip().upper()

        store_id = request.POST.get(
            "store",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        password_confirm = request.POST.get(
            "password_confirm",
            ""
        )

        # -----------------------------------------
        # VALIDATION
        # -----------------------------------------

        if not username:
            messages.error(
                request,
                "Username is required."
            )
            return redirect("add_user")

        if not role:
            messages.error(
                request,
                "Please select a user role."
            )
            return redirect("add_user")

        if role not in [
            "ADMIN",
            "MANAGER",
            "ATTENDANT",
        ]:
            messages.error(
                request,
                "Invalid user role."
            )
            return redirect("add_user")

        if not store_id:
            messages.error(
                request,
                "Please select a store."
            )
            return redirect("add_user")

        if not password:
            messages.error(
                request,
                "Password is required."
            )
            return redirect("add_user")

        if password != password_confirm:
            messages.error(
                request,
                "Passwords do not match."
            )
            return redirect("add_user")

        if len(password) < 6:
            messages.error(
                request,
                "Password must contain at least 6 characters."
            )
            return redirect("add_user")

        # -----------------------------------------
        # CHECK USERNAME
        # -----------------------------------------

        if User.objects.filter(
            username__iexact=username
        ).exists():

            messages.error(
                request,
                f"The username '{username}' already exists."
            )

            return redirect("add_user")

        # -----------------------------------------
        # GET ACTIVE STORE
        # -----------------------------------------

        store = get_object_or_404(
            Store,
            id=store_id,
            active=True,
        )

        # -----------------------------------------
        # CREATE USER
        # -----------------------------------------

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        # -----------------------------------------
        # ASSIGN ROLE AND STORE
        # -----------------------------------------

        user.role = role
        user.store = store

        # Normal store users
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False

        user.save(
            update_fields=[
                "role",
                "store",
                "is_active",
                "is_staff",
                "is_superuser",
            ]
        )

        messages.success(
            request,
            f"User '{username}' was created successfully as "
            f"{user.get_role_display()}."
        )

        return redirect("manage_users")

    # -----------------------------------------
    # GET REQUEST
    # -----------------------------------------

    return render(
        request,
        "core/add_user.html",
        {
            "stores": stores,
        },
    )


@login_required
def edit_user(request, user_id):

    if not can_manage_users(request.user):
        messages.error(
            request,
            "You do not have permission to edit users."
        )
        return redirect("dashboard")

    user = get_object_or_404(
        User.objects.select_related("store"),
        id=user_id,
    )

    if user.id == request.user.id:
        messages.error(
            request,
            "You cannot edit your own Super Admin account here."
        )
        return redirect("manage_users")

    stores = Store.objects.filter(
        active=True
    ).order_by("name")

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        role = request.POST.get(
            "role",
            "ATTENDANT"
        )

        store_id = request.POST.get(
            "store"
        )

        if not username:
            messages.error(
                request,
                "Username is required."
            )
            return redirect(
                "edit_user",
                user_id=user.id,
            )

        if role not in [
            "ADMIN",
            "MANAGER",
            "ATTENDANT",
        ]:
            messages.error(
                request,
                "Invalid user role."
            )
            return redirect(
                "edit_user",
                user_id=user.id,
            )

        if User.objects.filter(
            username=username
        ).exclude(
            id=user.id
        ).exists():

            messages.error(
                request,
                f"The username '{username}' is already in use."
            )

            return redirect(
                "edit_user",
                user_id=user.id,
            )

        if not store_id:
            messages.error(
                request,
                "Please select a store."
            )
            return redirect(
                "edit_user",
                user_id=user.id,
            )

        store = get_object_or_404(
            Store,
            id=store_id,
            active=True,
        )

        user.username = username
        user.email = email
        user.role = role
        user.store = store

        user.save()

        messages.success(
            request,
            f"User '{user.username}' was updated successfully."
        )

        return redirect("manage_users")

    return render(
        request,
        "core/edit_user.html",
        {
            "user_account": user,
            "stores": stores,
        },
    )


@login_required
def profile(request):
    user = request.user

    if request.method == "POST":
        action = request.POST.get("action", "profile")

        # -----------------------------
        # UPDATE PROFILE INFORMATION
        # -----------------------------
        if action == "profile":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            username = request.POST.get("username", "").strip()
            email = request.POST.get("email", "").strip()

            if not username:
                messages.error(request, "Username cannot be empty.")
                return redirect("profile")

            username_exists = (
                User.objects
                .filter(username__iexact=username)
                .exclude(pk=user.pk)
                .exists()
            )

            if username_exists:
                messages.error(request, "That username is already in use.")
                return redirect("profile")

            user.first_name = first_name
            user.last_name = last_name
            user.username = username
            user.email = email
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "username",
                    "email",
                ]
            )

            messages.success(
                request, "Your profile has been updated successfully.")
            return redirect("profile")

        # -----------------------------
        # CHANGE PASSWORD
        # -----------------------------
        if action == "password":
            password_form = PasswordChangeForm(user, request.POST)

            if password_form.is_valid():
                changed_user = password_form.save()

                # Keep the user logged in after changing password.
                update_session_auth_hash(request, changed_user)

                messages.success(
                    request,
                    "Your password has been changed successfully.",
                )
                return redirect("profile")

            for field_errors in password_form.errors.values():
                for error in field_errors:
                    messages.error(request, error)

            return redirect("profile")

    password_form = PasswordChangeForm(user)

    store = getattr(user, "store", None)

    if user.is_superuser:
        role_display = "Super Admin"
    else:
        role_display = user.get_role_display()

    context = {
        "password_form": password_form,
        "profile_user": user,
        "profile_store": store,
        "role_display": role_display,
    }

    return render(request, "core/profile.html", context)


@login_required
@require_POST
def toggle_user(request, user_id):

    if not can_manage_users(request.user):
        messages.error(
            request,
            "You do not have permission to perform this action."
        )
        return redirect("dashboard")

    user = get_object_or_404(
        User,
        id=user_id,
    )

    if user.id == request.user.id:
        messages.error(
            request,
            "You cannot deactivate your own Super Admin account."
        )
        return redirect("manage_users")

    user.is_active = not user.is_active

    user.save(
        update_fields=["is_active"]
    )

    status = (
        "activated"
        if user.is_active
        else "deactivated"
    )

    messages.success(
        request,
        f"User '{user.username}' was {status}."
    )

    return redirect("manage_users")


@login_required
@require_POST
def delete_user(request, user_id):

    if not can_manage_users(request.user):
        messages.error(
            request,
            "You do not have permission to delete users."
        )
        return redirect("dashboard")

    user = get_object_or_404(
        User,
        id=user_id,
    )

    if user.id == request.user.id:
        messages.error(
            request,
            "You cannot delete your own Super Admin account."
        )
        return redirect("manage_users")

    if Sale.objects.filter(
        sold_by=user
    ).exists():

        messages.error(
            request,
            (
                f"'{user.username}' has sales history and "
                "cannot be permanently deleted. "
                "Deactivate the account instead."
            )
        )

        return redirect("manage_users")

    username = user.username

    user.delete()

    messages.success(
        request,
        f"User '{username}' was deleted successfully."
    )

    return redirect("manage_users")


@login_required
def reset_user_password(request, user_id):

    if not can_manage_users(request.user):
        messages.error(
            request,
            "You do not have permission to reset passwords."
        )
        return redirect("dashboard")

    user = get_object_or_404(
        User,
        id=user_id,
    )

    if user.id == request.user.id:
        messages.error(
            request,
            "Use your account settings to change your own password."
        )
        return redirect("manage_users")

    if request.method == "POST":

        password = request.POST.get(
            "password",
            ""
        ).strip()

        password_confirm = request.POST.get(
            "password_confirm",
            ""
        ).strip()

        if not password:
            messages.error(
                request,
                "Password is required."
            )
            return redirect(
                "reset_user_password",
                user_id=user.id,
            )

        if password != password_confirm:
            messages.error(
                request,
                "Passwords do not match."
            )
            return redirect(
                "reset_user_password",
                user_id=user.id,
            )

        try:
            validate_password(
                password,
                user,
            )

        except ValidationError as error:

            for message in error.messages:
                messages.error(
                    request,
                    message
                )

            return redirect(
                "reset_user_password",
                user_id=user.id,
            )

        user.set_password(password)

        user.save(
            update_fields=["password"]
        )

        messages.success(
            request,
            f"Password for '{user.username}' was reset successfully."
        )

        return redirect("manage_users")

    return render(
        request,
        "core/reset_user_password.html",
        {
            "user_account": user,
        },
    )


# ============================================================
# STORE MANAGEMENT
# ============================================================

@login_required
def manage_stores(request):

    if not can_manage_stores(request.user):
        messages.error(
            request,
            "You do not have permission to manage stores."
        )
        return redirect("dashboard")

    stores = Store.objects.all().order_by(
        "-created_at"
    )

    store_data = []

    for store in stores:

        store_data.append({
            "store": store,
            "users_count": User.objects.filter(
                store=store
            ).count(),
        })

    return render(
        request,
        "core/manage_stores.html",
        {
            "store_data": store_data,
        },
    )


@login_required
def add_store(request):

    if not can_manage_stores(request.user):
        messages.error(
            request,
            "You do not have permission to add stores."
        )
        return redirect("dashboard")

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        phone = request.POST.get(
            "phone",
            ""
        ).strip()

        address = request.POST.get(
            "address",
            ""
        ).strip()

        if not name:
            messages.error(
                request,
                "Store name is required."
            )
            return redirect("add_store")

        Store.objects.create(
            name=name,
            phone=phone,
            address=address,
            active=True,
        )

        messages.success(
            request,
            f"Store '{name}' was created successfully."
        )

        return redirect("manage_stores")

    return render(
        request,
        "core/add_store.html",
    )


@login_required
def edit_store(request, store_id):

    if not can_manage_stores(request.user):
        messages.error(
            request,
            "You do not have permission to edit stores."
        )
        return redirect("dashboard")

    store = get_object_or_404(
        Store,
        id=store_id,
    )

    if request.method == "POST":

        name = request.POST.get(
            "name",
            ""
        ).strip()

        phone = request.POST.get(
            "phone",
            ""
        ).strip()

        address = request.POST.get(
            "address",
            ""
        ).strip()

        if not name:
            messages.error(
                request,
                "Store name is required."
            )

            return redirect(
                "edit_store",
                store_id=store.id,
            )

        store.name = name
        store.phone = phone
        store.address = address

        store.save()

        messages.success(
            request,
            "Store details updated successfully."
        )

        return redirect("manage_stores")

    return render(
        request,
        "core/edit_store.html",
        {
            "store": store,
        },
    )


@login_required
@require_POST
def toggle_store(request, store_id):

    if not can_manage_stores(request.user):
        messages.error(
            request,
            "You do not have permission to perform this action."
        )
        return redirect("dashboard")

    store = get_object_or_404(
        Store,
        id=store_id,
    )

    store.active = not store.active

    store.save(
        update_fields=["active"]
    )

    status = (
        "activated"
        if store.active
        else "deactivated"
    )

    messages.success(
        request,
        f"Store '{store.name}' was {status}."
    )

    return redirect("manage_stores")


@login_required
@require_POST
def delete_store(request, store_id):

    if not can_manage_stores(request.user):
        messages.error(
            request,
            "You do not have permission to delete stores."
        )
        return redirect("dashboard")

    store = get_object_or_404(
        Store,
        id=store_id,
    )

    if User.objects.filter(
        store=store
    ).exists():

        messages.error(
            request,
            (
                "This store cannot be deleted because "
                "it has users. Deactivate the store instead."
            )
        )

        return redirect("manage_stores")

    if Product.objects.filter(
        store=store
    ).exists():

        messages.error(
            request,
            (
                "This store cannot be deleted because "
                "it has products. Deactivate the store instead."
            )
        )

        return redirect("manage_stores")

    if Sale.objects.filter(
        store=store
    ).exists():

        messages.error(
            request,
            (
                "This store cannot be deleted because "
                "it has sales history. Deactivate the store instead."
            )
        )

        return redirect("manage_stores")

    if StockMovement.objects.filter(
        store=store
    ).exists():

        messages.error(
            request,
            (
                "This store cannot be deleted because "
                "it has stock history. Deactivate the store instead."
            )
        )

        return redirect("manage_stores")

    store_name = store.name

    store.delete()

    messages.success(
        request,
        f"Store '{store_name}' was deleted successfully."
    )

    return redirect("manage_stores")


# ============================================================
# DASHBOARD
# ============================================================

@login_required
def dashboard(request):

    store = get_current_store(request)

    if not store:

        if is_main_admin(request.user):
            return redirect("manage_stores")

        return render(
            request,
            "core/no_store.html"
        )

    active_products_count = Product.objects.filter(
        store=store,
        active=True,
    ).count()

    total_sales = sum(
        (
            sale.total
            for sale in Sale.objects.filter(
                store=store
            )
        ),
        Decimal("0.00"),
    )

    today = timezone.localdate()

    days_since_sunday = (
        today.weekday() + 1
    ) % 7

    week_start = (
        today
        - datetime.timedelta(
            days=days_since_sunday
        )
    )

    week_end = (
        week_start
        + datetime.timedelta(days=6)
    )

    weekly_sales = Sale.objects.filter(
        store=store,
        sold_at__date__gte=week_start,
        sold_at__date__lte=week_end,
    )

    weekly_sales_data = []

    for i in range(7):

        current_day = (
            week_start
            + datetime.timedelta(days=i)
        )

        day_sales = sum(
            (
                sale.total
                for sale in weekly_sales
                if timezone.localtime(
                    sale.sold_at
                ).date() == current_day
            ),
            Decimal("0.00"),
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
            "store": store,
            "active_products_count": active_products_count,
            "total_sales": total_sales,
            "weekly_sales_data": weekly_sales_data,
            "week_start": week_start,
            "week_end": week_end,
        },
    )


# ============================================================
# ACTIVE PRODUCTS
# ============================================================

@login_required
def active_products(request):

    store = get_current_store(request)

    if not store:

        if is_main_admin(request.user):
            return redirect("manage_stores")

        return render(
            request,
            "core/no_store.html"
        )

    products = (
        Product.objects
        .filter(
            store=store,
            active=True,
        )
        .select_related("category")
        .order_by("name")
    )

    total_products = products.count()

    low_stock_count = sum(
        1
        for product in products
        if product.is_low_stock
    )

    return render(
        request,
        "core/active_products.html",
        {
            "products": products,
            "store": store,
            "total_products": total_products,
            "low_stock_count": low_stock_count,
        },
    )


@login_required
@require_POST
def delete_product(request, product_id):

    if not can_manage_products(request.user):
        messages.error(
            request,
            "You do not have permission to delete products."
        )
        return redirect("active_products")

    store = get_current_store(request)

    if not store:
        messages.error(
            request,
            "You are not assigned to an active store."
        )
        return redirect("dashboard")

    product = get_object_or_404(
        Product,
        id=product_id,
        store=store,
    )

    if Sale.objects.filter(
        product=product
    ).exists():

        messages.error(
            request,
            (
                f'"{product.name}" has sales history and '
                "cannot be permanently deleted. "
                "Deactivate it instead."
            )
        )

        return redirect("active_products")

    product_name = product.name

    product.delete()

    messages.success(
        request,
        f'"{product_name}" was deleted successfully.'
    )

    return redirect("active_products")


@login_required
@require_POST
def reset_active_products(request):

    if not can_reset_data(request.user):
        messages.error(
            request,
            "You do not have permission to reset products."
        )
        return redirect("active_products")

    store = get_current_store(request)

    if not store:
        messages.error(
            request,
            "You are not assigned to an active store."
        )
        return redirect("dashboard")

    password = request.POST.get(
        "password",
        ""
    )

    if not password:
        messages.error(
            request,
            "Please enter your password."
        )
        return redirect("active_products")

    if not request.user.check_password(
        password
    ):
        messages.error(
            request,
            "Incorrect password. Products were not reset."
        )
        return redirect("active_products")

    with transaction.atomic():

        Product.objects.filter(
            store=store,
            active=True,
        ).update(
            active=False
        )

    messages.success(
        request,
        "All active products have been reset."
    )

    return redirect("active_products")


# ============================================================
# DAILY SALES
# ============================================================

@login_required
def daily_sales(request):

    store = get_current_store(request)

    if not store:

        if is_main_admin(request.user):
            return redirect("manage_stores")

        return render(
            request,
            "core/no_store.html"
        )

    date_value = request.GET.get(
        "date",
        ""
    )

    try:

        selected_date = (
            datetime.datetime.strptime(
                date_value,
                "%Y-%m-%d",
            ).date()
            if date_value
            else timezone.localdate()
        )

    except ValueError:

        selected_date = timezone.localdate()

    sales = (
        Sale.objects
        .filter(
            store=store,
            sold_at__date=selected_date,
        )
        .select_related(
            "product",
            "sold_by",
        )
        .order_by("-sold_at")
    )

    daily_total = sum(
        (
            sale.total
            for sale in sales
        ),
        Decimal("0.00"),
    )

    return render(
        request,
        "core/daily_sales.html",
        {
            "sales": sales,
            "selected_date": selected_date,
            "daily_total": daily_total,
            "store": store,
        },
    )


# ============================================================
# ALL SALES
# ============================================================

@login_required
def all_sales(request):

    store = get_current_store(request)

    if not store:

        if is_main_admin(request.user):
            return redirect("manage_stores")

        return render(
            request,
            "core/no_store.html"
        )

    if request.method == "POST":

        if not can_reset_data(request.user):
            messages.error(
                request,
                "You do not have permission to reset sales."
            )
            return redirect("all_sales")

        action = request.POST.get(
            "action",
            ""
        ).strip()

        if action == "reset_sales":

            password = request.POST.get(
                "password",
                ""
            )

            if not password:
                messages.error(
                    request,
                    "Please enter your password to reset sales."
                )
                return redirect("all_sales")

            user = authenticate(
                request=request,
                username=request.user.username,
                password=password,
            )

            if user is None:

                messages.error(
                    request,
                    "Incorrect password. Sales were not reset."
                )

                return redirect("all_sales")

            try:

                with transaction.atomic():

                    deleted_count, _ = (
                        Sale.objects
                        .filter(store=store)
                        .delete()
                    )

                messages.success(
                    request,
                    (
                        "Sales history reset successfully. "
                        f"{deleted_count} sales record(s) were removed."
                    )
                )

            except Exception:

                logger.exception(
                    "Sales reset failed"
                )

                messages.error(
                    request,
                    (
                        "Sales could not be reset. "
                        "Please try again."
                    )
                )

            return redirect("all_sales")

    sales = (
        Sale.objects
        .filter(store=store)
        .select_related(
            "product",
            "sold_by",
        )
        .order_by("-sold_at")
    )

    total_sales = sum(
        (
            sale.total
            for sale in sales
        ),
        Decimal("0.00"),
    )

    total_items = sum(
        sale.quantity
        for sale in sales
    )

    sales_count = sales.count()

    return render(
        request,
        "core/all_sales.html",
        {
            "sales": sales,
            "total_sales": total_sales,
            "total_items": total_items,
            "sales_count": sales_count,
            "store": store,
        },
    )


# ============================================================
# POS
# ============================================================

@login_required
def pos(request):

    store = get_current_store(request)

    if not store:

        if is_main_admin(request.user):
            return redirect("manage_stores")

        return render(
            request,
            "core/no_store.html"
        )

    query = request.GET.get(
        "q",
        ""
    ).strip()

    category = request.GET.get(
        "category",
        ""
    ).strip()

    products = (
        Product.objects
        .filter(
            store=store,
            active=True,
        )
        .select_related("category")
    )

    if query:

        products = products.filter(
            Q(name__icontains=query)
            | Q(barcode__icontains=query)
        )

    if category:

        products = products.filter(
            category__name=category
        )

    categories = [
        {
            "id": row["category_id"],
            "name": row["category__name"],
        }

        for row in (
            Product.objects
            .filter(
                store=store,
                active=True,
                category__isnull=False,
            )
            .values(
                "category_id",
                "category__name",
            )
            .distinct()
            .order_by(
                "category__name"
            )
        )
    ]

    return render(
        request,
        "core/pos.html",
        {
            "products": products.order_by("name"),
            "categories": categories,
            "selected_category": category,
            "query": query,
            "store": store,
        },
    )


@login_required
@require_POST
def sell_one(request, product_id):

    store = get_current_store(request)

    if not store:

        return JsonResponse(
            {
                "ok": False,
                "error": "No active store assigned.",
            },
            status=400,
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
                    "stock": 0,
                },
                status=400,
            )

        product.stock -= 1

        product.save(
            update_fields=["stock"]
        )

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


# ============================================================
# RESTOCK
# ============================================================

@login_required
def restock(request):

    if not can_manage_stock(request.user):
        messages.error(
            request,
            "You do not have permission to restock products."
        )
        return redirect("dashboard")

    store = get_current_store(request)

    if not store:

        if is_main_admin(request.user):
            return redirect("manage_stores")

        return render(
            request,
            "core/no_store.html"
        )

    products = (
        Product.objects
        .filter(
            store=store,
            active=True,
        )
        .order_by("name")
    )

    if request.method == "POST":

        product_id = request.POST.get(
            "product"
        )

        note = request.POST.get(
            "note",
            ""
        ).strip()

        try:

            quantity = int(
                request.POST.get(
                    "quantity"
                )
            )

            if quantity <= 0:
                raise ValueError

        except (
            TypeError,
            ValueError,
        ):

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
                active=True,
            )

            product.stock += quantity

            product.save(
                update_fields=["stock"]
            )

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
            (
                f"{product.name} restocked by "
                f"{quantity}. New stock: "
                f"{product.stock}"
            )
        )

        return redirect("restock")

    return render(
        request,
        "core/restock.html",
        {
            "products": products,
            "store": store,
        },
    )


# ============================================================
# CART SALE
# ============================================================

@login_required
@require_POST
def process_cart_sale(request):

    try:

        payload = json.loads(
            request.body.decode("utf-8")
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):

        return JsonResponse(
            {
                "ok": False,
                "error": "Invalid sale data.",
            },
            status=400,
        )

    cart_items = (
        payload.get("items")
        if isinstance(payload, dict)
        else None
    )

    if (
        not isinstance(cart_items, list)
        or not cart_items
    ):

        return JsonResponse(
            {
                "ok": False,
                "error": "Your cart is empty.",
            },
            status=400,
        )

    quantities = {}

    try:

        for item in cart_items:

            product_id = int(
                item["id"]
            )

            quantity = int(
                item["quantity"]
            )

            if (
                product_id <= 0
                or quantity <= 0
            ):
                raise ValueError

            quantities[product_id] = (
                quantities.get(
                    product_id,
                    0,
                )
                + quantity
            )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Each cart item needs "
                    "a valid product and quantity."
                ),
            },
            status=400,
        )

    store = get_current_store(request)

    if not store:

        return JsonResponse(
            {
                "ok": False,
                "error": "No active store assigned.",
            },
            status=400,
        )

    try:

        with transaction.atomic():

            product_ids = sorted(
                quantities
            )

            products = list(
                Product.objects
                .select_for_update()
                .filter(
                    id__in=product_ids,
                    store=store,
                    active=True,
                )
                .order_by("id")
            )

            products_by_id = {
                product.id: product
                for product in products
            }

            if set(product_ids) != set(
                products_by_id
            ):

                return JsonResponse(
                    {
                        "ok": False,
                        "error": (
                            "One or more products "
                            "are unavailable."
                        ),
                    },
                    status=404,
                )

            for product_id in product_ids:

                product = products_by_id[
                    product_id
                ]

                required_quantity = quantities[
                    product_id
                ]

                if (
                    product.stock
                    < required_quantity
                ):

                    return JsonResponse(
                        {
                            "ok": False,
                            "error": (
                                f"Insufficient inventory "
                                f"for {product.name}."
                            ),
                        },
                        status=400,
                    )

            updates = []

            for product_id in product_ids:

                product = products_by_id[
                    product_id
                ]

                quantity = quantities[
                    product_id
                ]

                product.stock -= quantity

                product.save(
                    update_fields=["stock"]
                )

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

                updates.append({
                    "id": product.id,
                    "new_stock": product.stock,
                    "is_low": (
                        product.stock
                        <= product.low_stock_threshold
                    ),
                })

        return JsonResponse(
            {
                "ok": True,
                "updates": updates,
            }
        )

    except Exception:

        logger.exception(
            "POS cart sale failed"
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "The sale could not be completed. "
                    "Please try again."
                ),
            },
            status=500,
        )


# ============================================================
# ADD PRODUCT
# ============================================================

@login_required
def add_product(request):
    if not can_manage_products(request.user):
        messages.error(request, "You do not have permission to add products.")
        return redirect("pos")

    store = get_current_store(request)

    if store is None:
        messages.error(request, "No active store is assigned to your account.")
        return redirect("dashboard")

    categories = Category.objects.all().order_by("name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        category_id = request.POST.get("category", "").strip()
        preferred_category = request.POST.get(
            "preferred_category", ""
        ).strip()

        selling_price = request.POST.get("selling_price", "").strip()
        cost_price = request.POST.get("cost_price", "").strip()
        stock = request.POST.get("stock", "0").strip()
        low_stock_threshold = request.POST.get(
            "low_stock_threshold", "20"
        ).strip()
        barcode = request.POST.get("barcode", "").strip()
        active = request.POST.get("active") == "on"

        # Which button was pressed?
        save_and_add_another = (
            request.POST.get("save_and_add_another") == "1"
        )

        # -----------------------------
        # BASIC VALIDATION
        # -----------------------------
        if not name:
            messages.error(request, "Please enter the product name.")
            return render(
                request,
                "core/add_product.html",
                {"categories": categories},
            )

        if not selling_price:
            messages.error(request, "Please enter the selling price.")
            return render(
                request,
                "core/add_product.html",
                {"categories": categories},
            )

        # -----------------------------
        # CATEGORY
        # -----------------------------
        category = None

        if preferred_category:
            category, created = Category.objects.get_or_create(
                name=preferred_category
            )
        elif category_id:
            category = get_object_or_404(
                Category,
                id=category_id,
            )

        # -----------------------------
        # NUMERIC VALUES
        # -----------------------------
        try:
            selling_price_decimal = Decimal(selling_price)

            if selling_price_decimal < 0:
                raise ValueError

        except (InvalidOperation, ValueError):
            messages.error(
                request,
                "Please enter a valid selling price."
            )
            return render(
                request,
                "core/add_product.html",
                {"categories": categories},
            )

        cost_price_decimal = None

        if cost_price:
            try:
                cost_price_decimal = Decimal(cost_price)

                if cost_price_decimal < 0:
                    raise ValueError

            except (InvalidOperation, ValueError):
                messages.error(
                    request,
                    "Please enter a valid cost price."
                )
                return render(
                    request,
                    "core/add_product.html",
                    {"categories": categories},
                )

        try:
            stock_value = int(stock)

            if stock_value < 0:
                raise ValueError

        except ValueError:
            messages.error(
                request,
                "Stock must be a valid number."
            )
            return render(
                request,
                "core/add_product.html",
                {"categories": categories},
            )

        try:
            low_stock_value = int(low_stock_threshold)

            if low_stock_value < 0:
                raise ValueError

        except ValueError:
            messages.error(
                request,
                "Low-stock threshold must be a valid number."
            )
            return render(
                request,
                "core/add_product.html",
                {"categories": categories},
            )

        # -----------------------------
        # CREATE PRODUCT
        # -----------------------------
        Product.objects.create(
            store=store,
            category=category,
            name=name,
            selling_price=selling_price_decimal,
            cost_price=cost_price_decimal,
            stock=stock_value,
            low_stock_threshold=low_stock_value,
            barcode=barcode or None,
            active=active,
        )

        messages.success(
            request,
            f'"{name}" was added successfully.'
        )

        # -----------------------------
        # SAVE & ADD ANOTHER
        # -----------------------------
        if save_and_add_another:
            return redirect("add_product")

        # -----------------------------
        # NORMAL ADD PRODUCT
        # -----------------------------
        return redirect("pos")

    return render(
        request,
        "core/add_product.html",
        {
            "categories": categories,
        },
    )

# ============================================================
# LOGOUT
# ============================================================


def custom_logout_view(request):

    auth_logout(request)

    return redirect("login")

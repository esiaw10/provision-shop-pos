from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import path

from core.views import (
    dashboard,
    pos,
    sell_one,
    process_cart_sale,
    restock,
    daily_sales,
    all_sales,
    active_products,
    reset_active_products,
    delete_product,
    add_product,
    custom_logout_view,
    signup,
    profile,

    # Store management
    manage_stores,
    add_store,
    edit_store,
    delete_store,
    toggle_store,

    # User management
    manage_users,
    add_user,
    edit_user,
    delete_user,
    toggle_user,
    reset_user_password,
)


urlpatterns = [

    # =========================================================
    # DJANGO ADMIN
    # =========================================================

    path(
        "admin/",
        admin.site.urls,
    ),


    # =========================================================
    # AUTHENTICATION
    # =========================================================

    path(
        "login/",
        LoginView.as_view(
            template_name="core/login.html"
        ),
        name="login",
    ),

    path(
        "logout/",
        custom_logout_view,
        name="logout",
    ),

    path("signup/", signup, name="signup"),

    # =========================================================
    # DASHBOARD
    # =========================================================

    path(
        "",
        dashboard,
        name="dashboard",
    ),


    # =========================================================
    # POS
    # =========================================================

    path(
        "pos/",
        pos,
        name="pos",
    ),

    path(
        "pos/sell/<int:product_id>/",
        sell_one,
        name="sell_one",
    ),

    path(
        "pos/cart-sale/",
        process_cart_sale,
        name="process_cart_sale",
    ),


    # =========================================================
    # PRODUCTS
    # =========================================================

    path(
        "products/active/",
        active_products,
        name="active_products",
    ),

    path(
        "products/active/reset/",
        reset_active_products,
        name="reset_active_products",
    ),

    path(
        "products/delete/<int:product_id>/",
        delete_product,
        name="delete_product",
    ),

    path(
        "add-product/",
        add_product,
        name="add_product",
    ),


    # =========================================================
    # STOCK
    # =========================================================

    path(
        "pos/restock/",
        restock,
        name="restock",
    ),


    # =========================================================
    # SALES
    # =========================================================

    path(
        "sales/daily/",
        daily_sales,
        name="daily_sales",
    ),

    path(
        "sales/all/",
        all_sales,
        name="all_sales",
    ),


    # =========================================================
    # SUPER ADMIN — STORE MANAGEMENT
    # =========================================================

    path(
        "management/stores/",
        manage_stores,
        name="manage_stores",
    ),

    path(
        "management/stores/add/",
        add_store,
        name="add_store",
    ),

    path(
        "management/stores/<int:store_id>/edit/",
        edit_store,
        name="edit_store",
    ),

    path(
        "management/stores/<int:store_id>/delete/",
        delete_store,
        name="delete_store",
    ),

    path(
        "management/stores/<int:store_id>/toggle/",
        toggle_store,
        name="toggle_store",
    ),


    # =========================================================
    # SUPER ADMIN — USER MANAGEMENT
    # =========================================================

    path(
        "management/users/",
        manage_users,
        name="manage_users",
    ),

    path(
        "management/users/add/",
        add_user,
        name="add_user",
    ),

    path(
        "management/users/<int:user_id>/edit/",
        edit_user,
        name="edit_user",
    ),

    path(
        "management/users/<int:user_id>/toggle/",
        toggle_user,
        name="toggle_user",
    ),

    path(
        "management/users/<int:user_id>/delete/",
        delete_user,
        name="delete_user",
    ),

    path(
        "management/users/<int:user_id>/reset-password/",
        reset_user_password,
        name="reset_user_password",
    ),

    path("profile/", profile, name="profile"),
]

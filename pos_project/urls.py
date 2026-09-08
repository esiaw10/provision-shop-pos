from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import path

from core import views


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "login/",
        LoginView.as_view(template_name="core/login.html"),
        name="login"
    ),
    path("logout/", views.custom_logout_view, name="logout"),

    path("", views.dashboard, name="dashboard"),
    path("pos/", views.pos, name="pos"),
    path("pos/sell/<int:product_id>/", views.sell_one, name="sell_one"),
    path("pos/cart-sale/", views.process_cart_sale, name="cart_sale"),
    path("pos/restock/", views.restock, name="restock"),
    path("sales/daily/", views.daily_sales, name="daily_sales"),
]

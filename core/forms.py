from .models import Product
from django import forms


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product

        fields = [
            "name",
            "category",
            "selling_price",
            "cost_price",
            "stock",
            "low_stock_threshold",
            "barcode",
            "active",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Enter product name",
            }),

            "selling_price": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "Enter selling price",
            }),

            "cost_price": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "Enter cost price",
            }),

            "stock": forms.NumberInput(attrs={
                "min": "0",
            }),

            "low_stock_threshold": forms.NumberInput(attrs={
                "min": "0",
            }),
        }

    def clean_selling_price(self):
        price = self.cleaned_data["selling_price"]

        if price < 0:
            raise forms.ValidationError(
                "Selling price cannot be negative."
            )

        return price

    def clean_cost_price(self):
        price = self.cleaned_data.get("cost_price")

        if price is not None and price < 0:
            raise forms.ValidationError(
                "Cost price cannot be negative."
            )

        return price

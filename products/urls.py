from django.urls import path
from . import views

urlpatterns = [
    # Your existing URL patterns...
    path('shopify-inventory/', views.shopify_inventory, name='shopify_inventory'),
    path('save-wholesale-availability/', views.save_wholesale_availability, name='save_wholesale_availability'),
]
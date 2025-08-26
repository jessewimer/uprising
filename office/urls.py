from django.urls import path
from .views import OfficeLoginView, OfficeLogoutView, office_landing, view_variety, analytics
from .views import *
import products.views as product_views
import stores.views as store_views
import lots.views as lot_views
import orders.views as order_views

urlpatterns = [
    # Authentication
    path('login/', OfficeLoginView.as_view(), name='office_login'),
    path('logout/', OfficeLogoutView.as_view(), name='office_logout'),
    
    # Main office page
    path('dashboard/', office_landing, name='office_landing'),
    
    # Action card destinations (matching the landing page links)
    path('edit-products/', product_views.edit_products, name='edit_products'),
    path('view-variety/', view_variety, name='view_variety'),
    path('inventory/', inventory_germination, name='inventory'),
    path('analytics/', analytics, name='analytics'),
    path('process-store-orders/', store_views.process_store_orders, name='process_store_orders'),
    path('view-stores/', store_views.view_stores, name='view_stores'),
    
    path('send-germ-samples/', lot_views.send_germ_samples, name='send_germ_samples'),
    path('inventory/', lot_views.inventory, name='inventory'),
    path('process-online-orders/', order_views.process_online_orders, name='process_online_orders'),
    # Keep your existing inventory page with original name for backward compatibility
    path('inventory-germination/', inventory_germination, name='inventory_germination'),
    
    # JSON API endpoints
    path('varieties-json/', varieties_json, name='varieties_json'),
    path("crops-json/", crops_json, name="crops_json"),
    path('inventory-germination/<str:crop>/', products_by_crop_json, name='products_by_crop_json'),

    path('print-product-labels/', print_product_labels, name='print_product_labels'),
    path('assign-lot-to-product/', assign_lot_to_product, name='assign_lot_to_product'),
    path('set-lot-low-inv/', set_lot_low_inv, name='set_lot_low_inv'),
    path('add-lot/', add_lot, name='add_lot'),
    path('delete-lot/', delete_lot, name='delete_lot'),
    path('retire-lot/', retire_lot, name='retire_lot'),
    path('record-stock-seed/', record_stock_seed, name='record_stock_seed'),
    path('record-germination/', record_germination, name='record_germination'),
]
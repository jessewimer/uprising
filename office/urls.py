from django.urls import path
from .views import OfficeLoginView, OfficeLogoutView, office_landing, view_variety, analytics, admin_dashboard
from .views import *
import products.views as product_views
# import stores.views as store_views
import lots.views as lot_views
import orders.views as order_views
# from stores.models import Store

urlpatterns = [
    # Authentication
    path('login/', OfficeLoginView.as_view(), name='office_login'),
    path('logout/', OfficeLogoutView.as_view(), name='office_logout'),
    path('api/check-admin-access/', check_admin_access, name='check_admin_access'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    
    # Main office page
    path('dashboard/', office_landing, name='office_landing'),
    
    # Action card destinations (matching the landing page links)
    path('edit-products/', product_views.edit_products, name='edit_products'),
    path('view-variety/', view_variety, name='view_variety'),
    path('analytics/', analytics, name='analytics'),
    path('envelope-data-for-printing/', get_envelope_data_for_printing, name='envelope_data_for_printing'),

    path('<int:store_num>/update/', update_store, name='update_store'),
    path('get-store-orders/<int:store_id>/', get_store_orders, name='get_store_orders'),
    path('process-store-orders/', process_store_orders, name='process_store_orders'),
    path('get-pending-orders/', get_pending_orders, name='get_pending_orders'),
    path('view-stores/', view_stores, name='view_stores'),
    path('get-order-details/<int:order_id>/', get_order_details, name='get_order_details'),
    path('save-order-changes/', save_order_changes, name='save_order_changes'),
    path('finalize-order/', finalize_order, name='finalize_order'),
    

    path('germ-samples/', lot_views.send_germ_samples, name='germ_samples'),
    path('growouts/', lot_views.growouts, name='growouts'),
    path('update-growout/<int:lot_id>/', lot_views.update_growout, name='update_growout'),
    path('api/variety-sales/<str:sku_prefix>/', variety_sales_data, name='variety_sales_data'),
    path('api/create-batch/', lot_views.create_new_batch, name='create_new_batch'),
    path('api/submit-batch/', lot_views.submit_batch, name='submit_batch'),

    path('inventory/', lot_views.inventory, name='inventory'),
    path('process-online-orders/', order_views.process_online_orders, name='process_online_orders'),
    path('germination-inventory/', germination_inventory_view, name='germination_inventory'),
    path('api/germination-inventory-data/', germination_inventory_data, name='germination_inventory_data'),
    path('api/create-germ-sample-print/', create_germ_sample_print, name='create_germ_sample_print'),
    
    # JSON API endpoints
    path('varieties-json/', varieties_json, name='varieties_json'),
    path("crops-json/", crops_json, name="crops_json"),
    path('inventory-germination/<str:crop>/', products_by_crop_json, name='products_by_crop_json'),
    path('add-variety/', add_variety, name='add_variety'),
    path('add-product/', add_product, name='add_product'),
    path('store-sales-details/', store_sales_details, name='store_sales_details'),
    path('get-lot-history/', get_lot_history, name='get_lot_history'),
    path('top-sellers-details/', top_sellers_details, name='top_sellers_details'),

    path('print-product-labels/', print_product_labels, name='print_product_labels'),
    path('assign-lot-to-product/', assign_lot_to_product, name='assign_lot_to_product'),
    path('edit-product/', edit_product, name='edit_product'),
    path('get-product-packing-history/', get_product_packing_history, name='get_product_packing_history'),
    path('edit-packing-record/', edit_packing_record, name='edit_packing_record'),
    path('delete-packing-record/', delete_packing_record, name='delete_packing_record'),
    path('set-lot-low-inv/', set_lot_low_inv, name='set_lot_low_inv'),
    path('add-lot/', add_lot, name='add_lot'),
    path('delete-lot/', delete_lot, name='delete_lot'),
    path('retire-lot/', retire_lot, name='retire_lot'),
    path('record-stock-seed/', record_stock_seed, name='record_stock_seed'),
    path('record-germination/', record_germination, name='record_germination'),
    path('change-lot-status/', change_lot_status, name='change_lot_status'),
    path('edit-front-labels/', edit_front_labels, name='edit_front_labels'),
    path('edit-back-labels/', edit_back_labels, name='edit_back_labels'),

    # path('check-stock-seed-exists/', check_stock_seed_exists, name='check_stock_seed_exists'),
    path('get-stock-seed-data/', get_stock_seed_data, name='get_stock_seed_data'),
]
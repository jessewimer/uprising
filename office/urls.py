from django.urls import path
from .views import OfficeLoginView, OfficeLogoutView, office_landing, view_variety, analytics, admin_dashboard
from .views import *
import products.views as product_views
import lots.views as lot_views
import orders.views as order_views

urlpatterns = [
    # ============================================================================
    # AUTHENTICATION & ADMIN
    # ============================================================================
    path('login/', OfficeLoginView.as_view(), name='office_login'),
    path('logout/', OfficeLogoutView.as_view(), name='office_logout'),
    path('api/check-admin-access/', check_admin_access, name='check_admin_access'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    
    # ============================================================================
    # MAIN DASHBOARD & NAVIGATION
    # ============================================================================
    path('dashboard/', office_landing, name='office_landing'),
    path('analytics/', analytics, name='analytics'),
    
    # ============================================================================
    # VARIETY MANAGEMENT
    # ============================================================================
    path('view-variety/', view_variety, name='view_variety'),  # For dashboard - loads last selected
    path('view-variety/<str:sku_prefix>/', view_variety, name='view_variety_with_sku'),  # For specific variety
    path('varieties-json/', varieties_json, name='varieties_json'),
    path('add-variety/', add_variety, name='add_variety'),
    path('edit-variety/', edit_variety, name='edit_variety'),
    path('update-variety-wholesale/', update_variety_wholesale, name='update_variety_wholesale'),
    path('api/update-website-bulk/', update_website_bulk, name='update_website_bulk'),
    path('variety/<str:sku_prefix>/update-growout/', update_variety_growout, name='update_variety_growout'),
    path('api/variety-sales/<str:sku_prefix>/', variety_sales_data, name='variety_sales_data'),
    path('variety-usage/<str:sku_prefix>/', variety_usage, name='variety_usage'),
    path('variety/<str:sku_prefix>/update_notes/', update_variety_notes, name='update_variety_notes'),
    path('api/check-shopify-inventory/<str:sku_prefix>/', check_shopify_inventory, name='check_shopify_inventory'),
    
    # ============================================================================
    # PRODUCT MANAGEMENT
    # ============================================================================
    path('edit-products/', product_views.edit_products, name='edit_products'),
    path('add-product/', add_product, name='add_product'),
    path('edit-product/', edit_product, name='edit_product'),
    path('update-product-scoop-size/', update_product_scoop_size, name='update_product_scoop_size'),
    path('assign-lot-to-product/', assign_lot_to_product, name='assign_lot_to_product'),
    path('get-product-packing-history/', get_product_packing_history, name='get_product_packing_history'),
    path('edit-packing-record/', edit_packing_record, name='edit_packing_record'),
    path('delete-packing-record/', delete_packing_record, name='delete_packing_record'),
    path('wholesale-availability/', product_views.wholesale_availability, name='wholesale_availability'),
    path('admin/process-pre-opening-report/', process_pre_opening_report_v2, name='process_pre_opening_report'),
    
    # ============================================================================
    # MIX PRODUCTS
    # ============================================================================
    path('mixes/', mixes, name='mixes'),
    path('mixes/available-lots/', get_available_lots_for_mix, name='get_available_lots_for_mix'),
    path('mixes/existing-lots/', get_existing_mix_lots, name='get_existing_mix_lots'),
    path('mixes/create-lot/', create_mix_lot, name='create_mix_lot'),
    path('mixes/lot-details/<int:mix_lot_id>/', get_mix_lot_details, name='get_mix_lot_details'),
    path('mixes/create-batch/', create_batch, name='create_batch'),
    path('assign-mix-lot/', assign_mix_lot, name='assign_mix_lot'),
    path('mixes/generate-lot-code/', generate_lot_code, name='generate_lot_code'),
    
    # ============================================================================
    # LOT MANAGEMENT
    # ============================================================================
    path('add-lot/', add_lot, name='add_lot'),
    path('delete-lot/', delete_lot, name='delete_lot'),
    path('retire-lot/', retire_lot, name='retire_lot'),
    path('change-lot-status/', change_lot_status, name='change_lot_status'),
    path('set-lot-low-inv/', set_lot_low_inv, name='set_lot_low_inv'),
    path('get-lot-history/', get_lot_history, name='get_lot_history'),
    
    # ============================================================================
    # INVENTORY MANAGEMENT
    # ============================================================================
    path('inventory/', lot_views.inventory, name='inventory'),
    path('update-inventory/', update_inventory, name='update_inventory'),
    path('record-inventory/', record_inventory, name='record_inventory'),
    path('germination-inventory/', germination_inventory_view, name='germination_inventory'),
    path('api/germination-inventory-data/', germination_inventory_data, name='germination_inventory_data'),
    path('inventory-germination/<str:crop>/', products_by_crop_json, name='products_by_crop_json'),
    path('crops-json/', crops_json, name='crops_json'),
    
    # ============================================================================
    # GERMINATION & TESTING
    # ============================================================================
    path('germ-samples/', lot_views.send_germ_samples, name='germ_samples'),
    path('record-germination/', record_germination, name='record_germination'),
    path('api/create-germ-sample-print/', create_germ_sample_print, name='create_germ_sample_print'),
    
    # ============================================================================
    # GROWOUTS
    # ============================================================================
    path('growouts/', lot_views.growouts, name='growouts'),
    path('update-growout/<int:lot_id>/', lot_views.update_growout, name='update_growout'),
    path('create-growout/', create_growout, name='create_growout'),
    path('growout-prep/', lot_views.growout_prep, name='growout_prep'),
    
    # ============================================================================
    # STOCK SEED & BATCHING
    # ============================================================================
    path('record-stock-seed/', record_stock_seed, name='record_stock_seed'),
    path('get-stock-seed-data/', get_stock_seed_data, name='get_stock_seed_data'),
    path('api/create-batch/', lot_views.create_new_batch, name='create_new_batch'),
    path('api/submit-batch/', lot_views.submit_batch, name='submit_batch'),
    
    # ============================================================================
    # PRINTING & LABELS
    # ============================================================================
    path('print-product-labels/', print_product_labels, name='print_product_labels'),
    path('edit-front-labels/', edit_front_labels, name='edit_front_labels'),
    path('edit-back-labels/', edit_back_labels, name='edit_back_labels'),
    path('envelope-data-for-printing/', get_envelope_data_for_printing, name='envelope_data_for_printing'),
    path('check-pick-list-printed/<int:order_id>/', check_pick_list_printed, name='check_pick_list_printed'),
    path('record-pick-list-printed/', record_pick_list_printed, name='record_pick_list_printed'),
    
    # ============================================================================
    # STORE MANAGEMENT
    # ============================================================================
    path('view-stores/', view_stores, name='view_stores'),
    path('<int:store_num>/update/', update_store, name='update_store'),
    path('get-store-orders/<int:store_id>/', get_store_orders, name='get_store_orders'),
    path('process-store-orders/', process_store_orders, name='process_store_orders'),
    path('record-store-returns/', record_store_returns, name='record_store_returns'),
    path('store-returns-years/', get_store_returns_years, name='get_store_returns_years'),
    path('store-returns-data/', get_store_returns_data, name='get_store_returns_data'),
    path('store-sales-data/', get_store_sales_data, name='get_store_sales_data'),
    path('store-sales-details/', store_sales_details, name='store_sales_details'),
    path('set-wholesale-price/', set_wholesale_price, name='set_wholesale_price'),
    
    # ============================================================================
    # ORDER MANAGEMENT
    # ============================================================================
    path('process-online-orders/', order_views.process_online_orders, name='process_online_orders'),
    path('get-pending-orders/', get_pending_orders, name='get_pending_orders'),
    path('get-order-details/<int:order_id>/', get_order_details, name='get_order_details'),
    path('save-order-changes/', save_order_changes, name='save_order_changes'),
    path('finalize-order/', finalize_order, name='finalize_order'),
    
    # ============================================================================
    # ANALYTICS & REPORTING
    # ============================================================================
    path('top-sellers-details/', top_sellers_details, name='top_sellers_details'),
]
## Add a view function to input new products into the database from admin/add-products

from django.shortcuts import render
from stores.models import Store, StoreProduct
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import user_passes_test
from django.http import JsonResponse
import json
from stores.models import StoreOrder
from products.models import Product, Variety
from uprising.utils.auth import is_employee
import os
from datetime import datetime
import io
from django.http import JsonResponse

from django.views.decorators.http import require_http_methods
import pandas as pd

# Handles requests from the admin user to edit the available products for a store
@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def edit_products(request):
    if request.method == 'POST':
        print("POST request received in edit_products view")
        # --- Selecting store - UPDATED ---
        if "store_id" in request.POST:

            store_id = request.POST.get('store_id')
            try:
                store = Store.objects.get(store_num=store_id)
                # Get all products that are available for this store from StoreProduct table
                available_sku_prefixes = list(
                    StoreProduct.objects.filter(
                        store=store, 
                        is_available=True
                    ).values_list('product__variety__sku_prefix', flat=True)
                )

                available_sku_prefixes = [str(item) for item in available_sku_prefixes]
                return JsonResponse({'success': True, 'available_sku_prefixes': available_sku_prefixes})
            except Store.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Store not found'})
        
        # --- Save button clicked - UPDATED ---
        elif "store_handle" in request.POST:
            store_handle = request.POST.get('store_handle')
            store = Store.objects.get(store_num=store_handle)
            new_sku_prefixes = json.loads(request.POST.get('varieties'))  # list of sku_prefixes
            print(f"New SKU prefixes for store {store_handle}: {new_sku_prefixes}")
        
            # set all products for this store to not available
            StoreProduct.objects.filter(store=store).update(is_available=False)
            
            # Then set selected products to available
            for sku_prefix in new_sku_prefixes:
                product = Product.objects.get(
                    variety__sku_prefix=sku_prefix,
                    sku_suffix__endswith="pkt"
                )

                store_product, created = StoreProduct.objects.get_or_create(
                    store=store, 
                    product=product,
                    defaults={'is_available': True}
                )
                if not created:
                    store_product.is_available = True
                    store_product.save()
            
            return JsonResponse({'success': True})
        
        # --- Add items to all stores - UPDATED ---
        elif "varieties_to_add" in request.POST:
            varieties_to_add = json.loads(request.POST.get('varieties_to_add'))  # list of sku_prefixes

            for store in Store.objects.all():
                for sku_prefix in varieties_to_add:
                    try:
                        # Get the 'pkt' product for this variety
                        product = Product.objects.get(
                            variety__sku_prefix=sku_prefix,
                            sku_suffix__endswith="pkt"
                        )

                        store_product, created = StoreProduct.objects.get_or_create(
                            store=store,
                            product=product,
                            defaults={'is_available': True}
                        )
                        if not created:
                            store_product.is_available = True
                            store_product.save()

                    except Product.DoesNotExist:
                        # optional: log or skip varieties without a 'pkt' product
                        print(f"No 'pkt' product found for variety {sku_prefix}")
                        continue

            return JsonResponse({'success': True})

        # --- Remove items from all stores - UPDATED ---
        elif "varieties_to_remove" in request.POST:
            varieties_to_remove = json.loads(request.POST.get('varieties_to_remove'))  # list of sku_prefixes

            for store in Store.objects.all():
                for sku_prefix in varieties_to_remove:
                    try:
                        # Find the 'pkt' product for this variety
                        product = Product.objects.get(
                            variety__sku_prefix=sku_prefix,
                            sku_suffix__endswith="pkt"
                        )

                        StoreProduct.objects.filter(
                            store=store,
                            product=product
                        ).update(is_available=False)

                    except Product.DoesNotExist:
                        print(f"No 'pkt' product found for variety {sku_prefix}")
                        continue

            return JsonResponse({'success': True})


        # --- Sync store from most recent order - UPDATED --- THIS IS NOT IMPLEMENTED YET
        # elif "store_to_sync" in request.POST:
        #     store_to_sync = json.loads(request.POST.get('store_to_sync'))
        #     store = Store.objects.get(store_number=store_to_sync)
        #     most_recent_order = StoreOrder.objects.filter(order_number__startswith=store_to_sync).order_by('-order_number').first()
        #     if most_recent_order:
        #         # First set all products for this store to not available
        #         StoreProduct.objects.filter(store=store).update(is_available=False)
                
        #         # Then set products from the order to available
        #         products_in_order = most_recent_order.products.all()
        #         for product in products_in_order:
        #             store_product, created = StoreProduct.objects.get_or_create(
        #                 store=store, 
        #                 product=product,
        #                 defaults={'is_available': True}
        #             )
        #             if not created:
        #                 store_product.is_available = True
        #                 store_product.save()
        #     return JsonResponse({'success': True})
        # else:
        #     return JsonResponse({'success': False})
    else:
        # GET request → render form with seed availabilities for first store (optional)
        varieties = Variety.objects.filter(wholesale=True).order_by('category', 'veg_type', 'var_name')
     
        # exclude stores whose name starts with "Ballard"
        stores = Store.objects.all()
        # stores = Store.objects.exclude(name__startswith="Ballard").all()
        veg_types = varieties.order_by('veg_type').values_list('veg_type', flat=True).distinct()
        veg_types = list(veg_types)
        context = {
            'varieties': varieties,
            'stores': stores,
            'veg_types': veg_types,
        }
        return render(request, 'products/edit_products.html', context)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def shopify_inventory(request):
    """
    Handle Shopify inventory CSV upload and processing
    """
    try:

        uploaded_file = request.FILES.get('csv_file')

        
        if not uploaded_file.name.endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'Only CSV files are allowed'})
        
        df = pd.read_csv(uploaded_file, dtype=str)

        # Check if bulk inventory was requested
        prefix = request.POST.get('sku_prefix')
        if prefix:
            # TODO: Implement bulk inventory processing logic her

            active_varieties = Variety.objects.filter(sku_prefix__startswith=prefix, active=True)
            print(f"Active varieties: {active_varieties}")

            if not active_varieties.exists():
                return JsonResponse({
                    'message': f"No products found with SKU prefix '{prefix}'",
                    'type_inventory': {}
                })

            inventory_dict = {}

            for variety in active_varieties:
                sku_prefix = variety.sku_prefix
                inventory_dict[sku_prefix] = {"variety": variety.var_name}

                for product in variety.products.all():  # assuming reverse FK is `products`
                    sku = f"{sku_prefix}-{product.sku_suffix}"

                    # safely look up the product in the DataFrame
                    product_row = df[df["Variant SKU"].str.startswith(sku, na=False)]
                    if product_row.empty:
                        continue

                    # check if product is tracked by Shopify
                    if product_row["Variant Inventory Tracker"].values[0] != "shopify":
                        inv_qty = "NOT TRACKED"
                    else:
                        inv_qty = product_row["Variant Inventory Qty"].values[0]

                    inventory_dict[sku_prefix][sku] = inv_qty

            return JsonResponse({
                'message': 'Bulk inventory processed successfully',
                'type_inventory': inventory_dict
            })

        else:

            pkt_threshold = request.POST.get('pkt_threshold')
            pkt_threshold = int(pkt_threshold)
   
            # Clean & prepare columns
            df["Variant Inventory Qty"] = (
                pd.to_numeric(df["Variant Inventory Qty"], errors="coerce")
                .fillna(0)
                .astype(int)
            )

            df["prefix"] = df["Variant SKU"].str[:6].fillna("")

            # Filter shopify-tracked items
            shop = df[df["Variant Inventory Tracker"] == "shopify"]

            # Low inventory packets
            pkts = shop[shop["Variant SKU"].str.contains("pkt", na=False)]

            low_pkts = pkts[(pkts["Variant Inventory Qty"] <= pkt_threshold) & (pkts["Variant Inventory Qty"] >= 0)]

            prefix_to_variety = {
                v.sku_prefix: v.var_name for v in Variety.objects.all()
            }
            
            variety_inventory = {}
            for _, row in low_pkts.iterrows():
                prefix = row["prefix"]
                qty = row["Variant Inventory Qty"]
                variety_name = prefix_to_variety.get(prefix, f"Unknown ({prefix})")

                variety_inventory[variety_name] = qty

            # ============ BULK INVENTORY SPLIT CHECK ============ #
            # Filter bulk SKUs (non-packets)
            bulk = shop[
                (~shop["Variant SKU"].str.contains("pkt", na=False))
                & shop["Variant SKU"].notna()
            ]

            # Build a simple dict of bulk SKUs needing split
            split_dict = {}

            for prefix, grp in bulk.groupby("prefix", sort=False):
                qtys = grp["Variant Inventory Qty"].tolist()
                
                # Check if any non-final zero needs splitting
                for idx, q in enumerate(qtys[:-1]):
                    if q == 0 and any(q2 > 0 for q2 in qtys[idx + 1 :]):
                        # lookup variety
                        variety = Variety.objects.filter(sku_prefix=prefix).first()
                        if variety:
                            split_dict[variety.var_name] = variety.veg_type
                        else:
                            split_dict[f"Unknown ({prefix})"] = "Unknown"
                        break
            print(f"Bulk SKUs needing splitting: {split_dict}")

            return JsonResponse({
                'message': 'Packet inventory processed successfully',
                'variety_inventory': variety_inventory,
                'bulk_split_dict': split_dict
            })

    except KeyError as e:
        print(">>> KeyError encountered:", str(e))
        return JsonResponse({'error': f"Missing expected column in CSV: {str(e)}"}, status=400)
    except Exception as e:
        import traceback
        print(">>> Unexpected error:", str(e))
        print(traceback.format_exc())
        return JsonResponse({'error': f"Unexpected error: {str(e)}"}, status=500)
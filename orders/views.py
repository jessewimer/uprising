from rest_framework import viewsets
from .serializers import OrderSerializer
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from io import BytesIO
from django.db.models import Max
from .models import OnlineOrder, OOIncludes, OOIncludesMisc, BatchMetadata, BulkBatch
from django.http import JsonResponse
from stores.models import StoreOrder, SOIncludes
import json
import csv
import io
from django.views.decorators.http import require_http_methods
import requests
from django.contrib.auth.decorators import login_required, user_passes_test
from uprising.utils.auth import is_employee
import pandas as pd
from products.models import Product, MiscProduct, LabelPrint
from lots.models import Lot, MixLot
from django.db import transaction
from django.utils.timezone import now
from datetime import datetime
import pytz
from django.utils import timezone
pacific_tz = pytz.timezone("America/Los_Angeles")
from django.utils.timezone import localtime
from io import BytesIO
from django.conf import settings
 

# ReportLab imports
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle



""" The following functionn takes a dict of bulk items. Full product SKU (e.g. BEA-TA-1/2lb) as keys and quantities as values
    and calculates how many bulk need to be printed vs. pulled and returns two dicts. If items need to be printed,
    the product.bulk_pre_pack field is updated accordingly."""

def calculate_bulk_pull_and_print(bulk_items):

    bulk_to_print = {}
    bulk_to_pull = {}

    for sku, qty in bulk_items.items():
        # Find product by prefix/suffix
        product = Product.objects.filter(
            variety=sku[:6],
            sku_suffix=sku[7:]
        ).select_related("variety").first()

        if not product:
            print(f"Product with SKU {sku} not found!")
            continue

        try:
            quantity_to_print = 0
            quantity_to_pull = 0

            if product.bulk_pre_pack == 0:
                quantity_to_print = qty

            elif qty <= product.bulk_pre_pack:
                product.bulk_pre_pack -= qty
                quantity_to_pull = qty

            else:
                pre_pack = product.bulk_pre_pack
                product.bulk_pre_pack = 0
                quantity_to_pull = pre_pack
                quantity_to_print = qty - pre_pack

            # persist product bulk_pre_pack changes
            product.save()

            lot_value = ""
            if product.lot:
                lot_value = f"{product.lot.grower}{product.lot.year}"
            else:
                lot_value = "N/A"
            current_germ_obj = product.lot.get_most_recent_germination() if product.lot else None
            germination = current_germ_obj.germination_rate if current_germ_obj else None
            for_year = current_germ_obj.for_year if current_germ_obj else None

            # ---- BUILD bulk_to_print dict ----
            if quantity_to_print > 0:
                if product.env_multiplier and product.env_multiplier > 1:
                    alt_sku = product.alt_sku
                    # extract portion of alt sku after the last dash
                    alt_sku_suffix = alt_sku.split("-")[-1] if alt_sku else ""
                    # alt_quantity_to_print *= product.env_multiplier
                    alt_product = product.variety.products.filter(
                        sku_suffix=alt_sku_suffix
                    ).first()
                    env_type = alt_product.env_type
                    pkg_size = alt_product.pkg_size if alt_product else product.pkg_size
                else:
                    pkg_size = product.pkg_size
                    env_type = product.env_type

                entry = {
                    "quantity": quantity_to_print,
                    "variety_name": product.variety.var_name,
                    "crop": product.variety.crop,
                    "category": product.variety.category,
                    "days": product.variety.days,
                    "common_name": product.variety.common_name or "",
                    "desc1": product.variety.desc_line1,
                    "desc2": product.variety.desc_line2,
                    "desc3": product.variety.desc_line3 or "",
                    "lot": lot_value,
                    "pkg_size": pkg_size,
                    "alt_sku": product.alt_sku or "",
                    "env_multiplier": product.env_multiplier,
                    "print_back": product.print_back,
                    "env_type": env_type,   # include for sorting
                    "sku_prefix": product.variety.sku_prefix,  # include for sorting
                    "rad_type": product.get_rad_type(),
                    "germination": germination,
                    "for_year": for_year,
                }

                if product.print_back:
                    # print(f"Processing print back for SKU {sku}")
                    entry.update({
                        "back1": product.variety.back1,
                        "back2": product.variety.back2,
                        "back3": product.variety.back3,
                        "back4": product.variety.back4,
                        "back5": product.variety.back5,
                        "back6": product.variety.back6,
                        "back7": product.variety.back7 or "",
                    })

                bulk_to_print[sku] = entry

            # ---- BUILD bulk_to_pull dict ----
            if quantity_to_pull > 0:
                bulk_to_pull[sku] = {
                    "var_name": product.variety.var_name,
                    "crop": product.variety.crop,
                    "category": product.variety.category,
                    "sku_suffix": product.sku_suffix,
                    "quantity": quantity_to_pull,
                }

        except Exception as e:
            print(f"Error processing SKU {sku}: {e}")
            continue

    # sort dicts by SKU
    # bulk_to_print = dict(sorted(bulk_to_print.items()))
    # bulk_to_print = dict(
    #     sorted(
    #         bulk_to_print.items(),
    #         key=lambda item: (item[1].get("env_type", ""), item[1].get("sku_prefix", ""))
    #     )
    # )
    bulk_to_print = dict(
        sorted(
            bulk_to_print.items(),
            key=lambda item: (
                item[1].get("category", ""),
                item[1].get("env_type", ""),
                item[1].get("sku_prefix", "")
            )
        )
    )

    bulk_to_pull = dict(
        sorted(
            bulk_to_pull.items(),
            key=lambda item: (item[1].get("category", ""), item[0])  # category first, then SKU
        )
    )
    # bulk_to_pull = dict(sorted(bulk_to_pull.items()))

    return bulk_to_print, bulk_to_pull

def enrich_bulk_to_pull_and_print(bulk_items):
    # print(f"DEBUG - enrich_bulk_to_pull_and_print received: {list(bulk_items.keys())}")
    # print(f"DEBUG - GRE-AS-5lb in bulk_items: {'GRE-AS-5lb' in bulk_items}")
    # print("Enriching bulk items:", bulk_items)
    bulk_to_print = {}
    bulk_to_pull = {}

    # new format of bulk_items:
    # sku: [print_qty, pull_qty]
    for sku, [print_qty, pull_qty] in bulk_items.items():
        # print(f"Processing SKU {sku} for action {action} with qty {qty}")
        # Find product by prefix/suffix
        product = Product.objects.filter(
            variety=sku[:6],
            sku_suffix=sku[7:]
        ).select_related("variety").first()
        # if action == 'print':
            # print(f'Enriching for print: {sku} qty {qty}') 
        if not product:
            print(f"Product with SKU {sku} not found!")
            continue

        if print_qty > 0:
            # quantity_to_print = qty
            # print(f'action is print for {sku} qty {qty}')

            if product.env_multiplier and product.env_multiplier > 1:
                # alt_quantity_to_print *= product.env_multiplier
                alt_sku = product.alt_sku
                # extract portion of alt sku after the last dash
                alt_sku_suffix = alt_sku.split("-")[-1] if alt_sku else ""
                alt_product = product.variety.products.filter(
                    sku_suffix=alt_sku_suffix
                ).first()
                env_type = alt_product.env_type
                pkg_size = alt_product.pkg_size if alt_product else product.pkg_size
            else:
                pkg_size = product.pkg_size
                env_type = product.env_type

            lot_value = ""
            if product.lot:
                lot_value = f"{product.lot.grower}{product.lot.year}"
            else:
                lot_value = "N/A"
            
            current_germ_obj = product.lot.get_most_recent_germination() if product.lot else None
            germination = current_germ_obj.germination_rate if current_germ_obj else None
            for_year = current_germ_obj.for_year if current_germ_obj else None

            entry = {
                "quantity": print_qty,
                "variety_name": product.variety.var_name,
                "crop": product.variety.crop,
                "category": product.variety.category, 
                "days": product.variety.days,
                "common_name": product.variety.common_name or "",
                "desc1": product.variety.desc_line1,
                "desc2": product.variety.desc_line2,
                "desc3": product.variety.desc_line3 or "",
                "lot": lot_value,
                "pkg_size": pkg_size,
                "alt_sku": product.alt_sku or "",
                "env_multiplier": product.env_multiplier,
                "print_back": product.print_back,
                "env_type": env_type,   # include for sorting
                "sku_prefix": product.variety.sku_prefix,  # include for sorting
                "rad_type": product.get_rad_type(),
                "germination": germination,
                "for_year": for_year,
            }

            if product.print_back:
                entry.update({
                    "back1": product.variety.back1,
                    "back2": product.variety.back2,
                    "back3": product.variety.back3,
                    "back4": product.variety.back4,
                    "back5": product.variety.back5,
                    "back6": product.variety.back6,
                    "back7": product.variety.back7 or "",
                })

            bulk_to_print[sku] = entry
        if pull_qty > 0:

            bulk_to_pull[sku] = {
                "var_name": product.variety.var_name,
                "crop": product.variety.crop,
                "category": product.variety.category,
                "sku_suffix": product.sku_suffix,
                "quantity": pull_qty,
            }


    # sort dicts by SKU
    # bulk_to_print = dict(sorted(bulk_to_print.items()))
    # bulk_to_print = dict(
    #     sorted(
    #         bulk_to_print.items(),
    #         key=lambda item: (item[1].get("env_type", ""), item[1].get("sku_prefix", ""))
    #     )
    # )
    bulk_to_print = dict(
        sorted(
            bulk_to_print.items(),
            key=lambda item: (
                item[1].get("category", ""),
                item[1].get("env_type", ""),
                item[1].get("sku_prefix", "")
            )
        )
    )

    bulk_to_pull = dict(
        sorted(
            bulk_to_pull.items(),
            key=lambda item: (item[1].get("category", ""), item[0])  # category first, then SKU
        )
    )
    # bulk_to_pull = dict(sorted(bulk_to_pull.items()))

    return bulk_to_print, bulk_to_pull


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def process_online_orders(request):
    """
    Order Processing Page
    """
    # Get the latest 5 BatchMetadata objects, newest first
    recent_batches = BatchMetadata.objects.order_by('-batch_date')[:5]
    batch_list = []
    
    """ Dict should take this form: {SKU: [print_qty, pull_qty]} """
    for batch in recent_batches:
        bulk_items = {}
        for bulk_item in batch.bulk_batches.all():
            sku = bulk_item.sku
            qty = bulk_item.quantity
            action = bulk_item.bulk_type  

                    # Initialize the list if this SKU doesn't exist yet
            if sku not in bulk_items:
                bulk_items[sku] = [0, 0]  # [print_qty, pull_qty]

            if action == 'print':
              bulk_items[sku][0] = qty
            elif action == 'pull':
              bulk_items[sku][1] = qty


        # print(f"Batch {batch.batch_identifier} bulk_items: {bulk_items}")
        # # Use your existing function to enrich SKUs with product info
        bulk_to_print, bulk_to_pull = enrich_bulk_to_pull_and_print(bulk_items)
        
        batch_list.append({
            'id': batch.id,
            'batch_date': batch.batch_date,
            'bulk_to_print': bulk_to_print,
            'bulk_to_pull': bulk_to_pull,
        })
    
    # cuyear = settings.CURRENT_ORDER_YEAR
    context = {
        'recent_batches': batch_list,
        'current_order_year': settings.CURRENT_ORDER_YEAR,
    }
    return render(request, 'orders/process_online_orders.html', context)




def sanitize_note(note_value):
    """
    Sanitize note text by removing or replacing problematic characters.
    Returns cleaned string or placeholder if cleaning fails.
    """
    if pd.isna(note_value):
        return ""
    
    try:
        # Convert to string and strip whitespace
        note = str(note_value).strip()
        
        # Replace common line breaks
        note = note.replace('\r\n', '\n').replace('\r', '\n')
        
        # Encode to ASCII, replacing unknown chars with '?', then decode back
        # This removes emojis and other non-ASCII characters
        note = note.encode('ascii', errors='ignore').decode('ascii')
        
        # If the note became empty after cleaning, indicate there was content
        if not note and str(note_value).strip():
            return "**Customer Note - See Shopify**"
        
        return note
        
    except Exception:
        # If any error occurs during sanitization
        return "**Customer Note - See Shopify**"
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
@transaction.atomic
def process_orders(request):
    """
    Process uploaded CSV file for orders
    Expected response format:
    - success: True/False
    - message: 'wrong file' | 'orders already processed' | success message
    - bulk_items_to_print: [{'name': str, 'quantity': int}, ...]
    - bulk_items_to_pull: [{'name': str, 'quantity': int}, ...]
    """
    try:
        if 'csv_file' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No CSV file provided'})
        
        csv_file = request.FILES['csv_file']

        if not csv_file.name.endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'Only CSV files are allowed'})
    
        df = pd.read_csv(csv_file, header=0, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)

        # Extract unique SKUs from the "Lineitem sku" column
        skus_in_csv = df["Lineitem sku"].dropna().unique()

        missing_skus = []

        for full_sku in skus_in_csv:
            full_sku = full_sku.strip()
            found = False

            # First, try splitting into prefix and suffix for Product table
            try:
                parts = full_sku.split("-")
                if len(parts) >= 3:
                    sku_prefix = "-".join(parts[:-1])
                    sku_suffix = parts[-1]
                    found = Product.objects.filter(
                        variety_id=sku_prefix, sku_suffix=sku_suffix
                    ).first() is not None
            except Exception:
                pass  # safe to ignore — fallback to misc below

            # Fallback: check full sku in MiscProduct table
            if not found:
                # MiscProduct lookup
                found = MiscProduct.objects.filter(sku=full_sku).first() is not None

            if not found:
                missing_skus.append(full_sku)


        # Show a message box and halt if any SKUs are missing
        if missing_skus:
            missing_str = "\n".join(sorted(missing_skus))
            return JsonResponse({
                'success': False,
                'error': f"The following SKUs are missing from the database:\n{missing_str}"
            })
        

        # find unique order numbers
        order_numbers = df['Name'].unique()

        # Strip 'S' prefix and convert to integers
        order_numbers_int = [int(order[1:]) for order in order_numbers]
        # Get the lowest and highest order numbers
        first_order = min(order_numbers_int)
        last_order = max(order_numbers_int)
        
        missing_orders = []
        print(f"First Order: {first_order}, Last Order: {last_order}")
        # check to see if any of the orders in the range are not present
        for order_number in range(first_order, last_order + 1):
            if order_number not in order_numbers_int:
                missing_orders.append(order_number)

        # check each unique order to see if it exists in the database
        for order_number in order_numbers:
            order = OnlineOrder.objects.filter(order_number=order_number).first()
            if order:
                return JsonResponse({
                    'success': False,
                    'error': 'One or more of these orders have already been printed.'
                })
        
        current_order = None
        current_order_items = []
        current_order_misc_items = []
        bulk_orders = []
        customer_orders = {}
        bulk_items = {}
        misc_orders = []
        order_start_date = None
        order_end_date = None

        for index, row in df.iterrows():
            order_number = row['Name']
            product_sku = str(row['Lineitem sku']).strip()
            product_qty = int(row['Lineitem quantity'])

            # Detect new order
            if current_order is None or order_number != current_order.order_number:
                # Save the previous order if it exists
                if current_order is not None:
                    current_order.save()
                    for item in current_order_items:
                        item.order = current_order
                        item.save()
                    for item in current_order_misc_items:
                        item.order = current_order
                        item.save()

                # === BEGIN NEW DATE PARSING LOGIC === 1/14/26
                # Parse date and extract just the date portion  
                date_string = row['Created at'].strip()
                formats = [
                    '%m/%d/%Y %H:%M',
                    '%Y-%m-%d %H:%M:%S %z',
                    '%Y-%m-%d %H:%M:%S',
                ]
                parsed_date = None
                for fmt in formats:
                    try:
                        parsed_datetime = datetime.strptime(date_string, fmt)
                        parsed_date = parsed_datetime.date()  # Extract just the date (1/8/2026)
                        break
                    except ValueError:
                        continue

                if parsed_date is None:
                    raise ValueError(f"Unexpected date format: {date_string}")

                # Create datetime at noon Pacific time - this ensures it stays the same date in any timezone
                date = pacific_tz.localize(datetime.combine(parsed_date, datetime.strptime('12:00', '%H:%M').time()))


                # === END NEW DATE PARSING LOGIC ===

                order_start_date = min(order_start_date, date) if order_start_date else date
                order_end_date = max(order_end_date, date) if order_end_date else date

                postal_code = str(row['Shipping Zip']).lstrip("'") if not pd.isna(row['Shipping Zip']) else str(row['Billing Zip'])
                address = row['Shipping Address1'] if not pd.isna(row['Shipping Address1']) else row['Billing Address1']
                address2 = row['Shipping Address2'] if not pd.isna(row['Shipping Address2']) else row['Billing Address2']
                country = row['Shipping Country'] if not pd.isna(row['Shipping Country']) else row['Billing Country']
                city = row['Shipping City'] if not pd.isna(row['Shipping City']) else row['Billing City']
                state = row['Shipping Province'] if not pd.isna(row['Shipping Province']) else row['Billing Province']
                customer_name = row['Shipping Name']
                if pd.isna(customer_name) or str(customer_name).strip() == "":
                    customer_name = row['Billing Name']
                # sanitize: make sure it's a string and empty if missing
                if pd.isna(address2) or str(address2).strip() == "" or isinstance(address2, float):
                    address2 = ""

                # note = row['Notes'] if not pd.isna(row['Notes']) else ""
                # note = str(note).strip().replace('\r\n', '\n').replace('\r', '\n')
                note = row['Notes'] if not pd.isna(row['Notes']) else ""
                note = sanitize_note(note) 

                current_order = OnlineOrder(
                    order_number=order_number,
                    shipping_company=row['Shipping Company'],
                    address=address,
                    address2=address2,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    country=country,
                    shipping=row['Shipping'],
                    customer_name=customer_name,
                    tax=row['Taxes'],
                    subtotal=row['Subtotal'],
                    total=row['Total'],
                    date=date,
                    note=note,
                )

                # # Track duplicates per customer
                if customer_name in customer_orders:
                    customer_orders[customer_name].append(order_number)
                else:
                    customer_orders[customer_name] = [order_number]

                current_order_items = []
                current_order_misc_items = []

            # Product lookups
            product = Product.objects.filter(
                variety=product_sku[:6],
                sku_suffix=product_sku[7:]
            ).first()

            if not product:
                product = MiscProduct.objects.filter(sku=product_sku).first()
                if not product:
                    print(f"Product with SKU {product_sku} not found, skipping…")
                    continue
                else:

                    misc_item = OOIncludesMisc(
                        order=current_order,
                        price=row['Lineitem price'],
                        qty=product_qty,
                        sku=product_sku,
                    )
                    current_order_misc_items.append(misc_item)

                    if order_number not in misc_orders:
                        current_order.misc = True
                        misc_orders.append(order_number)
            else:
                # bulk vs packet logic
                is_bulk_item = "pkt" not in product_sku.lower()
                if is_bulk_item:
                    bulk_items[product_sku] = bulk_items.get(product_sku, 0) + product_qty
                    if order_number not in bulk_orders:
                        current_order.bulk = True
                        bulk_orders.append(order_number)

                item = OOIncludes(
                    order=current_order,
                    price=row['Lineitem price'],
                    qty=product_qty,
                    product=product,
                )
                current_order_items.append(item)

        # Save last order
        if current_order is not None:
            current_order.save()
            for item in current_order_items:
                item.order = current_order
                item.save()
            for item in current_order_misc_items:
                item.order = current_order
                item.save()


        if bulk_items:

            # print(f"DEBUG - bulk_items keys: {list(bulk_items.keys())}")
            # print(f"DEBUG - GRE-AS-5lb in bulk_items: {'GRE-AS-5lb' in bulk_items}")

            # get the last batch record
            last_batch = BatchMetadata.objects.order_by("-id").first()
            if last_batch:
                last_batch_number = int(last_batch.batch_identifier.split("-")[1])
            else:
                last_batch_number = 0

            new_batch_number = last_batch_number + 1
            meta_batch_id = f"{now().strftime('%y%m%d')}-{new_batch_number}"

            # create the BatchMetadata record
            bulk_batch = BatchMetadata.objects.create(
                batch_date=localtime(timezone.now(), pacific_tz).date(),
                batch_identifier=meta_batch_id,
                start_order_number=first_order,
                end_order_number=last_order,
                start_order_date=order_start_date,
                end_order_date=order_end_date,
            )

            # calculate bulk items
            bulk_to_print, bulk_to_pull = calculate_bulk_pull_and_print(bulk_items)


            # print(f"Bulk to print: {bulk_to_print}")
            # print(f"Bulk to pull: {bulk_to_pull}")

            # add "print" bulk items
            if bulk_to_print:
                for sku, details in bulk_to_print.items():
                    BulkBatch.objects.create(
                        batch_identifier=bulk_batch,
                        bulk_type="print",
                        sku=sku,
                        quantity=details['quantity'],  # <-- extract the number
                    )

            # add "pull" bulk items
            if bulk_to_pull:
                for sku, details in bulk_to_pull.items():
                    BulkBatch.objects.create(
                        batch_identifier=bulk_batch,
                        bulk_type="pull",
                        sku=sku,
                        quantity=details['quantity'],  # <-- extract the number
                    )


        # ------------------------------------------------------------
        # Build a comprehensive dict to hold all order data
        # Keys = order numbers
        # Values = compound dicts with:
        #   - metadata from OnlineOrder
        #   - items grouped into:
        #       "misc_items"  (from OOIncludesMisc)
        #       "bulk_items"  (Product.sku_suffix != "pkt")
        #       "pkt_items"   (Product.sku_suffix == "pkt")
        # Items are sorted by: quantity DESC, then product.rack_location
        # ------------------------------------------------------------
        order_data = {}

        all_orders = OnlineOrder.objects.filter(
            order_number__in=order_numbers
        ).prefetch_related(
            "includes__product__variety",   # replaces ooincludes_set
            "includes_misc"                 # replaces ooincludesmisc_set
        )


        for order in all_orders:
            # collect base order info
            order_dict = {
                "order_number": order.order_number,
                "customer_name": order.customer_name,
                "address": order.address,
                "address2": order.address2,
                "city": order.city,
                "state": order.state,
                "postal_code": order.postal_code,
                "country": order.country,
                "shipping_company": order.shipping_company,
                "shipping": order.shipping,
                "tax": order.tax,
                "subtotal": order.subtotal,
                "total": order.total,
                "date": order.date.isoformat() if order.date else None,
                "note": order.note,
                "misc_items": [],
                "bulk_items": [],
                "pkt_items": [],
            }

            # -------------------------
            # Misc items
            # -------------------------
            for misc in order.includes_misc.all():   # ✅ use related_name
                misc_product = MiscProduct.objects.get(sku=misc.sku)
                lineitem_name = misc_product.lineitem_name
                order_dict["misc_items"].append({
                    "sku": misc.sku,
                    "qty": misc.qty,
                    "price": misc.price,
                    "lineitem": lineitem_name,
                })

            # -------------------------
            # Regular items (bulk / pkt)
            # -------------------------
            for inc in order.includes.all():   # ✅ use related_name
                product = inc.product
                variety = product.variety

                entry = {
                    "sku": f"{product.variety_id}-{product.sku_suffix}",
                    "qty": inc.qty,
                    "price": inc.price,
                    "rack_location": product.rack_location or "",
                    "variety_name": variety.var_name,
                    "crop": variety.crop,
                    "pkg_size": product.pkg_size,
                    'lineitem': product.lineitem_name or "",
                }

                if product.sku_suffix.lower() == "pkt":
                    order_dict["pkt_items"].append(entry)
                else:
                    order_dict["bulk_items"].append(entry)


            # -------------------------
            # Sort groups
            # -------------------------
            def sort_key(item):
                return (-item["qty"], item.get("rack_location") or "")

            order_dict["misc_items"].sort(key=sort_key)
            order_dict["bulk_items"].sort(key=sort_key)
            order_dict["pkt_items"].sort(key=sort_key)

            # Save into global dict
            order_data[order.order_number] = order_dict

        # ------------------------------------------------------------
            current_batch = BatchMetadata.objects.order_by("-batch_date").first()

            # serialize batch metadata
            batch_metadata_dict = None
            bulk_batches_list = []

            if current_batch:
                batch_metadata_dict = {
                    "id": current_batch.id,
                    "batch_identifier": current_batch.batch_identifier,
                    "batch_date": current_batch.batch_date.isoformat(),
                    "start_order_number": current_batch.start_order_number,
                    "end_order_number": current_batch.end_order_number,
                    "start_order_date": current_batch.start_order_date.isoformat(),
                    "end_order_date": current_batch.end_order_date.isoformat(),
                }
            

        return JsonResponse({
            'success': True,
            'message': f"Processed orders from {order_start_date} to {order_end_date}",
            'bulk_to_print': bulk_to_print,
            'bulk_to_pull': bulk_to_pull,
            'customer_orders': customer_orders,
            'missing_orders': missing_orders,
            'bulk_orders': bulk_orders,
            'misc_orders': misc_orders,
            'order_data': order_data,
            'batch_metadata': batch_metadata_dict,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Error processing orders: {e}"})
 

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def reprint_packing_slip(request, order_id):
    try:
        order_number = order_id.strip()
        
        if not order_number:
            return JsonResponse({'success': False, 'error': 'Order number required'})
       
        # print(f"Reprinting order: {order_number}")
       
        # Get the order and related data
        order = OnlineOrder.objects.filter(order_number=order_number).first()
        if not order:
            return JsonResponse({
                'success': True,
                'message': 'order not found'
            })
       
        # Get the order includes/line items
        order_includes = OOIncludes.objects.filter(order_id=order_number)
        order_includes_misc = OOIncludesMisc.objects.filter(order_id=order_number)
        
        # Build your order data dictionary (similar to what your original code expects)
        order_data = {
            'order_number': order.order_number,
            'customer_name': order.customer_name,
            'address': order.address,
            'address2': order.address2,
            'city': order.city,
            'state': order.state,
            'postal_code': order.postal_code,
            'country': order.country,
            'shipping': order.shipping,
            'subtotal': order.subtotal,
            'tax': order.tax,
            'total': order.total,
            'note': order.note,
            'date': order.date.isoformat(),
            'misc_items': [],  # populate from order_includes
            'bulk_items': [],  # populate from order_includes
            'pkt_items': [],   # populate from order_includes
        }
        
        # Populate the line items from OOIncludes
        if order_includes:
            # print(f"Found {order_includes.count()} line items for order {order_number}")
            for include in order_includes:
                line_item = {
                    'qty': include.qty,
                    'lineitem': include.product.lineitem_name if include.product else "Unknown",  
                    'price': str(float(include.price)), 
                    'rack_location': include.product.rack_location if include.product else "",
                    'sku_prefix': include.product.variety.sku_prefix if include.product else "",
                }

                if include.product.sku_suffix == 'pkt':
                    order_data['pkt_items'].append(line_item)
                else:
                    order_data['bulk_items'].append(line_item)

        if order_includes_misc:
            # print(f"Found {order_includes_misc.count()} misc items for order {order_number}")
            for include in order_includes_misc:
                # lookup misc product name
                misc_product = MiscProduct.objects.filter(sku=include.sku).first()
                line_item = {
                    'qty': include.qty,
                    'lineitem': misc_product.lineitem_name if misc_product else "Unknown",
                    'price': str(float(include.price)),
                }
                order_data['misc_items'].append(line_item)
        
        # sort misc by qty desc
        order_data['misc_items'].sort(key=lambda x: -x['qty'])

        # sort bulk by qty desc, then sku_prefix
        order_data['bulk_items'].sort(key=lambda x: (-x['qty'], x.get('sku_prefix', '')))

        # sort pkt by qty desc, then rack_location (convert to float for proper numerical sorting)
        order_data['pkt_items'].sort(key=lambda x: (
            -x['qty'], 
            float(x.get('rack_location', 0)) if x.get('rack_location') else 0
        ))

        # print(f"Made it this far!")
        return JsonResponse({
            'success': True,
            'order_data': order_data
        })

    except Exception as e:
        print(f"Error generating packing slip: {e}")
        return JsonResponse({'success': False, 'error': str(e)})





# NEEDS WORK !!!!!!!!!!!
@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def reprocess_order(request, order_id):
    try:
        order_number = order_id.strip()
        
        if not order_number:
            return JsonResponse({'success': False, 'error': 'Order number required'})
       
        # print(f"Reprocessing order: {order_number}")
       
        # Get the order and related data (same as reprint)
        order = OnlineOrder.objects.filter(order_number=order_number).first()
        if not order:
            return JsonResponse({
                'success': True,
                'message': 'order not found'
            })
       
        # Get the order includes/line items (same as reprint)
        order_includes = OOIncludes.objects.filter(order_id=order_number)
        order_includes_misc = OOIncludesMisc.objects.filter(order_id=order_number)
        
        # Build order data (same as reprint function)
        order_data = {
            'order_number': order.order_number,
            'customer_name': order.customer_name,
            'address': order.address,
            'address2': order.address2,
            'city': order.city,
            'state': order.state,
            'postal_code': order.postal_code,
            'country': order.country,
            'shipping': order.shipping,
            'subtotal': order.subtotal,
            'tax': order.tax,
            'total': order.total,
            'note': order.note,
            'date': order.date.isoformat(),
            'misc_items': [],
            'bulk_items': [],
            'pkt_items': [],
        }
        
        bulk_items = {}

        # Populate line items (same as reprint function)
        if order_includes:
            for include in order_includes:
                line_item = {
                    'qty': include.qty,
                    'lineitem': include.product.lineitem_name if include.product else "Unknown",  
                    'price': str(float(include.price)),
                    'rack_location': include.product.rack_location if include.product else "",
                    'sku_prefix': include.product.variety.sku_prefix if include.product else "",
                }
                if include.product.sku_suffix == 'pkt':
                    order_data['pkt_items'].append(line_item)
                else:
                    order_data['bulk_items'].append(line_item)
                    sku = f"{include.product.variety_id}-{include.product.sku_suffix}"
                    # print(f"Adding bulk item SKU: {sku} Qty: {include.qty}")
                    bulk_items[sku] = bulk_items.get(sku, 0) + include.qty


        if order_includes_misc:
            for include in order_includes_misc:
                misc_product = MiscProduct.objects.filter(sku=include.sku).first()
                line_item = {
                    'qty': include.qty,
                    'lineitem': misc_product.lineitem_name if misc_product else "Unknown",
                    'price': str(float(include.price)),
                }
                order_data['misc_items'].append(line_item)
       
        # Apply same sorting as reprint
        order_data['misc_items'].sort(key=lambda x: -x['qty'])
        order_data['bulk_items'].sort(key=lambda x: (-x['qty'], x.get('sku_prefix', '')))
        order_data['pkt_items'].sort(key=lambda x: (
            -x['qty'],
            float(x.get('rack_location', 0)) if x.get('rack_location') else 0
        ))
        
        bulk_to_print, bulk_to_pull = calculate_bulk_pull_and_print(bulk_items)
        # print(f"Bulk to print: {bulk_to_print}")
        # print(f"Bulk to pull: {bulk_to_pull}")

        return JsonResponse({
            'success': True,
            'order_data': order_data,
            'bulk_to_print': bulk_to_print,
            'bulk_to_pull': bulk_to_pull
        })
        
    except Exception as e:
        print(f"Error reprocessing order: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
# ========================================================================================================== #





# For store orders
@login_required
def get_order_id_by_number(request, order_number):
    """
    API endpoint to get order ID by order number
    """
    # print(f"Fetching order ID for order number: {order_number}")
    try:
        order = StoreOrder.objects.get(order_number=order_number)
        return JsonResponse({'order_id': order.id})
    except StoreOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)







@login_required
def generate_order_pdf(request, order_id):
    """
    Generate store invoice PDF matching the Flask version exactly
    """
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, Table, TableStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from datetime import timedelta
    from io import BytesIO
    from django.conf import settings
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os
    import platform
    
    # Register Calibri fonts for Unicode support (Turkish, etc.)
    # Try multiple locations for font files
    use_calibri = False
    
    # Font paths to try (in order of preference)
    font_paths = []
    
    # Windows path (for local development)
    if platform.system() == 'Windows':
        font_paths.append({
            'regular': 'C:/Windows/Fonts/calibri.ttf',
            'bold': 'C:/Windows/Fonts/calibrib.ttf'
        })
    
    # PythonAnywhere/Linux paths
    # Option 1: In a 'fonts' directory in your project
    font_dir = os.path.join(settings.BASE_DIR, 'fonts')
    if os.path.exists(font_dir):
        font_paths.append({
            'regular': os.path.join(font_dir, 'calibri.ttf'),
            'bold': os.path.join(font_dir, 'calibrib.ttf')
        })
    
    # # Option 2: In static files directory
    # if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
    #     static_font_dir = os.path.join(settings.STATIC_ROOT, 'fonts')
    #     if os.path.exists(static_font_dir):
    #         font_paths.append({
    #             'regular': os.path.join(static_font_dir, 'calibri.ttf'),
    #             'bold': os.path.join(static_font_dir, 'calibrib.ttf')
    #         })
    
    # Try each font path until one works
    for paths in font_paths:
        try:
            if os.path.exists(paths['regular']) and os.path.exists(paths['bold']):
                pdfmetrics.registerFont(TTFont('Calibri', paths['regular']))
                pdfmetrics.registerFont(TTFont('Calibri-Bold', paths['bold']))
                use_calibri = True
                # print(f"✓ Calibri fonts loaded from: {paths['regular']}")
                break
        except Exception as e:
            # print(f"Failed to load Calibri from {paths['regular']}: {e}")
            continue
    
    if not use_calibri:
        pass
        # print("⚠ Warning: Calibri font not found, using Helvetica (may not display Turkish characters correctly)")
        # print(f"  Searched paths: {[p['regular'] for p in font_paths]}")
        # print(f"  To fix: Create a 'fonts' folder at {os.path.join(settings.BASE_DIR, 'fonts')} and add calibri.ttf and calibrib.ttf")
    
    try:
        # Get the order and items
        order = get_object_or_404(StoreOrder, id=order_id)
        order_includes = (
            SOIncludes.objects.filter(store_order=order)
            .select_related("product__variety")
        )
        
        # Get store information
        store = order.store
        
        # Extract order data
        order_number = order.order_number
        shipping = float(order.shipping or 0)
        
        # Calculate subtotal from order items
        subtotal = sum(
            float(item.quantity or 0) * float(item.price or 0) 
            for item in order_includes
        )

        # Check if order is pending (no fulfilled_date) or finalized
        is_pending = not order.fulfilled_date

        if is_pending:
            # For pending orders: show TBD for everything except subtotal
            order_date_formatted = 'TBD'
            due_date_str = 'TBD'
            shipping = 'TBD'
            credit = 'TBD'
            total_due = 'TBD'
        else:
            # For finalized orders: calculate actual values
            shipping = float(order.shipping or 0)
            
            # Get order date and calculate due date (Net 30)
            try:
                if order.fulfilled_date:
                    order_date = order.fulfilled_date
                    order_date_formatted = order_date.strftime("%m/%d/%Y")
                    due_date = order_date + timedelta(days=30)
                    due_date_str = due_date.strftime("%m/%d/%Y")
                else:
                    order_date_formatted = 'TBD'
                    due_date_str = 'TBD'
            except:
                order_date_formatted = 'TBD'
                due_date_str = 'TBD'
            






    # Get credit from store returns for first invoice of the year
            # Order number format: WXXYY-ZZ where XX=store_id, YY=order_seq, ZZ=year
            # Example: W1501-25 means store 15, first order (01), year 2025
            try:
                # Extract parts from order number (format: WXXYY-ZZ)
                order_parts = order_number.split('-')
                order_prefix = order_parts[0]  # WXXYY
                year_suffix = order_parts[1]   # ZZ
                
                # Get the YY part (order sequence number - last 2 digits of prefix)
                order_sequence = order_prefix[-2:]  # Last 2 digits
                
                # print(f"\n=== CREDIT CALCULATION DEBUG ===")
                # print(f"Order number: {order_number}")
                # print(f"Order prefix: {order_prefix}")
                # print(f"Order sequence: {order_sequence}")
                # print(f"Year suffix: {year_suffix}")
                
                # Check if this is the first order of the year (sequence = "01")
                if order_sequence == "01":
                    invoice_year = int(year_suffix)  # Keep as 2-digit year (e.g., 25)
                    previous_year = invoice_year - 1  # e.g., 24
                    # print(f"✓ This IS the first order of year {invoice_year}")
                    # print(f"Looking for returns from previous year: {previous_year}")
                    
                    # Apply credit using StoreReturns model
                    from stores.models import StoreReturns
                    
                    # Manually query for returns using 2-digit year
                    try:
                        return_record = StoreReturns.objects.get(
                            store__store_num=store.store_num,
                            return_year=previous_year
                        )
                        # print(f"✓ Found return record: {return_record}")
                        # print(f"  Packets returned: {return_record.packets_returned}")
                        
                        # Calculate credit using the packet price
                        from stores.models import WholesalePktPrice
                        price = WholesalePktPrice.get_price_for_year(previous_year)
                        # print(f"  Price for year {previous_year}: {price}")
                        
                        if price:
                            from decimal import Decimal
                            credit_amount = Decimal(str(return_record.packets_returned)) * price
                            credit = float(credit_amount)
                            # print(f"✓ Calculated credit: ${credit}")
                        else:
                            # print(f"✗ No price found for year {previous_year}")
                            credit = 0.0
                    except StoreReturns.DoesNotExist:
                        # print(f"✗ No return record found for store {store.store_num}, year {previous_year}")
                        credit = 0.0
                else:
                    # print(f"✗ NOT first order (sequence is {order_sequence}, not 01)")
                    credit = 0.0
                
                # print(f"=== CREDIT CALCULATION DEBUG END ===\n")
            except (IndexError, ValueError, AttributeError) as e:
                # print(f"Error parsing order number for credit: {e}")
                import traceback
                traceback.print_exc()
                credit = 0.0
                
            # Calculate total due
            total_due = subtotal + shipping - credit

       
        
        # total_due = subtotal + shipping - credit
        
        # # Get order date and calculate due date (Net 30)
        # try:
        #     if order.fulfilled_date:
        #         order_date = order.fulfilled_date
        #         order_date_formatted = order_date.strftime("%m/%d/%Y")
        #         due_date = order_date + timedelta(days=30)
        #         due_date_str = due_date.strftime("%m/%d/%Y")
        #     else:
        #         order_date_formatted = 'N/A'
        #         due_date_str = 'N/A'
        # except:
        #     order_date_formatted = 'N/A'
        #     due_date_str = 'N/A'
        
        # Store address information
        store_address = store.store_address or ''
        store_address2 = store.store_address2 or ''
        store_city = store.store_city or ''
        store_state = store.store_state or ''
        store_zip = store.store_zip or ''
        
        # Build items data
        items = []
        for item in order_includes:
            variety_name = item.product.variety.var_name if item.product and item.product.variety else 'Unknown'
            crop = item.product.variety.crop if item.product and item.product.variety else 'Unknown'
            quantity = item.quantity or 0
            price = float(settings.PACKET_PRICE)
            
            items.append({
                'variety_name': variety_name,
                'crop': crop,
                'quantity': quantity,
                'price': price
            })
        
        # Create PDF buffer
        buffer = BytesIO()
        width, height = letter
        
        # Calculate pagination based on item count
        item_count = len(items)
        if item_count <= 25:
            num_pages = 1
        elif item_count <= 62:
            num_pages = 2
        elif item_count <= 99:
            num_pages = 3
        elif item_count <= 136:
            num_pages = 4
        elif item_count <= 173:
            num_pages = 5
        elif item_count <= 210:
            num_pages = 6
        elif item_count <= 247:
            num_pages = 7
        else:
            num_pages = 8
        
        # Build table data - COLUMN ORDER: Qty, Variety, Crop, Unit Price, Extended
        data = [["Qty", "Variety", "Crop", "Unit Price", "Extended"]]
        for item in items:
            variety = item['variety_name']
            crop = item['crop']
            quantity = item['quantity']
            price = item['price']
            line_total = quantity * price
            
            data.append([
                str(quantity),
                variety,
                crop,
                f"${price:.2f}",
                f"${line_total:.2f}"
            ])
        
        # Create table with exact column widths from Flask
        table = Table(data, colWidths=[40, 193, 135, 70, 70], repeatRows=1, hAlign='LEFT')
        
        # Determine which font to use
        font_name = "Calibri" if use_calibri else "Helvetica"
        font_bold = "Calibri-Bold" if use_calibri else "Helvetica-Bold"
        
        # Apply exact table styling from Flask
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, -1), font_name),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (1, 1), (2, -1), "LEFT"),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ]))
        
        # Frames with different top margins (matching Flask)
        first_page_frame = Frame(
            45,
            30,
            width - 60,
            height - 300
        )
        
        later_pages_frame = Frame(
            45,
            30,
            width - 60,
            height - 80
        )
        
        # Logo path - adjust this to match your Django static files setup
        # You'll need to use Django's static file finder or hardcode the path
        logo_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'images', 'logo.png')
        # Alternative: logo_path = finders.find('images/logo.png')
        
        # Page header functions
        def on_first_page(canvas, doc):
            # Top header line with order number and page number
            canvas.setFont(font_name, 13)
            canvas.drawString(30, height - 30, f"Order #: {order_number}")
            canvas.drawCentredString(width / 2, height - 30, "INVOICE")
            canvas.drawRightString(width - 40, height - 30, f"PAGE 1 of {num_pages}")
            canvas.line(0, height - 40, width - 0, height - 40)
            
            # Logo (if logo file exists)
            if os.path.exists(logo_path):
                logo_width = 100
                logo_height = 50
                logo_x = width - logo_width - 40
                logo_y = height - logo_height - 50
                canvas.drawImage(logo_path, logo_x, logo_y, width=logo_width, height=logo_height, mask='auto')
            
            # Company info
            canvas.setFont(font_bold, 14)
            canvas.drawString(50, height - 60, "Uprising Seeds")
            canvas.setFont(font_name, 12)
            canvas.drawString(50, height - 75, "1501 Fraser St")
            canvas.drawString(50, height - 90, "Suite 105")
            canvas.drawString(50, height - 105, "Bellingham, WA 98229")
            canvas.drawString(50, height - 120, "360-778-3749")
            canvas.drawString(50, height - 135, "wholesale@uprisingorganics.com")
            
            # Ship To box
            canvas.line(50, height - 150, width - 300, height - 150)
            canvas.setFont(font_bold, 12)
            canvas.drawString(60, height - 164, "SHIP TO:")
            canvas.line(50, height - 150, 50, height - 265)
            canvas.line(width - 300, height - 150, width - 300, height - 265)
            canvas.line(50, height - 170, width - 300, height - 170)
            
            # Right-aligned label helper
            def draw_right_label(label, y):
                text_width = canvas.stringWidth(label, font_name, 12)
                canvas.drawString(130 - text_width, y, label)
            
            canvas.setFont(font_name, 12)
            
            # Ship to info
            draw_right_label("Order #:", height - 185)
            draw_right_label("Name:", height - 200)
            draw_right_label("Date:", height - 215)
            canvas.drawString(140, height - 215, order_date_formatted)
            draw_right_label("Address:", height - 230)
            canvas.drawString(140, height - 230, store_address)
            
            if store_address2:
                draw_right_label("Address 2:", height - 245)
                canvas.drawString(140, height - 245, store_address2)
                draw_right_label("City/State/Zip:", height - 260)
                canvas.drawString(140, height - 260, f"{store_city}, {store_state}   {store_zip}")
            else:
                draw_right_label("City/State/Zip:", height - 245)
                canvas.drawString(140, height - 245, f"{store_city}, {store_state}   {store_zip}")
            
            # Order info
            canvas.setFont(font_bold, 12)
            canvas.drawString(140, height - 185, order_number)
            canvas.drawString(140, height - 200, store.store_name)
            
            # Order summary box
            right_x = 550
            label_x = 435
            
            def format_currency(value):
                if value == 'TBD':
                    return 'TBD'
                try:
                    return f"${float(value):.2f}"
                except (ValueError, TypeError):
                    return "$0.00"

            def draw_right_aligned_label_value(label, value, y_position):
                if value == 'TBD':
                    value_str = 'TBD'
                else:
                    try:
                        float(value)
                        value_str = format_currency(value)
                    except (ValueError, TypeError):
                        value_str = str(value)
                
                canvas.drawString(label_x, y_position, label)
                value_width = canvas.stringWidth(value_str, font_name, 12)
                canvas.drawString(right_x - value_width, y_position, value_str)
            
            canvas.setFont(font_name, 12)
            draw_right_aligned_label_value("Subtotal:", subtotal, height - 180)
            draw_right_aligned_label_value("Shipping:", shipping, height - 195)
            draw_right_aligned_label_value("Credit:", credit, height - 210)
            
            canvas.setFont(font_bold, 12)
            draw_right_aligned_label_value("Total Due:", total_due, height - 225)
            canvas.setFont(font_name, 12)
            draw_right_aligned_label_value("Term:", "Net 30", height - 245)
            draw_right_aligned_label_value("Due Date:", due_date_str, height - 260)
            
            # Box around order summary
            canvas.drawString(452, height - 159, "Order Summary")
            canvas.line(428, height - 145, 428, height - 265)
            canvas.line(558, height - 145, 558, height - 265)
            canvas.line(428, height - 145, 558, height - 145)
            canvas.line(428, height - 166, 558, height - 166)
            canvas.line(428, height - 265, 558, height - 265)
            canvas.line(428, height - 232, 558, height - 232)
            
            canvas.line(50, height - 265, width - 300, height - 265)
        
        def on_later_pages(canvas, doc):
            canvas.setFont(font_name, 13)
            canvas.drawString(30, height - 30, f"Order #: {order_number}")
            canvas.drawCentredString(width / 2, height - 30, "INVOICE")
            canvas.drawRightString(width - 40, height - 30, f"PAGE {doc.page} of {num_pages}")
            canvas.line(0, height - 40, width - 0, height - 40)
        
        # Set up the document
        doc = BaseDocTemplate(buffer, pagesize=letter)
        doc.addPageTemplates([
            PageTemplate(id='FirstPage', frames=first_page_frame, onPage=on_first_page),
            PageTemplate(id='LaterPages', frames=later_pages_frame, onPage=on_later_pages)
        ])
        
        # Build elements list with first page handling
        elements = [
            NextPageTemplate('LaterPages'),
            table
        ]
        
        # Build the PDF
        doc.build(elements)
        
        # Return the PDF
        pdf_data = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(pdf_data, content_type="application/pdf")
        clean_filename = f"Uprising_Invoice_{order_number}.pdf"
        response["Content-Disposition"] = f'inline; filename="{clean_filename}"'
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f"Error generating PDF: {str(e)}", content_type="text/plain", status=500)


@login_required
@require_http_methods(["POST"])
def record_label_prints(request):
    """
    Records label prints in the LabelPrint table.
    Expects JSON data with:
    {
        "items": [
            {
                "sku": "BEA-TA-1/2lb",
                "quantity": 50,
                "for_year": 2025
            },
            ...
        ]
    }
    """
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        
        if not items:
            return JsonResponse({'success': False, 'error': 'No items provided'}, status=400)
        
        today = localtime(timezone.now(), pacific_tz).date()
        recorded_count = 0
        errors = []
        
        with transaction.atomic():
            for item in items:
                sku = item.get('sku')
                quantity = item.get('quantity')
                for_year = item.get('for_year')
                
                if not all([sku, quantity, for_year]):
                    errors.append(f"Missing data for SKU: {sku}")
                    continue
                
                # Find the product
                product = Product.objects.filter(
                    variety__sku_prefix=sku[:6],
                    sku_suffix=sku[7:]
                ).select_related('variety', 'lot', 'mix_lot').first()
                
                if not product:
                    errors.append(f"Product not found for SKU: {sku}")
                    continue
                
                # Create LabelPrint record
                LabelPrint.objects.create(
                    product=product,
                    lot=product.lot,
                    mix_lot=product.mix_lot,
                    date=today,
                    qty=quantity,
                    for_year=for_year
                )
                recorded_count += 1
        
        return JsonResponse({
            'success': True,
            'recorded_count': recorded_count,
            'errors': errors if errors else None
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return OnlineOrder.objects.filter(pulled_for_processing=False)
    

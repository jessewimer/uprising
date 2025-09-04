from rest_framework import viewsets
from .serializers import OrderSerializer
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
import datetime
from .models import OnlineOrder, OOIncludes, OOIncludesMisc, BatchMetadata, BulkBatch
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from stores.models import StoreOrder, SOIncludes
import json
import csv
import io
from django.views.decorators.http import require_http_methods
import requests
from django.contrib.auth.decorators import login_required, user_passes_test
from uprising.utils.auth import is_employee
import pandas as pd
from products.models import Product, MiscProduct
from django.db import transaction
from django.utils.timezone import now


def calculate_bulk_pull_and_print(bulk_items):
    bulk_to_print = {}
    bulk_to_pull = {}

    for sku, qty in bulk_items.items():
        # Find product by prefix/suffix
        product = Product.objects.filter(
            sku_prefix=sku[:6],
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
            


            # ---- BUILD bulk_to_print dict ----
            if quantity_to_print > 0:
                if product.env_multiplier and product.env_multiplier > 1:
                    quantity_to_print *= product.env_multiplier
                    alt_product = product.variety.products.filter(
                        sku_suffix=product.alt_sku
                    ).first()
                    pkg_size = alt_product.pkg_size if alt_product else product.pkg_size
                else:
                    pkg_size = product.pkg_size

                entry = {
                    "quantity": quantity_to_print,
                    "variety_name": product.variety.var_name,
                    "crop": product.variety.crop,
                    "days": product.variety.days,
                    "common_name": product.variety.common_name or "",
                    "desc1": product.variety.desc_line1,
                    "desc2": product.variety.desc_line2,
                    "desc3": product.variety.desc_line3 or "",
                    "lot": getattr(product, "lot", ""),  # adjust if Lot FK exists
                    "pkg_size": pkg_size,
                    "alt_sku": product.alt_sku or "",
                    "env_multiplier": product.env_multiplier or 1,
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

            # ---- BUILD bulk_to_pull dict ----
            if quantity_to_pull > 0:
                bulk_to_pull[sku] = {
                    "var_name": product.variety.var_name,
                    "veg_type": product.variety.veg_type,
                    "sku_suffix": product.sku_suffix,
                    "quantity": quantity_to_pull,
                }

        except Exception as e:
            print(f"Error processing SKU {sku}: {e}")
            continue

    # sort dicts by SKU
    bulk_to_print = dict(sorted(bulk_to_print.items()))
    bulk_to_pull = dict(sorted(bulk_to_pull.items()))

    return bulk_to_print, bulk_to_pull


@login_required
@user_passes_test(is_employee)
def process_online_orders(request):
    '''
    Order Processing Page
    '''
    context = {}
    return render(request, 'orders/process_online_orders.html', context)

@login_required
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

                # Parse dates with multiple format fallbacks
                date_string = row['Created at'].strip()
                formats = [
                    '%m/%d/%Y %H:%M',
                    '%Y-%m-%d %H:%M:%S %z',
                    '%Y-%m-%d %H:%M:%S',
                ]
                for fmt in formats:
                    try:
                        date = datetime.strptime(date_string, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Unexpected date format: {date_string}")

                date = date.date()
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

                note = row['Notes'] if not pd.isna(row['Notes']) else ""
                note = str(note).strip().replace('\r\n', '\n').replace('\r', '\n')

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
                # if customer_name in customer_orders:
                #     customer_orders[customer_name].append(order_number)
                # else:
                #     customer_orders[customer_name] = [order_number]

                current_order_items = []
                current_order_misc_items = []

            # Product lookups
            product = Product.objects.filter(
                sku_prefix=product_sku[:6],
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
                batch_date=now().date(),
                batch_identifier=meta_batch_id,
                start_order_number=first_order,
                end_order_number=last_order,
                start_order_date=order_start_date,
                end_order_date=order_end_date,
            )

            # calculate bulk items
            bulk_to_print, bulk_to_pull = calculate_bulk_pull_and_print(bulk_items)

            # add "print" bulk items
            if bulk_to_print:
                for sku, qty in bulk_to_print.items():
                    BulkBatch.objects.create(
                        batch_identifier=bulk_batch.batch_identifier,
                        bulk_type="print",
                        sku=sku,
                        quantity=qty,
                    )

            # add "pull" bulk items
            if bulk_to_pull:
                for sku, qty in bulk_to_pull.items():
                    BulkBatch.objects.create(
                        batch_identifier=bulk_batch.batch_identifier,
                        bulk_type="pull",
                        sku=sku,
                        quantity=qty,
                    )


        




        return JsonResponse({
            'success': True,
            'message': f"Processed orders from {order_start_date} to {order_end_date}"
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Error processing orders: {e}"})
    

        # Variables to hold the current order being processed
        # current_order = None
        # current_order_items = []
        # bulk_orders = []
        # customer_orders = {}
        # bulk_items = {}
        # misc_orders = []
        # order_start_date = None
        # order_end_date = None

        # # Iterate over the rows of the CSV
        # for index, row in df.iterrows():
        #     order_number = row['Name']  
        #     product_sku = row['Lineitem sku']
        #     product_qty = row['Lineitem quantity']
        #     # Check if we are still processing the same order
        #     if current_order is None or order_number != current_order.order_number:
        #         # If the order changes, save the previous order (if any)
        #         if current_order is not None:
        #             # Save the order and its items to the database
        #             session.add(current_order)
        #             session.commit()

        #             # Save the items for the current order
        #             for item in current_order_items:
        #                 session.add(item)
        #             session.commit()

        #             # save misc items for the current order
        #             for item in current_order_misc_items:
        #                 session.add(item)
        #             session.commit()

        #         date_string = row['Created at'].strip()  # Ensure no extra spaces

        #         # List of possible formats in the CSV
        #         formats = [
        #             '%m/%d/%Y %H:%M',         # Example: 3/17/2025 23:32
        #             '%Y-%m-%d %H:%M:%S %z',   # Example: 2025-03-17 23:32:47 -0700
        #             '%Y-%m-%d %H:%M:%S'       # Example: 2025-03-17 23:32:47 (without timezone)
        #         ]

        #         # Try each format until one works
        #         for fmt in formats:
        #             try:
        #                 date = datetime.strptime(date_string, fmt)
        #                 break
        #             except ValueError:
        #                 continue
        #         else:
        #             raise ValueError(f"Unexpected date format: {date_string}")

        #         # Extract only the date if needed
        #         date = date.date()
        #         if order_start_date is None or date < order_start_date:
        #             order_start_date = date
        #         if order_end_date is None or date > order_end_date:
        #             order_end_date = date
        #         postal_code = str(row['Shipping Zip']).lstrip("'") if not pd.isna(row['Shipping Zip']) else str(row['Billing Zip'])
        #         address = row['Shipping Address1'] if not pd.isna(row['Shipping Address1']) else row['Billing Address1']
        #         address2 = row['Shipping Address2'] if not pd.isna(row['Shipping Address2']) else row['Billing Address2']
        #         country = row['Shipping Country'] if not pd.isna(row['Shipping Country']) else row['Billing Country']
        #         city = row['Shipping City'] if not pd.isna(row['Shipping City']) else row['Billing City']
        #         state = row['Shipping Province'] if not pd.isna(row['Shipping Province']) else row['Billing Province']
        #         customer_name = row['Shipping Name']
        #         if pd.isna(customer_name) or str(customer_name).strip() == "":
        #             customer_name = row['Billing Name']  # Fallback to Billing Name if Shipping Name is empty   

        #         note = row['Notes'] if not pd.isna(row['Notes']) else ""
        #         note = str(note).strip().replace('\r\n', '\n').replace('\r', '\n')

        #         # Create a new OnlineOrder for the new order number
        #         current_order = OnlineOrder(
        #             order_number=order_number,
        #             shipping_company=row['Shipping Company'],
        #             address=address, 
        #             address2=address2,  
        #             city=city,         
        #             state=state,    
        #             postal_code = postal_code, 
        #             country=country,   
        #             shipping=row['Shipping'],          
        #             customer_name=customer_name,
        #             tax=row['Taxes'], 
        #             subtotal=row['Subtotal'],                
        #             total=row['Total'],                
        #             date=date,
        #             note=note,           
        #         )
                
        #         customer_name = row['Shipping Name']
        #         if customer_name in customer_orders:
        #         # If customer has already ordered, append the new order number
        #             customer_orders[customer_name].append(order_number)
        #             print(f"Adding a duplicate order of {customer_name}")
        #         else:
        #             # If it's the first order from this customer, create a new entry
        #             customer_orders[customer_name] = [order_number] 

        #         # Initialize the list of items for the new order
        #         current_order_items = []
        #         current_order_misc_items = []


        #     # see if the sku is a normal product
        #     product = session.query(Product).filter(Product.sku_prefix == row['Lineitem sku'][:6], Product.sku_suffix == row['Lineitem sku'][7:]).first()
        #     if not product:
        #         # check to see if it is a misc_product
        #         product = session.query(MiscProduct).filter(MiscProduct.sku == row['Lineitem sku']).first()
        #         if not product:
        #             print(f"Product with SKU {row['Lineitem sku']} not found, skipping...")
        #             continue
        #         else:
        #             # the column in the table is sold_in_25
        #             sales_column = f"sold_in_{YEAR}"
                    
        #             if hasattr(product, sales_column):
        #                 current_value = getattr(product, sales_column, 0) or 0
        #                 setattr(product, sales_column, current_value + int(row['Lineitem quantity']))
        #             else:
        #                 print(f"Warning: {sales_column} is not a valid column on MiscProduct")
                    
        #             misc_item = OOIncludesMisc(
        #                 order_number=order_number,
        #                 price=row['Lineitem price'],              
        #                 qty=row['Lineitem quantity'],       
        #                 sku=row['Lineitem sku'],
        #             )

        #             # Add the item to the list of current order items
        #             current_order_items.append(misc_item)
        #             if order_number not in misc_orders:
        #                 current_order.misc = True
        #                 misc_orders.append(order_number)
        #     else:

        #         # Check if SKU contains "pkt" or not
        #         is_bulk_item = "pkt" not in row['Lineitem sku'].lower()
                
        #         if is_bulk_item:

        #             if product_sku in bulk_items:
        #                 bulk_items[product_sku] += product_qty
        #             else:
        #                 bulk_items[product_sku] = product_qty
        #             if order_number not in bulk_orders:
        #                 current_order.bulk = True
        #                 bulk_orders.append(order_number)

        #         product.total_sold_online += row['Lineitem quantity']
            
        #         product_id = product.product_id
        #         # Add the item to the current order's includes
        #         item = OOIncludes(
        #             order_number=order_number,
        #             price=row['Lineitem price'],              
        #             qty=row['Lineitem quantity'],       
        #             product_id=product_id,
        #         )

        #         # Add the item to the list of current order items
        #         current_order_items.append(item)
        
        # # Commit the last order and its items (after loop ends)
        # if current_order is not None:
        #     session.add(current_order)
        #     session.commit()

        #     for item in current_order_items:
        #         session.add(item)
        #     session.commit()

        #     for item in current_order_misc_items:
        #         session.add(item)
        #     session.commit()
        













        combined_orders = {}
    
        # Iterate through the original dictionary and filter out customers with more than one order
        for customer_name, order_nums in customer_orders.items():
            if len(order_nums) > 1: 
                combined_orders[customer_name] = order_nums
                # print(customer_name, " is greater than 1")
        combined_order_numbers = [order for orders in combined_orders.values() for order in orders]
        
        # SENDING ORDERS TO BE PRINTED... FIRST BULK, THEN PKT ONLY, THEN COMBINED

        # PACKET ONLY (OR PACKET AND MISC/ MISC ONLY)
        for order in reversed(order_numbers):
            if order not in bulk_orders and order not in combined_order_numbers:
                order = session.query(OnlineOrder).filter(OnlineOrder.order_number == order).first()
                generate_pdf(order, session, action="print")

        # BULK ONLY (OR BULK AND PKT, OR BULK AND MISC)
        for order in reversed(order_numbers):
            if order in bulk_orders and order not in combined_order_numbers:
                order = session.query(OnlineOrder).filter(OnlineOrder.order_number == order).first()
                generate_pdf(order, session, action="print")

        # COMBINED ORDERS
        for customer_name, order_numbers in combined_orders.items():
    
            for order in order_numbers:
                order = session.query(OnlineOrder).filter(OnlineOrder.order_number == order).first()
                generate_pdf(order, session, action="print")

        # # print the dict of bulk orders
        # print("\nBulk Items:")
        # for sku, qty in bulk_items.items():
        #     print(f"SKU: {sku}, Qty: {qty}")
        
        # HANDLING BULK BATCH AND PULL/PRINT LOGIC
        if bulk_items:

            # check to see what the last batch number is
            last_batch = session.query(BatchMetadata).order_by(BatchMetadata.id.desc()).first()
            if last_batch:
                last_batch_number = last_batch.batch_identifier.split("-")[1]
                last_batch_number = int(last_batch_number)
            else:
                last_batch_number = 0

            new_batch_number = last_batch_number + 1

            meta_batch_id = f"{datetime.now().strftime('%y%m%d')}-{new_batch_number}"
            # add an object to the BulkBatchMetadata table
            bulk_batch = BatchMetadata(
                batch_date=datetime.now().date(),  # Use the current date
                batch_identifier=meta_batch_id,
                start_order_number=first_order,
                end_order_number=last_order,
                start_order_date=order_start_date,
                end_order_date=order_end_date,
            )
            session.add(bulk_batch)
            session.commit()

            # add bulk items to the database

            # for sku, qty in bulk_items.items():
            bulk_to_print, bulk_to_pull = calculate_bulk_pull_and_print(bulk_items, session)
            # add to database
            if bulk_to_print:
                for sku, qty in bulk_to_print.items():
                    bulk_item = BulkBatch(
                        batch_identifier=bulk_batch.batch_identifier,
                        bulk_type="print",
                        sku=sku,
                        quantity=qty,
                    )
                    session.add(bulk_item)
            if bulk_to_pull:
                for sku, qty in bulk_to_pull.items():
                    bulk_item = BulkBatch(
                        batch_identifier=bulk_batch.batch_identifier,
                        bulk_type="pull",
                        sku=sku,
                        quantity=qty,
                    )
                    session.add(bulk_item)
            session.commit()





























        # Read and decode the CSV
        csv_content = csv_file.read().decode('utf-8')
        print(f"CSV received: {len(csv_content)} characters")
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        # Validate CSV format (check for required columns)
        required_columns = ['order_number', 'item_name', 'quantity']  # Adjust as needed
        if not all(col in csv_reader.fieldnames for col in required_columns):
            return JsonResponse({
                'success': True, 
                'message': 'wrong file'
            })
        
        # Process the CSV data
        orders = list(csv_reader)
        
        # Check if orders already processed (implement your logic here)
        # Example: Check against database
        # if orders_already_exist(orders):
        #     return JsonResponse({
        #         'success': True,
        #         'message': 'orders already processed'
        #     })
        
        # Process orders and categorize items
        bulk_items_to_print = []
        bulk_items_to_pull = []
        
        # Your business logic here to categorize items
        for order in orders:
            item_name = order.get('item_name', '')
            quantity = int(order.get('quantity', 0))
            
            # Example logic - adjust based on your business rules
            if 'seed' in item_name.lower():
                bulk_items_to_print.append({
                    'name': item_name,
                    'quantity': quantity
                })
            else:
                bulk_items_to_pull.append({
                    'name': item_name,
                    'quantity': quantity
                })
        
        # Send to Flask for printing (async)
        send_to_flask_for_printing(csv_content)
        
        return JsonResponse({
            'success': True,
            'bulk_items_to_print': bulk_items_to_print,
            'bulk_items_to_pull': bulk_items_to_pull
        })
        
    except Exception as e:
        print(f"Error processing orders: {e}")
        return JsonResponse({'success': False, 'error': str(e)})




























@login_required
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def reprint_order(request):
    """
    Reprint a specific order by order number
    Expected response format:
    - success: True/False
    - message: 'order not found' | success message
    - bulk_items_to_print: [{'name': str, 'quantity': int}, ...]
    - bulk_items_to_pull: [{'name': str, 'quantity': int}, ...]
    """
    try:
        data = json.loads(request.body)
        order_number = data.get('order_number', '').strip()
        for_year = f"20{settings.CURRENT_ORDER_YEAR}"
        # validate order number format        
        if not order_number:
            return JsonResponse({'success': False, 'error': 'Order number required'})
        
        if not order_number.startswith('S' or 's'):
            order_number = 'S' + order_number

        if order_number.startswith('s'):
            order_number = 'S' + order_number[1:]
        
        if order_number.length < 6 or order_number.length > 6:
            return JsonResponse({'success': False, 'error': 'Invalid order number format'})
        
        print(f"Reprinting order: {order_number}")
        
        # Query database for the order (implement your database logic)
        # Example:
        order = OnlineOrder.objects.filter(order_number=order_number).first()
        if not order:
            return JsonResponse({
                'success': True,
                'message': 'order not found'
            })
        

        # Retrieve data from order and OOIncludes tables
        order_data = {
            'order_number': order.order_number,
            'date': order.date,
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
            'bulk': order.bulk,
            'misc': order.misc,
            'note': order.note,
        }

        includes = OOIncludes.objects.filter(order=order)
        misc_includes = OOIncludesMisc.objects.filter(order=order)
        items = {}
        misc_items = {}
        bulk_items_to_print = {}
        bulk_items_to_pull = {}

# class Product(models.Model):
#     variety = models.ForeignKey("Variety", on_delete=models.CASCADE, related_name="products", null=True, blank=True)
#     lot = models.ForeignKey("lots.Lot", on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
#     pkg_size = models.CharField(max_length=50, blank=True, null=True)
#     sku_suffix = models.CharField(max_length=50, blank=True, null=True)
#     alt_sku = models.CharField(max_length=50, blank=True, null=True)
#     lineitem_name = models.CharField(max_length=255, blank=True, null=True)

#     rack_location = models.CharField(max_length=100, blank=True, null=True)
#     env_type = models.CharField(max_length=50, blank=True, null=True)
#     env_multiplier = models.IntegerField(blank=True, null=True)
#     label = models.CharField(max_length=1, blank=True, null=True)

#     num_printed = models.IntegerField(blank=True, null=True)
#     num_printed_next_year = models.IntegerField(default=0)
#     scoop_size = models.CharField(max_length=50, blank=True, null=True)
#     print_back = models.BooleanField(default=False)
#     bulk_pre_pack = models.IntegerField(blank=True, null=True, default=0)
#     is_sub_product = models.BooleanField(default=False)

        if includes.exists():
            for item in includes:
                lot = f"{item.product.lot.grower}{item.product.lot.year}{item.product.lot.harvest if item.product.lot.harvest else ''}" if item.product and item.product.lot else "N/A"
                sku = f"{item.product.variety.sku_prefix}-{item.product.sku_suffix}"
                
                if item.product.sku_suffix != 'pkt':

                    # determine how many to print vs pull
                    if item.product.bulk_pre_pack == 0:
                        quantity_to_print = item.qty
                    elif item.product.bulk_pre_pack >= item.qty:
                        quantity_to_pull = item.qty
                        item.product.bulk_pre_pack -= item.qty
                        # save to db
                        item.product.save()
                    else:
                        quantity_to_pull = item.product.bulk_pre_pack
                        quantity_to_print = item.qty - quantity_to_pull
                        item.product.bulk_pre_pack = 0
                        # save to db
                        item.product.save()


                    if quantity_to_print > 0:
                        if item.product.env_multiplier and item.product.env_multiplier > 1:
                            quantity_to_print = quantity_to_print * item.product.env_multiplier
                            # look up other product with the alt_sku
                            alt_product = item.product.variety.products.filter(sku_suffix=item.product.alt_sku).first()
                            pkg_size = alt_product.pkg_size if alt_product else item.product.pkg_size
                        else:
                            pkg_size = item.product.pkg_size

                        if item.product.print_back:
                            bulk_items_to_print[sku] = {
                                'quantity': quantity_to_print,
                                'variety_name': item.product.variety.var_name,
                                'crop': item.product.variety.crop,
                                'days': item.product.variety.days,
                                'common_name': item.product.variety.common_name if item.product.variety.common_name else "",
                                'desc1': item.product.variety.desc_line1,
                                'desc2': item.product.variety.desc_line2,
                                'desc3': item.product.variety.desc_line3 if item.product.variety.desc_line3 else "",
                                'back1': item.product.variety.back1,
                                'back2': item.product.variety.back2,
                                'back3': item.product.variety.back3,
                                'back4': item.product.variety.back4,
                                'back5': item.product.variety.back5,
                                'back6': item.product.variety.back6,
                                'back7': item.product.variety.back7 if item.product.variety.back7 else "",
                                'lot': lot,
                                'pkg_size': pkg_size,
                                'alt_sku': item.product.alt_sku if item.product.alt_sku else "",
                                'env_multiplier': item.product.env_multiplier if item.product.env_multiplier else 1,  
                            }
                            
                        else:
                            bulk_items_to_print[sku] = {
                                'quantity': quantity_to_print,
                                'variety_name': item.product.variety.var_name,
                                'crop': item.product.variety.crop,
                                'days': item.product.variety.days,
                                'common_name': item.product.variety.common_name if item.product.variety.common_name else "",
                                'desc1': item.product.variety.desc_line1,
                                'desc2': item.product.variety.desc_line2,
                                'desc3': item.product.variety.desc_line3 if item.product.variety.desc_line3 else "",
                                'lot': lot,
                                'pkg_size': pkg_size,
                                'alt_sku': item.product.alt_sku if item.product.alt_sku else "",
                                'env_multiplier': item.product.env_multiplier if item.product.env_multiplier else 1,  
                            }
            # ENDED HERE, ALTHOUGH ALL CODE BEFORE AND AFTER THIS IS UNTESTED
                sku_prefix = item.product.variety.sku_prefix if item.product else "N/A"
                items[sku_prefix] = {
                    'quantity': item.qty,
                    'price': float(item.price),
                    'line_item_name': item.product.lineitem_name if item.product else "N/A",
                    'rack_location': item.product.rack_location if item.product else "N/A",
                }
        if misc_includes.exists():
            for misc_item in misc_includes:
                misc_items[misc_item.sku] = {
                    'quantity': misc_item.qty,
                    'price': float(misc_item.price),
                    'line_item_name': misc_item.sku
                }


            # Simulate found order - replace with actual database data
            bulk_items_to_print = [
                {'name': f'Item for order {order_number}', 'quantity': 1}
            ]
            bulk_items_to_pull = [
                {'name': f'Pre-packed item for {order_number}', 'quantity': 1}
            ]
            
            return JsonResponse({
                'success': True,
                'bulk_items_to_print': bulk_items_to_print,
                'bulk_items_to_pull': bulk_items_to_pull
            })
        else:
            return JsonResponse({
                'success': True,
                'message': 'order not found'
            })
        
    except Exception as e:
        print(f"Error reprinting order: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def print_range(request):
    """
    Generate PDF for a range of items
    Returns PDF file as response
    """
    try:
        data = json.loads(request.body)
        start = data.get('start', 0)
        end = data.get('end', 0)
        items = data.get('items', [])
        
        print(f"Printing range {start+1}-{end+1} with {len(items)} items")
        
        # Generate PDF (implement your PDF generation logic)
        # This is a placeholder - replace with actual PDF generation
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import tempfile
        import os
        
        # Create temporary file for PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            # Create PDF
            p = canvas.Canvas(tmp_file.name, pagesize=letter)
            y = 750
            
            p.drawString(100, y, f"Bulk Order Labels ({start+1}-{end+1})")
            y -= 30
            
            for i, item in enumerate(items):
                p.drawString(100, y, f"{i+1}. {item['name']} - Qty: {item['quantity']}")
                y -= 20
                if y < 100:  # New page if needed
                    p.showPage()
                    y = 750
            
            p.save()
            
            # Read and return PDF
            with open(tmp_file.name, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="bulk_orders_{start+1}-{end+1}.pdf"'
                
            # Clean up temp file
            os.unlink(tmp_file.name)
            return response
    
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@user_passes_test(is_employee)
# Helper function to send CSV to Flask
def send_to_flask_for_printing(csv_content):
    """
    Send CSV to Flask service for printing processing
    This is called after successful Django processing
    """
    try:
        flask_url = 'http://localhost:5000/print-orders'  # Adjust URL as needed
        
        files = {'csv_file': ('orders.csv', csv_content, 'text/csv')}
        response = requests.post(flask_url, files=files, timeout=30)
        
        if response.status_code == 200:
            print("Flask processing successful")
            return response.json()
        else:
            print(f"Flask processing failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error sending to Flask: {e}")
        return None





# ========================================================================================================== #





# For store orders
@login_required
@user_passes_test(is_employee)
def get_order_id_by_number(request, order_number):
    """
    API endpoint to get order ID by order number
    """
    print(f"Fetching order ID for order number: {order_number}")
    try:
        order = StoreOrder.objects.get(order_number=order_number)
        return JsonResponse({'order_id': order.id})
    except StoreOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)


@login_required
@user_passes_test(is_employee)
def generate_order_pdf(request, order_id):
    try:
        # Get the order and items
        order = get_object_or_404(StoreOrder, id=order_id)
        order_includes = (
            SOIncludes.objects.filter(store_order_id=order)
            .select_related("product")
        )

        # Create PDF buffer and document
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
        )

        elements = []
        styles = getSampleStyleSheet()

        # Custom styles
        header_style = ParagraphStyle(
            "CustomHeader",
            parent=styles["Heading1"],
            fontSize=28,
            spaceAfter=8,
            textColor=colors.HexColor("#2d4a22"),
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )

        subheader_style = ParagraphStyle(
            "CustomSubHeader",
            parent=styles["Normal"],
            fontSize=16,
            spaceAfter=20,
            textColor=colors.HexColor("#4a5568"),
            alignment=TA_CENTER,
            fontName="Helvetica",
        )

        # Header
        elements.append(Paragraph("UPRISING SEEDS", header_style))
        elements.append(Paragraph("Wholesale Order Summary", subheader_style))
        elements.append(Spacer(1, 20))

        # Order info
        elements.append(
            Paragraph(f"<b>Order Number:</b> {order.order_number}", styles["Normal"])
        )
        elements.append(
            Paragraph(
                f"<b>Order Date:</b> {order.date.strftime('%B %d, %Y') if order.date else 'N/A'}",
                styles["Normal"],
            )
        )

        if hasattr(order, "store") and order.store:
            elements.append(
                Paragraph(f"<b>Store:</b> {order.store.store_name}", styles["Normal"])
            )

        elements.append(Spacer(1, 25))

        # Items table
        elements.append(Paragraph("Order Items", styles["Heading2"]))

        table_data = [["Qty", "Variety", "Type", "Unit Price", "Subtotal"]]
        pkt_price = settings.PACKET_PRICE
        total_cost = 0
        for item in order_includes:
            quantity = item.quantity or 0
            variety = (
                item.product.variety.var_name if item.product else "N/A"
            )
            veg_type = item.product.variety.veg_type if item.product else "N/A"
            line_total = quantity * pkt_price

            # Truncate long variety names
            if len(variety) > 35:
                variety = variety[:32] + "..."

            table_data.append(
                [
                    str(quantity),
                    variety,
                    veg_type,
                    f"${pkt_price:.2f}",
                    f"${line_total:.2f}",
                ]
            )

            total_cost += line_total

        items_table = Table(
            table_data,
            colWidths=[0.6 * inch, 3.2 * inch, 1.2 * inch, 0.8 * inch, 0.8 * inch],
        )
        items_table.setStyle(
            TableStyle(
                [
                    # Header
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d4a22")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    # Data rows
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                    ("ALIGN", (0, 1), (0, -1), "CENTER"),
                    ("ALIGN", (1, 1), (2, -1), "LEFT"),
                    ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                    # Styling
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ]
            )
        )

        elements.append(items_table)
        elements.append(Spacer(1, 25))

        # Totals
        elements.append(Paragraph("Order Summary", styles["Heading2"]))

        totals_data = [
            ["Subtotal:", f"${total_cost:.2f}"],
            ["Shipping:", "TBD"],
            ["Total:", "TBD"],
        ]

        totals_table = Table(totals_data, colWidths=[4.5 * inch, 1.5 * inch])
        totals_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        elements.append(totals_table)
        elements.append(Spacer(1, 30))

        # Footer
        footer_style = ParagraphStyle(
            "FooterStyle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#6c757d"),
            alignment=TA_CENTER,
        )

        elements.append(
            Paragraph("Thank you for your wholesale order!", footer_style)
        )
        elements.append(
            Paragraph(
                "For questions, please contact us through our wholesale portal.",
                footer_style,
            )
        )

         # Metadata callback
        def add_pdf_metadata(canvas, doc):
            # clean_title = f"Uprising Order {order.order_number}"
            clean_title = f""
            canvas.setTitle(clean_title)
            canvas.setAuthor("Uprising Seeds")
            canvas.setSubject("Wholesale Order Summary")

        # Build PDF with metadata
        doc.build(elements, onFirstPage=add_pdf_metadata)

        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type="application/pdf")
        clean_filename = f"Uprising Order {order.order_number}.pdf"
        response["Content-Disposition"] = f'inline; filename="{clean_filename}"'
        return response

    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", content_type="text/plain")


# def generate_order_pdf(request, order_id):
#     try:
#         # Get the order and items
#         order = get_object_or_404(StoreOrder, id=order_id)
#         order_includes = (
#             SOIncludes.objects.filter(store_order_id=order)
#             .select_related("product")
#         )

#         # Create PDF buffer and document
#         buffer = BytesIO()
#         doc = SimpleDocTemplate(
#             buffer,
#             pagesize=letter,
#             topMargin=0.75 * inch,
#             bottomMargin=0.75 * inch,
#             leftMargin=0.75 * inch,
#             rightMargin=0.75 * inch,
#         )

#         elements = []
#         styles = getSampleStyleSheet()

#         # Custom styles
#         header_style = ParagraphStyle(
#             "CustomHeader",
#             parent=styles["Heading1"],
#             fontSize=28,
#             spaceAfter=8,
#             textColor=colors.HexColor("#2d4a22"),
#             alignment=TA_CENTER,
#             fontName="Helvetica-Bold",
#         )

#         subheader_style = ParagraphStyle(
#             "CustomSubHeader",
#             parent=styles["Normal"],
#             fontSize=16,
#             spaceAfter=20,
#             textColor=colors.HexColor("#4a5568"),
#             alignment=TA_CENTER,
#             fontName="Helvetica",
#         )

#         # Header
#         elements.append(Paragraph("UPRISING SEEDS", header_style))
#         elements.append(Paragraph("Wholesale Order Summary", subheader_style))
#         elements.append(Spacer(1, 20))

#         # Order info
#         elements.append(
#             Paragraph(f"<b>Order Number:</b> {order.order_number}", styles["Normal"])
#         )
#         elements.append(
#             Paragraph(
#                 f"<b>Order Date:</b> {order.date.strftime('%B %d, %Y') if order.date else 'N/A'}",
#                 styles["Normal"],
#             )
#         )

#         if hasattr(order, "store") and order.store:
#             elements.append(
#                 Paragraph(f"<b>Store:</b> {order.store.store_name}", styles["Normal"])
#             )

#         elements.append(Spacer(1, 25))

#         # Items table
#         elements.append(Paragraph("Order Items", styles["Heading2"]))

#         table_data = [["Qty", "Variety", "Type", "Unit Price", "Subtotal"]]
#         pkt_price = settings.PACKET_PRICE
#         total_cost = 0
#         for item in order_includes:
#             quantity = item.quantity or 0
#             variety = (
#                 item.product.variety.var_name if item.product else "N/A"
#             )
#             veg_type = item.product.variety.veg_type if item.product else "N/A"
#             line_total = quantity * pkt_price

#             # Truncate long variety names
#             if len(variety) > 35:
#                 variety = variety[:32] + "..."

#             table_data.append(
#                 [
#                     str(quantity),
#                     variety,
#                     veg_type,
#                     f"${pkt_price:.2f}",
#                     f"${line_total:.2f}",
#                 ]
#             )

#             total_cost += line_total

#         items_table = Table(
#             table_data,
#             colWidths=[0.6 * inch, 3.2 * inch, 1.2 * inch, 0.8 * inch, 0.8 * inch],
#         )
#         items_table.setStyle(
#             TableStyle(
#                 [
#                     # Header
#                     ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d4a22")),
#                     ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
#                     ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
#                     ("FONTSIZE", (0, 0), (-1, 0), 11),
#                     ("ALIGN", (0, 0), (-1, 0), "CENTER"),
#                     # Data rows
#                     ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
#                     ("FONTSIZE", (0, 1), (-1, -1), 10),
#                     ("ALIGN", (0, 1), (0, -1), "CENTER"),
#                     ("ALIGN", (1, 1), (2, -1), "LEFT"),
#                     ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
#                     # Styling
#                     ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
#                     ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
#                     ("TOPPADDING", (0, 0), (-1, -1), 8),
#                     ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
#                     ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
#                 ]
#             )
#         )

#         elements.append(items_table)
#         elements.append(Spacer(1, 25))

#         # Totals
#         elements.append(Paragraph("Order Summary", styles["Heading2"]))

#         totals_data = [
#             ["Subtotal:", f"${total_cost:.2f}"],
#             ["Shipping:", "TBD"],
#             ["Total:", "TBD"],
#         ]

#         totals_table = Table(totals_data, colWidths=[4.5 * inch, 1.5 * inch])
#         totals_table.setStyle(
#             TableStyle(
#                 [
#                     ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
#                     ("FONTSIZE", (0, 0), (-1, -1), 11),
#                     ("ALIGN", (0, 0), (0, -1), "RIGHT"),
#                     ("ALIGN", (1, 0), (1, -1), "RIGHT"),
#                     ("TOPPADDING", (0, 0), (-1, -1), 4),
#                     ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
#                 ]
#             )
#         )

#         elements.append(totals_table)
#         elements.append(Spacer(1, 30))

#         # Footer
#         footer_style = ParagraphStyle(
#             "FooterStyle",
#             parent=styles["Normal"],
#             fontSize=9,
#             textColor=colors.HexColor("#6c757d"),
#             alignment=TA_CENTER,
#         )

#         elements.append(
#             Paragraph("Thank you for your wholesale order!", footer_style)
#         )
#         elements.append(
#             Paragraph(
#                 "For questions, please contact us through our wholesale portal.",
#                 footer_style,
#             )
#         )

#         # Metadata callback
#         def add_pdf_metadata(canvas, doc):
#             canvas.setTitle(f"Uprising Seeds Order {order.order_number}")
#             canvas.setAuthor("Uprising Seeds")
#             canvas.setSubject("Wholesale Order Summary")

#         # Build PDF with metadata
#         doc.build(elements, onFirstPage=add_pdf_metadata)

#         pdf_data = buffer.getvalue()
#         buffer.close()

#         response = HttpResponse(pdf_data, content_type="application/pdf")
#         response["Content-Disposition"] = (
#             f'inline; filename="Uprising - {order.order_number}.pdf"'
#         )
#         return response

#     except Exception as e:
#         return HttpResponse(f"Error: {str(e)}", content_type="text/plain")

# def generate_order_pdf(request, order_id):
#     try:

#         # Get the order and items
#         order = get_object_or_404(StoreOrder, id=order_id)
#         order_includes = SOIncludes.objects.filter(store_order_id=order).select_related('product')

#         # Create PDF
#         buffer = BytesIO()
#         doc = SimpleDocTemplate(
#             buffer,
#             pagesize=letter,
#             topMargin=0.75*inch,
#             bottomMargin=0.75*inch,
#             leftMargin=0.75*inch,
#             rightMargin=0.75*inch
#         )

#         elements = []
#         styles = getSampleStyleSheet()

#         # Custom styles
#         header_style = ParagraphStyle(
#             'CustomHeader',
#             parent=styles['Heading1'],
#             fontSize=28,
#             spaceAfter=8,
#             textColor=colors.HexColor('#2d4a22'),
#             alignment=TA_CENTER,
#             fontName='Helvetica-Bold'
#         )

#         subheader_style = ParagraphStyle(
#             'CustomSubHeader',
#             parent=styles['Normal'],
#             fontSize=16,
#             spaceAfter=20,
#             textColor=colors.HexColor('#4a5568'),
#             alignment=TA_CENTER,
#             fontName='Helvetica'
#         )

#         # Header
#         elements.append(Paragraph("UPRISING SEEDS", header_style))
#         elements.append(Paragraph("Wholesale Order Summary", subheader_style))
#         elements.append(Spacer(1, 20))

#         # Order info
#         # current_date = datetime.date.today().strftime("%B %d, %Y")
#         elements.append(Paragraph(f"<b>Order Number:</b> {order.order_number}", styles['Normal']))
#         elements.append(Paragraph(f"<b>Order Date:</b> {order.date.strftime('%B %d, %Y') if order.date else 'N/A'}", styles['Normal']))

#         if hasattr(order, 'store') and order.store:
#             elements.append(Paragraph(f"<b>Store:</b> {order.store.store_name}", styles['Normal']))

#         elements.append(Spacer(1, 25))

#         # Items table
#         elements.append(Paragraph("Order Items", styles['Heading2']))

#         table_data = [['Qty', 'Variety', 'Type', 'Unit Price', 'Subtotal']]
#         pkt_price = settings.PACKET_PRICE
#         total_cost = 0
#         for item in order_includes:
#             quantity = item.quantity or 0
#             variety = item.product.variety.var_name if item.product else 'N/A'
#             veg_type = item.product.variety.veg_type if item.product else 'N/A'
#             # unit_price = item.product.price if item.product else 0
#             line_total = quantity * pkt_price
            
#             # Truncate long variety names
#             if len(variety) > 35:
#                 variety = variety[:32] + "..."

#             table_data.append([
#                 str(quantity),
#                 variety,
#                 veg_type,
#                 f"${pkt_price:.2f}",
#                 f"${line_total:.2f}"
#             ])

#             total_cost += line_total

#         # Create and style table
#         items_table = Table(table_data, colWidths=[0.6*inch, 3.2*inch, 1.2*inch, 0.8*inch, 0.8*inch])
#         items_table.setStyle(TableStyle([
#             # Header
#             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d4a22')),
#             ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 0), (-1, 0), 11),
#             ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

#             # Data rows
#             ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
#             ('FONTSIZE', (0, 1), (-1, -1), 10),
#             ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Qty centered
#             ('ALIGN', (1, 1), (2, -1), 'LEFT'),    # Variety and type left
#             ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),  # Prices right

#             # Styling
#             ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
#             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
#             ('TOPPADDING', (0, 0), (-1, -1), 8),
#             ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
#             ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
#         ]))

#         elements.append(items_table)
#         elements.append(Spacer(1, 25))

#         # Totals
#         elements.append(Paragraph("Order Summary", styles['Heading2']))

#         totals_data = [
#             ['Subtotal:', f"${total_cost:.2f}"],
#             ['Shipping:', 'TBD'],
#             ['Total:', 'TBD']
#         ]

#         totals_table = Table(totals_data, colWidths=[4.5*inch, 1.5*inch])
#         totals_table.setStyle(TableStyle([
#             ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
#             ('FONTSIZE', (0, 0), (-1, -1), 11),
#             ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
#             ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
#             ('TOPPADDING', (0, 0), (-1, -1), 4),
#             ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
#         ]))

#         elements.append(totals_table)
#         elements.append(Spacer(1, 30))

#         # Footer
#         footer_style = ParagraphStyle(
#             'FooterStyle',
#             parent=styles['Normal'],
#             fontSize=9,
#             textColor=colors.HexColor('#6c757d'),
#             alignment=TA_CENTER
#         )

#         elements.append(Paragraph("Thank you for your wholesale order!", footer_style))
#         elements.append(Paragraph("For questions, please contact us through our wholesale portal.", footer_style))

#         # Build PDF
#         doc.build(elements)

#         pdf_data = buffer.getvalue()
#         buffer.close()

#         response = HttpResponse(pdf_data, content_type='application/pdf')
#         response['Content-Disposition'] = f'inline; filename="Uprising - {order.order_number}.pdf"'
#         return response

#     except Exception as e:
#         return HttpResponse(f"Error: {str(e)}", content_type='text/plain')


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return OnlineOrder.objects.filter(pulled_for_processing=False)
    

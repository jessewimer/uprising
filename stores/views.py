from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import LoginForm
from .models import Store
from products.models import Product, Variety
import json
from .models import StoreOrder, SOIncludes
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse
from django.http import JsonResponse, HttpResponseNotFound, HttpResponseForbidden
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum
import pytz
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.http.request import RawPostDataException
from uprising.utils.auth import is_employee
from django.contrib.admin.views.decorators import user_passes_test


class CustomLogoutView(LogoutView):
    next_page = 'login'

class CustomLoginView(LoginView):
    def get_success_url(self):
        store_name = self.request.user.username
        return reverse('dashboard', kwargs={'store_name': store_name})

@login_required(login_url='/accounts/login')
def dashboard(request, store_name):
    user = request.user
    
    try:
        # Get the store by store_user username (matching the URL parameter)
        store = Store.objects.select_related('store_user').get(store_user__username=store_name)
    except Store.DoesNotExist:
        return HttpResponseNotFound("Store not found")
    
    # Check if user has permission to access this store
    if user != store.store_user and not user.is_staff:
        return HttpResponseForbidden("You don't have permission to access this store")
    
    current_year = settings.CURRENT_ORDER_YEAR
    year_suffix = f"{current_year % 100:02d}"
    pkt_price = settings.PACKET_PRICE

    # Replace the POST handling section in your dashboard view with this:

    if request.method == 'POST':
        print("POST request received in dashboard view")
        
        try:
            # Process the form submission - handle potential RawPostDataException
            try:
                order_data = json.loads(request.body)
            except RawPostDataException:
                # If body was already read, try to get data from request.POST
                print("Request body already read, trying request.POST")
                order_data = {}
                for key, value in request.POST.items():
                    if key != 'csrfmiddlewaretoken':
                        try:
                            order_data[key] = int(value)
                        except ValueError:
                            continue
            
            print("ORDER DATA:", order_data)
            print("Order data type:", type(order_data))
            print("Order data keys:", list(order_data.keys()) if order_data else "No keys")
            
            if not order_data:
                return JsonResponse({'error': 'No order data received'}, status=400)
            
            # Process the order data to extract SKU prefixes and quantities
            processed_order_data = {}
            for key, quantity in order_data.items():
                if key.startswith('quantity_'):
                    # Strip the 'quantity_' prefix to get the actual SKU prefix
                    sku_prefix = key[9:]  # Remove 'quantity_' (9 characters)
                    processed_order_data[sku_prefix] = quantity
                else:
                    # If it doesn't start with quantity_, assume it's already a SKU prefix
                    processed_order_data[key] = quantity
            
            print("PROCESSED ORDER DATA:", processed_order_data)
            
            invalid_products = []
            
            # Check for invalid products using the processed SKU prefixes
            for sku_prefix in processed_order_data.keys():
                print(f"Checking SKU prefix: {sku_prefix}")
                try:
                    # Check if a 'pkt' product with this SKU prefix exists in the store's available products
                    exists = store.available_products.filter(
                        variety__sku_prefix=sku_prefix,
                        sku_suffix='pkt'
                    ).exists()
                    print(f"SKU {sku_prefix} exists: {exists}")
                    
                    if not exists:
                        invalid_products.append(sku_prefix)
                except Exception as e:
                    print(f"Error checking SKU prefix {sku_prefix}: {e}")
                    invalid_products.append(sku_prefix)
            
            print(f"Invalid products: {invalid_products}")
            
            if invalid_products:
                print("Invalid products found:", invalid_products)
                return JsonResponse({'invalid_products': invalid_products}, status=400)
            
            print("All products valid, creating order...")
            
            # Create the order
            try:
                existing_orders = StoreOrder.objects.filter(store=store, order_number__endswith=f"-{year_suffix}")
                this_year_order_count = existing_orders.count() + 1
                print(f"This year order count: {this_year_order_count}")
                
                pacific_tz = pytz.timezone('US/Pacific')
                pacific_now = timezone.now().astimezone(pacific_tz).date()
                # print(f"Pacific now: {pacific_now}")
                
                order = StoreOrder.objects.create(
                    store=store,
                    order_number=f"W{store.store_num:02d}{this_year_order_count:02d}-{year_suffix}",
                    date=pacific_now,
                )
                
                print(f"Created order: {order.order_number}")
            except Exception as e:
                print(f"Error creating order: {e}")
                return JsonResponse({'error': f'Error creating order: {str(e)}'}, status=500)
            
            # Create SOIncludes entries for each product in the order
            items_created = 0
            for sku_prefix, quantity in processed_order_data.items():  # Use processed_order_data here
                print(f"Processing SKU: {sku_prefix}, Quantity: {quantity}")
                
                # Skip if quantity is 0 or negative
                if not quantity or quantity <= 0:
                    print(f"Skipping SKU {sku_prefix} - invalid quantity: {quantity}")
                    continue
                    
                try:
                    # Find the product by SKU prefix through the variety, specifically the 'pkt' product
                    product = Product.objects.select_related('variety').get(
                        variety__sku_prefix=sku_prefix,
                        sku_suffix='pkt'
                    )
                    
                    print(f"Found product: {product.variety.var_name} (ID: {product.id})")
                    print(f"About to create SOIncludes with:")
                    # print(f"  - store_order: {order} (ID: {order.id})")
                    print(f"  - product: {product} (ID: {product.id})")
                    print(f"  - quantity: {quantity}")
                    print(f"  - price: {pkt_price}")
                    
                    so_include = SOIncludes.objects.create(
                        store_order=order,
                        product=product,
                        quantity=quantity,
                        price=pkt_price,
                    )
                    
                    items_created += 1
                    print(f"Successfully created SOIncludes: ID={so_include.id}")
                    
                    # Verify it was actually saved
                    verify_so_include = SOIncludes.objects.get(id=so_include.id)
                    print(f"Verification - SOIncludes {verify_so_include.id} exists with quantity {verify_so_include.quantity}")
                    
                except Product.DoesNotExist:
                    print(f"ERROR: Product with SKU prefix {sku_prefix} and sku_suffix='pkt' does not exist")
                    # Let's see what products DO exist with this SKU prefix
                    matching_products = Product.objects.filter(variety__sku_prefix=sku_prefix)
                    print(f"Products found with SKU prefix {sku_prefix}: {list(matching_products.values('id', 'sku_suffix'))}")
                    continue
                except Exception as e:
                    print(f"ERROR creating SOIncludes for SKU {sku_prefix}: {e}")
                    print(f"Error type: {type(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"Order {order.order_number} created successfully with {items_created} items")
            
            # Return success response for AJAX
            return JsonResponse({
                'status': 'success', 
                'order_number': order.order_number,
                'order_id': order.id,
                'items_created': items_created
            }, status=200)
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"Unexpected error in POST request: {e}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

    # Replace the GET request section in your dashboard view with this:

    # GET request handling
    # Get all orders for the current year for this store

    # Get all orders for the current year for this store
    current_year_orders = StoreOrder.objects.filter(
        store=store,
        order_number__endswith=f"-{year_suffix}"
    ).prefetch_related('items__product__variety').order_by('-date')

    # --- Previous Orders: total quantity per product sku_prefix ---
    previous_orders = (
        SOIncludes.objects
        .filter(store_order__store=store)  # This might also need to be 'order__store' depending on your field name
        .values('product__variety__sku_prefix')
        .annotate(total_qty=Sum('quantity'))
    )

    # Convert to dictionary: { 'sku_prefix': total_qty }
    previous_items_dict = {
        entry['product__variety__sku_prefix']: entry['total_qty']
        for entry in previous_orders
        if entry['product__variety__sku_prefix']  # Skip None values
    }

    # --- Get all available products for the store ---
    try:
        # Try the relationship name you're using in your template/view
        products = store.available_products.filter(
            sku_suffix='pkt',
            storeproduct__is_available=True
        ).select_related('variety').order_by('variety__category', 'variety__veg_type', 'variety__var_name')
    except AttributeError:
        # Fallback if the relationship name is different
        products = Product.objects.filter(
            storeproduct__store=store,
            storeproduct__is_available=True,
            sku_suffix='pkt'
        ).select_related('variety').order_by('variety__category', 'variety__veg_type', 'variety__var_name')

    # Attach previously ordered count using variety.sku_prefix
    for product in products:
        sku_prefix = getattr(product.variety, 'sku_prefix', None)
        product.previously_ordered_count = previous_items_dict.get(sku_prefix, 0)

    # --- Prepare current year orders for JavaScript ---
    orders_data = []
    for order in current_year_orders:
        order_items = []
        total_items = 0
        
        # Access the related SOIncludes objects using the correct related_name
        so_includes = order.items.all()
        
        for so_include in so_includes:
            variety = getattr(so_include.product, 'variety', None)
            if variety:
                order_items.append({
                    'sku_prefix': getattr(variety, 'sku_prefix', ''),
                    'variety_name': getattr(variety, 'var_name', ''),
                    'quantity': so_include.quantity,
                    'price': float(so_include.price or pkt_price)
                })
                total_items += so_include.quantity

        # Format fulfilled_date for display
        fulfilled_status = 'Pending'
        if order.fulfilled_date:
            fulfilled_status = order.fulfilled_date.strftime('%m/%d/%Y')

        orders_data.append({
            'id': order.id,
            'order_number': order.order_number,
            'date': order.date.strftime('%m/%d/%Y') if order.date else '',
            'items': order_items,
            'total_items': total_items,
            'total_cost': total_items * pkt_price,
            'shipping_cost': getattr(order, 'shipping_cost', None),
            'fulfilled_status': fulfilled_status
        })

    # --- Prepare product dictionary for JS ---
    product_dict = {}
    for product in products:
        variety = getattr(product, 'variety', None)
        if variety and getattr(variety, 'sku_prefix', None):
            product_dict[variety.sku_prefix] = [
                getattr(variety, 'var_name', ''), 
                getattr(variety, 'veg_type', '')
            ]

    # --- Render context ---
    context = {
        'store': store,
        'products': products,
        'slots': getattr(store, 'slots', 50),  # Default to 50 if no slots field
        'previous_items': json.dumps(previous_items_dict),
        'current_year_orders': orders_data,
        'orders_data': json.dumps(orders_data),
        'current_year': current_year,
        'year_suffix': year_suffix,
        'pkt_price': pkt_price,
        'product_dict_json': json.dumps(product_dict),
    }

    return render(request, 'stores/dashboard.html', context)
# def dashboard(request, store_name):
#     user = request.user
#     store = Store.objects.get(store_user=user)
#     # store = Store.objects.select_related('store_user').get(store_user__username=store_name)
#     current_year = settings.CURRENT_ORDER_YEAR
#     year_suffix = f"{current_year % 100:02d}"
#     pkt_price = settings.PACKET_PRICE

#     if request.method == 'POST':
#         print("POST request received in dashboard view")
        
#         try:
#             # Process the form submission
#             print("Request body:", request.body)
#             order_data = json.loads(request.body)
#             print("ORDER DATA: ", order_data)
#             print("Order data type:", type(order_data))
#             print("Order data keys:", list(order_data.keys()) if order_data else "No keys")
            
#             invalid_products = []
            
#             # Check for invalid products using SKU prefixes
#             for sku_prefix in order_data.keys():
#                 print(f"Checking SKU prefix: {sku_prefix}")
#                 try:
#                     # Check if a 'pkt' product with this SKU prefix exists in the store's available products
#                     exists = store.available_products.filter(
#                         variety__sku_prefix=sku_prefix,
#                         sku_suffix='pkt'
#                     ).exists()
#                     print(f"SKU {sku_prefix} exists: {exists}")
                    
#                     if not exists:
#                         invalid_products.append(sku_prefix)
#                 except Exception as e:
#                     print(f"Error checking SKU prefix {sku_prefix}: {e}")
#                     invalid_products.append(sku_prefix)
            
#             print(f"Invalid products: {invalid_products}")
            
#             if invalid_products:
#                 print("Invalid products found:", invalid_products)
#                 return JsonResponse({'invalid_products': invalid_products}, status=400)
            
#             print("All products valid, creating order...")
            
#             # Create the order
#             try:
#                 existing_orders = StoreOrder.objects.filter(store=store, order_number__endswith=f"-{year_suffix}")
#                 this_year_order_count = existing_orders.count() + 1
#                 print(f"This year order count: {this_year_order_count}")
                
#                 pacific_tz = pytz.timezone('US/Pacific')
#                 pacific_now = timezone.now().astimezone(pacific_tz).date()
#                 print(f"Pacific now: {pacific_now}")
                
#                 order = StoreOrder.objects.create(
#                     store=store,
#                     order_number=f"W{store.store_num:02d}{this_year_order_count:02d}-{year_suffix}",
#                     date=pacific_now,
#                 )
                
#                 print(f"Created order: {order.order_number}")
#             except Exception as e:
#                 print(f"Error creating order: {e}")
#                 return JsonResponse({'error': f'Error creating order: {str(e)}'}, status=500)
            
#             # Create SOIncludes entries for each product in the order
#             items_created = 0
#             for sku_prefix, quantity in order_data.items():
#                 print(f"Processing SKU: {sku_prefix}, Quantity: {quantity}")
#                 try:
#                     # Find the product by SKU prefix through the variety, specifically the 'pkt' product
#                     product = Product.objects.select_related('variety').get(
#                         variety__sku_prefix=sku_prefix,
#                         sku_suffix='pkt'
#                     )
                    
#                     print(f"Found product: {product.variety.var_name} (ID: {product.id})")
                    
#                     so_include = SOIncludes.objects.create(
#                         order=order,
#                         product=product,
#                         quantity=quantity,
#                         unit_price=pkt_price,
#                     )
                    
#                     items_created += 1
#                     print(f"Created SOIncludes: {so_include.id}")
                    
#                 except Product.DoesNotExist:
#                     print(f"Product with SKU prefix {sku_prefix} does not exist")
#                     continue
#                 except Exception as e:
#                     print(f"Error creating SOIncludes for SKU {sku_prefix}: {e}")
#                     print(f"Error type: {type(e)}")
#                     continue
            
#             print(f"Order {order.order_number} created successfully with {items_created} items")
            
#             # Return success response for AJAX
#             return JsonResponse({
#                 'status': 'success', 
#                 'order_number': order.order_number,
#                 'order_id': order.id,
#                 'items_created': items_created
#             }, status=200)
            
#         except json.JSONDecodeError as e:
#             print(f"JSON decode error: {e}")
#             return JsonResponse({'error': 'Invalid JSON data'}, status=400)
#         except Exception as e:
#             print(f"Unexpected error in POST request: {e}")
#             print(f"Error type: {type(e)}")
#             import traceback
#             traceback.print_exc()  # This will print the full traceback
#             return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

#     # Get all orders for the current year for this store
#     current_year_orders = StoreOrder.objects.filter(
#         store=store,
#         order_number__endswith=f"-{year_suffix}"
#     ).select_related('store').prefetch_related('orderincludes_set__product').order_by('-date')


#     # --- Previous Orders: total quantity per product sku_prefix ---
#     previous_orders = (
#         SOIncludes.objects
#         .filter(store_order__store=store)
#         .values('product__variety__sku_prefix')
#         .annotate(total_qty=Sum('quantity'))
#     )

#     # Convert to dictionary: { 'sku_prefix': total_qty }
#     previous_items_dict = {
#         entry['product__variety__sku_prefix']: entry['total_qty']
#         for entry in previous_orders
#     }

#     # --- Get all available products for the store ---
#     products = Product.objects.filter(
#         available_in_stores=store,
#         storeproduct__is_available=True
#     )

#     # Attach previously ordered count using variety.sku_prefix
#     for product in products:
#         sku_prefix = getattr(product.variety, 'sku_prefix', None)
#         product.previously_ordered_count = previous_items_dict.get(sku_prefix, 0)

#     # --- Prepare current year orders for JavaScript ---
#     orders_data = []
#     for order in current_year_orders:
#         order_items = []
#         for order_include in order.items.all():  # related_name="items"
#             variety = getattr(order_include.product, 'variety', None)
#             order_items.append({
#                 'sku_prefix': getattr(variety, 'sku_prefix', ''),
#                 'variety_name': getattr(variety, 'name', ''),
#                 'quantity': order_include.quantity,
#                 'price': float(pkt_price)
#             })

#         orders_data.append({
#             'id': order.id,
#             'order_number': order.order_number,
#             'date': order.date.strftime('%Y-%m-%d'),
#             'items': order_items,
#             'total_items': sum(item['quantity'] for item in order_items),
#             'total_cost': sum(item['quantity'] for item in order_items) * pkt_price
#         })

#     # --- Prepare product dictionary for JS ---
#     product_qs = Product.objects.all().select_related('variety')
#     product_dict = {}
#     for p in product_qs:
#         variety = getattr(p, 'variety', None)
#         if variety and getattr(variety, 'sku_prefix', None) and getattr(p, 'veg_type', None):
#             product_dict[variety.sku_prefix] = [variety.name, p.veg_type]

#     product_dict_json = json.dumps(product_dict)

#     # --- Render context ---
#     context = {
#         'store': store,
#         'products': products,
#         'slots': store.slots,
#         'previous_items': json.dumps(previous_items_dict),  # for JS
#         'current_year_orders': orders_data,
#         'orders_data': json.dumps(orders_data),  # JSON for JS
#         'current_year': current_year,
#         'year_suffix': year_suffix,
#         'pkt_price': pkt_price,
#         'product_dict_json': product_dict_json,
#     }

#     return render(request, 'stores/dashboard.html', context)


    # previous_orders = (
    #     SOIncludes.objects
    #     .filter(store_order__store=store)  # <-- use store_order, not order
    #     .values('product__variety__sku_prefix')
    #     .annotate(total_qty=Sum('quantity'))
    # )

    # # Convert to dictionary: { 'sku_prefix': quantity }
    # previous_items_dict = {
    #     entry['product__variety__sku_prefix']: entry['total_qty']
    #     for entry in previous_orders
    # }

    # products = Product.objects.filter(
    #     available_in_stores=store,
    #     storeproduct__is_available=True
    # )

    # for product in products:
    #     product.previously_ordered_count = previous_items_dict.get(
    #         product.variety.sku_prefix, 0
    #     )


    # # Prepare orders data for JavaScript (if needed)
    # orders_data = []
    # for order in current_year_orders:
    #     order_items = []
    #     for order_include in order.orderincludes_set.all():
    #         order_items.append({
    #             'item_number': order_include.product.item_number,
    #             'variety': order_include.product.variety,
    #             'quantity': order_include.quantity,
    #             'price': float(pkt_price)
    #         })

    #     orders_data.append({
    #         'id': order.id,
    #         'order_number': order.order_number,
    #         'date': order.date.strftime('%Y-%m-%d'),
    #         'items': order_items,
    #         'total_items': sum(item['quantity'] for item in order_items),
    #         'total_cost': sum(item['quantity'] for item in order_items) * pkt_price
    #     })

    # # for order in orders_data:
    # #     print(f"Order ID: {order['id']}, Order Num: {order['order_number']}, Total Cost: {order['total_cost']}")

    # product_qs = Product.objects.all().values('item_number', 'variety', 'veg_type')
    # product_dict = {}

    # for p in product_qs:
    #     item_num = p['item_number']
    #     # Skip if item_number is None or missing variety/veg_type to avoid bad entries
    #     if item_num is not None and p['variety'] and p['veg_type']:
    #         product_dict[item_num] = [p['variety'], p['veg_type']]


    # product_dict_json = json.dumps(product_dict)

    # context = {
    #     'store': store,
    #     'products': products,
    #     'slots': store.slots,
    #     'previous_items': json.dumps(previous_items_dict),  # still useful for JS
    #     'current_year_orders': orders_data,
    #     'orders_data': json.dumps(orders_data),  # JSON data for JavaScript
    #     'current_year': current_year,
    #     'year_suffix': year_suffix,
    #     'pkt_price': pkt_price,
    #     'product_dict_json': product_dict_json,
    # }
    # return render(request, 'stores/dashboard.html', context)


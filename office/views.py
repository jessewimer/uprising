import json
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.http import JsonResponse
from django.contrib.auth import login
from products.models import Variety, Product, LastSelected, LabelPrint, Sales
from stores.models import Store, StoreProduct, StoreOrder, SOIncludes
from orders.models import OOIncludes, OnlineOrder
from lots.models import Grower, Lot, RetiredLot, StockSeed, Germination, GermSamplePrint
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Case, When, IntegerField, Max, Sum, F, CharField, Value
from django.db.models.functions import Concat
from uprising.utils.auth import is_employee
from uprising import settings
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.utils import timezone




@login_required
@require_http_methods(["GET"])
def check_admin_access(request):
    """Check if user has admin access"""
    is_admin = request.user.is_staff or request.user.is_superuser
    return JsonResponse({'is_admin': is_admin})
class OfficeLoginForm(AuthenticationForm):
    """
    Custom login form that keeps the standard AuthenticationForm behavior.
    """
    pass  # You can add custom validation here if needed


class OfficeLoginView(LoginView):
    template_name = 'office/login.html'
    form_class = OfficeLoginForm
    redirect_authenticated_user = False  # Let users see login page

    def form_valid(self, form):
        """
        Only log in the user if they are in the 'employees' group.
        Otherwise, treat it as an invalid login.
        """
        user = form.get_user()
        if is_employee(user):
            login(self.request, user)  # Log in the employee
            return super().form_valid(form)
        else:
            # Add a form error so the template shows invalid credentials
            form.add_error(None, "Invalid username or password.")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('office_landing')
    
class OfficeLogoutView(LogoutView):
    next_page = 'office_login'


@login_required
@user_passes_test(is_employee)
def office_landing(request):
    """
    Office landing page view - displays the main office portal with action cards
    """
    context = {
        'user': request.user,
        'user_name': request.user.get_full_name() or request.user.username,
    }
    
    return render(request, 'office/office_landing.html', context)


@login_required
@user_passes_test(is_employee)
def view_variety(request):
    """
    View all varieties, last selected variety, products, lots, and all_vars dictionary.
    Handles POSTs for selecting variety, printing, editing, and adding records.
    """
    user = request.user
    
    # --- Get the user's last selected variety (if any), else default to AST-HP ---
    last_selected_entry = LastSelected.objects.filter(user=user).last()
    last_selected_variety = (
        last_selected_entry.variety if last_selected_entry else Variety.objects.get(pk="BEA-CA")
    )
    
    # --- All varieties ---
    varieties = Variety.objects.all().order_by('veg_type', 'sku_prefix')
    
    # --- Build all_vars dict for front-end dropdown (JS-friendly) ---
    all_vars = {
        v.sku_prefix: {
            'common_spelling': v.common_spelling,
            'var_name': v.var_name,
            'veg_type': v.veg_type,

        }
        for v in varieties
    }

    # Add this line to convert to JSON
    all_vars_json = json.dumps(all_vars)
    
    # --- Initialize objects to pass to template ---
    variety_obj = last_selected_variety  # Default to last selected
    products = None
    lots = None
    
    # --- Handle POST actions ---
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Handle variety selection (this changes the current variety)
        if action == 'select_variety':
            selected_variety_pk = request.POST.get('variety_sku')
            if selected_variety_pk:
                variety_obj = get_object_or_404(Variety, pk=selected_variety_pk)
                # Save as last selected for this user
                LastSelected.objects.update_or_create(
                    user=user,
                    defaults={'variety': variety_obj}
                )
                return redirect('view_variety')

    # --- Get associated products and lots for the current variety ---
    if variety_obj:
        products = Product.objects.filter(variety=variety_obj)
        # sort products based on SKU_SUFFIXES
        products = Product.objects.filter(variety=variety_obj).order_by(
            Case(*[When(sku_suffix=s, then=i) for i, s in enumerate(settings.SKU_SUFFIXES)],
                output_field=IntegerField())
        )
        lots = Lot.objects.filter(variety=variety_obj).order_by("year")
        # sort lots based on year

        growers = Grower.objects.all().order_by('code') 

        lots_json = json.dumps([
            {
                'id': lot.id,
                'grower': str(lot.grower) if lot.grower else '',
                'year': lot.year,
                'harvest': lot.harvest or '',
                'is_retired': hasattr(lot, 'retired_info'),
                'low_inv': lot.low_inv,
            }
            for lot in lots
        ])

    else:
        products = Product.objects.none()

        lots = Lot.objects.none()
    
    context = {
        'last_selected': last_selected_variety,
        'variety': variety_obj,
        'products': products,
        'lots': lots,
        'lots_json': lots_json,
        'all_vars_json': all_vars_json,
        'growers': growers,
        'env_types': settings.ENV_TYPES,
        'sku_suffixes': settings.SKU_SUFFIXES,
        'pkg_sizes': settings.PKG_SIZES,
    }
    return render(request, 'office/view_variety.html', context)

@login_required
@user_passes_test(is_employee)
def print_product_labels(request):
    
    from datetime import date
    if request.method == 'POST':
        if request.user.username not in ["office", "admin"]:
            return JsonResponse({'error': 'You are not allowed to print labels'}, status=403)
        
        
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            print_type = data.get('print_type')
            quantity = int(data.get('quantity', 1))
            
            product = Product.objects.get(pk=product_id)
                        
            # Only log if not printing back-only labels
            if print_type not in ['back_single', 'back_sheet']:
                # Calculate actual label quantity
                if print_type in ['front_sheet', 'front_back_sheet']:
                    actual_qty = quantity * 30  # 30 labels per sheet
                else:
                    actual_qty = quantity  # Singles and front_back_single
                
                # Log the print job in LabelPrint table
                LabelPrint.objects.create(
                    product=product,
                    lot=product.lot,
                    date=date.today(),
                    qty=actual_qty,
                    for_year=date.today().year
                )
            
            print(f"Printing {quantity} {print_type} labels for product: {product.variety_id}")
            # Add your actual printing logic here
            
            return JsonResponse({
                'success': True, 
                'message': f"Printing {quantity} {print_type} labels for {product.variety}."
            })
            
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@user_passes_test(is_employee)
def assign_lot_to_product(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            lot_id = data.get('lot_id')
            change_all_products = data.get('change_all_products', False)
            if change_all_products:
                product = Product.objects.get(pk=product_id)
                lot = Lot.objects.get(pk=lot_id) if lot_id else None
                # Update all products with the same variety
                Product.objects.filter(variety=product.variety).update(lot=lot)
                return JsonResponse({'success': True})
            
            product = Product.objects.get(pk=product_id)
            
            if lot_id:
                lot = Lot.objects.get(pk=lot_id)
                product.lot = lot
            else:
                product.lot = None
                
            product.save()
            
            return JsonResponse({'success': True})
        except (Product.DoesNotExist, Lot.DoesNotExist) as e:
            return JsonResponse({'error': 'Product or lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@user_passes_test(is_employee)
def set_lot_low_inv(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lot_id = data.get('lot_id')
            low_inv = data.get('low_inv')
            
            lot = Lot.objects.get(pk=lot_id)
            lot.low_inv = low_inv
            lot.save()
            
            return JsonResponse({'success': True})
        except Lot.DoesNotExist:
            return JsonResponse({'error': 'Lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@user_passes_test(is_employee)
def analytics(request):
    """
    View for displaying analytics and business performance metrics
    """
    # Get envelope count data for the most recent sales year
    envelope_data = get_envelope_count_data()
    total_store_sales, pending_store_sales = Store.get_total_store_sales(settings.CURRENT_ORDER_YEAR)
    # print(f"DEBUG VIEW: total_store_sales = {total_store_sales}")
    total_store_pkts, pending_store_pkts = Store.get_total_store_packets(settings.CURRENT_ORDER_YEAR)
    # print(f"DEBUG VIEW: total_store_pkts = {total_store_pkts}")
    current_year = f"20{settings.CURRENT_ORDER_YEAR}"

    # Ensure we serialize the JSON properly
    envelope_json = json.dumps(envelope_data['envelope_counts'])
    # print(f"DEBUG VIEW: envelope_json = {envelope_json}")
    top_sellers = get_top_selling_products(limit=3)
    
    context = {
        'page_title': 'Analytics Dashboard',
        'envelope_data_json': envelope_json,
        'envelope_data': envelope_data['envelope_counts'],
        'envelope_total': envelope_data['total'],
        'last_sales_year': envelope_data['year'],
        'total_store_sales': total_store_sales,
        'pending_store_sales': pending_store_sales,
        'total_store_pkts': total_store_pkts,
        'pending_store_pkts': pending_store_pkts,
        'current_year': current_year,
        'top_sellers': top_sellers,
    }
    
    # print(f"DEBUG VIEW: final context envelope_data_json = {context['envelope_data_json']}")
   
    return render(request, 'products/analytics.html', context)


def get_envelope_count_data():
    """
    Calculate envelope usage for the most recent sales year
    """
    # Find the most recent sales year
    latest_year = Sales.objects.aggregate(max_year=Max('year'))['max_year']
    # print(f"DEBUG: Latest sales year: {latest_year}")
    
    if not latest_year:
        return {
            'envelope_counts': {},
            'total': 0,
            'year': None
        }
    
    # Get all sales for the latest year
    sales_data = Sales.objects.filter(year=latest_year).select_related('product')
    # print(f"DEBUG: Found {sales_data.count()} sales records for {latest_year}")
    
    # Group by product and sum quantities (combining wholesale and retail)
    product_totals = {}
    for sale in sales_data:
        product_id = sale.product.id
        if product_id not in product_totals:
            product_totals[product_id] = {
                'product': sale.product,
                'total_quantity': 0
            }
        product_totals[product_id]['total_quantity'] += sale.quantity
    
    # print(f"DEBUG: Found {len(product_totals)} unique products")
    
    # Group by envelope type and calculate totals
    envelope_counts = {}
    total_envelopes = 0
    products_with_env_type = 0
    products_without_env_type = 0
    
    for product_data in product_totals.values():
        product = product_data['product']
        quantity = product_data['total_quantity']
        
        # print(f"DEBUG: Product {product.id} - env_type: '{product.env_type}' - quantity: {quantity}")
        
        # Skip if product doesn't have env_type or it's empty
        if not product.env_type:
            products_without_env_type += 1
            print(f"DEBUG: Skipping product {product.id} - no env_type")
            continue
            
        products_with_env_type += 1
        envelope_type = product.env_type
        
        if envelope_type not in envelope_counts:
            envelope_counts[envelope_type] = 0
        
        envelope_counts[envelope_type] += quantity
        total_envelopes += quantity

    # Miscellaneous models
    # class MiscSale(models.Model):
    #     variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name="misc_sales")
    #     lbs = models.FloatField()
    #     date = models.DateField()
    #     customer = models.CharField(max_length=255)
    #     notes = models.TextField(blank=True, null=True)


    # class MiscProduct(models.Model):
    #     lineitem_name = models.CharField(max_length=255)
    #     sku = models.CharField(max_length=50, unique=True)
    #     category = models.CharField(max_length=100, blank=True, null=True)
    #     description = models.TextField(blank=True, null=True)   


    # misc products with envelope types
    # TOM-CH-pkts -> 7 Tomato envelopes
    # PEA-SP-pkts -> 3 Pea envelopes
    # BEA-MF-pkts -> 4 Bean envelopes

    # TODO - include misc product sales in envelope counts

    
    # Sort envelope counts by quantity (descending)
    envelope_counts = dict(sorted(envelope_counts.items(), key=lambda x: x[1], reverse=True))
    
    return {
        'envelope_counts': envelope_counts,
        'total': total_envelopes,
        'year': latest_year
    }

def get_top_selling_products(limit=5):
    """
    Get top selling products by total sales quantity for the most recent sales year
    """
    # Get the current order year (two digit) and convert to full year
    current_year = settings.CURRENT_ORDER_YEAR
    full_year = 2000 + int(current_year)  # 25 -> 2025
    
    # DEBUG: Print what year we're looking for
    print(f"DEBUG: Looking for orders from year {full_year}")
    print(f"DEBUG: CURRENT_ORDER_YEAR setting = {current_year}")
    
    # DEBUG: Check if we have any orders from this year
    total_orders = OnlineOrder.objects.filter(date__year=full_year).count()
    print(f"DEBUG: Found {total_orders} orders from {full_year}")
    
    # DEBUG: Check if we have any OOIncludes from this year
    total_includes = OOIncludes.objects.filter(order__date__year=full_year).count()
    print(f"DEBUG: Found {total_includes} OOIncludes entries from {full_year}")
    
    # Query OOIncludes for orders from that year, aggregate by product
    top_products = (
        OOIncludes.objects
        .filter(order__date__year=full_year)
        .values('product__variety__var_name', 'product__sku_suffix')
        .annotate(
            display_name=Case(
                When(product__sku_suffix__isnull=True, 
                     then=F('product__variety__var_name')),
                When(product__sku_suffix='', 
                     then=F('product__variety__var_name')),
                default=Concat(
                    F('product__variety__var_name'),
                    Value(' ('),
                    F('product__sku_suffix'),
                    Value(')'),
                    output_field=CharField()
                )
            ),
            total_packets=Sum('qty'),
            total_revenue=Sum(F('qty') * F('price'))
        )
        .order_by('-total_packets')
        [:limit]
    )
    
    # DEBUG: Print the raw queryset
    print(f"DEBUG: Query returned {len(list(top_products))} results")
    
    # Convert to the format expected by frontend
    result = []
    for item in top_products:
        print(f"DEBUG: Processing item: {item}")
        result.append({
            'name': item['display_name'] or 'Unknown Product',
            'packets': int(item['total_packets'] or 0),
            'revenue': float(item['total_revenue'] or 0)
        })
    
    print(f"DEBUG: Final result: {result}")
    return result

def get_detailed_top_sellers(limit=50):
    """
    Get detailed top sellers for modal - same logic, more items
    """
    return get_top_selling_products(limit=limit)

# Add this API endpoint for the modal
@login_required
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def top_sellers_details(request):
    """
    API endpoint for detailed top sellers data (for the modal)
    """
    try:
        top_sellers = get_detailed_top_sellers(limit=50)
        
        return JsonResponse({
            'success': True,
            'top_sellers': top_sellers
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@user_passes_test(is_employee)
def store_sales_details(request):
    """
    API endpoint for store sales analytics data
    Returns data for charts and tables in the store sales modal
    """
    try:
        # Get current year suffix (e.g., "25" for 2025)
        current_year = getattr(settings, 'CURRENT_ORDER_YEAR', str(timezone.now().year)[-2:])
        year_suffix = str(current_year)[-2:]
        
        print(f"DEBUG: Looking for orders ending with: -{year_suffix}")
        
        # Base queryset for fulfilled orders this year
        base_orders = StoreOrder.objects.filter(
            order_number__endswith=f'-{year_suffix}',
            fulfilled_date__isnull=False
        ).select_related('store').prefetch_related('items__product__variety')
        
        print(f"DEBUG: Found {base_orders.count()} fulfilled orders")
        
        # 1. Sales over time - group by fulfilled date
        sales_over_time = []
        daily_sales = base_orders.values('fulfilled_date__date').annotate(
            total_sales=Sum(F('items__price') * F('items__quantity'))
        ).order_by('fulfilled_date__date')
        
        for day in daily_sales:
            if day['total_sales'] and day['fulfilled_date__date']:
                sales_over_time.append({
                    'date': day['fulfilled_date__date'].isoformat(),
                    'total_sales': float(day['total_sales'])
                })
        
        print(f"DEBUG: Sales over time entries: {len(sales_over_time)}")
        
        # 2. Sales by store
        sales_by_store = []
        store_sales = base_orders.values(
            'store__store_name'
        ).annotate(
            total_sales=Sum(F('items__price') * F('items__quantity')),
            total_packets=Sum('items__quantity')
        ).order_by('-total_sales')
        
        for store in store_sales:
            if store['total_sales']:
                sales_by_store.append({
                    'store_name': store['store__store_name'] or 'Unknown Store',
                    'total_sales': float(store['total_sales']),
                    'total_packets': store['total_packets'] or 0
                })
        
        print(f"DEBUG: Sales by store entries: {len(sales_by_store)}")
        
        # 3. Sales by product - Use var_name with veg_type in parentheses
        sales_by_product = []
        product_sales = base_orders.values(
            'items__product__variety__var_name',
            'items__product__variety__veg_type'
        ).annotate(
            total_sales=Sum(F('items__price') * F('items__quantity')),
            total_packets=Sum('items__quantity')
        ).order_by('-total_sales')
        
        for product in product_sales:
            if product['total_sales']:
                var_name = product['items__product__variety__var_name'] or 'Unknown Variety'
                veg_type = product['items__product__variety__veg_type']
                
                # Format: "Variety Name (Veg Type)" or just "Variety Name" if no veg_type
                if veg_type:
                    product_name = f"{var_name} ({veg_type})"
                else:
                    product_name = var_name
                
                sales_by_product.append({
                    'product_name': product_name,
                    'total_sales': float(product['total_sales']),
                    'total_packets': product['total_packets'] or 0
                })
        
        print(f"DEBUG: Sales by product entries: {len(sales_by_product)}")
        
        response_data = {
            'sales_over_time': sales_over_time,
            'sales_by_store': sales_by_store,
            'sales_by_product': sales_by_product
        }
        
        print(f"DEBUG: Returning response with {len(response_data)} keys")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"ERROR in store_sales_details: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)




@login_required
@user_passes_test(is_employee)
def varieties_json(request):
    """
    Get distinct non-null, non-empty varieties as JSON
    """
    varieties = Product.objects.exclude(variety__isnull=True).exclude(variety='').values_list('variety', flat=True).distinct()
    data = [{"name": v} for v in varieties]
    return JsonResponse(data, safe=False)


@login_required
@user_passes_test(is_employee)
def crops_json(request):
    """
    Get crops/veg_types as JSON with optional search
    """
    q = request.GET.get('q', '')
    crops = Product.objects.exclude(veg_type__isnull=True).exclude(veg_type='')
    
    if q:
        crops = crops.filter(veg_type__icontains=q)
    
    crop_names = crops.values_list('veg_type', flat=True).distinct()
    data = [{"name": name} for name in crop_names]
    return JsonResponse(data, safe=False)


@login_required
@user_passes_test(is_employee)
def products_by_crop_json(request, crop):
    """
    Get products by specific crop/veg_type as JSON
    """
    products = Product.objects.filter(veg_type=crop)
    data = []
    
    for p in products:
        data.append({
            "veg_type": p.veg_type,
            "variety": p.variety,
            "current_inventory": "-",
            "previous_inventory": "-",
            "difference": "-",
            "germ_23": "-",
            "germ_24": "-",
            "germ_25": "-"
        })
    
    return JsonResponse(data, safe=False)


@login_required
@user_passes_test(is_employee)
def delete_lot(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lot_id = data.get('lot_id')
            
            lot = Lot.objects.get(pk=lot_id)
            lot.delete()
            
            return JsonResponse({'success': True})
        except Lot.DoesNotExist:
            return JsonResponse({'error': 'Lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@user_passes_test(is_employee)
def add_lot(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            variety_sku = data.get('variety_sku')
            grower_id = data.get('grower_id')
            year = data.get('year')
            harvest = data.get('harvest', '')
            
            variety = Variety.objects.get(pk=variety_sku)
            grower = Grower.objects.get(pk=grower_id)
            
            # Create the lot
            lot = Lot.objects.create(
                variety=variety,
                grower=grower,
                year=year,
                harvest=harvest,
                low_inv=False
            )
            
            return JsonResponse({'success': True})
        except (Variety.DoesNotExist, Grower.DoesNotExist):
            return JsonResponse({'error': 'Variety or Grower not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@user_passes_test(is_employee)
def retire_lot(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("Backend data:", data)
            lot_id = data.get('lot_id')
            lbs_remaining = data.get('lbs_remaining')
            notes = data.get('notes', '')
            retire_date = data.get('retire_date')
            
            lot = Lot.objects.get(pk=lot_id)
            
            if hasattr(lot, 'retired_info'):
                return JsonResponse({'error': 'This lot is already retired'}, status=400)
            
            # Create the RetiredLot entry
            RetiredLot.objects.create(
                lot=lot,
                lbs_remaining=lbs_remaining,
                retired_date=retire_date, 
                notes=notes
            )
            
            return JsonResponse({'success': True})
        except Lot.DoesNotExist:
            return JsonResponse({'error': 'Lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@user_passes_test(is_employee)
def record_stock_seed(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lot_id = data.get('lot_id')
            qty = data.get('qty')
            notes = data.get('notes', '')
            
            lot = Lot.objects.get(pk=lot_id)
            
            # Create the StockSeed entry
            StockSeed.objects.create(
                lot=lot,
                qty=qty,
                notes=notes
            )
            
            return JsonResponse({'success': True})
        except Lot.DoesNotExist:
            return JsonResponse({'error': 'Lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@user_passes_test(is_employee)
def record_germination(request):
    if request.method == 'POST':
        try:
            from datetime import date as date_class
            data = json.loads(request.body)
            lot_id = data.get('lot_id')
            germination_rate = data.get('germination_rate')
            test_date = data.get('test_date')
            notes = data.get('notes', '')
            
            lot = Lot.objects.get(pk=lot_id)
            
            # Find the most recent germination record
            # most_recent_germ = lot.germinations.order_by('-test_date').first()
            germ_record = lot.get_germ_record_with_no_test_date()
            
            # print(f"{most_recent_germ.lot.variety.sku_prefix}-{most_recent_germ.lot.grower}{most_recent_germ.lot.year} for 20{most_recent_germ.for_year} if most_recent_germ else 'No germination record'")
            if not germ_record:
                print("DEBUG: No empty germination record found to update")
                germ_record = lot.get_most_recent_germination()
            
            # Update the germination record
            germ_record.germination_rate = germination_rate
            germ_record.test_date = test_date if test_date else date_class.today()
            if notes:
                germ_record.notes = notes
            germ_record.save()
            
            return JsonResponse({'success': True})
        except Lot.DoesNotExist:
            return JsonResponse({'error': 'Lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@user_passes_test(is_employee)
def change_lot_status(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lot_id = data.get('lot_id')
            new_status = data.get('status')
            
            if not lot_id or not new_status:
                return JsonResponse({'error': 'Missing lot_id or status'}, status=400)
                
            if new_status not in ['pending', 'active']:
                return JsonResponse({'error': 'Invalid status. Must be pending or active'}, status=400)
            
            # Get the lot
            lot = Lot.objects.get(pk=lot_id)
            
            # Get the most recent germination record
            most_recent_germ = lot.get_most_recent_germination()
            
            if not most_recent_germ:
                return JsonResponse({'error': 'No germination records found for this lot'}, status=404)
            
            # Update the status
            most_recent_germ.status = new_status
            most_recent_germ.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Lot status changed to {new_status}'
            })
            
        except Lot.DoesNotExist:
            return JsonResponse({'error': 'Lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)



@login_required
@user_passes_test(is_employee)
def edit_front_labels(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            variety_sku = data.get('variety_sku')
            
            variety = Variety.objects.get(pk=variety_sku)
            
            variety.desc_line1 = data.get('desc_line1', '')
            variety.desc_line2 = data.get('desc_line2', '')
            variety.desc_line3 = data.get('desc_line3', '')
            
            variety.save()
            
            return JsonResponse({'success': True})
        except Variety.DoesNotExist:
            return JsonResponse({'error': 'Variety not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)

@login_required
@user_passes_test(is_employee)
def edit_back_labels(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            variety_sku = data.get('variety_sku')
            
            variety = Variety.objects.get(pk=variety_sku)
            
            variety.back1 = data.get('back1', '')
            variety.back2 = data.get('back2', '')
            variety.back3 = data.get('back3', '')
            variety.back4 = data.get('back4', '')
            variety.back5 = data.get('back5', '')
            variety.back6 = data.get('back6', '')
            variety.back7 = data.get('back7', '')
            
            variety.save()
            
            return JsonResponse({'success': True})
        except Variety.DoesNotExist:
            return JsonResponse({'error': 'Variety not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
@staff_member_required
def admin_dashboard(request):
    context = {
        'pkg_sizes': settings.PKG_SIZES,
        'sku_suffixes': settings.SKU_SUFFIXES,
        'env_types': settings.ENV_TYPES,
        'crops': settings.CROPS,
        'groups': settings.GROUPS,
        'veg_types': settings.VEG_TYPES,
        # 'supergroups': settings.SUPERGROUPS,
        'subtypes': settings.SUBTYPES,
        'categories': settings.CATEGORIES,
        'user_name': request.user.get_full_name() or request.user.username,
    }
    return render(request, 'office/admin_dashboard.html', context)



@login_required
@user_passes_test(is_employee)
def germination_inventory_view(request):
    """Render the germination/inventory page"""
    return render(request, 'office/germination_inventory.html')



@login_required
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def germination_inventory_data(request):
    """API endpoint to get germination and inventory data"""
    
    try:
        # Find the most recent germination year across all lots
        max_germ_year = Germination.objects.aggregate(
            max_year=Max('for_year')
        )['max_year']
        
        # Calculate the 4 germination years to display
        germ_years = []
        for i in range(3, -1, -1):  # 3, 2, 1, 0 (last 4 years)
            year = max_germ_year - i
            if year >= 0:  # Don't go negative
                germ_years.append(f"{year:02d}")  # Format as 2-digit string
        
        # The current year is the most recent (rightmost column)
        current_year = f"{max_germ_year:02d}"

        # Get all lots with related data, EXCLUDING retired lots
        lots = Lot.objects.select_related(
            'variety', 'grower'
        ).prefetch_related(
            'inventory', 'germinations', 'germ_sample_prints'
        ).filter(
            variety__isnull=False
        ).exclude(
            retired_info__isnull=False  # Exclude lots that have a RetiredLot record
        ).annotate(
            # Custom ordering for category: Vegetables=1, Flowers=2, Herbs=3, Others=4
            category_order=Case(
                When(variety__category='Vegetables', then=1),
                When(variety__category='Flowers', then=2),
                When(variety__category='Herbs', then=3),
                default=4,
                output_field=IntegerField()
            )
        ).order_by(
            'category_order',        # Custom category order (Vegetables, Flowers, Herbs)
            'variety__sku_prefix',   # Then by sku_prefix
            'year'                   # Then by lot year
        )
        
        inventory_data = []
        categories = set()
        groups = set()
        veg_types = set()
        
        for lot in lots:
            variety = lot.variety
            
            # Add to filter sets
            if variety.category:
                categories.add(variety.category)
            if variety.group:
                groups.add(variety.group)
            if variety.veg_type:
                veg_types.add(variety.veg_type)
            
            # Get inventory data for this lot
            inventories = lot.inventory.order_by('-inv_date')
            
            current_inventory_weight = None
            current_inventory_date = None
            previous_inventory_weight = None
            previous_inventory_date = None
            inventory_difference = None
            
            if inventories.exists():
                current_inv = inventories.first()
                current_inventory_weight = float(current_inv.weight)
                current_inventory_date = current_inv.inv_date.strftime('%m/%Y')  # Format as MM/YYYY
                
                if inventories.count() > 1:
                    previous_inv = inventories[1]
                    previous_inventory_weight = float(previous_inv.weight)
                    previous_inventory_date = previous_inv.inv_date.strftime('%m/%Y')  # Format as MM/YYYY
                    inventory_difference = current_inventory_weight - previous_inventory_weight
            
            # Get germination data for the display years (existing logic)
            germination_rates = {}
            for year_str in germ_years:
                year_for_lookup = int(year_str)  # Use 2-digit year directly
                
                germ = lot.germinations.filter(for_year=year_for_lookup).first()
                if germ:
                    germination_rates[year_str] = germ.germination_rate
                else:
                    germination_rates[year_str] = None
            
            # Get germination sample prints for this lot
            germ_sample_prints = {}
            for print_record in lot.germ_sample_prints.all():
                year_str = f"{print_record.for_year:02d}"
                if year_str in germ_years:  # Only include years we're displaying
                    germ_sample_prints[year_str] = True
            
            # Get detailed germination records for this lot
            germination_records = {}
            for germ_record in lot.germinations.all():
                year_str = f"{germ_record.for_year:02d}"
                if year_str in germ_years:  # Only include years we're displaying
                    germination_records[year_str] = {
                        'germination_rate': germ_record.germination_rate,
                        'test_date': germ_record.test_date.strftime('%Y-%m-%d') if germ_record.test_date else None,
                        'status': germ_record.status,
                        'notes': germ_record.notes
                    }
            
            # Create lot code
            grower_code = lot.grower.code if lot.grower else 'UNK'
            lot_code = f"{grower_code}{lot.year}"
            
            inventory_data.append({
                'lot_id': lot.id,  # Add lot ID for frontend reference
                'variety_name': variety.var_name,
                'sku_prefix': variety.sku_prefix,
                'category': variety.category,
                'group': variety.group,
                'veg_type': variety.veg_type,
                'species': variety.species,
                'lot_code': lot_code,
                'current_inventory_weight': current_inventory_weight,
                'current_inventory_date': current_inventory_date,
                'previous_inventory_weight': previous_inventory_weight,
                'previous_inventory_date': previous_inventory_date,
                'inventory_difference': inventory_difference,
                'germination_rates': germination_rates,  # Keep existing for backward compatibility
                'germ_sample_prints': germ_sample_prints,  # New: sample print status by year
                'germination_records': germination_records  # New: detailed germination records by year
            })
        
        # Convert sets to sorted lists
        categories = sorted(list(categories))
        groups = sorted(list(groups))
        veg_types = sorted(list(veg_types))
        
        # print(f"Returning {len(inventory_data)} active lot records (retired lots excluded)")
        germ_year = settings.FOR_YEAR
        return JsonResponse({
            'inventory_data': inventory_data,
            'germ_years': germ_years,
            'current_year': current_year,  # New: the most recent germination year
            'categories': categories,
            'groups': groups,
            'veg_types': veg_types,
            'germ_year': germ_year
        })
        
    except Exception as e:
        # print(f"Error in germination_inventory_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
    

@login_required
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def create_germ_sample_print(request):
    """API endpoint to create a germination sample print record"""
    
    try:
        data = json.loads(request.body)
        lot_id = data.get('lot_id')
        germ_year = data.get('germ_year')
        
        if not lot_id or germ_year is None:
            return JsonResponse({'error': 'lot_id and germ_year are required'}, status=400)
        
        # Get the lot
        try:
            lot = Lot.objects.get(id=lot_id)
        except Lot.DoesNotExist:
            return JsonResponse({'error': 'Lot not found'}, status=404)
        
        # Check if a print record already exists for this lot/year combo
        existing_print = GermSamplePrint.objects.filter(
            lot=lot, 
            for_year=germ_year
        ).first()
        
        if existing_print:
            return JsonResponse({
                'success': True,
                'message': 'Print record already exists',
                'existing': True,
                'print_date': existing_print.print_date.strftime('%Y-%m-%d')
            })
        
        # Create new print record
        germ_print = GermSamplePrint.objects.create(
            lot=lot,
            for_year=germ_year
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Germination sample print record created successfully',
            'existing': False,
            'print_id': germ_print.id,
            'print_date': germ_print.print_date.strftime('%Y-%m-%d')
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)



@login_required
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def variety_sales_data(request, sku_prefix):
    """Get sales data for a specific variety from the most recent year"""
    
    try:
        # print(f"Getting sales data for variety: {sku_prefix}")
        
        # Get the variety
        try:
            variety = Variety.objects.get(sku_prefix=sku_prefix)
        except Variety.DoesNotExist:
            return JsonResponse({'error': 'Variety not found'}, status=404)
        
        # Find the most recent year with sales data for this variety
        most_recent_year = Sales.objects.filter(
            product__variety=variety
        ).aggregate(max_year=Max('year'))['max_year']
        
        if not most_recent_year:
            # print(f"No sales data found for variety {sku_prefix}")
            return JsonResponse({'sales_data': [], 'year': None})
        
        # print(f"Most recent sales year for {sku_prefix}: {most_recent_year}")
        
        # Convert 2-digit year to 4-digit for display (25 -> 2025)
        display_year = f"20{most_recent_year:02d}" if most_recent_year < 100 else str(most_recent_year)
        
        # Get sales data for the most recent year, grouped by product AND wholesale status
        sales_data = Sales.objects.filter(
            product__variety=variety,
            year=most_recent_year
        ).values(
            'product__sku_suffix',
            'product__variety__sku_prefix',
            'wholesale'
        ).annotate(
            total_quantity=Sum('quantity')
        ).order_by('product__sku_suffix', 'wholesale')  # Order by product, then wholesale status
        
        # Group and format the data for frontend
        product_groups = {}
        for sale in sales_data:
            base_sku = sale['product__sku_suffix'] or sale['product__variety__sku_prefix']
            sku_suffix = sale['product__sku_suffix']
            
            if base_sku not in product_groups:
                product_groups[base_sku] = {
                    'online': 0,
                    'wholesale': 0,
                    'sku_suffix': sku_suffix
                }
            
            if sale['wholesale']:
                product_groups[base_sku]['wholesale'] = sale['total_quantity']
            else:
                product_groups[base_sku]['online'] = sale['total_quantity']
        
        formatted_sales = []
        
        for base_sku, data in product_groups.items():
            online_qty = data['online']
            wholesale_qty = data['wholesale']
            sku_suffix = data['sku_suffix']
            
            # Determine if this is a packet product (sku_suffix contains "PKT")
            is_packet = sku_suffix and 'PKT' in sku_suffix.upper()
            
            # Only PKT products with sku_suffix need online/wholesale distinction
            if is_packet and sku_suffix:
                # Products with PKT sku_suffix need online/wholesale distinction
                if online_qty > 0:
                    formatted_sales.append({
                        'display_name': f"{base_sku} - online",
                        'quantity': online_qty,
                        'is_packet': True,
                        'is_total': False
                    })
                
                if wholesale_qty > 0:
                    formatted_sales.append({
                        'display_name': f"{base_sku} - wholesale",
                        'quantity': wholesale_qty,
                        'is_packet': True,
                        'is_total': False
                    })
                
                # Add total row if both online and wholesale exist
                if online_qty > 0 and wholesale_qty > 0:
                    formatted_sales.append({
                        'display_name': f"{base_sku} - total",
                        'quantity': online_qty + wholesale_qty,
                        'is_packet': True,
                        'is_total': True
                    })
            else:
                # All other products: no online/wholesale distinction
                total_qty = online_qty + wholesale_qty
                formatted_sales.append({
                    'display_name': base_sku,
                    'quantity': total_qty,
                    'is_packet': bool(sku_suffix and 'PKT' in sku_suffix.upper()),
                    'is_total': False
                })
        
        # Sort: packets first, then bulk, then by quantity descending within each group
        formatted_sales.sort(key=lambda x: (not x['is_packet'], -x['quantity']))
        
        # print(f"Returning {len(formatted_sales)} sales records for {sku_prefix}")
        
        return JsonResponse({
            'sales_data': formatted_sales,
            'year': most_recent_year,
            'display_year': display_year,  # Add 4-digit year for display
            'variety_name': variety.var_name
        })
        
    except Exception as e:
        # print(f"Error getting sales data for {sku_prefix}: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
    





# VIEW FUNCTONS FOR MANAGING WHOLESALE STORE ORDERS
@login_required
@user_passes_test(is_employee)
def process_store_orders(request):
    """
    View for processing wholesale orders
    """
    variety_data = {}
   
    # Build the variety data in the expected format - only wholesale varieties
    varieties = Variety.objects.filter(wholesale=True)
    for variety in varieties:
        variety_data[variety.sku_prefix] = {
            'common_spelling': variety.common_spelling,
            'var_name': variety.var_name,
            'veg_type': variety.veg_type,  # or variety.veg_type if that's the field name
            'category': variety.category 
        }
   
    stores = Store.objects.all()
   
    context = {
        'stores': stores,
        'variety_data': json.dumps(variety_data)  # Convert to JSON string for the template
    }
    return render(request, 'office/store_orders.html', context)


@login_required
@user_passes_test(is_employee)
def view_stores(request):
    """
    View for displaying all store locations and their details
    """
    # fetch all store objects from the database, excluding ones whose name attribute start with "PCC"
    stores = Store.objects.exclude(store_name__startswith="Ballard")
    context = {'stores': stores}
    
    return render(request, 'office/view_stores.html', context)

@login_required
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def update_store(request, store_num):
    print(f"Updating store with number: {store_num}")
    try:
        # Get the store object
        store = get_object_or_404(Store, store_num=store_num)
        
        # Parse the JSON data from the request
        data = json.loads(request.body)
        
        # Update the store fields
        if 'name' in data:
            store.store_name = data['name']
        if 'email' in data:
            store.store_email = data['email']
        if 'slots' in data:
            store.slots = int(data['slots']) if data['slots'] else None
        if 'contact_name' in data:
            store.store_contact_name = data['contact_name']

        # Save the changes to the database
        store.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Store updated successfully'
        })
        
    except Exception as e:
        # Log the error for debugging
        print(f"Error in update_store: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    


@login_required
@user_passes_test(is_employee)
@login_required
def get_store_orders(request, store_id):
    try:
        orders = StoreOrder.objects.filter(store__store_num=store_id).order_by('-date')
        
        formatted_orders = []
        for order in orders:
            formatted_orders.append({
                'id': order.id,
                'order_number': order.order_number,
                'date': order.date.strftime('%Y-%m-%d') if order.date else 'No date',
                'is_pending': order.fulfilled_date is None  # Add this line
            })
        
        return JsonResponse({'orders': formatted_orders})
        
    except Exception as e:
        print(f"ERROR in get_store_orders: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    

@login_required
@user_passes_test(is_employee)
def get_pending_orders(request):
    try:
        # Get orders where fulfilled_date is None
        pending_orders = StoreOrder.objects.filter(
            fulfilled_date__isnull=True
        ).select_related('store').order_by('-date')

        formatted_orders = []
        for order in pending_orders:
            formatted_orders.append({
                'id': order.id,
                'order_number': order.order_number,
                'store_name': order.store.store_name,
                'date': order.date.strftime('%Y-%m-%d') if order.date else 'No date'
            })
        
        return JsonResponse({'orders': formatted_orders})
        
    except Exception as e:
        print(f"ERROR in get_pending_orders: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    

@login_required
@user_passes_test(is_employee)
def get_order_details(request, order_id):
    try:
        # Get the order and its items
        order = StoreOrder.objects.get(id=order_id)
        order_items = SOIncludes.objects.filter(store_order=order).select_related('product', 'product__variety')
       
        # Format the items for the frontend
        formatted_items = []
        for item in order_items:
            # Access variety data through the product relationship
            variety = item.product.variety
            print(f"DEBUG: item.product = {item.product}, variety = {variety}")
            if variety:  # Make sure variety exists
                formatted_items.append({
                    'sku_prefix': variety.sku_prefix,
                    'var_name': variety.var_name,
                    'veg_type': variety.veg_type,
                    'quantity': item.quantity,
                    'category': variety.category,
                    'has_photo': item.photo  # Use the stored preference
                })
       
        return JsonResponse({
            'order': {  # Add the order object
                'id': order.id,
                'order_number': order.order_number,
                'fulfilled_date': order.fulfilled_date.strftime('%Y-%m-%d %H:%M:%S') if order.fulfilled_date else None
            },
            'items': formatted_items
        })
       
    except StoreOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        print(f"ERROR in get_order_details: {e}")
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@user_passes_test(is_employee)
def save_order_changes(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        items = data.get('items', [])
        
        # Get the order
        order = StoreOrder.objects.get(id=order_id)
        
        # Clear existing SOIncludes for this order
        SOIncludes.objects.filter(store_order=order).delete()
        pkt_price = settings.PACKET_PRICE
        # Add new items
        for item_data in items:
            # Find the product based on variety with sku_suffix="pkt"
            variety = Variety.objects.get(sku_prefix=item_data['sku_prefix'])
            product = Product.objects.filter(variety=variety, sku_suffix="pkt").first()
            
            if product:
                SOIncludes.objects.create(
                    store_order=order,
                    product=product,
                    quantity=item_data['quantity'],
                    price=pkt_price,  # You'll need to set appropriate price logic
                    photo=item_data.get('has_photo', False)
                )
            else:
                # Log or handle case where no "pkt" product exists for this variety
                print(f"Warning: No 'pkt' product found for variety {variety.sku_prefix}")
        
        return JsonResponse({'success': True, 'message': f'Order updated with {len(items)} items'})
        
    except StoreOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Variety.DoesNotExist:
        return JsonResponse({'error': 'Variety not found'}, status=404)
    except Exception as e:
        print(f"ERROR in save_order_changes: {e}")
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def finalize_order(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        items = data.get('items', [])
        
        # Get the order
        order = StoreOrder.objects.get(id=order_id)
        
        # Set fulfilled_date to current timezone-aware datetime
        from django.utils import timezone
        order.fulfilled_date = timezone.now()
        order.save()
        pkt_price = settings.PACKET_PRICE   
        # Validate all products exist first (safer approach)
        new_so_includes = []
        for item in items:
            try:
                # Get Variety by sku_prefix
                variety = Variety.objects.get(sku_prefix=item['sku_prefix'])
                
                # Find the associated Product with sku_suffix == "pkt"
                # Adjust the relationship field name as needed (e.g., variety__sku_prefix or however they're connected)
                product = Product.objects.get(
                    variety=variety,  # Adjust this field name based on your Product model
                    sku_suffix="pkt"
                )
                
                new_so_includes.append({
                    'product': product,
                    'variety': variety,  # Keep variety reference for response
                    'quantity': item['quantity'],
                    'photo': item.get('has_photo', False),
                    'price': pkt_price  # Set price here if needed
                })
                
            except Variety.DoesNotExist:
                return JsonResponse({'error': f'Variety with sku_prefix {item["sku_prefix"]} not found'}, status=400)
            except Product.DoesNotExist:
                return JsonResponse({'error': f'Packet product not found for variety {item["sku_prefix"]}'}, status=400)
        
        # Only delete existing ones after validating all new ones can be created
        SOIncludes.objects.filter(store_order=order).delete()
        
        # Create new SOIncludes
        for include_data in new_so_includes:
            SOIncludes.objects.create(
                store_order=order,
                product=include_data['product'],
                quantity=include_data['quantity'],
                price=pkt_price,
                photo=include_data['photo']
            )
        
        # Get store and return response
        store = order.store
        so_includes = SOIncludes.objects.filter(store_order=order).select_related('product', 'product__variety')
        
        return JsonResponse({
            'success': True,
            'order': {
                'id': order.id,
                'order_number': order.order_number,
                'fulfilled_date': order.fulfilled_date.strftime('%Y-%m-%d %H:%M:%S')
            },
            'store': {
                'name': store.store_name,
            },
            'items': [
                {
                    'sku_prefix': include.product.variety.sku_prefix,
                    'var_name': include.product.variety.var_name,
                    'quantity': include.quantity,
                    'has_photo': include.photo
                }
                for include in so_includes
            ]
        })
        
    except Exception as e:
        print(f"Error in finalize_order: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    

@login_required
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def add_variety(request):
    """Create a new variety via AJAX"""
    try:
        # Extract form data
        data = {
            'sku_prefix': request.POST.get('sku_prefix', '').strip(),
            'var_name': request.POST.get('var_name', '').strip() or None,
            'crop': request.POST.get('crop', '').strip() or None,
            'common_spelling': request.POST.get('common_spelling', '').strip() or None,
            'common_name': request.POST.get('common_name', '').strip() or None,
            'group': request.POST.get('group', '').strip() or None,
            'veg_type': request.POST.get('veg_type', '').strip() or None,
            'species': request.POST.get('species', '').strip() or None,
            'subtype': request.POST.get('subtype', '').strip() or None,
            'days': request.POST.get('days', '').strip() or None,
            'active': request.POST.get('active') == 'true',
            'stock_qty': request.POST.get('stock_qty', '').strip() or None,
            'photo_path': request.POST.get('photo_path', '').strip() or None,
            'wholesale': request.POST.get('wholesale') == 'true',
            'desc_line1': request.POST.get('desc_line1', '').strip() or None,
            'desc_line2': request.POST.get('desc_line2', '').strip() or None,
            'desc_line3': request.POST.get('desc_line3', '').strip() or None,
            'back1': request.POST.get('back1', '').strip() or None,
            'back2': request.POST.get('back2', '').strip() or None,
            'back3': request.POST.get('back3', '').strip() or None,
            'back4': request.POST.get('back4', '').strip() or None,
            'back5': request.POST.get('back5', '').strip() or None,
            'back6': request.POST.get('back6', '').strip() or None,
            'back7': request.POST.get('back7', '').strip() or None,
            'ws_notes': request.POST.get('ws_notes', '').strip() or None,
            'ws_description': request.POST.get('ws_description', '').strip() or None,
            'category': request.POST.get('category', '').strip() or None,
        }

        # Validate required fields
        if not data['sku_prefix']:
            return JsonResponse({
                'success': False,
                'errors': {'sku_prefix': ['SKU Prefix is required']}
            }, status=400)

        # Check if SKU prefix already exists
        if Variety.objects.filter(sku_prefix=data['sku_prefix']).exists():
            return JsonResponse({
                'success': False,
                'errors': {'sku_prefix': ['A variety with this SKU Prefix already exists']}
            }, status=400)

        # Create the variety
        variety = Variety.objects.create(**data)

        return JsonResponse({
            'success': True,
            'message': 'Variety created successfully',
            'variety': {
                'sku_prefix': variety.sku_prefix,
                'var_name': variety.var_name or '',
                'id': variety.sku_prefix  # Since sku_prefix is the primary key
            }
        })
    
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'errors': {'__all__': [str(e)]}
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def add_product(request):
    """Create a new product via AJAX"""
    try:
        # Get the variety
        variety_id = request.POST.get('variety_id', '').strip()
        if not variety_id:
            return JsonResponse({
                'success': False,
                'errors': {'variety': ['Variety is required']}
            }, status=400)

        try:
            variety = Variety.objects.get(sku_prefix=variety_id)
        except Variety.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'variety': ['Variety not found']}
            }, status=400)

        # Extract form data
        data = {
            'variety': variety,
            'sku_suffix': request.POST.get('sku_suffix', '').strip() or None,
            'pkg_size': request.POST.get('pkg_size', '').strip() or None,
            'alt_sku': request.POST.get('alt_sku', '').strip() or None,
            'lineitem_name': request.POST.get('lineitem_name', '').strip() or None,
            'rack_location': request.POST.get('rack_location', '').strip() or None,
            'env_type': request.POST.get('env_type', '').strip() or None,
            'env_multiplier': None,
            # 'label': request.POST.get('label', '').strip() or None,
            # 'num_printed': None,
            # 'num_printed_next_year': 0,
            'scoop_size': request.POST.get('scoop_size', '').strip() or None,
            'print_back': request.POST.get('print_back') == 'true',
            # 'bulk_pre_pack': 0,
            'is_sub_product': request.POST.get('is_sub_product') == 'true',
        }

        # Handle integer fields
        try:
            env_multiplier = request.POST.get('env_multiplier', '').strip()
            if env_multiplier:
                data['env_multiplier'] = int(env_multiplier)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'errors': {'env_multiplier': ['Enter a valid number']}
            }, status=400)

        # try:
        #     num_printed = request.POST.get('num_printed', '').strip()
        #     if num_printed:
        #         data['num_printed'] = int(num_printed)
        # except (ValueError, TypeError):
        #     return JsonResponse({
        #         'success': False,
        #         'errors': {'num_printed': ['Enter a valid number']}
        #     }, status=400)

        # try:
        #     num_printed_next_year = request.POST.get('num_printed_next_year', '0').strip()
        #     if num_printed_next_year:
        #         data['num_printed_next_year'] = int(num_printed_next_year)
        # except (ValueError, TypeError):
        #     return JsonResponse({
        #         'success': False,
        #         'errors': {'num_printed_next_year': ['Enter a valid number']}
        #     }, status=400)

        # try:
        #     bulk_pre_pack = request.POST.get('bulk_pre_pack', '0').strip()
        #     if bulk_pre_pack:
        #         data['bulk_pre_pack'] = int(bulk_pre_pack)
        # except (ValueError, TypeError):
        #     return JsonResponse({
        #         'success': False,
        #         'errors': {'bulk_pre_pack': ['Enter a valid number']}
        #     }, status=400)

        # Validate required fields
        if not data['sku_suffix']:
            return JsonResponse({
                'success': False,
                'errors': {'sku_suffix': ['SKU Suffix is required']}
            }, status=400)

        # Validate label length (max 1 character)
        # if data['label'] and len(data['label']) > 1:
        #     return JsonResponse({
        #         'success': False,
        #         'errors': {'label': ['Label must be 1 character or less']}
        #     }, status=400)

        # Create the product
        product = Product.objects.create(**data)

        return JsonResponse({
            'success': True,
            'message': 'Product created successfully',
            'product': {
                'id': product.id,
                'variety': variety.sku_prefix,
                'sku_suffix': product.sku_suffix
            }
        })

    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'errors': {'__all__': [str(e)]}
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)
    

@login_required
@user_passes_test(is_employee)
def get_lot_history(request):
    """Get comprehensive history for a lot"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'})
    
    try:
        data = json.loads(request.body)
        lot_id = data.get('lot_id')
        
        if not lot_id:
            return JsonResponse({'success': False, 'error': 'Lot ID required'})
        
        # Get the lot with all related data
        lot = Lot.objects.select_related('variety', 'grower', 'retired_info').get(pk=lot_id)
        
        # Build response data
        history_data = {
            'variety_name': lot.variety.var_name,
            'sku_display': f"{lot.variety.sku_prefix}-{lot.grower.code if lot.grower else 'UNK'}{lot.year}{lot.harvest or ''}",
            'low_inventory': lot.low_inv,
            'is_retired': hasattr(lot, 'retired_info'),
            'retired_info': None,
            'stock_seeds': [],
            'inventory_records': [],
            'germination_records': [],
            'packing_history': [],
            'notes': []
        }
        
        # Retired information
        if hasattr(lot, 'retired_info'):
            retired = lot.retired_info
            history_data['retired_info'] = {
                'date': retired.retired_date.strftime('%Y-%m-%d'),
                'lbs_remaining': float(retired.lbs_remaining),
                'notes': retired.notes or ''
            }
        
        # Stock seed records
        stock_seeds = lot.stock_seeds.all().order_by('-date')
        for stock_seed in stock_seeds:
            history_data['stock_seeds'].append({
                'date': stock_seed.date.strftime('%Y-%m-%d'),
                'qty': stock_seed.qty,
                'notes': stock_seed.notes or ''
            })
        
        # Inventory records
        inventory_records = lot.inventory.all().order_by('-inv_date')
        for inv in inventory_records:
            history_data['inventory_records'].append({
                'date': inv.inv_date.strftime('%Y-%m-%d'),
                'weight': float(inv.weight)
            })
        
        # Germination records
        germination_records = lot.germinations.all().order_by('-test_date')
        for germ in germination_records:
            history_data['germination_records'].append({
                'test_date': germ.test_date.strftime('%Y-%m-%d') if germ.test_date else '',
                'germination_rate': germ.germination_rate,
                'for_year': germ.for_year,
                'status': germ.status,
                'notes': germ.notes or ''
            })
        
        # Packing history (Label prints)
        label_prints = lot.label_prints.select_related('product').all().order_by('-date')
        for print_record in label_prints:
            history_data['packing_history'].append({
                'date': print_record.date.strftime('%Y-%m-%d'),
                'qty': print_record.qty,
                'for_year': print_record.for_year,
                'product_sku': print_record.product.sku_suffix if print_record.product.sku_suffix else '--'
            })
        
        # General notes
        notes = lot.notes.all().order_by('-date')
        for note in notes:
            history_data['notes'].append({
                'date': note.date.strftime('%Y-%m-%d %H:%M'),
                'note': note.note
            })
        
        return JsonResponse({'success': True, 'data': history_data})
        
    except Lot.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Lot not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



# def get_lot_history(request):
    # """Get comprehensive history for a lot"""
    # if request.method != 'POST':
    #     return JsonResponse({'success': False, 'error': 'POST method required'})
    
    # try:
    #     data = json.loads(request.body)
    #     lot_id = data.get('lot_id')
        
    #     if not lot_id:
    #         return JsonResponse({'success': False, 'error': 'Lot ID required'})
        
    #     # Get the lot with all related data
    #     lot = Lot.objects.select_related('variety', 'grower', 'retired_info').get(pk=lot_id)
        
    #     # Build response data
    #     history_data = {
    #         'variety_name': lot.variety.var_name,
    #         'sku_display': f"{lot.variety.sku_prefix}-{lot.grower.code if lot.grower else 'UNK'}{lot.year}{lot.harvest or ''}",
    #         'low_inventory': lot.low_inv,
    #         'is_retired': hasattr(lot, 'retired_info'),
    #         'retired_info': None,
    #         'stock_seeds': [],
    #         'inventory_records': [],
    #         'germination_records': [],
    #         'notes': []
    #     }
        
    #     # Retired information
    #     if hasattr(lot, 'retired_info'):
    #         retired = lot.retired_info
    #         history_data['retired_info'] = {
    #             'date': retired.retired_date.strftime('%Y-%m-%d'),
    #             'lbs_remaining': float(retired.lbs_remaining),
    #             'notes': retired.notes or ''
    #         }
        
    #     # Stock seed records
    #     stock_seeds = lot.stock_seeds.all().order_by('-date')
    #     for stock_seed in stock_seeds:
    #         history_data['stock_seeds'].append({
    #             'date': stock_seed.date.strftime('%Y-%m-%d'),
    #             'qty': stock_seed.qty,
    #             'notes': stock_seed.notes or ''
    #         })
        
    #     # Inventory records
    #     inventory_records = lot.inventory.all().order_by('-inv_date')
    #     for inv in inventory_records:
    #         history_data['inventory_records'].append({
    #             'date': inv.inv_date.strftime('%Y-%m-%d'),
    #             'weight': float(inv.weight)
    #         })
        
    #     # Germination records
    #     germination_records = lot.germinations.all().order_by('-test_date')
    #     for germ in germination_records:
    #         history_data['germination_records'].append({
    #             'test_date': germ.test_date.strftime('%Y-%m-%d') if germ.test_date else '',
    #             'germination_rate': germ.germination_rate,
    #             'for_year': germ.for_year,
    #             'status': germ.status,
    #             'notes': germ.notes or ''
    #         })
        
    #     # General notes
    #     notes = lot.notes.all().order_by('-date')
    #     for note in notes:
    #         history_data['notes'].append({
    #             'date': note.date.strftime('%Y-%m-%d %H:%M'),
    #             'note': note.note
    #         })
        
    #     return JsonResponse({'success': True, 'data': history_data})
        
    # except Lot.DoesNotExist:
    #     return JsonResponse({'success': False, 'error': 'Lot not found'})
    # except Exception as e:
    #     return JsonResponse({'success': False, 'error': str(e)})
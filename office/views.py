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
from lots.models import Grower, Lot, RetiredLot, StockSeed, Germination
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Case, When, IntegerField, Max, Sum
from uprising.utils.auth import is_employee
from uprising import settings
from django.views.decorators.http import require_http_methods


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
                LastSelected.objects.update(user=user, variety=variety_obj)
                return redirect('view_variety')
    #     # For all other actions, determine the current variety context
    #     else:
    #         # Try to get variety from various sources depending on the action
    #         current_variety_pk = None
            
    #         if action == 'print_product':
    #             # Get variety from the product being printed
    #             product_id = request.POST.get('product_id')
    #             if product_id:
    #                 try:
    #                     product = Product.objects.get(pk=product_id)
    #                     current_variety_pk = product.variety.sku_prefix
    #                 except Product.DoesNotExist:
    #                     pass
            
    #         elif action in ['edit_product', 'add_product']:
    #             # Get variety from product context or form data
    #             current_variety_pk = request.POST.get('variety_sku') or request.POST.get('current_variety')
            
    #         elif action in ['edit_lot', 'add_lot']:
    #             # Get variety from lot context or form data
    #             lot_id = request.POST.get('lot_id')
    #             if lot_id and action == 'edit_lot':
    #                 try:
    #                     lot = Lot.objects.get(pk=lot_id)
    #                     current_variety_pk = lot.variety.sku_prefix
    #                 except Lot.DoesNotExist:
    #                     pass
    #             else:
    #                 current_variety_pk = request.POST.get('variety_sku') or request.POST.get('current_variety')
            
    #         elif action in ['edit_variety', 'edit_label']:
    #             # Get variety from form data
    #             current_variety_pk = request.POST.get('variety_sku') or request.POST.get('current_variety')
            
    #         # Set the variety object based on what we found
    #         if current_variety_pk:
    #             try:
    #                 variety_obj = Variety.objects.get(pk=current_variety_pk)
    #             except Variety.DoesNotExist:
    #                 variety_obj = last_selected_variety
    #         else:
    #             variety_obj = last_selected_variety

    #         # Handle the specific actions
    #         if action == 'print_product':
    #             if request.user.username not in ["office", "admin"]:
    #                 # Block printing for anyone except "office"
    #                 print(f"User {request.user.username} attempted to print but is not allowed.")
    #                 messages.error(request, "You are not allowed to print labels.")
    #             else:
    #                 product_id = request.POST.get('product_id')
    #                 print_type = request.POST.get('print_type')
    #                 quantity = request.POST.get('quantity')

    #                 try:
    #                     product = Product.objects.get(pk=product_id)
    #                     print(f"Printing {quantity} {print_type} labels for product: {product.variety_id}")
    #                     # Add your actual printing logic here
    #                     # Example: send_to_printer(product, print_type, quantity)
    #                     # log print job in db

    #                     messages.success(request, f"Printing {quantity} {print_type} labels for {product.variety}.")

    #                 except Product.DoesNotExist:
    #                     print(f"Product {product_id} not found")
    #                     messages.error(request, f"Product {product_id} not found.")

            # elif action == 'edit_label':
            #     # Handle label editing
            #     variety_pk = request.POST.get('variety_sku') or request.POST.get('current_variety')
            #     if variety_pk:
            #         try:
            #             variety_to_edit = Variety.objects.get(pk=variety_pk)
            #             # Update label fields
            #             variety_to_edit.desc_line1 = request.POST.get('desc_line1', '')
            #             variety_to_edit.desc_line2 = request.POST.get('desc_line2', '')
            #             variety_to_edit.desc_line3 = request.POST.get('desc_line3', '')
            #             variety_to_edit.back1 = request.POST.get('back1', '')
            #             variety_to_edit.back2 = request.POST.get('back2', '')
            #             variety_to_edit.back3 = request.POST.get('back3', '')
            #             variety_to_edit.back4 = request.POST.get('back4', '')
            #             variety_to_edit.back5 = request.POST.get('back5', '')
            #             variety_to_edit.back6 = request.POST.get('back6', '')
            #             variety_to_edit.back7 = request.POST.get('back7', '')
            #             variety_to_edit.days = request.POST.get('days', '')
            #             variety_to_edit.save()
            #             print(f"Updated labels for variety: {variety_to_edit.var_name}")
            #             variety_obj = variety_to_edit  # Update the current variety object
            #         except Variety.DoesNotExist:
            #             print(f"Variety {variety_pk} not found for label editing")
            
            # elif action == 'add_product':
            #     # Handle adding new product
            #     variety_pk = request.POST.get('variety_sku') or request.POST.get('current_variety')
            #     if variety_pk:
            #         try:
            #             target_variety = Variety.objects.get(pk=variety_pk)
            #             new_product = Product.objects.create(
            #                 variety=target_variety,
            #                 pkg_size=request.POST.get('pkg_size', ''),
            #                 sku_suffix=request.POST.get('sku_suffix', ''),
            #                 # lineitem_name=request.POST.get('lineitem_name', ''),
            #                 rack_location=request.POST.get('rack_location', ''),
            #                 label=request.POST.get('label', ''),
            #                 print_back=request.POST.get('print_back') == 'on'
            #             )
            #             # print(f"Added new product: {new_product.lineitem_name}")
            #         except Variety.DoesNotExist:
            #             print(f"Variety {variety_pk} not found for adding product")

            
            # elif action == 'edit_product':
            #     # Handle editing existing product
            #     product_id = request.POST.get('product_id')
            #     if product_id:
            #         try:
            #             product = Product.objects.get(pk=product_id)
            #             product.pkg_size = request.POST.get('pkg_size', product.pkg_size)
            #             product.sku_suffix = request.POST.get('sku_suffix', product.sku_suffix)
            #             # product.lineitem_name = request.POST.get('lineitem_name', product.lineitem_name)
            #             product.rack_location = request.POST.get('rack_location', product.rack_location)
            #             product.label = request.POST.get('label', product.label)
            #             product.print_back = request.POST.get('print_back') == 'on'
            #             product.save()
            #             # print(f"Updated product: {product.lineitem_name}")
            #             variety_obj = product.variety  # Ensure we stay with this variety
            #         except Product.DoesNotExist:
            #             print(f"Product {product_id} not found")
            
            # elif action == 'edit_lot':
            #     # Handle editing existing lot
            #     lot_id = request.POST.get('lot_id')
            #     if lot_id:
            #         try:
            #             lot = Lot.objects.get(pk=lot_id)
            #             lot.grower = request.POST.get('grower', lot.grower)
            #             lot.year = request.POST.get('year', lot.year)
            #             lot.harvest = request.POST.get('harvest', lot.harvest)
            #             lot.external_lot_id = request.POST.get('external_lot_id', lot.external_lot_id)
            #             lot.low_inv = request.POST.get('low_inv') == 'on'
            #             lot.save()
            #             print(f"Updated lot: {lot.external_lot_id}")
            #             variety_obj = lot.variety  # Ensure we stay with this variety
            #         except Lot.DoesNotExist:
            #             print(f"Lot {lot_id} not found")
            
            # elif action == 'edit_variety':
            #     # Handle editing variety information
            #     variety_pk = request.POST.get('variety_sku') or request.POST.get('current_variety')
            #     if variety_pk:
            #         try:
            #             variety_to_edit = Variety.objects.get(pk=variety_pk)
            #             variety_to_edit.var_name = request.POST.get('var_name', variety_to_edit.var_name)
            #             variety_to_edit.veg_type = request.POST.get('veg_type', variety_to_edit.veg_type)
            #             variety_to_edit.common_spelling = request.POST.get('common_spelling', variety_to_edit.common_spelling)
            #             # Add other variety fields as needed
            #             variety_to_edit.save()
            #             print(f"Updated variety: {variety_to_edit.var_name}")
            #             variety_obj = variety_to_edit
            #         except Variety.DoesNotExist:
            #             print(f"Variety {variety_pk} not found for editing")
    

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


# @login_required
# @user_passes_test(is_employee)
# def analytics(request):
#     """
#     View for displaying analytics and business performance metrics
#     """
#     context = {
#         'page_title': 'Analytics Dashboard',
#         # Add any data you want to pass to the template
#         # For example:
#         # 'sales_data': get_sales_data(),
#         # 'inventory_metrics': get_inventory_metrics(),
#         # 'popular_products': get_popular_products(),
#     }
    
#     # Render the template from the products app
#     return render(request, 'products/analytics.html', context)


@login_required
@user_passes_test(is_employee)
def analytics(request):
    """
    View for displaying analytics and business performance metrics
    """
    # Get envelope count data for the most recent sales year
    envelope_data = get_envelope_count_data()
    
    # print(f"DEBUG VIEW: envelope_data = {envelope_data}")
    # print(f"DEBUG VIEW: envelope_counts = {envelope_data['envelope_counts']}")
    # print(f"DEBUG VIEW: total = {envelope_data['total']}")
    
    # Ensure we serialize the JSON properly
    envelope_json = json.dumps(envelope_data['envelope_counts'])
    print(f"DEBUG VIEW: envelope_json = {envelope_json}")
    
    context = {
        'page_title': 'Analytics Dashboard',
        'envelope_data_json': envelope_json,
        'envelope_data': envelope_data['envelope_counts'],  # Keep original for template display
        'envelope_total': envelope_data['total'],
        'last_sales_year': envelope_data['year'],
        # Add any other data you want to pass to the template
        # For example:
        # 'sales_data': get_sales_data(),
        # 'inventory_metrics': get_inventory_metrics(),
        # 'popular_products': get_popular_products(),
    }
    
    print(f"DEBUG VIEW: final context envelope_data_json = {context['envelope_data_json']}")
   
    return render(request, 'products/analytics.html', context)

def get_envelope_count_data():
    """
    Calculate envelope usage for the most recent sales year
    """
    # Find the most recent sales year
    latest_year = Sales.objects.aggregate(max_year=Max('year'))['max_year']
    print(f"DEBUG: Latest sales year: {latest_year}")
    
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
        # print(f"DEBUG: Added {quantity} to envelope type '{envelope_type}'")
    
    # print(f"DEBUG: Products WITH env_type: {products_with_env_type}")
    # print(f"DEBUG: Products WITHOUT env_type: {products_without_env_type}")
    # print(f"DEBUG: Final envelope_counts: {envelope_counts}")
    # print(f"DEBUG: Total envelopes: {total_envelopes}")
    
    # Sort envelope counts by quantity (descending)
    envelope_counts = dict(sorted(envelope_counts.items(), key=lambda x: x[1], reverse=True))
    
    return {
        'envelope_counts': envelope_counts,
        'total': total_envelopes,
        'year': latest_year
    }

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
            
            lot = Lot.objects.get(pk=lot_id)
            
            if hasattr(lot, 'retired_info'):
                return JsonResponse({'error': 'This lot is already retired'}, status=400)
            
            # Create the RetiredLot entry
            RetiredLot.objects.create(
                lot=lot,
                lbs_remaining=lbs_remaining,
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
            most_recent_germ = lot.germinations.order_by('-test_date').first()
            
            if not most_recent_germ:
                return JsonResponse({'error': 'No germination record found for this lot'}, status=404)
            
            # Update the germination record
            most_recent_germ.germination_rate = germination_rate
            most_recent_germ.test_date = test_date if test_date else date_class.today()
            if notes:
                most_recent_germ.notes = notes
            most_recent_germ.save()
            
            return JsonResponse({'success': True})
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
    return render(request, 'office/admin_dashboard.html')



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
        
        if max_germ_year is None:
            max_germ_year = 25  # Default if no germination data
            
        # Calculate the 4 germination years to display
        germ_years = []
        for i in range(3, -1, -1):  # 3, 2, 1, 0 (last 4 years)
            year = max_germ_year - i
            if year >= 0:  # Don't go negative
                germ_years.append(f"{year:02d}")  # Format as 2-digit string
        
        # print(f"Max germ year: {max_germ_year}, Displaying years: {germ_years}")
        
        # Get all lots with related data, EXCLUDING retired lots
        lots = Lot.objects.select_related(
            'variety', 'grower'
        ).prefetch_related(
            'inventory', 'germinations'
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
            
            # Get germination data for the display years
            germination_rates = {}
            for year_str in germ_years:
                year_for_lookup = int(year_str)  # Use 2-digit year directly
                
                germ = lot.germinations.filter(for_year=year_for_lookup).first()
                if germ:
                    germination_rates[year_str] = germ.germination_rate
                else:
                    germination_rates[year_str] = None
            
            # Create lot code
            grower_code = lot.grower.code if lot.grower else 'UNK'
            lot_code = f"{grower_code}{lot.year}"
            
            inventory_data.append({
                'variety_name': variety.var_name,
                'sku_prefix': variety.sku_prefix,
                'category': variety.category,
                'group': variety.group,
                'veg_type': variety.veg_type,
                'lot_code': lot_code,
                'current_inventory_weight': current_inventory_weight,
                'current_inventory_date': current_inventory_date,
                'previous_inventory_weight': previous_inventory_weight,
                'previous_inventory_date': previous_inventory_date,
                'inventory_difference': inventory_difference,
                'germination_rates': germination_rates
            })
        
        # Convert sets to sorted lists
        categories = sorted(list(categories))
        groups = sorted(list(groups))
        veg_types = sorted(list(veg_types))
        
        # print(f"Returning {len(inventory_data)} active lot records (retired lots excluded)")
        
        return JsonResponse({
            'inventory_data': inventory_data,
            'germ_years': germ_years,
            'categories': categories,
            'groups': groups,
            'veg_types': veg_types
        })
        
    except Exception as e:
        # print(f"Error in germination_inventory_data: {str(e)}")
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




# def get_order_details(request, order_id):
#     try:
#         # Get the order and its items
#         order = StoreOrder.objects.get(id=order_id)
#         order_items = SOIncludes.objects.filter(store_order=order).select_related('product', 'product__variety')
        
#         # Format the items for the frontend
#         formatted_items = []
#         for item in order_items:
#             # Access variety data through the product relationship
#             variety = item.product.variety
#             print(f"DEBUG: item.product = {item.product}, variety = {variety}")
#             if variety:  # Make sure variety exists
#                 formatted_items.append({
#                     'sku_prefix': variety.sku_prefix,
#                     'var_name': variety.var_name,
#                     'veg_type': variety.veg_type,
#                     'quantity': item.quantity,
#                     'category': variety.category,
#                     'has_photo': item.photo  # Use the stored preference
#                 })
        
#         return JsonResponse({
#             'order_number': order.order_number,
#             'items': formatted_items
#         })
        
#     except StoreOrder.DoesNotExist:
#         return JsonResponse({'error': 'Order not found'}, status=404)
#     except Exception as e:
#         print(f"ERROR in get_order_details: {e}")
#         return JsonResponse({'error': str(e)}, status=400)


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
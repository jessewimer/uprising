import json
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.http import JsonResponse
from django.contrib.auth import login
from products.models import Variety, Product, LastSelected, LabelPrint
from lots.models import Grower, Lot, RetiredLot, StockSeed 
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Case, When, IntegerField
from uprising.utils.auth import is_employee
from uprising import settings
from django.views.decorators.http import require_http_methods


from django.db.models import Max
from django.views.decorators.http import require_http_methods
from lots.models import Lot, Inventory, Germination


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


# @login_required
# @user_passes_test(is_employee)
# def inventory_germination(request):
#     """
#     Inventory and germination tracking view
#     """
#     return render(request, 'office/inventory_germination.html')


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


@login_required
@user_passes_test(is_employee)
def analytics(request):
    """
    View for displaying analytics and business performance metrics
    """
    context = {
        'page_title': 'Analytics Dashboard',
        # Add any data you want to pass to the template
        # For example:
        # 'sales_data': get_sales_data(),
        # 'inventory_metrics': get_inventory_metrics(),
        # 'popular_products': get_popular_products(),
    }
    
    # Render the template from the products app
    return render(request, 'products/analytics.html', context)


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
        
        print(f"Max germ year: {max_germ_year}, Displaying years: {germ_years}")
        
        # Get all lots with related data, EXCLUDING retired lots
        lots = Lot.objects.select_related(
            'variety', 'grower'
        ).prefetch_related(
            'inventory', 'germinations'
        ).filter(
            variety__isnull=False
        ).exclude(
            retired_info__isnull=False  # Exclude lots that have a RetiredLot record
        ).order_by(
            'variety__supergroup', 
            'variety__group', 
            'variety__sku_prefix', 
            'year'
        )
        
        inventory_data = []
        supergroups = set()
        groups = set()
        
        for lot in lots:
            variety = lot.variety
            
            # Add to filter sets
            if variety.supergroup:
                supergroups.add(variety.supergroup)
            if variety.group:
                groups.add(variety.group)
            
            # Get inventory data for this lot
            inventories = lot.inventory.order_by('-inv_date')
            
            current_inventory = None
            previous_inventory = None
            inventory_difference = None
            
            if inventories.exists():
                current_inventory = float(inventories.first().weight)
                if inventories.count() > 1:
                    previous_inventory = float(inventories[1].weight)
                    inventory_difference = current_inventory - previous_inventory
            
            # Get germination data for the display years
            germination_rates = {}
            for year_str in germ_years:
                year_int = int(year_str)  # Convert back to 4-digit year for database lookup
                
                germ = lot.germinations.filter(for_year=year_int).first()
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
                'supergroup': variety.supergroup,
                'group': variety.group,
                'lot_code': lot_code,
                'current_inventory': current_inventory,
                'previous_inventory': previous_inventory,
                'inventory_difference': inventory_difference,
                'germination_rates': germination_rates
            })
        
        # Convert sets to sorted lists
        supergroups = sorted(list(supergroups))
        groups = sorted(list(groups))
        
        print(f"Returning {len(inventory_data)} active lot records (retired lots excluded)")
        print(f"Supergroups: {supergroups}")
        print(f"Groups: {groups}")
        
        return JsonResponse({
            'inventory_data': inventory_data,
            'germ_years': germ_years,
            'supergroups': supergroups,
            'groups': groups
        })
        
    except Exception as e:
        print(f"Error in germination_inventory_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
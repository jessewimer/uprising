import json
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.http import JsonResponse
from django.contrib.auth import login
from products.models import Variety, Product, LastSelected, LabelPrint, Sales, MiscSales, MiscProduct
from stores.models import Store, StoreProduct, StoreOrder, SOIncludes, PickListPrinted, StoreReturns, WholesalePktPrice
from orders.models import OOIncludes, OnlineOrder
from lots.models import Grower, Lot, RetiredLot, StockSeed, Germination, GermSamplePrint, Inventory, MixLot, MixLotComponent, MixBatch, RetiredMixLot
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Case, When, IntegerField, Max, Sum, F, CharField, Value, Q, Prefetch
from django.db.models.functions import Concat
from uprising.utils.auth import is_employee
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import pytz
from decimal import Decimal, InvalidOperation
from stores.models import WholesalePktPrice
import math
import csv
import io
import shopify


BASE_COMPONENT_MIXES = {
    'MIX-LB': {
        'name': 'Lettuce Mix',
        'type': 'base',
        'varieties': ['LET-HR', 'LET-FB', 'LET-GR', 'LET-CI', 'LET-FT', 'LET-AY', 'LET-MA', 'LET-RV', 'LET-EM', 'LET-ME'],
    },
    'MIX-SB': {
        'name': 'Spicy Mix',
        'type': 'base',
        'varieties': ['GRE-AS', 'GRE-TA', 'GRE-RS', 'KAL-RF', 'KAL-RR', 'GRE-WC', 'CHA-RA', 'GRE-GF', 'GRE-MZ']
    },
    'MIX-MB': {
        'name': 'Mild Mix',
        'type': 'base',
        'varieties': ['GRE-AS', 'GRE-TA', 'SPI-BE', 'KAL-RF', 'GRE-MZ', 'CHA-RA'] 
    }
}

mix_prefixes = ['CAR-RA', 'BEE-3B', 'LET-MX', 'MIX-SP', 'MIX-MI', 'MIX-BR', 'FLO-ED']

# Mix configurations
FINAL_MIX_CONFIGS = {
    'CAR-RA': {
        'name': 'Rainbow Carrot Mix',
        'varieties': ['CAR-SN', 'CAR-YE', 'CAR-DR'],
    },
    'BEE-3B': {
        'name': '3 Beet Mix',
        'type': 'regular',
        'varieties': ['BEE-TG', 'BEE-SH', 'BEE-CH'],
    },
    'LET-MX': {
        'name': 'Uprising Lettuce Mix',
        'type': 'regular',
        # 'varieties_prefix': 'LET',
        'varieties': ['LET-AB', 'LET-AD', 'LET-AY', 'LET-BG', 'LET-BI', 'LET-CI', 'LET-CR', 'LET-DV', 'LET-EM', 'LET-ER', 'LET-FB', 'LET-FT', 'LET-GA', 'LET-GR', 'LET-HR', 'LET-IT', 'LET-JE', 'LET-LB', 'LET-LG', 'LET-MA', 'LET-ME', 'LET-MQ', 'LET-OD', 'LET-OS', 'LET-PI', 'LET-QH', 'LET-RG', 'LET-RR', 'LET-RV', 'LET-SB', 'LET-SU', 'LET-TB', 'LET-WD'],
        'varieties_exclude': ['LET-MX']
    },
    'MIX-SP': {
        'name': 'Uprising Spicy Mesclun',
        'type': 'nested',
        'base_components': ['MIX-LB', 'MIX-SB']  
    },
    'MIX-MI': {
        'name': 'Uprising Mild Mesclun',
        'type': 'nested',
        'base_components': ['MIX-LB', 'MIX-MB']  
    },
    'MIX-BR': {
        'name': 'Uprising Braising Mix',
        'type': 'regular',
        'varieties': ['GRE-TA', 'GRE-RS', 'GRE-PC', 'SPI-BE', 'SPI-WG', 'SPI-WB', 'KAL-RR', 'KAL-RF', 'KAL-DB', 'CHA-RA', 'GRE-MZ', 'GRE-GF']  
    },
    'FLO-ED': {
        'name': 'Edible Flower Mix',
        'type': 'regular',
        'varieties': ['FLO-BO', 'CAL-MX', 'NAS-TM', 'BAB-FB', 'BAB-BB'] 
    }
}


@login_required(login_url='/office/login/')
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
    redirect_authenticated_user = False
    
    def form_valid(self, form):
        user = form.get_user()
        if is_employee(user):
            return super().form_valid(form)
        else:
            form.add_error(None, "Invalid username or password.")
            return self.form_invalid(form)
    
    def get_success_url(self):
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        return reverse_lazy('office_landing')

    
class OfficeLogoutView(LogoutView):
    next_page = 'office_login'


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def office_landing(request):
    """
    Office landing page view - displays the main office portal with action cards
    """

    pending_orders_count = StoreOrder.objects.filter(fulfilled_date__isnull=True).count()

    context = {
        'user': request.user,
        'user_name': request.user.get_full_name() or request.user.username,
        'pending_orders_count': pending_orders_count,
    }
    
    return render(request, 'office/office_landing.html', context)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def view_variety(request, sku_prefix=None):  # Add optional parameter
    """
    View all varieties, last selected variety, products, lots, and all_vars dictionary.
    Handles POSTs for selecting variety, printing, editing, and adding records.
    """
    user = request.user
   
    # --- Determine which variety to display ---
    if sku_prefix:
        # If variety is in URL, use that
        variety_obj = get_object_or_404(Variety, pk=sku_prefix)
        # Update their last selected
        LastSelected.objects.update_or_create(
            user=user,
            defaults={'variety': variety_obj}
        )
    else:
        # No variety in URL, so get their last selected (or default)
        last_selected_entry = LastSelected.objects.filter(user=user).last()
        variety_obj = (
            last_selected_entry.variety if last_selected_entry 
            else Variety.objects.get(pk="BEA-CA")
        )
        # Redirect to URL with variety
        # return redirect('view_variety', sku_prefix=variety_obj.sku_prefix)
        return redirect('view_variety_with_sku', sku_prefix=variety_obj.sku_prefix)
    
    packed_for_year = settings.CURRENT_ORDER_YEAR
    
    # --- All varieties ---
    # Exclude base component mixes (MIX-LB, MIX-SB, MIX-MB)
    varieties = Variety.objects.exclude(
        sku_prefix__in=['MIX-LB', 'MIX-SB', 'MIX-MB']
    ).order_by('crop', 'sku_prefix')
    
    # --- Build all_vars dict for front-end dropdown (JS-friendly) ---
    all_vars = {
        v.sku_prefix: {
            'common_spelling': v.common_spelling,
            'var_name': v.var_name,
            'crop': v.crop,
        }
        for v in varieties
    }
    all_vars_json = json.dumps(all_vars)
   
    # --- Handle POST actions ---
    if request.method == 'POST':
        action = request.POST.get('action')
       
        # Handle variety selection (this changes the current variety)
        if action == 'select_variety':
            selected_variety_pk = request.POST.get('variety_sku')
            if selected_variety_pk:
                # Redirect to URL with new variety
                return redirect('view_variety', sku_prefix=selected_variety_pk)

    # --- Get associated products and lots for the current variety ---
    products = Product.objects.filter(variety=variety_obj).order_by(
        Case(*[When(sku_suffix=s, then=i) for i, s in enumerate(settings.SKU_SUFFIXES)],
            output_field=IntegerField())
    )
    # Check if this is a mix variety
    is_mix = variety_obj.is_mix

    if is_mix:
        # Get MixLots instead of regular Lots
        mix_lots = MixLot.objects.filter(variety=variety_obj).order_by("-created_date")

        # Find the active (non-retired) mix lot
        active_mix_lot = None
        for mix_lot in mix_lots:
            if not hasattr(mix_lot, 'retired_mix_info'):
                active_mix_lot = mix_lot
                break
        
        # Auto-assign active mix lot to all products
        if active_mix_lot:
            products.update(mix_lot=active_mix_lot, lot=None)

        has_pending_germ = False  # Mixes don't have pending germ samples
        
        # Build mix lots JSON data
        lots_json = json.dumps([
            {
                'id': mix_lot.id,
                'lot_code': mix_lot.lot_code,
                'is_retired': hasattr(mix_lot, 'retired_mix_info'),
                'is_mix': True,
                'germ_rate': mix_lot.get_current_germ_rate(),
            }
            for mix_lot in mix_lots
        ])
        
        # Build mix lots extra data
        lots_extra_data_list = []
        for mix_lot in mix_lots:
            extra_data = {
                'id': mix_lot.id,
                'is_next_year_only': False,  # Mixes don't have this concept
                'is_mix': True,
                'batch_count': mix_lot.batches.count(),
            }
            lots_extra_data_list.append(extra_data)
        
        lots_extra_data = json.dumps(lots_extra_data_list)
        lots = mix_lots  # For template
        
    else:
        # Regular lots logic
        lots = Lot.objects.filter(variety=variety_obj).order_by("year")
        has_pending_germ = any(lot.get_germ_record_with_no_test_date() for lot in lots)
        
        # Build lots JSON data
        lots_json = json.dumps([
            {
                'id': lot.id,
                'grower': str(lot.grower) if lot.grower else '',
                'year': lot.year,
                'harvest': lot.harvest or '',
                'is_retired': hasattr(lot, 'retired_info'),
                'low_inv': lot.low_inv,
                'is_mix': False,
            }
            for lot in lots
        ])
        
        # Build lots extra data
        lots_extra_data_list = []
        six_months_ago = timezone.now().date() - timedelta(days=180)

        for lot in lots:
            extra_data = {
                'id': lot.id,
                'is_next_year_only': lot.is_next_year_only_lot(packed_for_year),
                'is_mix': False,
            }
            
            recent_inv = lot.inventory.order_by('-inv_date').first()
            if recent_inv and recent_inv.inv_date >= six_months_ago:
                extra_data['recent_inventory'] = {
                    'id': recent_inv.id,
                    'weight': str(recent_inv.weight),
                    'date': recent_inv.inv_date.strftime('%m/%Y'),
                    'display': f"{recent_inv.weight} lbs ({recent_inv.inv_date.strftime('%m/%Y')})"
                }
            
            lots_extra_data_list.append(extra_data)

        lots_extra_data = json.dumps(lots_extra_data_list)

    growers = Grower.objects.all().order_by('code')

    if variety_obj.wholesale:
        wholesale_status = f"Available ({variety_obj.wholesale_rack_designation or 'No rack'})"
    elif variety_obj.wholesale_rack_designation == 'N':
        wholesale_status = "Not available"
    else:
        wholesale_status = "N/A"

    context = {
        'last_selected': variety_obj,
        'variety': variety_obj,
        'is_mix': is_mix, 
        'products': products,
        'lots': lots,
        'lots_json': lots_json,
        'lots_extra_data': lots_extra_data,
        'all_vars_json': all_vars_json,
        'growers': growers,
        'env_types': settings.ENV_TYPES,
        'sku_suffixes': settings.SKU_SUFFIXES,
        'pkg_sizes': settings.PKG_SIZES,
        'groups': settings.GROUPS,
        'categories': settings.CATEGORIES,
        'crops': settings.CROPS,
        'subtypes': settings.SUBTYPES,
        'packed_for_year': packed_for_year,
        'transition': settings.TRANSITION,
        'has_pending_germ': has_pending_germ,
        'wholesale_status': wholesale_status,
        'require_password': settings.REQUIRE_EDIT_PASSWORD,
    }
    return render(request, 'office/view_variety.html', context)



@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def print_product_labels(request):
    if request.method == 'POST':
        if request.user.username not in ["office", "admin"]:
            return JsonResponse({'error': 'You are not allowed to print labels'}, status=403)
        
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            print_type = data.get('print_type')
            quantity = int(data.get('quantity', 1))
            packed_for_year = int(data.get('packed_for_year', 1))
            add_to_bulk_pre_pack = data.get('add_to_bulk_pre_pack', False)
            bulk_pre_pack_qty = int(data.get('bulk_pre_pack_qty', 0))
            
            print(f"Packed for year: {packed_for_year}")
            print(f"Add to bulk pre-pack: {add_to_bulk_pre_pack}, Qty: {bulk_pre_pack_qty}")
            
            product = Product.objects.get(pk=product_id)
            
            # Determine if this is a mix or regular product
            has_mix_lot = product.mix_lot is not None
            has_regular_lot = product.lot is not None
            
            # Update bulk_pre_pack if requested
            if add_to_bulk_pre_pack and bulk_pre_pack_qty > 0:
                if product.bulk_pre_pack is None:
                    product.bulk_pre_pack = 0
                product.bulk_pre_pack += bulk_pre_pack_qty
                product.save()
                print(f"Updated bulk_pre_pack: added {bulk_pre_pack_qty}, new total: {product.bulk_pre_pack}")
            
            # Only log if not printing back-only labels
            if print_type not in ['back_single', 'back_sheet']:
                # Calculate actual label quantity
                if print_type in ['front_sheet', 'front_back_sheet']:
                    actual_qty = quantity * 30  # 30 labels per sheet
                else:
                    actual_qty = quantity  # Singles and front_back_single
                
                # Get today's date in PST/PDT
                pst = pytz.timezone('America/Los_Angeles')
                today_pst = timezone.now().astimezone(pst).date()
                
                # Build filter for existing print job based on lot type
                filter_kwargs = {
                    'product': product,
                    'date': today_pst,
                    'for_year': packed_for_year
                }
                
                if has_mix_lot:
                    filter_kwargs['mix_lot'] = product.mix_lot
                    filter_kwargs['lot__isnull'] = True
                elif has_regular_lot:
                    filter_kwargs['lot'] = product.lot
                    filter_kwargs['mix_lot__isnull'] = True
                else:
                    # No lot assigned at all
                    filter_kwargs['lot__isnull'] = True
                    filter_kwargs['mix_lot__isnull'] = True
                
                # Check if there's already a print job for this product today with same for_year
                existing_print = LabelPrint.objects.filter(**filter_kwargs).first()
                
                if existing_print:
                    # Add to existing quantity
                    existing_print.qty += actual_qty
                    existing_print.save()
                    print(f"Updated existing print job: added {actual_qty} to existing {existing_print.qty - actual_qty}")
                else:
                    # Create new print job with appropriate lot assignment
                    create_kwargs = {
                        'product': product,
                        'date': today_pst,
                        'qty': actual_qty,
                        'for_year': packed_for_year,
                    }
                    
                    if has_mix_lot:
                        create_kwargs['mix_lot'] = product.mix_lot
                        create_kwargs['lot'] = None
                    elif has_regular_lot:
                        create_kwargs['lot'] = product.lot
                        create_kwargs['mix_lot'] = None
                    else:
                        create_kwargs['lot'] = None
                        create_kwargs['mix_lot'] = None
                    
                    LabelPrint.objects.create(**create_kwargs)
                    print(f"Created new print job for {actual_qty} labels")
            
            print(f"Printing {quantity} {print_type} labels for product: {product.variety_id}")
            
            return JsonResponse({
                'success': True,
                'message': f"Printing {quantity} {print_type} labels for {product.variety}."
            })
            
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required(login_url='/office/login/')
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


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def assign_mix_lot(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        mix_lot_id = data.get('mix_lot_id')
        
        product = Product.objects.get(pk=product_id)
        mix_lot = MixLot.objects.get(pk=mix_lot_id)
        
        product.mix_lot = mix_lot
        product.lot = None  # Clear regular lot
        product.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    







@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def edit_product(request):
    if request.method == 'POST':
        try:
            product_id = request.POST.get('product_id')
            product = Product.objects.get(pk=product_id)
            
            # Update the product fields
            product.sku_suffix = request.POST.get('sku_suffix', product.sku_suffix)
            product.pkg_size = request.POST.get('pkg_size', product.pkg_size)
            product.env_type = request.POST.get('env_type', product.env_type)
            product.alt_sku = request.POST.get('alt_sku', product.alt_sku)
            product.lineitem_name = request.POST.get('lineitem_name', product.lineitem_name)
            product.rack_location = request.POST.get('rack_location', product.rack_location)
            
            # Handle numeric fields
            env_multiplier = request.POST.get('env_multiplier')
            if env_multiplier:
                try:
                    product.env_multiplier = int(env_multiplier)
                except ValueError:
                    product.env_multiplier = 1
            
            product.scoop_size = request.POST.get('scoop_size', product.scoop_size)
            
            # Handle boolean fields
            product.print_back = request.POST.get('print_back') == 'on'
            product.is_sub_product = request.POST.get('is_sub_product') == 'on'
            
            product.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Product updated successfully'
            })
            
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required(login_url='/office/login/')
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


@login_required(login_url='/office/login/')
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

    # --- Misc Sales Mapping ---
    MISC_ENVELOPE_MAP = {
        "TOM-CH-pkts": ("Tomato", 7),
        "PEA-SP-pkts": ("Pea", 3),
        "BEA-MF-pkts": ("Bean", 4),
    }

    misc_sales = MiscSales.objects.filter(year=latest_year).select_related("product")

    for misc_sale in misc_sales:
        sku = misc_sale.product.sku
        quantity = misc_sale.quantity

        if sku in MISC_ENVELOPE_MAP:
            env_type, multiplier = MISC_ENVELOPE_MAP[sku]
            env_count = quantity * multiplier

            if env_type not in envelope_counts:
                envelope_counts[env_type] = 0

            envelope_counts[env_type] += env_count
            total_envelopes += env_count
        else:
            # Optional: log or skip unknown SKUs
            print(f"⚠️ Unmapped misc SKU: {sku}")

    
    # Sort envelope counts by quantity (descending)
    envelope_counts = dict(sorted(envelope_counts.items(), key=lambda x: x[1], reverse=True))
    
    return {
        'envelope_counts': envelope_counts,
        'total': total_envelopes,
        'year': latest_year
    }


def get_envelope_data_for_printing(request):
    """
    Get envelope data for the last 3 years for printing
    """
    from django.http import JsonResponse
    from django.db.models import Max
    from datetime import datetime
    
    try:
        # Get the most recent sales year
        latest_year = Sales.objects.aggregate(max_year=Max('year'))['max_year']
        
        if not latest_year:
            return JsonResponse({'error': 'No sales data found'}, status=404)
        
        # Get data for last 3 years
        years_to_include = [latest_year - i for i in range(3)]
        
        envelope_data_by_year = {}
        
        for year in years_to_include:
            # print(f"Getting envelope data for year: {year}")
            year_data = get_envelope_count_data_for_year(year)
            
            # Only include years that have data
            if year_data['total'] > 0:
                envelope_data_by_year[str(year)] = year_data
                # print(f"Added data for year {year}: {year_data['total']} total envelopes")
            else:
                print(f"No data found for year {year}")
        
        # Calculate grand totals across all years
        grand_total_envelopes = sum(data['total'] for data in envelope_data_by_year.values())
        
        # Get all unique envelope types across all years
        all_envelope_types = set()
        for data in envelope_data_by_year.values():
            all_envelope_types.update(data['envelope_counts'].keys())
        
        # print(f"Returning data for {len(envelope_data_by_year)} years")
        # print(f"Grand total envelopes: {grand_total_envelopes}")
        # print(f"Unique envelope types: {sorted(all_envelope_types)}")
        
        return JsonResponse({
            'envelope_data_by_year': envelope_data_by_year,
            'years': [year for year in years_to_include if str(year) in envelope_data_by_year],
            'grand_total': grand_total_envelopes,
            'envelope_types': sorted(all_envelope_types),
            'generated_at': datetime.now().isoformat(),
            'report_title': f'Envelope Usage Report - Last 3 Years ({min(years_to_include)} - {max(years_to_include)})'
        })
        
    except Exception as e:
        print(f"Error in get_envelope_data_for_printing: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

def get_envelope_count_data_for_year(year):
    """
    Calculate envelope usage for a specific sales year
    """
    from django.db.models import Sum
    
    if not year:
        return {
            'envelope_counts': {},
            'total': 0,
            'year': None
        }
   
    # Get aggregated sales data for the specific year, grouped by product
    # This combines wholesale and retail quantities for each product
    product_totals = (
        Sales.objects
        .filter(year=year)
        .values('product', 'product__env_type')
        .annotate(total_quantity=Sum('quantity'))
    )
    
    # print(f"DEBUG: Found {len(product_totals)} unique products for {year}")
   
    # Group by envelope type and calculate totals
    envelope_counts = {}
    total_envelopes = 0
    products_with_env_type = 0
    products_without_env_type = 0
   
    for item in product_totals:
        env_type = item['product__env_type']
        quantity = item['total_quantity']
        product_id = item['product']
        
        # print(f"DEBUG: Product {product_id} - env_type: '{env_type}' - quantity: {quantity}")
       
        # Skip if product doesn't have env_type or it's empty
        if not env_type or env_type.strip() == '':
            products_without_env_type += 1
            print(f"DEBUG: Skipping product {product_id} - no env_type")
            continue
           
        products_with_env_type += 1
       
        if env_type not in envelope_counts:
            envelope_counts[env_type] = 0
       
        envelope_counts[env_type] += quantity
        total_envelopes += quantity
    
    # print(f"DEBUG: Products with env_type: {products_with_env_type}")
    # print(f"DEBUG: Products without env_type: {products_without_env_type}")
    
    # --- Misc Sales Mapping ---
    MISC_ENVELOPE_MAP = {
        "TOM-CH-pkts": ("Tomato", 7),
        "PEA-SP-pkts": ("Pea", 3),
        "BEA-MF-pkts": ("Bean", 4),
    }
    
    misc_sales = MiscSales.objects.filter(year=year).select_related("product")
    # print(f"DEBUG: Found {misc_sales.count()} misc sales records for {year}")
    
    for misc_sale in misc_sales:
        sku = misc_sale.product.sku
        quantity = misc_sale.quantity
        # print(f"DEBUG: Processing misc sale - SKU: {sku}, Quantity: {quantity}")
        
        if sku in MISC_ENVELOPE_MAP:
            env_type, multiplier = MISC_ENVELOPE_MAP[sku]
            env_count = quantity * multiplier
            # print(f"DEBUG: Mapping {sku} -> {env_type} (x{multiplier}) = {env_count} envelopes")
            
            if env_type not in envelope_counts:
                envelope_counts[env_type] = 0
            envelope_counts[env_type] += env_count
            total_envelopes += env_count
        else:
            print(f"⚠️ Unmapped misc SKU: {sku}")
   
    # Sort envelope counts by quantity (descending)
    envelope_counts = dict(sorted(envelope_counts.items(), key=lambda x: x[1], reverse=True))
    
    # print(f"DEBUG: Final envelope counts for {year}: {envelope_counts}")
    # print(f"DEBUG: Total envelopes for {year}: {total_envelopes}")
   
    return {
        'envelope_counts': envelope_counts,
        'total': total_envelopes,
        'year': year
    }


def get_top_selling_products(limit=4):
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
@login_required(login_url='/office/login/')
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


@login_required(login_url='/office/login/')
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
        
        # 3. Sales by product - Use var_name with crop in parentheses
        sales_by_product = []
        product_sales = base_orders.values(
            'items__product__variety__var_name',
            'items__product__variety__crop'
        ).annotate(
            total_sales=Sum(F('items__price') * F('items__quantity')),
            total_packets=Sum('items__quantity')
        ).order_by('-total_sales')
        
        for product in product_sales:
            if product['total_sales']:
                var_name = product['items__product__variety__var_name'] or 'Unknown Variety'
                crop = product['items__product__variety__crop']
                
                # Format: "Variety Name (Crop)" or just "Variety Name" if no crop
                if crop:
                    product_name = f"{var_name} ({crop})"
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




@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def varieties_json(request):
    """
    Get distinct non-null, non-empty varieties as JSON
    """
    varieties = Product.objects.exclude(variety__isnull=True).exclude(variety='').values_list('variety', flat=True).distinct()
    data = [{"name": v} for v in varieties]
    return JsonResponse(data, safe=False)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def crops_json(request):
    """
    Get crops as JSON with optional search
    """
    q = request.GET.get('q', '')
    crops = Product.objects.exclude(crop__isnull=True).exclude(crop='')
    
    if q:
        crops = crops.filter(crop__icontains=q)
    
    crop_names = crops.values_list('crop', flat=True).distinct()
    data = [{"name": name} for name in crop_names]
    return JsonResponse(data, safe=False)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def products_by_crop_json(request, crop):
    """
    Get products by specific crop as JSON
    """
    products = Product.objects.filter(crop=crop)
    data = []
    
    for p in products:
        data.append({
            "variety": p.variety,
            "current_inventory": "-",
            "previous_inventory": "-",
            "difference": "-",
            "germ_23": "-",
            "germ_24": "-",
            "germ_25": "-"
        })
    
    return JsonResponse(data, safe=False)


@login_required(login_url='/office/login/')
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


@login_required(login_url='office/login/')
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


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def retire_lot(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("Backend data:", data)
            lot_id = data.get('lot_id')
            is_mix = data.get('is_mix', False)
            notes = data.get('notes', '')
            retire_date = data.get('retire_date')
            
            if is_mix:
                # Handle mix lot retirement
                mix_lot = MixLot.objects.get(pk=lot_id)
                
                if hasattr(mix_lot, 'retired_mix_info'):
                    return JsonResponse({'error': 'This mix lot is already retired'}, status=400)
                
                RetiredMixLot.objects.create(
                    mix_lot=mix_lot,
                    retired_date=retire_date,
                    notes=notes
                )
                
                return JsonResponse({'success': True, 'message': f'Mix lot {mix_lot.lot_code} retired'})
            else:
                # Handle regular lot retirement
                lot = Lot.objects.get(pk=lot_id)
                
                if hasattr(lot, 'retired_info'):
                    return JsonResponse({'error': 'This lot is already retired'}, status=400)
                
                lbs_remaining = data.get('lbs_remaining', 0)
                
                RetiredLot.objects.create(
                    lot=lot,
                    lbs_remaining=lbs_remaining,
                    retired_date=retire_date,
                    notes=notes
                )
                
                return JsonResponse({'success': True, 'message': 'Lot retired'})
                
        except (Lot.DoesNotExist, MixLot.DoesNotExist):
            return JsonResponse({'error': 'Lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required(login_url='/office/login/')
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


@login_required(login_url='/office/login/')
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
            is_home_test = data.get('is_home_test', False)
            for_year = data.get('for_year')  # Get the packed_for_year from frontend
            
            lot = Lot.objects.get(pk=lot_id)
            
            if is_home_test:
                # Create a new germination record
                Germination.objects.create(
                    lot=lot,
                    status='active',
                    germination_rate=germination_rate,
                    test_date=test_date if test_date else date_class.today(),
                    notes=notes if notes else '',
                    for_year=int(for_year)
                )
            else:
                # Existing logic: update an existing record
                germ_record = lot.get_germ_record_with_no_test_date()
                
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
        # try:
        #     from datetime import date as date_class
        #     data = json.loads(request.body)
        #     lot_id = data.get('lot_id')
        #     germination_rate = data.get('germination_rate')
        #     test_date = data.get('test_date')
        #     notes = data.get('notes', '')
            
        #     lot = Lot.objects.get(pk=lot_id)
            
        #     # Find the most recent germination record
        #     # most_recent_germ = lot.germinations.order_by('-test_date').first()
        #     germ_record = lot.get_germ_record_with_no_test_date()
            
        #     # print(f"{most_recent_germ.lot.variety.sku_prefix}-{most_recent_germ.lot.grower}{most_recent_germ.lot.year} for 20{most_recent_germ.for_year} if most_recent_germ else 'No germination record'")
        #     if not germ_record:
        #         print("DEBUG: No empty germination record found to update")
        #         germ_record = lot.get_most_recent_germination()
            
        #     # Update the germination record
        #     germ_record.germination_rate = germination_rate
        #     germ_record.test_date = test_date if test_date else date_class.today()
        #     if notes:
        #         germ_record.notes = notes
        #     germ_record.save()
            
        #     return JsonResponse({'success': True})
        except Lot.DoesNotExist:
            return JsonResponse({'error': 'Lot not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def record_inventory(request):
    try:
        data = json.loads(request.body)
        lot_id = data.get('lot_id')
        weight = data.get('weight')
        inv_date = data.get('inv_date')
        notes = data.get('notes', '')
        
        if not lot_id or weight is None:
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        lot = Lot.objects.get(pk=lot_id)
        
        # Create inventory record with notes
        Inventory.objects.create(
            lot=lot,
            weight=Decimal(weight),
            inv_date=inv_date if inv_date else timezone.now().date(),
            notes=notes if notes else None
        )
        
        return JsonResponse({'success': True})
        
    except Lot.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Lot not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

@login_required(login_url='/office/login/')
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



@login_required(login_url='/office/login/')
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

@login_required(login_url='/office/login/')
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


@login_required(login_url='/office/login/')
@staff_member_required
def admin_dashboard(request):
    context = {
        'pkg_sizes': settings.PKG_SIZES,
        'sku_suffixes': settings.SKU_SUFFIXES,
        'env_types': settings.ENV_TYPES,
        'crops': settings.CROPS,
        'groups': settings.GROUPS,
        'subtypes': settings.SUBTYPES,
        'categories': settings.CATEGORIES,
        'user_name': request.user.get_full_name() or request.user.username,
        'current_order_year': settings.CURRENT_ORDER_YEAR,
    }
    return render(request, 'office/admin_dashboard.html', context)



@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def germination_inventory_view(request):
    """Render the germination/inventory page"""
    return render(request, 'office/germination_inventory.html')


@login_required(login_url='/office/login/')
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

        # Get all active lots with related data, EXCLUDING retired lots AND mix product lots
        lots = Lot.objects.select_related(
            'variety', 'grower'
        ).prefetch_related(
            'inventory', 'germinations', 'germ_sample_prints'
        ).filter(
            variety__isnull=False
        ).exclude(
            retired_info__isnull=False  # Exclude lots that have a RetiredLot record
        ).exclude(
            variety__sku_prefix__in=['CAR-RA', 'BEE-3B', 'LET-MX', 'MIX-SP', 'MIX-MI', 'MIX-BR', 'FLO-ED']
        ).order_by('year')  # Order lots by year within each variety
        
        inventory_data = []
        categories = set()
        groups = set()
        crops = set()
        
        # Build lot data grouped by variety SKU
        lot_data_by_variety = {}
        for lot in lots:
            variety = lot.variety
            sku = variety.sku_prefix
            
            if sku not in lot_data_by_variety:
                lot_data_by_variety[sku] = []
            
            # Add to filter sets
            if variety.category:
                categories.add(variety.category)
            if variety.group:
                groups.add(variety.group)
            if variety.crop:
                crops.add(variety.crop)
            
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
                current_inventory_date = current_inv.inv_date.strftime('%m/%Y')
                
                if inventories.count() > 1:
                    previous_inv = inventories[1]
                    previous_inventory_weight = float(previous_inv.weight)
                    previous_inventory_date = previous_inv.inv_date.strftime('%m/%Y')
                    inventory_difference = current_inventory_weight - previous_inventory_weight
            
            # Get germination data for the display years - take MAX rate if multiple tests
            germination_rates = {}
            for year_str in germ_years:
                year_for_lookup = int(year_str)
                
                # Get the highest germination rate for this year
                germ = lot.germinations.filter(for_year=year_for_lookup).order_by('-germination_rate').first()
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
            
            # Get detailed germination records - respect the print/test/result cycle
            germination_records = {}
            for year_str in germ_years:
                year_for_lookup = int(year_str)
                
                # Get the most recent print for this year
                most_recent_print = lot.germ_sample_prints.filter(for_year=year_for_lookup).order_by('-print_date').first()
                
                germ_record = None
                
                if most_recent_print:
                    # There's a print - check what stage we're at
                    
                    # STAGE 1: Check for pending tests (no test_date) - these show as "Germ Sent"
                    pending = lot.germinations.filter(
                        for_year=year_for_lookup,
                        test_date__isnull=True
                    ).first()
                    
                    if pending:
                        germ_record = pending
                    else:
                        # STAGE 2: No pending - look for completed tests AFTER the print (take highest)
                        # If no completed test after print, this returns None → shows "Label Printed"
                        germ_record = lot.germinations.filter(
                            for_year=year_for_lookup,
                            test_date__isnull=False,  # Must have a test_date
                            test_date__gte=most_recent_print.print_date  # Test must be AFTER print
                        ).order_by('-germination_rate').first()
                else:
                    # No print yet - get the highest rate test that has a test_date
                    germ_record = lot.germinations.filter(
                        for_year=year_for_lookup,
                        test_date__isnull=False
                    ).order_by('-germination_rate').first()
                
                if germ_record:
                    germination_records[year_str] = {
                        'germination_rate': germ_record.germination_rate,
                        'test_date': germ_record.test_date.strftime('%Y-%m-%d') if germ_record.test_date else None,
                        'status': germ_record.status,
                        'notes': germ_record.notes
                    }
            
            # Create lot code
            grower_code = lot.grower.code if lot.grower else 'UNK'
            lot_code = f"{grower_code}{lot.year}"
            
            lot_data_by_variety[sku].append({
                'lot_id': lot.id,
                'variety_name': variety.var_name,
                'sku_prefix': variety.sku_prefix,
                'category': variety.category,
                'group': variety.group,
                'crop': variety.crop,
                'species': variety.species,
                'lot_code': lot_code,
                'website_bulk': variety.website_bulk,
                'current_inventory_weight': current_inventory_weight,
                'current_inventory_date': current_inventory_date,
                'previous_inventory_weight': previous_inventory_weight,
                'previous_inventory_date': previous_inventory_date,
                'inventory_difference': inventory_difference,
                'germination_rates': germination_rates,
                'germ_sample_prints': germ_sample_prints,
                'germination_records': germination_records
            })
        
        # Now build the final list by iterating through ALL varieties in sorted order
        all_varieties = Variety.objects.exclude(
            # sku_prefix__in=['CAR-RA', 'BEE-3B', 'LET-MX', 'MIX-SP', 'MIX-MI', 'MIX-BR', 'FLO-ED', 'MIX-LB', 'MIX-SB', 'MIX-MB']
            sku_prefix__in=['MIX-LB', 'MIX-SB', 'MIX-MB']
        ).annotate(
            category_order=Case(
                When(category='Vegetables', then=1),
                When(category='Flowers', then=2),
                When(category='Herbs', then=3),
                default=4,
                output_field=IntegerField()
            )
        ).order_by('category_order', 'sku_prefix')
        
        for variety in all_varieties:
            # Add to filter sets
            if variety.category:
                categories.add(variety.category)
            if variety.group:
                groups.add(variety.group)
            if variety.crop:
                crops.add(variety.crop)
            
            if variety.sku_prefix in lot_data_by_variety:
                # Has lots - add all lot rows
                inventory_data.extend(lot_data_by_variety[variety.sku_prefix])
            else:
                # No lots - add empty row
                inventory_data.append({
                    'lot_id': None,
                    'variety_name': variety.var_name,
                    'sku_prefix': variety.sku_prefix,
                    'category': variety.category,
                    'group': variety.group,
                    'crop': variety.crop,
                    'species': variety.species,
                    'lot_code': '-',
                    'website_bulk': variety.website_bulk,
                    'current_inventory_weight': None,
                    'current_inventory_date': None,
                    'previous_inventory_weight': None,
                    'previous_inventory_date': None,
                    'inventory_difference': None,
                    'germination_rates': {year_str: None for year_str in germ_years},
                    'germ_sample_prints': {},
                    'germination_records': {}
                })
        
        # Convert sets to sorted lists
        categories = sorted(list(categories))
        groups = sorted(list(groups))
        crops = sorted(list(crops))
        
        
        # print(f"Returning {len(inventory_data)} records")
        germ_year = settings.FOR_YEAR
        return JsonResponse({
            'inventory_data': inventory_data,
            'germ_years': germ_years,
            'current_year': current_year,
            'categories': categories,
            'groups': groups,
            'crops': crops,
            'germ_year': germ_year
        })
        
    except Exception as e:
        print(f"Error in germination_inventory_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def update_website_bulk(request):
    """API endpoint to update website_bulk status for a variety"""
    try:
        import json
        data = json.loads(request.body)
        sku_prefix = data.get('sku_prefix')
        new_status = data.get('website_bulk')  # ADD THIS LINE
        
        if not sku_prefix:
            return JsonResponse({'error': 'sku_prefix is required'}, status=400)
        
        variety = Variety.objects.get(sku_prefix=sku_prefix)
        variety.website_bulk = new_status  # CHANGE THIS LINE
        variety.save()
        
        return JsonResponse({
            'success': True,
            'sku_prefix': sku_prefix,
            'website_bulk': new_status  # CHANGE THIS LINE
        })
        
    except Variety.DoesNotExist:
        return JsonResponse({'error': 'Variety not found'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def create_germ_sample_print(request):
    """API endpoint to create a germination sample print record"""
    try:
        data = json.loads(request.body)
        lot_id = data.get('lot_id')
        germ_year = data.get('germ_year')
        force_new = data.get('force_new', False)  # NEW: Allow forcing new record
        
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
        
        if existing_print and not force_new:
            # Return existing without creating new
            return JsonResponse({
                'success': True,
                'message': 'Print record already exists',
                'existing': True,
                'print_date': existing_print.print_date.strftime('%Y-%m-%d')
            })
        
        # Create new print record (either first time or forced)
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


def calculate_variety_usage(variety, sales_year):
    """
    Calculate how many lbs of a variety were used during a sales year.
    
    Scenarios:
    1. Normal: has inventory at both start and end of season
    2. Retired during season: has start inventory, retired with lbs_remaining
    3. Used up but not retired: has start inventory, no end inventory (assume 0)
    4. No inventory at expected times: skip the lot
    """
    from decimal import Decimal
    from datetime import datetime
    
    # Find all lots for this variety that had active status for this sales year
    active_lots = Lot.objects.filter(
        variety=variety,
        germinations__status='active',
        germinations__for_year=sales_year
    ).distinct()
    
    total_usage = Decimal('0.00')
    lot_details = []
    lots_processed = 0
    retired_or_depleted_count = 0  # Count BOTH retired AND depleted lots
    
    # Define the sales year date ranges
    year_full = 2000 + int(sales_year)
    
    # Start of season: Sept 1 - Nov 15 of PREVIOUS calendar year
    season_start_begin = datetime(year_full - 1, 9, 1)
    season_start_end = datetime(year_full - 1, 11, 15, 23, 59, 59)
    
    # End of season: Sept 1 - Nov 15 of CURRENT calendar year
    season_end_begin = datetime(year_full, 9, 1)
    season_end_end = datetime(year_full, 11, 15, 23, 59, 59)
        
    for lot in active_lots:
        # Get all inventory records for this lot, ordered by date
        inventory_records = lot.inventory.all().order_by('inv_date')
        inventory_count = inventory_records.count()
        
        # Skip lots with no inventory records
        if inventory_count == 0:
            continue
        
        # Find inventory at START of season
        start_inventory = inventory_records.filter(
            inv_date__gte=season_start_begin,
            inv_date__lte=season_start_end
        ).order_by('-inv_date').first()
        
        # Find inventory at END of season
        end_inventory = inventory_records.filter(
            inv_date__gte=season_end_begin,
            inv_date__lte=season_end_end
        ).order_by('-inv_date').first()

        # If no inventory in normal window, check if there's ANY inventory after season start
        # This handles cases where inventory was taken late (e.g., December)
        if not end_inventory:
            end_inventory = inventory_records.filter(
                inv_date__gt=season_end_begin
            ).order_by('inv_date').first()
        
        # Determine start weight
        if start_inventory:
            start_weight = start_inventory.weight
        else:
            # No inventory at start of season - skip this lot for this year
            continue
        
        # Determine end weight and status
        retired_during_season = False
        depleted_not_retired = False
        
        if end_inventory:
            # Normal case: has inventory at end of season
            end_weight = end_inventory.weight
        elif hasattr(lot, 'retired_info'):
            # Retired during season
            end_weight = lot.retired_info.lbs_remaining
            retired_during_season = True
            retired_or_depleted_count += 1
        else:
            # No end inventory AND not retired
            # This means it was used up but never properly retired
            # Assume it was depleted to 0
            end_weight = Decimal('0.00')
            depleted_not_retired = True
            retired_or_depleted_count += 1
        
        lot_usage = start_weight - end_weight
        lots_processed += 1
        
        # Only count positive usage
        if lot_usage > 0:
            total_usage += lot_usage
            lot_details.append({
                'lot_code': lot.get_four_char_lot_code(),
                'start_weight': float(start_weight),
                'end_weight': float(end_weight),
                'usage': float(lot_usage),
                'retired': retired_during_season,
                'depleted_not_retired': depleted_not_retired  # NEW FLAG
            })
    
    # Check if ALL processed lots were retired OR depleted during the season
    ran_out_of_seed = (
        lots_processed > 0 and 
        retired_or_depleted_count == lots_processed
    )
    
    return {
        'total_lbs': float(total_usage),
        'lot_count': len(lot_details),
        'lots': lot_details,
        'sales_year': sales_year,
        'display_year': f"20{sales_year}",
        'ran_out_of_seed': ran_out_of_seed
    }

def get_variety_lot_inventory(variety, current_order_year):
    """
    Get all non-retired lots for a variety with their germination data
    for current year and two previous years, plus current inventory.
    Only includes inventory from the last 12 months.
    """
    from decimal import Decimal
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Get all non-retired lots for this variety
    lots = Lot.objects.filter(
        variety=variety
    ).exclude(
        retired_info__isnull=False
    ).order_by('year', 'grower')
    
    lot_data = []
    total_inventory = Decimal('0.00')
    
    # Calculate 12 months ago
    twelve_months_ago = timezone.now().date() - timedelta(days=365)
    
    years_to_check = [
        current_order_year - 2,
        current_order_year - 1,
        current_order_year
    ]
    
    for lot in lots:
        # Get most recent inventory
        recent_inv = lot.inventory.order_by('-inv_date').first()
        
        # Only count inventory if it's within the last 12 months
        inv_weight = Decimal('0.00')
        inv_date = None
        if recent_inv and recent_inv.inv_date >= twelve_months_ago:
            inv_weight = recent_inv.weight
            inv_date = recent_inv.inv_date.strftime('%m/%Y')
            total_inventory += inv_weight
        
        # Get germination data for each year
        germ_data = {}
        for year in years_to_check:
            germ = lot.germinations.filter(for_year=year).order_by('-test_date').first()
            if germ:
                germ_data[year] = {
                    'rate': germ.germination_rate,
                    'has_test_date': germ.test_date is not None
                }
            else:
                germ_data[year] = None
        
        lot_data.append({
            'lot_code': lot.get_four_char_lot_code(),
            'lot_id': lot.id,
            'germ_data': germ_data,
            'inventory': float(inv_weight),
            'inv_date': inv_date
        })
    
    return {
        'lots': lot_data,
        'total_inventory': float(total_inventory),
        'years': years_to_check
    }


@login_required(login_url='/office/login/')
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
        
        # Calculate usage for previous sales year
        # During transition, look back 2 years; otherwise look back 1 year
        previous_sales_year = settings.CURRENT_ORDER_YEAR - (2 if settings.TRANSITION else 1)
        usage_data = calculate_variety_usage(variety, previous_sales_year)
      
        lot_inventory_data = get_variety_lot_inventory(variety, settings.CURRENT_ORDER_YEAR)

        return JsonResponse({
            'sales_data': formatted_sales,
            'year': most_recent_year,
            'display_year': display_year,  # Add 4-digit year for display
            'variety_name': variety.var_name,
            'sku_prefix': variety.sku_prefix,
            'wholesale': variety.wholesale, 
            'wholesale_rack_designation': variety.wholesale_rack_designation,
            'usage_data': usage_data,
            'lot_inventory_data': lot_inventory_data,
            'growout_needed': variety.growout_needed or '',
        })
        
    except Exception as e:
        # print(f"Error getting sales data for {sku_prefix}: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
    





# VIEW FUNCTONS FOR MANAGING WHOLESALE STORE ORDERS
@login_required(login_url='/office/login/')
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
            'crop': variety.crop,  # or variety.crop if that's the field name
            'category': variety.category 
        }
   
    stores = Store.objects.all()
   
    context = {
        'stores': stores,
        'variety_data': json.dumps(variety_data)  # Convert to JSON string for the template
    }
    return render(request, 'office/store_orders.html', context)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def view_stores(request):
    """
    View for displaying all store locations and their details
    """
    # fetch all store objects from the database, excluding ones whose name attribute start with "PCC"
    stores = Store.objects.exclude(store_name__startswith="Ballard")
    context = {'stores': stores}
    
    return render(request, 'office/view_stores.html', context)

@login_required(login_url='/office/login/')
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
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
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
    

@login_required(login_url='/office/login/')
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
    


@login_required(login_url='/office/login/')
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
                    'crop': variety.crop,
                    'quantity': item.quantity,
                    'category': variety.category,
                    'has_photo': item.photo  # Use the stored preference
                })
       
        return JsonResponse({
            'order': {  # Add the order object
                'id': order.id,
                'order_number': order.order_number,
                'fulfilled_date': order.fulfilled_date.strftime('%Y-%m-%d %H:%M:%S') if order.fulfilled_date else None,
                'store_name': order.store.store_name
            },
            'items': formatted_items
        })
       
    except StoreOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        print(f"ERROR in get_order_details: {e}")
        return JsonResponse({'error': str(e)}, status=400)


@login_required(login_url='/office/login/')
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


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def finalize_order(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        items = data.get('items', [])
        shipping = data.get('shipping', 0) 
        
        # Get the order
        order = StoreOrder.objects.get(id=order_id)

        # Calculate credit if it is their first order for the year
        credit = 0
        order_number = order.order_number
        
        print(f"\n=== CREDIT DEBUG START ===")
        print(f"Order number: {order_number}")
        print(f"Store number: {order.store.store_num}")
        
        # Extract order sequence from order number (e.g., "W1001-26" -> "01")
        # Format: W[store_id 2 digits][order_num 2 digits]-[year 2 digits]
        try:
            # Get the part before the hyphen (e.g., "W1001")
            before_hyphen = order_number.split('-')[0]
            print(f"Before hyphen: {before_hyphen}")
            
            # Get the last 2 digits (order number within year)
            order_sequence = before_hyphen[-2:]
            print(f"Order sequence: {order_sequence}")
            
            # Check if this is the first order of the year
            if order_sequence == "01":
                print("✓ This IS the first order of the year")
                
                # Extract year from order number (e.g., "26" from "W1001-26")
                year_suffix = order_number.split('-')[-1]
                invoice_year = int(year_suffix)
                print(f"Invoice year: {invoice_year}")
                print(f"Will look for returns from year: {invoice_year - 1}")
                
                # Get credit from previous year's returns
                from stores.models import StoreReturns
                packets_returned, credit = StoreReturns.get_credit_for_first_invoice(
                    order.store.store_num,
                    invoice_year
                )
                
                print(f"Packets returned: {packets_returned}")
                print(f"Credit amount: ${credit}")
                
                if credit > 0:
                    print(f"✓ Applied credit of ${credit} to order {order_number} (from {packets_returned} packets returned)")
                else:
                    print(f"✗ No credit applied")
            else:
                print(f"✗ This is NOT the first order (sequence: {order_sequence})")
                
        except (IndexError, ValueError) as e:
            print(f"✗ Error parsing order number for credit calculation: {e}")
            import traceback
            traceback.print_exc()
            credit = 0
        
        print(f"Final credit value: {credit}")
        print(f"=== CREDIT DEBUG END ===\n")
       
        # Set fulfilled_date to current timezone-aware datetime
        from django.utils import timezone
        order.fulfilled_date = timezone.now()
        order.shipping = shipping
        order.save()
        
        pkt_price = settings.PACKET_PRICE  
        
        # Validate all products exist first (safer approach)
        new_so_includes = []
        for item in items:
            try:
                # Get Variety by sku_prefix
                variety = Variety.objects.get(sku_prefix=item['sku_prefix'])
               
                # Find the associated Product with sku_suffix == "pkt"
                product = Product.objects.get(
                    variety=variety,
                    sku_suffix="pkt"
                )
               
                new_so_includes.append({
                    'product': product,
                    'variety': variety,  # Keep variety reference for response
                    'quantity': item['quantity'],
                    'photo': item.get('has_photo', False),
                    'price': pkt_price
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
        
        print(f"\n=== RESPONSE DEBUG ===")
        print(f"Credit being returned in response: {credit}")
        print(f"Credit as float: {float(credit)}")
        print(f"=== RESPONSE DEBUG END ===\n")
       
        return JsonResponse({
            'success': True,
            'order': {
                'id': order.id,
                'order_number': order.order_number,
                'date': order.date.isoformat() if order.date else None,
                'fulfilled_date': order.fulfilled_date.isoformat(),
                'notes': order.notes or '',
                'shipping': float(order.shipping), 
                'credit': float(credit)  # Convert Decimal to float for JSON
            },
            'store': {
                'store_name': store.store_name,
                'store_contact_name': store.store_contact_name or '',
                'store_contact_phone': store.store_contact_phone or '',
                'store_contact_email': store.store_contact_email or '',
                'store_address': store.store_address or '',
                'store_address2': store.store_address2 or '',
                'store_city': store.store_city or '',
                'store_state': store.store_state or '',
                'store_zip': store.store_zip or ''
            },
            'items': [
                {
                    'sku_prefix': include.product.variety.sku_prefix,
                    'variety_name': include.product.variety.var_name,
                    'crop': include.product.variety.crop,
                    'quantity': include.quantity,
                    'has_photo': include.photo,
                    'price': float(include.price)
                }
                for include in so_includes
            ]
        })
       
    except Exception as e:
        print(f"Error in finalize_order: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='/office/login/')
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


@login_required(login_url='/office/login/')
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

        # Validate required fields
        if not data['sku_suffix']:
            return JsonResponse({
                'success': False,
                'errors': {'sku_suffix': ['SKU Suffix is required']}
            }, status=400)

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
    

@login_required(login_url='/office/login/')
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
                'weight': float(inv.weight),
                'notes': inv.notes
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


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def get_product_packing_history(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        

        try:
            product = Product.objects.get(id=product_id)
            
            # Check if this is a mix product
            is_mix = product.variety.sku_prefix in mix_prefixes
            
            # Get all print records for this product
            if is_mix:
                print_records = product.label_prints.select_related('mix_lot').all().order_by('-date')
            else:
                print_records = product.label_prints.select_related('lot').all().order_by('-date')


            packing_history = []
            for record in print_records:
                # Determine lot code based on whether it's a mix or regular lot
                if is_mix and record.mix_lot:
                    lot_code = record.mix_lot.lot_code
                elif record.lot:
                    lot_code = record.lot.get_four_char_lot_code()
                else:
                    lot_code = 'UNK'
                packing_history.append({
                    'id': record.id,
                    'date': record.date.strftime('%Y-%m-%d'),
                    'qty': record.qty,
                    'lot_code': lot_code,
                    'for_year': record.for_year or '--'
                })


        # try:
        #     product = Product.objects.get(id=product_id)
            
        #     # Get all print records for this product
        #     print_records = product.label_prints.all().order_by('-date')


        #     packing_history = []
        #     for record in print_records:
        #         lot_code = record.lot.get_four_char_lot_code() if record.lot else 'UNK'
        #         packing_history.append({
        #             'id': record.id,
        #             'date': record.date.strftime('%Y-%m-%d'),
        #             'qty': record.qty,
        #             'lot_code': lot_code,
        #             'for_year': record.for_year or '--'
        #         })
            
            return JsonResponse({
                'success': True,
                'data': {
                    'variety_name': product.variety.var_name,
                    'product_sku': f"{product.variety.sku_prefix}-{product.sku_suffix}",
                    # 'total_printed': product.get_total_printed(),
                    'packing_history': packing_history
                }
            })
            
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Product not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required(login_url='/office/login/')
@require_http_methods(["POST"])
def edit_packing_record(request):
    """Edit a packing record by updating its quantity"""
    try:
        data = json.loads(request.body)
        record_id = data.get('record_id')
        new_qty = data.get('new_qty')
        
        if not record_id or new_qty is None:
            return JsonResponse({
                'success': False,
                'error': 'Missing record_id or new_qty'
            })
        
        # Validate quantity
        try:
            new_qty = int(new_qty)
            if new_qty <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Quantity must be greater than 0'
                })
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid quantity value'
            })
        
        # Get the record
        try:
            record = LabelPrint.objects.get(id=record_id)
        except LabelPrint.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Packing record not found'
            })
        
        # Update the quantity
        old_qty = record.qty
        record.qty = new_qty
        record.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Quantity updated from {old_qty} to {new_qty}'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        })


@login_required(login_url='/office/login/')
@require_http_methods(["POST"])
def delete_packing_record(request):
    """Delete a packing record"""
    try:
        data = json.loads(request.body)
        record_id = data.get('record_id')
        
        if not record_id:
            return JsonResponse({
                'success': False,
                'error': 'Missing record_id'
            })
        
        # Get the record
        try:
            record = LabelPrint.objects.get(id=record_id)
        except LabelPrint.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Packing record not found'
            })
        
        # Store info for confirmation message
        record_info = {
            'date': record.date,
            'qty': record.qty,
            'product': str(record.product),
            'lot': str(record.lot) if record.lot else 'No lot'
        }
        
        # Delete the record
        record.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Deleted packing record: {record_info["date"]} - {record_info["qty"]} units'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        })
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def get_stock_seed_data(request):
    

    if request.method == 'POST':
        data = json.loads(request.body)
        print(f"Raw request body: {request.body}") 
        lot_id = data.get('lot_id')
        print(f"Parsed JSON data: {data}")
        try:
            # Debug: Print what we're looking for
            print(f"Searching for lot_id: {lot_id} (type: {type(lot_id)})")
            
            # Try to get the lot first
            try:
                lot = Lot.objects.get(id=lot_id)
                print(f"Found lot: {lot}")
            except Lot.DoesNotExist:
                print(f"Lot with id {lot_id} does not exist")
                return JsonResponse({
                    'success': False,
                    'error': f'Lot with id {lot_id} does not exist'
                })
            
            # Check stock seeds for this lot
            stock_seeds = StockSeed.objects.filter(lot=lot)
            print(f"Found {stock_seeds.count()} stock seed records for this lot")
            
            for ss in stock_seeds:
                print(f"StockSeed: qty={ss.qty}, date={ss.date}")
            
            stock_seed = stock_seeds.order_by('-date').first()
            
            if not stock_seed:
                return JsonResponse({
                    'success': False,
                    'error': f'No stock seed found for lot {lot}. Found {stock_seeds.count()} records total.'
                })
            
            # Construct lot number
            lot_number = f"{lot.grower.code}{lot.year}"
            
            return JsonResponse({
                'success': True,
                'variety_name': lot.variety.var_name,
                'crop': lot.variety.crop or '',
                'lot_number': lot_number,
                'quantity': stock_seed.qty
            })
        except Exception as e:
            print(f"Exception in get_stock_seed_data: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def update_inventory(request):
    try:
        data = json.loads(request.body)
        inventory_id = data.get('inventory_id')
        weight = data.get('weight')
        action = data.get('action')  # 'add' or 'overwrite'
        
        if not inventory_id or weight is None or action not in ['add', 'overwrite']:
            return JsonResponse({'success': False, 'error': 'Missing or invalid fields'})
        
        inventory = Inventory.objects.get(pk=inventory_id)
        
        if action == 'add':
            inventory.weight += Decimal(weight)
        else:  # overwrite
            inventory.weight = Decimal(weight)
        
        inventory.save()
        
        return JsonResponse({'success': True})
        
    except Inventory.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Inventory not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def check_pick_list_printed(request, order_id):
    """
    Check if a pick list has already been printed for this order
    """
    try:
        order = StoreOrder.objects.get(id=order_id)
        already_printed = PickListPrinted.objects.filter(store_order=order).exists()
        
        return JsonResponse({
            'already_printed': already_printed
        })
            
    except StoreOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def record_pick_list_printed(request):
    """
    Record that a pick list has been printed for an order
    """
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        
        order = StoreOrder.objects.get(id=order_id)
        
        # Create the record (only if it doesn't exist)
        PickListPrinted.objects.get_or_create(store_order=order)
        
        return JsonResponse({'success': True})
        
    except StoreOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def set_wholesale_price(request):
    """
    Set or update wholesale packet price for a given year
    """
    try:
        year = request.POST.get('year')
        price_per_packet = request.POST.get('price_per_packet')
        
        # Validate inputs
        if not year or not price_per_packet:
            return JsonResponse({
                'success': False,
                'message': 'Year and price are required'
            }, status=400)
        
        try:
            year = int(year)
            
            price_per_packet = Decimal(price_per_packet)
            
            if price_per_packet < 0:
                return JsonResponse({
                    'success': False,
                    'errors': {'price_per_packet': ['Price must be positive']}
                }, status=400)
                
        except (ValueError, InvalidOperation) as e:
            return JsonResponse({
                'success': False,
                'message': 'Invalid year or price format'
            }, status=400)
        
        # Create or update the price record
        price_obj, created = WholesalePktPrice.objects.update_or_create(
            year=year,
            defaults={'price_per_packet': price_per_packet}
        )
        
        action = "created" if created else "updated"
        
        return JsonResponse({
            'success': True,
            'message': f'Wholesale price {action} successfully',
            'data': {
                'year': year,
                'price_per_packet': str(price_per_packet)
            }
        })
        
    except Exception as e:
        print(f"Error setting wholesale price: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def record_store_returns(request):
    """
    Record packet returns for a store
    """
    try:
        store_num = request.POST.get('store_num')
        year = request.POST.get('year')
        packets_returned = request.POST.get('packets_returned')
        
        # Validate inputs
        if not store_num or not year or not packets_returned:
            return JsonResponse({
                'success': False,
                'message': 'All fields are required'
            }, status=400)
        
        try:
            store_num = int(store_num)
            year = int(year)
            packets_returned = int(packets_returned)
            
            if packets_returned < 0:
                return JsonResponse({
                    'success': False,
                    'errors': {'packets': ['Number of packets must be positive']}
                }, status=400)
                
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'message': 'Invalid input format'
            }, status=400)
        
        # Get the store
        try:
            store = Store.objects.get(store_num=store_num)
        except Store.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'store': ['Store not found']}
            }, status=404)
        
        # Create or update the return record
        return_obj, created = StoreReturns.objects.update_or_create(
            store=store,
            return_year=year,
            defaults={'packets_returned': packets_returned}
        )
        
        action = "created" if created else "updated"
        
        return JsonResponse({
            'success': True,
            'message': f'Returns {action} successfully',
            'data': {
                'store_name': store.store_name,
                'year': year,
                'packets_returned': packets_returned
            }
        })
        
    except Exception as e:
        print(f"Error recording store returns: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def get_store_returns_years(request):
    """
    Get list of all years from store orders, always including 25 as minimum
    """
    try:
        # Extract unique years from order numbers (e.g., "W1001-25" -> 25)
        order_numbers = StoreOrder.objects.values_list('order_number', flat=True)
        years = set()
        
        for order_num in order_numbers:
            try:
                # Split by '-' and get last part (year)
                year_str = order_num.split('-')[-1]
                year = int(year_str)
                years.add(year)
            except (ValueError, IndexError):
                continue
        
        # Always include 25 as minimum
        years.add(25)
        
        # Sort in descending order (most recent first)
        sorted_years = sorted(years, reverse=True)
        
        return JsonResponse({
            'success': True,
            'years': sorted_years
        })
        
    except Exception as e:
        print(f"Error getting returns years: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required(login_url='office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def get_store_returns_data(request):
    """
    Get returns data for all stores for a specific year
    Calculates # packets allowed based on 5% of total packets sold
    """
    try:
        year = request.GET.get('year')
        
        if not year:
            return JsonResponse({
                'success': False,
                'message': 'Year parameter is required'
            }, status=400)
        
        try:
            year = int(year)
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid year format'
            }, status=400)
        
        # Get all stores
        stores = Store.objects.all().order_by('store_num')
        
        # Get wholesale price for this year
        try:
            price = WholesalePktPrice.objects.get(year=year).price_per_packet
        except WholesalePktPrice.DoesNotExist:
            price = None
        
        # Build data for each store
        stores_data = []
        for store in stores:
            # Calculate total packets sold for this store in this year
            # Get all orders for this store ending with this year
            year_suffix = str(year).zfill(2)  # Ensure 2 digits (e.g., 25)
            
            total_packets_sold = SOIncludes.objects.filter(
                store_order__store=store,
                store_order__order_number__endswith=f'-{year_suffix}',
                store_order__fulfilled_date__isnull=False  # Only count fulfilled orders
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Calculate 5% of total packets sold, rounded up
            if total_packets_sold > 0:
                packets_allowed = math.ceil(total_packets_sold * 0.05)
            else:
                packets_allowed = None  # Will display as "--"
            
            # Get returns for this store/year
            try:
                returns = StoreReturns.objects.get(store=store, return_year=year)
                packets_returned = returns.packets_returned
            except StoreReturns.DoesNotExist:
                packets_returned = 0
            
            # Calculate credit
            credit = float(packets_returned * price) if (price and packets_returned > 0) else 0
            
            stores_data.append({
                'store_num': store.store_num,
                'store_name': store.store_name,
                'total_packets_sold': total_packets_sold,
                'packets_allowed': packets_allowed if packets_allowed is not None else '--',
                'packets_returned': packets_returned,
                'credit': credit
            })
        
        return JsonResponse({
            'success': True,
            'year': year,
            'price_per_packet': float(price) if price else None,
            'stores': stores_data
        })
        
    except Exception as e:
        print(f"Error getting store returns data: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def get_store_sales_data(request):
    """
    Get sales data for all stores for a specific year
    """
    try:
        year = request.GET.get('year')
        
        if not year:
            return JsonResponse({
                'success': False,
                'message': 'Year parameter is required'
            }, status=400)
        
        try:
            year = int(year)
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid year format'
            }, status=400)
        
        # Get all stores
        stores = Store.objects.all().order_by('store_num')
        
        # Build sales data for each store
        stores_data = []
        year_suffix = str(year).zfill(2)  # Ensure 2 digits
        
        for store in stores:
            # Get all fulfilled orders for this store in this year
            orders = StoreOrder.objects.filter(
                store=store,
                order_number__endswith=f'-{year_suffix}',
                fulfilled_date__isnull=False
            )
            
            # Calculate total packets
            total_packets = SOIncludes.objects.filter(
                store_order__in=orders
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Calculate subtotal (sum of all line items)
            from django.db.models import F
            subtotal = SOIncludes.objects.filter(
                store_order__in=orders
            ).aggregate(
                total=Sum(F('quantity') * F('price'))
            )['total'] or 0
            
            # Calculate total shipping
            total_shipping = orders.aggregate(
                total=Sum('shipping')
            )['total'] or 0
            
            # Calculate grand total
            total = float(subtotal) + float(total_shipping)
            
            stores_data.append({
                'store_num': store.store_num,
                'store_name': store.store_name,
                'total_packets': total_packets,
                'subtotal': float(subtotal),
                'total_shipping': float(total_shipping),
                'total': total
            })
        
        return JsonResponse({
            'success': True,
            'year': year,
            'stores': stores_data
        })
        
    except Exception as e:
        print(f"Error getting store sales data: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def edit_variety(request):
    try:
        data = json.loads(request.body)
        sku_prefix = data.get('sku_prefix')
        
        # Get the variety object
        variety = Variety.objects.get(sku_prefix=sku_prefix)
        
        # Update fields
        variety.var_name = data.get('var_name', variety.var_name)
        variety.crop = data.get('crop').upper() if data.get('crop') else None
        variety.common_spelling = data.get('common_spelling', variety.common_spelling)
        variety.common_name = data.get('common_name', variety.common_name)
        variety.group = data.get('group', variety.group)
        variety.species = data.get('species', variety.species)
        variety.subtype = data.get('subtype', variety.subtype)
        variety.days = data.get('days', variety.days)
        variety.active = data.get('active', variety.active)
        variety.stock_qty = data.get('stock_qty', variety.stock_qty)
        variety.photo_path = data.get('photo_path', variety.photo_path)
        variety.wholesale = data.get('wholesale', variety.wholesale)
        variety.ws_notes = data.get('ws_notes', variety.ws_notes)
        variety.ws_description = data.get('ws_description', variety.ws_description)
        variety.category = data.get('category', variety.category)
                
        variety.save()
        
        return JsonResponse({'success': True, 'message': 'Variety updated successfully'})
    
    except Variety.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Variety not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def update_variety_wholesale(request):
    """Update variety wholesale status and rack designation"""
    try:
        data = json.loads(request.body)
        sku_prefix = data.get('sku_prefix')
        wholesale = data.get('wholesale')
        rack_designation = data.get('wholesale_rack_designation')
        
        variety = Variety.objects.get(sku_prefix=sku_prefix)
        variety.wholesale = wholesale
        variety.wholesale_rack_designation = rack_designation
        variety.save()
        
        return JsonResponse({'success': True})
    except Variety.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Variety not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def variety_usage(request, sku_prefix):
    """Get usage and inventory data for a specific variety"""
    
    try:
        # Get the variety
        try:
            variety = Variety.objects.get(sku_prefix=sku_prefix)
        except Variety.DoesNotExist:
            return JsonResponse({'error': 'Variety not found'}, status=404)
        
        # Calculate usage for previous sales year (CURRENT_ORDER_YEAR - 1)
        previous_sales_year = settings.CURRENT_ORDER_YEAR - (2 if settings.TRANSITION else 1)
        usage_data = calculate_variety_usage(variety, previous_sales_year)
      
        # Get lot inventory data
        lot_inventory_data = get_variety_lot_inventory(variety, settings.CURRENT_ORDER_YEAR)
        
        return JsonResponse({
            'success': True,
            'variety_name': variety.var_name,
            'sku_prefix': variety.sku_prefix,
            'usage_data': usage_data,
            'lot_inventory_data': lot_inventory_data
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def update_product_scoop_size(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        scoop_size = data.get('scoop_size', '').strip()
        
        # Get the product
        product = Product.objects.get(pk=product_id)
        
        # Update scoop size
        product.scoop_size = scoop_size if scoop_size else None
        product.save()
        
        return JsonResponse({'success': True})
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def mixes(request):
    """Render the mixes page"""
    context = {
        'current_order_year': settings.CURRENT_ORDER_YEAR,
        'final_mixes': FINAL_MIX_CONFIGS,
        'base_mixes': BASE_COMPONENT_MIXES
    }
    return render(request, 'office/mixes.html', context)
# def mixes(request):
#     """Render the mixes page"""
#     context = {
#         'current_year': settings.CURRENT_ORDER_YEAR
#     }
#     return render(request, 'office/mixes.html', context)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def get_available_lots_for_mix(request):
    """Get available component lots for creating a new mix lot"""
    mix_id = request.GET.get('mix')
    year = int(request.GET.get('year', settings.CURRENT_ORDER_YEAR))
    
    # Check if it's a base component or final mix
    if mix_id in BASE_COMPONENT_MIXES:
        config = BASE_COMPONENT_MIXES[mix_id]
    elif mix_id in FINAL_MIX_CONFIGS:
        config = FINAL_MIX_CONFIGS[mix_id]
    else:
        return JsonResponse({'error': 'Invalid mix'}, status=400)
    
    # Handle nested mixes (composed of other mix lots)
    if config.get('type') == 'nested':
        base_component_skus = config.get('base_components', [])
        
        # Fetch MixLots for the base components
        from products.models import Variety
        varieties = Variety.objects.filter(sku_prefix__in=base_component_skus)
        mix_lots = MixLot.objects.filter(
            variety__in=varieties
        ).select_related('variety').prefetch_related('batches')
        
        # Exclude retired mix lots
        mix_lots = mix_lots.exclude(retired_mix_info__isnull=False)
        
        available_lots = []
        for mix_lot in mix_lots:
            germ_rate = mix_lot.calculate_germ_rate(for_year=year)
            
            # Include all mix lots, even without germ rate
            total_weight = mix_lot.batches.aggregate(
                total=Sum('final_weight')
            )['total'] or 0
            
            available_lots.append({
                'id': mix_lot.id,
                'variety_name': mix_lot.variety.var_name,
                'variety_sku': mix_lot.variety.sku_prefix,
                'lot_code': mix_lot.lot_code,
                'full_lot_code': mix_lot.lot_code,  # Changed from str(mix_lot)
                'germ_rate': germ_rate,
                'status': 'active' if germ_rate else 'no_germ',
                'inventory': f"{total_weight} lbs",
                'is_mix': True  # Flag to identify this is a MixLot
            })
        
        return JsonResponse(available_lots, safe=False)
    
    # Handle regular mixes (composed of regular lots)
    # Get specific varieties from config
    sku_prefixes = config.get('varieties', [])
    lots = Lot.objects.filter(variety__sku_prefix__in=sku_prefixes)
    
    # Exclude retired lots
    lots = lots.exclude(retired_info__isnull=False)
    
    # Prefetch related data
    lots = lots.select_related('variety', 'grower').prefetch_related('germinations', 'inventory')
    
    available_lots = []
    for lot in lots:
        germ = lot.germinations.filter(status='active', for_year=year).first()
        inventory = lot.get_most_recent_inventory()
        
        # Include all non-retired lots, regardless of germ status
        available_lots.append({
            'id': lot.id,
            'variety_name': lot.variety.var_name,
            'variety_sku': lot.variety.sku_prefix,
            'lot_code': lot.get_four_char_lot_code(),
            'full_lot_code': lot.get_four_char_lot_code(),  # Changed from str(lot)
            'germ_rate': germ.germination_rate if germ else None,
            'status': germ.status if germ else 'no_germ',
            'inventory': inventory,
            'is_mix': False  # Flag to identify this is a regular Lot
        })
    
    return JsonResponse(available_lots, safe=False)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def get_existing_mix_lots(request):
    """Get all existing mix lots for a specific mix variety"""
    mix_sku = request.GET.get('mix')
    
    if not mix_sku:
        return JsonResponse({'error': 'Mix SKU required'}, status=400)
    
    try:
        variety = Variety.objects.get(sku_prefix=mix_sku)
    except Variety.DoesNotExist:
        return JsonResponse({'error': 'Variety not found'}, status=404)
    
    mix_lots = MixLot.objects.filter(variety=variety).prefetch_related('batches', 'components')
    
    lots_data = []
    for lot in mix_lots:
        is_retired = hasattr(lot, 'retired_mix_info') and lot.retired_mix_info is not None
        
        germ_rate = lot.calculate_germ_rate(for_year=settings.CURRENT_ORDER_YEAR)
        total_weight = lot.batches.aggregate(total=Sum('final_weight'))['total'] or 0
        
        lots_data.append({
            'id': lot.id,
            'lot_code': lot.lot_code,
            'germ_rate': germ_rate,
            'batch_count': lot.batches.count(),
            'total_weight': total_weight,
            'is_retired': is_retired
        })
    
    return JsonResponse(lots_data, safe=False)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def create_mix_lot(request):
    """Create a new mix lot"""
    try:
        data = json.loads(request.body)
        mix_sku = data.get('mix_sku')
        lot_code = data.get('lot_code')
        components = data.get('components')  # [{lot_id: x, parts: y}, ...]
        
        if not all([mix_sku, lot_code, components]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        variety = Variety.objects.get(sku_prefix=mix_sku)
        
        # Check if lot_code already exists for this variety
        if MixLot.objects.filter(variety=variety, lot_code=lot_code).exists():
            return JsonResponse({'error': f'Lot code {lot_code} already exists for this mix'}, status=400)
        
        # Create mix lot
        mix_lot = MixLot.objects.create(
            variety=variety,
            lot_code=lot_code
        )
        
        # Create components
        for comp in components:
            MixLotComponent.objects.create(
                mix_lot=mix_lot,
                lot_id=comp['lot_id'],
                parts=comp['parts']
            )
        
        return JsonResponse({
            'success': True,
            'mix_lot_id': mix_lot.id,
            'lot_code': lot_code,
            'germ_rate': mix_lot.get_current_germ_rate()
        })
        
    except Variety.DoesNotExist:
        return JsonResponse({'error': 'Variety not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def get_mix_lot_details(request, mix_lot_id):
    """Get detailed information about a specific mix lot"""
    try:
        mix_lot = MixLot.objects.get(id=mix_lot_id)
        
        # Get components
        components = []
        for comp in mix_lot.components.select_related('lot__variety', 'lot__grower'):
            lot = comp.lot
            germ = lot.germinations.filter(
                status='active',
                for_year=settings.CURRENT_ORDER_YEAR
            ).first()
            
            components.append({
                'variety_name': lot.variety.var_name,
                'variety_sku': lot.variety.sku_prefix,
                'lot_code': lot.get_four_char_lot_code(),
                'is_retired': hasattr(mix_lot, 'retired_mix_info') and mix_lot.retired_mix_info is not None,
                'created_date': mix_lot.created_date.strftime('%Y-%m-%d'),
                'full_lot_code': str(lot),
                'germ_rate': germ.germination_rate if germ else None,
                'parts': comp.parts
            })
        
        # Get batches
        batches = []
        for batch in mix_lot.batches.all():
            batches.append({
                'id': batch.id,
                'date': batch.date.strftime('%m/%d/%Y'),
                'final_weight': float(batch.final_weight),
                'notes': batch.notes or ''
            })
        
        return JsonResponse({
            'id': mix_lot.id,
            'variety_sku': mix_lot.variety.sku_prefix,
            'variety_name': mix_lot.variety.var_name,
            'lot_code': mix_lot.lot_code,
            'created_date': mix_lot.created_date.strftime('%m/%d/%Y'),
            'germ_rate': mix_lot.get_current_germ_rate(),
            'germ_display': mix_lot.get_germ_rate_display(),
            'is_retired': hasattr(mix_lot, 'retired_mix_info'),
            'components': components,
            'batches': batches
        })
        
    except MixLot.DoesNotExist:
        return JsonResponse({'error': 'Mix lot not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def generate_lot_code(request):
    """Generate the next available lot code for a mix"""
    mix_sku = request.GET.get('mix')
    
    if not mix_sku:
        return JsonResponse({'error': 'Mix SKU required'}, status=400)
    
    try:
        from products.models import Variety
        variety = Variety.objects.get(sku_prefix=mix_sku)
    except Variety.DoesNotExist:
        return JsonResponse({'error': 'Variety not found'}, status=404)
    
    # Get existing mix lots for this variety
    existing_lots = MixLot.objects.filter(variety=variety).values_list('lot_code', flat=True)
    
    # Get the current year (last 2 digits)
    current_year = str(settings.CURRENT_ORDER_YEAR)[-2:]
    prefix = f"UO{current_year}"
    
    # Filter lots for current year only
    current_year_lots = [lot for lot in existing_lots if lot.startswith(prefix)]
    
    if len(current_year_lots) == 0:
        # No lots for current year, start with A
        next_code = f"{prefix}A"
    else:
        # Extract the letter suffixes and find the highest
        letters = [lot[len(prefix):] for lot in current_year_lots]
        letters.sort()
        last_letter = letters[-1]
        
        # Get next letter (assuming single letter A-Z)
        next_char_code = ord(last_letter[0]) + 1
        next_letter = chr(next_char_code)
        
        next_code = f"{prefix}{next_letter}"
    
    return JsonResponse({
        'success': True,
        'lot_code': next_code
    })


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def create_batch(request):
    """Record a new batch for a mix lot"""
    try:
        data = json.loads(request.body)
        mix_lot_id = data.get('mix_lot_id')
        date = data.get('date')
        final_weight = data.get('final_weight')
        notes = data.get('notes', '')
        
        if not all([mix_lot_id, date, final_weight]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        mix_lot = MixLot.objects.get(id=mix_lot_id)
        
        batch = MixBatch.objects.create(
            mix_lot=mix_lot,
            date=date,
            final_weight=final_weight,
            notes=notes
        )
        
        return JsonResponse({
            'success': True,
            'batch_id': batch.id
        })
        
    except MixLot.DoesNotExist:
        return JsonResponse({'error': 'Mix lot not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def update_variety_growout(request, sku_prefix):
    """Update growout_needed status for a variety"""
    try:
        variety = Variety.objects.get(sku_prefix=sku_prefix)
        data = json.loads(request.body)
        
        growout_value = data.get('growout_needed', '')
        # Validate the value
        if growout_value not in ['', 'green', 'orange', 'red']:
            return JsonResponse({'error': 'Invalid growout value'}, status=400)
        
        variety.growout_needed = growout_value if growout_value else None
        variety.save()
        
        return JsonResponse({'success': True})
    except Variety.DoesNotExist:
        return JsonResponse({'error': 'Variety not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def process_pre_opening_report_v2(request):
    """
    Process uploaded CSV and generate pre-opening report
    """
    try:
        current_order_year = settings.CURRENT_ORDER_YEAR
        
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
        
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({'error': 'File must be a CSV'}, status=400)
        
        # Read entire CSV into memory
        decoded_file = csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded_file))
        
        # Store CSV data with title forward-filling
        csv_products = {}
        last_title = ""
        
        for row in csv_reader:
            sku = row.get('Variant SKU', '').strip()
            title = row.get('Title', '').strip()
            
            # Forward-fill title if blank (same variety, different variant)
            if title:
                last_title = title
            elif last_title:
                title = last_title
            
            if sku:
                csv_products[sku] = {
                    'title': title,
                    'tracker': row.get('Variant Inventory Tracker', '').strip(),
                    'qty': int(row.get('Variant Inventory Qty', '0').strip() or 0)
                }
        
        # Check 1: Products in CSV not in database
        products_not_in_db = []
        for sku, data in csv_products.items():
            if not check_product_exists(sku):
                products_not_in_db.append({
                    'sku': sku,
                    'title': data['title'],
                    'tracker': data['tracker'],
                    'qty': data['qty']
                })
        
        # Check 2: Tracked products without active germinations
        products_without_germ = []
        for sku, data in csv_products.items():
            if data['tracker'].lower() == 'shopify':
                if check_product_exists(sku) and not check_active_germination(sku, current_order_year):
                    products_without_germ.append({
                        'sku': sku,
                        'title': data['title'],
                        'qty': data['qty']
                    })
        
        # Check 3: Varieties with active germ but pkt product inventory <=0
        varieties_with_germ_but_no_inventory = []
        
        varieties_with_active_germ = Variety.objects.filter(
            lots__germinations__status='active',
            lots__germinations__for_year=current_order_year
        ).distinct()
        
        for variety in varieties_with_active_germ:
            pkt_sku = f"{variety.sku_prefix}-pkt"
            
            if pkt_sku in csv_products:
                csv_data = csv_products[pkt_sku]
                
                # Check if tracked and inventory <=0
                if csv_data['tracker'].lower() == 'shopify' and csv_data['qty'] <= 0:
                    varieties_with_germ_but_no_inventory.append({
                        'variety': variety.sku_prefix,
                        'var_name': variety.var_name or '',
                        'sku': pkt_sku,
                        'qty': csv_data['qty'],
                        'title': csv_data['title']
                    })
        
        report_data = {
            'current_order_year': current_order_year,
            'products_not_in_db': products_not_in_db,
            'products_without_germ': products_without_germ,
            'varieties_with_germ_but_no_inventory': varieties_with_germ_but_no_inventory,
            'summary': {
                'total_not_in_db': len(products_not_in_db),
                'total_without_germ': len(products_without_germ),
                'total_germ_but_no_inv': len(varieties_with_germ_but_no_inventory),
                'total_csv_products': len(csv_products)
            }
        }
        
        return JsonResponse({
            'success': True,
            'report': report_data
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


def check_product_exists(variant_sku):
    """
    Check if a product exists in either Product or MiscProduct table
    """
    # Check MiscProduct first (simpler - just match SKU)
    if MiscProduct.objects.filter(sku=variant_sku).exists():
        return True
    
    # Check Product table (need to parse SKU)
    # SKU format: PREFIX-SUFFIX (e.g., "PEA-SP-pkt")
    parts = variant_sku.rsplit('-', 1)  # Split from right, only once
    
    if len(parts) == 2:
        sku_prefix = parts[0]
        sku_suffix = parts[1]
        
        if Product.objects.filter(
            variety__sku_prefix=sku_prefix,
            sku_suffix=sku_suffix
        ).exists():
            return True
    
    return False


def check_active_germination(variant_sku, current_order_year):
    """
    Check if a product has an active germination for the current order year
    """
    # Parse SKU to get variety prefix
    parts = variant_sku.rsplit('-', 1)
    
    if len(parts) != 2:
        return False
    
    sku_prefix = parts[0]
    
    # Check if variety has any lots with active germinations for current year
    has_active_germ = Germination.objects.filter(
        lot__variety__sku_prefix=sku_prefix,
        status='active',
        for_year=current_order_year
    ).exists()
    
    return has_active_germ

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def update_variety_notes(request, sku_prefix):
    try:
        data = json.loads(request.body)
        variety = Variety.objects.get(sku_prefix=sku_prefix)
        variety.var_notes = data.get('var_notes', '')
        variety.save()
        return JsonResponse({'status': 'success', 'message': 'Notes updated successfully'})
    except Variety.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Variety not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["GET"])
def check_shopify_inventory(request, sku_prefix):
    try:
        # Get your variety by sku_prefix (the primary key)
        variety = Variety.objects.get(pk=sku_prefix)
        
        if not variety.sku_prefix:
            return JsonResponse({
                'success': False,
                'error': 'Variety has no SKU prefix'
            })
        
        # Configure Shopify session
        session = shopify.Session(
            settings.SHOPIFY_SHOP_URL,
            settings.SHOPIFY_API_VERSION,
            settings.SHOPIFY_ACCESS_TOKEN
        )
        shopify.ShopifyResource.activate_session(session)
        
        # Get ALL products using cursor-based pagination
        all_products = []
        since_id = 0
        
        while True:
            products = shopify.Product.find(limit=250, since_id=since_id)
            if not products:
                break
            all_products.extend(products)
            since_id = products[-1].id  # Get the last product's ID
            
            # Safety check to prevent infinite loops
            if len(all_products) >= 2500:
                break
        
        matching_variants = []
        
        for product in all_products:
            for variant in product.variants:
                if variant.sku and variant.sku.startswith(sku_prefix):
                    # Check if inventory is tracked
                    is_tracked = variant.inventory_management == 'shopify'
                    inventory_display = variant.inventory_quantity if is_tracked else 'No limit'
                    
                    matching_variants.append({
                        'product_title': product.title,
                        'variant_title': variant.title,
                        'sku': variant.sku,
                        'inventory_quantity': inventory_display,
                        'is_tracked': is_tracked,
                        'price': str(variant.price)
                    })
        
        shopify.ShopifyResource.clear_session()
        
        if not matching_variants:
            return JsonResponse({
                'success': False,
                'error': f'No products found with SKU prefix "{sku_prefix}"'
            })
        
        return JsonResponse({
            'success': True,
            'sku_prefix': sku_prefix,
            'variants': matching_variants,
            'total_found': len(matching_variants),
            'website_bulk': variety.website_bulk
        })
        
    except Variety.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Variety not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    finally:
        if shopify.ShopifyResource.site:
            shopify.ShopifyResource.clear_session()
# def check_shopify_inventory(request, sku_prefix):
#     try:
#         # Get your variety by sku_prefix (the primary key)
#         variety = Variety.objects.get(pk=sku_prefix)
        
#         if not variety.sku_prefix:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Variety has no SKU prefix'
#             })
        
#         # Configure Shopify session
#         session = shopify.Session(
#             settings.SHOPIFY_SHOP_URL,
#             settings.SHOPIFY_API_VERSION,
#             settings.SHOPIFY_ACCESS_TOKEN
#         )
#         shopify.ShopifyResource.activate_session(session)
        
#         # Get all products and filter by variant SKU prefix
#         all_products = []
#         page = 1
#         max_pages = 10  # This would get up to 2500 products
#         while page <= max_pages:
#             products = shopify.Product.find(limit=250, page=page)
#             if not products:
#                 break
#             all_products.extend(products)
#             page += 1
        
#         matching_variants = []
        
#         for product in all_products:
#             for variant in product.variants:
#                 if variant.sku and variant.sku.startswith(sku_prefix):
#                     # Check if inventory is tracked
#                     is_tracked = variant.inventory_management == 'shopify'
#                     inventory_display = variant.inventory_quantity if is_tracked else 'No limit'
                    
#                     matching_variants.append({
#                         'product_title': product.title,
#                         'variant_title': variant.title,
#                         'sku': variant.sku,
#                         'inventory_quantity': inventory_display,
#                         'is_tracked': is_tracked,
#                         'price': str(variant.price)
#                     })
        
#         shopify.ShopifyResource.clear_session()
        
#         if not matching_variants:
#             return JsonResponse({
#                 'success': False,
#                 'error': f'No products found with SKU prefix "{sku_prefix}"'
#             })
        
#         return JsonResponse({
#             'success': True,
#             'sku_prefix': sku_prefix,
#             'variants': matching_variants,
#             'total_found': len(matching_variants),
#             'website_bulk': variety.website_bulk
#         })
        
#     except Variety.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Variety not found'
#         }, status=404)
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         }, status=500)
#     finally:
#         if shopify.ShopifyResource.site:
#             shopify.ShopifyResource.clear_session()
# def check_shopify_inventory(request, sku_prefix):
#     try:
#         # Get your variety by sku_prefix (the primary key)
#         variety = Variety.objects.get(pk=sku_prefix)
        
#         if not variety.sku_prefix:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Variety has no SKU prefix'
#             })
        
#         # Configure Shopify session
#         session = shopify.Session(
#             settings.SHOPIFY_SHOP_URL,
#             settings.SHOPIFY_API_VERSION,
#             settings.SHOPIFY_ACCESS_TOKEN
#         )
#         shopify.ShopifyResource.activate_session(session)
        
#         # Get all products and filter by variant SKU prefix
#         all_products = shopify.Product.find(limit=250)
        
#         matching_variants = []
        
#         for product in all_products:
#             for variant in product.variants:
#                 if variant.sku and variant.sku.startswith(sku_prefix):
#                     matching_variants.append({
#                         'product_title': product.title,
#                         'variant_title': variant.title,
#                         'sku': variant.sku,
#                         'inventory_quantity': variant.inventory_quantity,
#                         'price': str(variant.price)
#                     })
        
#         shopify.ShopifyResource.clear_session()
        
#         if not matching_variants:
#             return JsonResponse({
#                 'success': False,
#                 'error': f'No products found with SKU prefix "{sku_prefix}"'
#             })
        
#         return JsonResponse({
#             'success': True,
#             'sku_prefix': sku_prefix,
#             'variants': matching_variants,
#             'total_found': len(matching_variants),
#             'website_bulk': variety.website_bulk  # Add this line
#         })
        
#     except Variety.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Variety not found'
#         }, status=404)
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         }, status=500)
#     finally:
#         if shopify.ShopifyResource.site:
#             shopify.ShopifyResource.clear_session()
# def check_shopify_inventory(request, sku_prefix):
#     try:
#         # Get your variety by sku_prefix (the primary key)
#         variety = Variety.objects.get(sku_prefix=sku_prefix)
        
#         if not variety.sku_prefix:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Variety has no SKU prefix'
#             })
        
#         # Configure Shopify session
#         session = shopify.Session(
#             settings.SHOPIFY_SHOP_URL,
#             settings.SHOPIFY_API_VERSION,
#             settings.SHOPIFY_ACCESS_TOKEN
#         )
#         shopify.ShopifyResource.activate_session(session)
        
#         # Get all products and filter by variant SKU prefix
#         all_products = shopify.Product.find(limit=250)
        
#         matching_variants = []
        
#         for product in all_products:
#             for variant in product.variants:
#                 if variant.sku and variant.sku.startswith(sku_prefix):
#                     matching_variants.append({
#                         'product_title': product.title,
#                         'variant_title': variant.title,
#                         'sku': variant.sku,
#                         'inventory_quantity': variant.inventory_quantity,
#                         'price': str(variant.price)
#                     })
        
#         shopify.ShopifyResource.clear_session()
        
#         if not matching_variants:
#             return JsonResponse({
#                 'success': False,
#                 'error': f'No products found with SKU prefix "{sku_prefix}"'
#             })
        
#         return JsonResponse({
#             'success': True,
#             'sku_prefix': sku_prefix,
#             'variants': matching_variants,
#             'total_found': len(matching_variants)
#         })
        
#     except Variety.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Variety not found'
#         }, status=404)
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         }, status=500)
#     finally:
#         if shopify.ShopifyResource.site:
#             shopify.ShopifyResource.clear_session()
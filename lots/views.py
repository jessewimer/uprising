# from datetime import timezone
from django.utils import timezone 
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from uprising.utils.auth import is_employee
from .models import Lot, GerminationBatch, Germination, Grower, Growout, GrowoutPrep
import json
from django.views.decorators.http import require_http_methods
from products.models import Variety
from datetime import datetime
from django.db.models import Q
from django.conf import settings 


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def send_germ_samples(request):
    # Get all batches with their data (no ordering limit)
    batches = []
    germination_batches = GerminationBatch.objects.all().order_by('-id')  # Show all, most recent first
   
    for batch in germination_batches:
        germinations = batch.germinations.select_related(
            'lot__variety', 'lot__grower'
        ).all()
       
        # Status based on date: if date is None, it's pending; if date exists, it's sent
        status = 'pending' if batch.date is None else 'sent'
        
        batch_data = {
            'id': batch.id,
            'batch_number': batch.batch_number,
            'date': batch.date.strftime('%Y-%m-%d') if batch.date else None,
            'tracking_number': batch.tracking_number or '',
            'status': status,
       
            'germinations': [
                {
                    'id': g.id,
                    'barcode': f"{g.lot.variety.sku_prefix}-{g.lot.grower.code if g.lot.grower else 'UNK'}{g.lot.year}",
                    'sku_prefix': g.lot.variety.sku_prefix,
                    'lot_code': f"{g.lot.grower.code if g.lot.grower else 'UNK'}{g.lot.year}",
                    'variety_name': g.lot.variety.var_name,
                    'crop_name': g.lot.variety.crop if g.lot.variety.crop else 'Unknown',
                    'germination_rate': g.germination_rate,  # ADD THIS LINE
                    'scan_time': 'Previously scanned'  # Since we don't track individual scan times
                } for g in germinations
            ]
            
        }
        batches.append(batch_data)
   
    # Get all possible lots for scanning lookup
    lots_data = {}
    lots = Lot.objects.select_related('variety', 'grower').all()
    
    for lot in lots:
        barcode = f"{lot.variety.sku_prefix}-{lot.grower.code if lot.grower else 'UNK'}{lot.year}"
        lots_data[barcode] = {
            'sku_prefix': lot.variety.sku_prefix,
            'lot_code': f"{lot.grower.code if lot.grower else 'UNK'}{lot.year}",
            'variety_name': lot.variety.var_name,
            'crop_name': lot.variety.crop if lot.variety.crop else 'Unknown',
            'lot_id': lot.id,
        }
    
    context = {
        'batches_json': json.dumps(batches),
        'lots_json': json.dumps(lots_data),
    }
   
    return render(request, 'lots/germ_samples.html', context)


@login_required(login_url='/office/login/')
@require_http_methods(["POST"])
@user_passes_test(is_employee)
def create_new_batch(request):
    """Create a new germination batch"""
    try:
        # Check if there's already a pending batch (date is None)
        pending_batch = GerminationBatch.objects.filter(date__isnull=True).first()
        if pending_batch:
            return JsonResponse({
                'success': False, 
                'error': 'There is already a pending batch. Please complete it first.'
            })
        
        # Generate next batch number
        last_batch = GerminationBatch.objects.all().order_by('-id').first()
        if last_batch:
            try:
                last_number = int(last_batch.batch_number)
                new_number = str(last_number + 1).zfill(3)
            except ValueError:
                new_number = '001'
        else:
            new_number = '001'
        
        # Create new batch with NO DATE (this makes it pending)
        new_batch = GerminationBatch(batch_number=new_number)
        new_batch.save()
        
        return JsonResponse({
            'success': True,
            'batch': {
                'id': new_batch.id,
                'batch_number': new_batch.batch_number,
                'date': None,  # No date for pending batches
                'status': 'pending'
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
@login_required(login_url='/office/login/')
@require_http_methods(["POST"])
@user_passes_test(is_employee)
def submit_batch(request):
    """Submit completed batch to database"""
    
    try:
        print(f"=== submit_batch called by user: {request.user} ===")
        
        data = json.loads(request.body)
        print(f"Request data: {data}")
        
        batch_id = data.get('batch_id')
        sample_ids = data.get('sample_ids', [])  # Array of lot_ids
        tracking_number = data.get('tracking_number', '').strip()
        for_year = data.get('for_year')  # This will be the 2-digit year (e.g., 25)
        
        print(f"Parsed: batch_id={batch_id}, sample_ids={sample_ids}, tracking={tracking_number}, year={for_year}")
        
        if not batch_id:
            print("ERROR: No batch_id provided")
            return JsonResponse({'success': False, 'error': 'No batch ID provided'})
            
        if not sample_ids:
            print("ERROR: No sample_ids provided")
            return JsonResponse({'success': False, 'error': 'No sample IDs provided'})
            
        if not for_year:
            print("ERROR: No for_year provided")
            return JsonResponse({'success': False, 'error': 'No year provided'})
        
        try:
            batch = GerminationBatch.objects.get(id=batch_id)
            print(f"Found batch: {batch} (ID: {batch.id})")
        except GerminationBatch.DoesNotExist:
            print(f"ERROR: Batch {batch_id} does not exist")
            return JsonResponse({'success': False, 'error': f'Batch {batch_id} not found'})
        
        # Verify batch is still pending (has no date)
        if batch.date is not None:
            print("ERROR: Batch already submitted")
            return JsonResponse({'success': False, 'error': 'Batch has already been submitted'})
        
        # Create germination entries for each scanned sample
        created_germinations = []
        print(f"Processing {len(sample_ids)} sample IDs...")
        
        for lot_id in sample_ids:
            print(f"Processing lot_id: {lot_id}")
            
            try:
                lot = Lot.objects.get(id=lot_id)
                print(f"Found lot: {lot} (ID: {lot.id})")
                
                germination, created = Germination.objects.get_or_create(
                    lot=lot,
                    batch=batch,
                    defaults={
                        'status': 'pending',
                        'germination_rate': 0,
                        'for_year': for_year
                    }
                )
                
                if created:
                    print(f"✓ Created new germination: {germination} (ID: {germination.id})")
                    created_germinations.append(germination)
                else:
                    print(f"→ Germination already exists: {germination} (ID: {germination.id})")
                    # Update the for_year in case it changed
                    germination.for_year = for_year
                    germination.save()
                    
            except Lot.DoesNotExist:
                print(f"ERROR: Lot {lot_id} does not exist")
                return JsonResponse({'success': False, 'error': f'Lot {lot_id} not found'})
        
        print(f"Created {len(created_germinations)} new germinations")
        
        # Update batch with submission details - SET THE DATE NOW (this marks it as sent)
        batch.date = timezone.now().date()  # THIS is what changes status from pending to sent
        if tracking_number:
            batch.tracking_number = tracking_number
        batch.save()
        
        print(f"Updated batch: date set to {batch.date}, tracking={batch.tracking_number}")
        
        # Verify germinations were created
        total_germinations = batch.germinations.count()
        print(f"Total germinations in batch now: {total_germinations}")
        
        for germ in batch.germinations.all():
            print(f"  - {germ.lot.variety.var_name} ({germ.lot.variety.sku_prefix}) - Lot: {germ.lot.grower.code if germ.lot.grower else 'UNK'}{germ.lot.year} - Status: {germ.status}")
        
        print("=== submit_batch completed successfully ===")
        
        return JsonResponse({
            'success': True, 
            'germinations_created': len(created_germinations),
            'total_germinations': total_germinations
        })
        
    except Exception as e:
        print(f"EXCEPTION in submit_batch: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})
    
# Update your existing process_orders and view_stores views if needed:
@login_required(login_url='/office/login/')
def inventory(request):
    context = {}

    # Point to lots app template if that's where it's located
    return render(request, 'lots/inventory.html', context)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def growouts(request):
    # Define SKU prefixes to exclude
    excluded_sku_prefixes = ['FLO-ED', 'CAR-RA', 'MIX-BR', 'MIX-MI', 'MIX-SP', 'LET-MX', 'BEE-3B']
    
    # Get year parameter from URL, default to current year
    selected_year_param = request.GET.get('year')
    current_year = datetime.now().year
   
    if selected_year_param:
        try:
            selected_year_4digit = int(selected_year_param)
            # Convert 4-digit year back to 2-digit for database query
            selected_year = selected_year_4digit - 2000 if selected_year_4digit >= 2000 else selected_year_4digit
        except (ValueError, TypeError):
            selected_year = current_year - 2000  # Convert current year to 2-digit
    else:
        selected_year = current_year - 2000  # Convert current year to 2-digit
   
    # Get available years from existing lots, excluding specified sku_prefixes
    raw_years = (Lot.objects
                .exclude(variety__sku_prefix__in=excluded_sku_prefixes)
                .values_list('year', flat=True)
                .distinct()
                .order_by('-year'))
    
    # Convert 2-digit years to 4-digit years for display
    available_years = [year + 2000 if year < 100 else year for year in raw_years]
    
    growers = {g.code: g.name for g in Grower.objects.all()}
    
    # Query lots for the selected year (using 2-digit year for database)
    lots = (Lot.objects
            .filter(year=selected_year)  # Now uses 2-digit year
            .exclude(variety__sku_prefix__in=excluded_sku_prefixes)
            .select_related(
                'variety',
                'growout_info'
            )
            .order_by(
                'variety__category',
                'variety__sku_prefix',
                'variety__var_name',
                'grower'
            ))
   
    current_for_year = getattr(settings, 'FOR_YEAR', None)

    # Add inventory status as a dynamic attribute to each lot
    for lot in lots:
        lot.has_inventory_status = lot.has_inventory() 
        # Check if lot has germination for current FOR_YEAR
        lot_germ_year = lot.get_most_recent_sent_germ()
        lot.has_germination_for_year = lot_germ_year == current_for_year

    context = {
        'lots': lots,
        'available_years': available_years,
        'current_year': selected_year + 2000,  # Display as 4-digit
        'selected_year': selected_year,
        'growers': growers,
    }
   
    return render(request, 'lots/growouts.html', context)

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
def update_growout(request, lot_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lot = Lot.objects.get(id=lot_id)
            
            # Get or create growout info
            growout, created = Growout.objects.get_or_create(lot=lot)
            
            # Update fields
            growout.planted_date = data.get('planted_date', '')
            growout.transplant_date = data.get('transplant_date', '')
            growout.quantity = data.get('quantity', '')
            growout.price_per_lb = data.get('price_per_lb', '')
            growout.bed_ft = data.get('bed_ft', '')
            growout.amt_sown = data.get('amt_sown', '')
            growout.notes = data.get('notes', '')
            
            growout.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def growout_prep(request):
    # Get all varieties with orange or red growout_needed
    base_varieties = Variety.objects.filter(
        growout_needed__in=['orange', 'red']
    ).order_by('category', 'crop', 'var_name')
    
    # Build enhanced variety list with prep data
    varieties_with_prep = []
    for variety in base_varieties:
        # Get existing prep records for this variety
        existing_preps = variety.growout_preps.all()
        
        if existing_preps.exists():
            # Add each existing prep record as a separate row
            for idx, prep in enumerate(existing_preps):
                # Row is locked if a lot has been created
                is_locked = prep.created_lot is not None
                
                variety_data = {
                    'id': variety.sku_prefix,
                    'var_name': variety.var_name,
                    'sku_prefix': variety.sku_prefix,
                    'category': variety.category or '',
                    'crop': variety.crop or '',
                    'growout_needed': variety.growout_needed,
                    'prep_id': prep.id,
                    'assigned_grower': prep.grower,
                    'prep_year': prep.year,
                    'prep_quantity': prep.quantity or '',
                    'prep_price': prep.price_per_lb or '',
                    'lot_created': prep.lot_created,
                    'is_first_row': idx == 0,
                    'is_locked': is_locked,  # New field
                    'created_lot_code': prep.created_lot.build_lot_code() if prep.created_lot else None,
                }
                varieties_with_prep.append(variety_data)
        else:
            # No prep records yet - show empty row
            variety_data = {
                'id': variety.sku_prefix,
                'var_name': variety.var_name,
                'sku_prefix': variety.sku_prefix,
                'category': variety.category or '',
                'crop': variety.crop or '',
                'growout_needed': variety.growout_needed,
                'prep_id': None,
                'assigned_grower': None,
                'prep_year': settings.CURRENT_ORDER_YEAR,
                'prep_quantity': '',
                'prep_price': '',
                'lot_created': False,
                'is_first_row': True,
                'is_locked': False,  # New field
                'created_lot_code': None,
            }
            varieties_with_prep.append(variety_data)
    
    # Get all growers, sorted with Uprising first, then alphabetically
    growers = Grower.objects.all()
    uprising_grower = growers.filter(code='UO').first()
    other_growers = growers.exclude(code='UO').order_by('name')
    
    sorted_growers = []
    if uprising_grower:
        sorted_growers.append(uprising_grower)
    sorted_growers.extend(other_growers)
    
    # Get unique categories and crops for filters
    categories = Variety.objects.filter(
        growout_needed__in=['orange', 'red']
    ).values_list('category', flat=True).distinct().order_by('category')
    
    crops = Variety.objects.filter(
        growout_needed__in=['orange', 'red']
    ).values_list('crop', flat=True).distinct().order_by('crop')
    
    context = {
        'varieties': varieties_with_prep,
        'growers': sorted_growers,
        'current_order_year': settings.CURRENT_ORDER_YEAR,
        'categories': [c for c in categories if c],
        'crops': [c for c in crops if c],
    }
    
    return render(request, 'lots/growout_prep.html', context)


@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def save_growout_prep(request):
    """Save or update growout prep records and create lots as needed"""
    try:
        data = json.loads(request.body)
        records = data.get('records', [])
        
        saved_records = []
        created_lots = []
        errors = []
        
        for record in records:
            sku_prefix = record.get('variety_id')
            prep_id = record.get('prep_id')
            is_locked = record.get('is_locked', False)
            
            try:
                if prep_id:
                    # Update existing
                    prep = GrowoutPrep.objects.get(id=prep_id)
                else:
                    # Create new
                    prep = GrowoutPrep(variety_id=sku_prefix)
                
                # Always update qty and price
                prep.quantity = record.get('quantity', '')
                prep.price_per_lb = record.get('price_per_lb') or None
                
                # Only update grower/year/lot if NOT locked
                if not is_locked:
                    if record.get('grower_code'):
                        prep.grower_id = record['grower_code']
                    prep.year = record.get('year')
                    
                    lot_should_be_created = record.get('lot_created', False)
                    
                    # Handle lot creation
                    if lot_should_be_created and not prep.created_lot:
                        # User wants to create a lot and one doesn't exist yet
                        
                        # Validate required fields
                        if not prep.grower_id:
                            errors.append(f"Cannot create lot for {prep.variety.var_name}: No grower assigned")
                            continue
                        
                        # Check if lot already exists with these parameters
                        existing_lot = Lot.objects.filter(
                            variety_id=sku_prefix,
                            grower_id=prep.grower_id,
                            year=prep.year % 100,  # Convert to 2-digit year
                            harvest__isnull=True
                        ).first()
                        
                        if existing_lot:
                            # Lot already exists, just link it
                            prep.created_lot = existing_lot
                            prep.lot_created = True
                        else:
                            # Create new lot
                            new_lot = Lot.objects.create(
                                variety_id=sku_prefix,
                                grower_id=prep.grower_id,
                                year=prep.year % 100,  # 2-digit year
                                harvest=None
                            )
                            prep.created_lot = new_lot
                            prep.lot_created = True
                            created_lots.append({
                                'lot_code': new_lot.build_lot_code(),
                                'variety': prep.variety.var_name
                            })
                    else:
                        # Just update the boolean
                        prep.lot_created = lot_should_be_created
                
                prep.save()
                saved_records.append({
                    'prep_id': prep.id,
                    'variety_id': prep.variety_id,
                    'lot_created': prep.lot_created,
                    'created_lot_id': prep.created_lot_id if prep.created_lot else None
                })
            
            except Exception as e:
                errors.append(f"Error saving {sku_prefix}: {str(e)}")
                continue
        
        response_data = {
            'success': True,
            'saved_records': saved_records,
            'created_lots': created_lots
        }
        
        if errors:
            response_data['errors'] = errors
        
        return JsonResponse(response_data)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    

@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def add_growout_prep_row(request):
    """Add a new prep row for an existing variety"""
    try:
        data = json.loads(request.body)
        sku_prefix = data.get('variety_id')  # This will be sku_prefix
        
        # Create new blank prep record
        prep = GrowoutPrep.objects.create(
            variety_id=sku_prefix,
            year=settings.CURRENT_ORDER_YEAR
        )
        
        return JsonResponse({
            'success': True,
            'prep_id': prep.id,
            'year': prep.year
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
@login_required(login_url='/office/login/')
@user_passes_test(is_employee)
@require_http_methods(["POST"])
def delete_growout_prep_row(request):
    """Delete a growout prep record"""
    try:
        data = json.loads(request.body)
        prep_id = data.get('prep_id')
        
        if not prep_id:
            return JsonResponse({
                'success': False,
                'error': 'No prep_id provided'
            }, status=400)
        
        # Get and delete the prep record
        prep = GrowoutPrep.objects.get(id=prep_id)
        prep.delete()
        
        return JsonResponse({
            'success': True
        })
    
    except GrowoutPrep.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Record not found'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
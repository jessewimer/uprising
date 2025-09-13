# from datetime import timezone
from django.utils import timezone 
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from uprising.utils.auth import is_employee
from .models import Lot, GerminationBatch, Germination
import json
from django.views.decorators.http import require_http_methods
from products.models import Variety

@login_required
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
                    'crop_name': g.lot.variety.veg_type if g.lot.variety.veg_type else 'Unknown',
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
            'crop_name': lot.variety.veg_type if lot.variety.veg_type else 'Unknown',
            'lot_id': lot.id,
        }
    
    context = {
        'batches_json': json.dumps(batches),
        'lots_json': json.dumps(lots_data),
    }
   
    return render(request, 'lots/germ_samples.html', context)


@login_required
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
    
    
@login_required
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
@login_required
def inventory(request):
    context = {}

    # Point to lots app template if that's where it's located
    return render(request, 'lots/inventory.html', context)


def growouts(request):
    context = {}
    return render(request, 'lots/growouts.html', context)
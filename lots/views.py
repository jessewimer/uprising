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
    # Get all batches with their data
    batches = []
    germination_batches = GerminationBatch.objects.all().order_by('-date')
   
    for batch in germination_batches:
        germinations = batch.germinations.select_related(
            'lot__variety', 'lot__grower'  # Remove __veg_type since it's not a foreign key
        ).all()
       
        batch_data = {
            'id': batch.id,
            'batch_number': batch.batch_number,
            'date': batch.date.strftime('%Y-%m-%d'),
            'tracking_number': batch.tracking_number,
            'status': 'sent' if batch.tracking_number else 'pending',
            'germinations': [
                {
                    'barcode': f"{g.lot.variety.sku_prefix}-{g.lot.grower.code if g.lot.grower else 'UNK'}{g.lot.year}",
                    'sku_prefix': g.lot.variety.sku_prefix,
                    'lot_code': f"{g.lot.grower.code if g.lot.grower else 'UNK'}{g.lot.year}",
                    'variety_name': g.lot.variety.var_name,
                    'crop_name': g.lot.variety.veg_type if g.lot.variety.veg_type else 'Unknown',
                } for g in germinations
            ]
        }
        batches.append(batch_data)
   
    # Get all possible lots for scanning lookup
    lots_data = {}
    lots = Lot.objects.select_related('variety', 'grower').all()  # Remove __veg_type here too
    
    for lot in lots:
        barcode = f"{lot.variety.sku_prefix}-{lot.grower.code if lot.grower else 'UNK'}{lot.year}"
        lots_data[barcode] = {
            'sku_prefix': lot.variety.sku_prefix,
            'lot_code': f"{lot.grower.code if lot.grower else 'UNK'}{lot.year}",
            'variety_name': lot.variety.var_name,
            'crop_name': lot.variety.veg_type if lot.variety.veg_type else 'Unknown',
            'lot_id': lot.id,  # You'll need this for the submit_batch function
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
        # Check if there's already a pending batch
        pending_batch = GerminationBatch.objects.filter(tracking_number__isnull=True).first()
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
        
        # Create new batch
        new_batch = GerminationBatch.objects.create(batch_number=new_number)
        
        return JsonResponse({
            'success': True,
            'batch': {
                'id': new_batch.id,
                'batch_number': new_batch.batch_number,
                'date': new_batch.date.strftime('%Y-%m-%d'),
                'status': 'pending'
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
# Keep this for when they submit the final batch
@login_required
@require_http_methods(["POST"])
@user_passes_test(is_employee)
def submit_batch(request):
    """Submit completed batch to database"""
    try:
        data = json.loads(request.body)
        batch_id = data.get('batch_id')
        sample_ids = data.get('sample_ids', [])  # Array of lot_ids
        tracking_number = data.get('tracking_number', '').strip()  # New tracking number field
        
        batch = GerminationBatch.objects.get(id=batch_id)
        
        # Create germination entries for each scanned sample
        for lot_id in sample_ids:
            lot = Lot.objects.get(id=lot_id)
            Germination.objects.get_or_create(
                lot=lot,
                batch=batch,
                defaults={
                    'status': 'pending',
                    'germination_rate': 0,
                    'for_year': lot.year
                }
            )
        
        # Update batch with submission details
        batch.date = timezone.now().date()  # Set to current date
        if tracking_number:
            batch.tracking_number = tracking_number
        batch.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# Update your existing process_orders and view_stores views if needed:
@login_required
def inventory(request):
    context = {}

    # Point to lots app template if that's where it's located
    return render(request, 'lots/inventory.html', context)
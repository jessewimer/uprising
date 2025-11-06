import os
import django
import csv
import sys
from django.db import transaction
from datetime import datetime
from django.utils import timezone

# Get the current directory path
current_path = os.path.dirname(os.path.abspath(__file__))

# Get the project directory path by going up two levels from the current directory
project_path = os.path.abspath(os.path.join(current_path, '..'))

# Add the project directory to the sys.path
sys.path.append(project_path)

# Set the DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
django.setup()
from lots.models import Grower, Lot, StockSeed, Inventory, GermSamplePrint, Germination, GerminationBatch
from products.models import Variety

def import_stock_seed(csv_file, dry_run=False):
    created = 0
    updated = 0
    skipped = 0
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be saved to database\n")
    else:
        print("💾 LIVE MODE - Changes will be saved to database\n")
    
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku_prefix = row.get("sku_prefix", "").strip()
            lot_code = row.get("Lot", "").strip()
            date_str = row.get("Date", "").strip()
            amt = row.get("Amt", "").strip()
            notes = row.get("Notes", "").strip() or None
            
            # Validate required fields
            if not sku_prefix or not lot_code or not date_str:
                print(f"⚠️ Skipping row, missing required fields: {row}")
                skipped += 1
                continue
            
            # Parse lot code (format: GGYY or GGYYA where A is harvest letter)
            if len(lot_code) < 4:
                print(f"⚠️ Skipping row, invalid lot code '{lot_code}': {row}")
                skipped += 1
                continue
            
            grower_code = lot_code[:2]
            year = int(lot_code[2:4])
            harvest = lot_code[4:5] if len(lot_code) > 4 else None
            
            # Look up the variety by sku_prefix
            try:
                variety = Variety.objects.get(sku_prefix=sku_prefix)
            except Variety.DoesNotExist:
                print(f"⚠️ Skipping row, variety not found for sku_prefix '{sku_prefix}': {row}")
                skipped += 1
                continue
            
            # Look up the grower
            try:
                grower = Grower.objects.get(code=grower_code)
            except Grower.DoesNotExist:
                print(f"⚠️ Skipping row, grower not found for code '{grower_code}': {row}")
                skipped += 1
                continue
            
            # Look up the lot
            try:
                lot = Lot.objects.get(
                    variety=variety,
                    grower=grower,
                    year=year,
                    harvest=harvest
                )
            except Lot.DoesNotExist:
                print(f"⚠️ Skipping row, lot not found for {sku_prefix}-{lot_code}: {row}")
                skipped += 1
                continue
            
            # Parse date (assuming format MM/DD/YYYY or YYYY-MM-DD)
            try:
                # Try multiple date formats
                for date_format in ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"]:
                    try:
                        parsed_date = datetime.strptime(date_str, date_format).date()
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Unable to parse date: {date_str}")
            except ValueError as e:
                print(f"⚠️ Skipping row, invalid date '{date_str}': {row}")
                skipped += 1
                continue
            
            # Check if record already exists
            existing = StockSeed.objects.filter(lot=lot, date=parsed_date).first()
            
            if dry_run:
                # Just report what would happen
                if existing:
                    print(f"🔄 Would UPDATE: {sku_prefix}-{lot_code} | Date: {parsed_date} | Qty: {existing.qty} → {amt}")
                    updated += 1
                else:
                    print(f"✨ Would CREATE: {sku_prefix}-{lot_code} | Date: {parsed_date} | Qty: {amt}")
                    created += 1
            else:
                # Actually create or update in database
                stock_seed, is_created = StockSeed.objects.update_or_create(
                    lot=lot,
                    date=parsed_date,
                    defaults={
                        "qty": amt,
                        "notes": notes,
                    }
                )
                
                if is_created:
                    print(f"✅ CREATED: {sku_prefix}-{lot_code} | Date: {parsed_date} | Qty: {amt}")
                    created += 1
                else:
                    print(f"♻️ UPDATED: {sku_prefix}-{lot_code} | Date: {parsed_date} | Qty: {amt}")
                    updated += 1
    
    print(f"\n{'=' * 60}")
    if dry_run:
        print(f"🔍 DRY RUN SUMMARY:")
    else:
        print(f"💾 IMPORT SUMMARY:")
    print(f"  ✨ Created: {created}")
    print(f"  ♻️ Updated: {updated}")
    print(f"  ⚠️ Skipped: {skipped}")
    print(f"{'=' * 60}")
    
    if dry_run:
        print("\n💡 To save these changes, run with dry_run=False")

if __name__ == "__main__":
    csv_file_path = os.path.join(current_path, "stock_seed.csv")
    import_stock_seed(csv_file_path)
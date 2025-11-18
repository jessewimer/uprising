import os
import django
import csv
import sys
from django.db import transaction
from datetime import datetime
# import time
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

from products.models import Product, Sales, MiscProduct, MiscSales

# Define prefixes that indicate misc products
MISC_PRODUCT_PREFIXES = ["TOO", "BEA-MF", "GIF", "TOM-CH-pkts", "gift", "SFA", "MER", "SGB", "PEA-SP-pkts"]

def import_sales_2025(csv_file, year=25, wholesale=False, dry_run=False):
    """
    Import sales data from CSV file.
    
    CSV format: SKU, QTY
    SKU format: XXX-XX-suffix (e.g., BEA-RN-pkt, CAR-DR-250s)
    Special: SKUs starting with TOO, BEA-MF, GIF, TOM-CH-pkts, gift, SFA, or MER go to MiscSales
    """
    created = 0
    updated = 0
    skipped = 0
    misc_created = 0
    misc_updated = 0
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be saved to database\n")
    else:
        print("💾 LIVE MODE - Changes will be saved to database\n")
    
    print(f"📅 Importing sales for year: {year}")
    print(f"🏪 Wholesale: {'Yes' if wholesale else 'No (Retail)'}\n")
    
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header row
            # sleep for 1 second
            
            # time.sleep(1)
            
            sku = row.get("SKU", "").strip()
            qty_str = row.get("QTY", "").strip()
            
            # Validate required fields
            if not sku or not qty_str:
                print(f"⚠️ Row {row_num}: Skipping, missing required fields: {row}")
                skipped += 1
                continue
            
            # Parse quantity
            try:
                qty = int(qty_str)
            except ValueError:
                print(f"⚠️ Row {row_num}: Skipping, invalid quantity '{qty_str}': {row}")
                skipped += 1
                continue
            
            # Skip if quantity is 0
            if qty == 0:
                print(f"⏭️ Row {row_num}: Skipping, quantity is 0: {sku}")
                skipped += 1
                continue
            
            # Check if this is a misc product
            is_misc = any(sku.startswith(prefix) for prefix in MISC_PRODUCT_PREFIXES)
            
            if is_misc:
                # Handle misc product
                try:
                    misc_product = MiscProduct.objects.get(sku=sku)
                except MiscProduct.DoesNotExist:
                    print(f"⚠️ Row {row_num}: Skipping, misc product not found for SKU '{sku}'")
                    skipped += 1
                    continue
                
                # Check if misc sales record already exists
                existing = MiscSales.objects.filter(
                    product=misc_product,
                    year=year
                ).first()
                
                if dry_run:
                    if existing:
                        print(f"🔄 Row {row_num}: Would UPDATE (MISC): {sku} | Qty: {existing.quantity} → {qty}")
                        misc_updated += 1
                    else:
                        print(f"✨ Row {row_num}: Would CREATE (MISC): {sku} | Qty: {qty}")
                        misc_created += 1
                else:
                    if existing:
                        existing.quantity = qty
                        existing.save()
                        print(f"♻️ Row {row_num}: UPDATED (MISC): {sku} | Qty: {qty}")
                        misc_updated += 1
                    else:
                        MiscSales.objects.create(
                            product=misc_product,
                            quantity=qty,
                            year=year
                        )
                        print(f"✅ Row {row_num}: CREATED (MISC): {sku} | Qty: {qty}")
                        misc_created += 1
            else:
                # Handle regular product
                # Parse SKU: XXX-XX-suffix
                sku_parts = sku.split("-")
                if len(sku_parts) < 3:
                    print(f"⚠️ Row {row_num}: Skipping, invalid SKU format '{sku}' (expected XXX-XX-suffix): {row}")
                    skipped += 1
                    continue
                
                # sku_prefix is first two parts joined with dash
                sku_prefix = f"{sku_parts[0]}-{sku_parts[1]}"
                # sku_suffix is everything after the second dash
                sku_suffix = "-".join(sku_parts[2:])
                
                # Look up the product
                try:
                    product = Product.objects.get(
                        variety__sku_prefix=sku_prefix,
                        sku_suffix=sku_suffix
                    )
                except Product.DoesNotExist:
                    print(f"⚠️ Row {row_num}: Skipping, product not found for SKU '{sku}' (prefix: {sku_prefix}, suffix: {sku_suffix})")
                    skipped += 1
                    continue
                except Product.MultipleObjectsReturned:
                    print(f"⚠️ Row {row_num}: Skipping, multiple products found for SKU '{sku}' (prefix: {sku_prefix}, suffix: {sku_suffix})")
                    skipped += 1
                    continue
                
                # Check if sales record already exists
                existing = Sales.objects.filter(
                    product=product,
                    year=year,
                    wholesale=wholesale
                ).first()
                
                if dry_run:
                    if existing:
                        print(f"🔄 Row {row_num}: Would UPDATE: {sku} | Qty: {existing.quantity} → {qty}")
                        updated += 1
                    else:
                        print(f"✨ Row {row_num}: Would CREATE: {sku} | Qty: {qty}")
                        created += 1
                else:
                    if existing:
                        existing.quantity = qty
                        existing.save()
                        print(f"♻️ Row {row_num}: UPDATED: {sku} | Qty: {qty}")
                        updated += 1
                    else:
                        Sales.objects.create(
                            product=product,
                            quantity=qty,
                            year=year,
                            wholesale=wholesale
                        )
                        print(f"✅ Row {row_num}: CREATED: {sku} | Qty: {qty}")
                        created += 1
    
    print(f"\n{'=' * 60}")
    if dry_run:
        print(f"🔍 DRY RUN SUMMARY:")
    else:
        print(f"💾 IMPORT SUMMARY:")
    print(f"  Regular Products:")
    print(f"    ✨ Created: {created}")
    print(f"    ♻️ Updated: {updated}")
    print(f"  Misc Products:")
    print(f"    ✨ Created: {misc_created}")
    print(f"    ♻️ Updated: {misc_updated}")
    print(f"  ⚠️ Skipped: {skipped}")
    print(f"  📊 Total processed: {created + updated + misc_created + misc_updated + skipped}")
    print(f"{'=' * 60}")
    
    if dry_run:
        print("\n💡 To save these changes, run with dry_run=False")


if __name__ == "__main__":
    # Path to your CSV file
    csv_file_path = os.path.join(current_path, "ytd_sales_2025.csv")
    
    # Check if file exists
    if not os.path.exists(csv_file_path):
        print(f"❌ Error: CSV file not found at {csv_file_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("🌱 Sales Import Script")
    print("=" * 60)
    print()
    
    # Run with dry_run=True first to preview
    import_sales_2025(csv_file_path, year=25, wholesale=False, dry_run=False)
    
    # Uncomment below to actually import (after reviewing dry run)
    # import_sales_2025(csv_file_path, year=2025, wholesale=False, dry_run=False)
from PIL import Image
from django.conf import settings
import os
import django
import sys
import csv
from prettytable import PrettyTable
from collections import Counter
from django.db.models import Q, Sum, Max

# Get the current directory path
current_path = os.path.dirname(os.path.abspath(__file__))

# Get the project directory path by going up two levels from the current directory
project_path = os.path.abspath(os.path.join(current_path, '..'))

# Add the project directory to the sys.path
sys.path.append(project_path)

# Set the DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
django.setup()

from products.models import Product, Variety, Sales, MiscProduct, MiscSales, LabelPrint
from lots.models import Lot
from django.db import transaction


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def pause():
    """Pause and wait for user input"""
    input("\nPress Enter to continue...")

def get_choice(prompt, valid_choices):
    """Get validated user choice"""
    while True:
        choice = input(prompt).strip()
        if choice in valid_choices:
            return choice
        print(f"Invalid choice. Please select from: {', '.join(valid_choices)}")


# ============================================================================
# VARIETY MANAGEMENT
# ============================================================================

def view_all_varieties():
    """View all varieties with key details"""
    varieties = Variety.objects.all().order_by('sku_prefix')
    
    if not varieties:
        print("\n❌ No varieties found.")
        return
    
    print("\n" + "="*120)
    print("ALL VARIETIES")
    print("="*120)
    print(f"{'SKU Prefix':<15} {'Variety Name':<30} {'Category':<20} {'Active':<8} {'Photo':<10}")
    print("-"*120)
    
    for var in varieties:
        photo_status = "✓" if var.photo_path else "✗"
        active_status = "✓" if var.active else "✗"
        print(f"{var.sku_prefix:<15} {(var.var_name or '--'):<30} {(var.category or '--'):<20} {active_status:<8} {photo_status:<10}")
    
    print(f"\nTotal: {varieties.count()} varieties")

def view_variety_details():
    """View detailed information for a specific variety"""
    sku_prefix = input("\nEnter SKU prefix (e.g., BEA-RN): ").strip().upper()
    
    try:
        variety = Variety.objects.get(sku_prefix=sku_prefix)
    except Variety.DoesNotExist:
        print(f"\n❌ No variety found with SKU prefix '{sku_prefix}'")
        return
    
    print("\n" + "="*80)
    print(f"VARIETY DETAILS: {variety.sku_prefix}")
    print("="*80)
    print(f"Name: {variety.var_name or '--'}")
    print(f"Crop: {variety.crop or '--'}")
    print(f"Common Name: {variety.common_name or '--'}")
    print(f"Common Spelling: {variety.common_spelling or '--'}")
    print(f"Category: {variety.category or '--'}")
    print(f"Group: {variety.group or '--'}")
    print(f"Veg Type: {variety.veg_type or '--'}")
    print(f"Species: {variety.species or '--'}")
    print(f"Days to Maturity: {variety.days or '--'}")
    print(f"Active: {'Yes' if variety.active else 'No'}")
    print(f"Wholesale: {'Yes' if variety.wholesale else 'No'}")
    print(f"Photo Path: {variety.photo_path or 'No photo'}")
    
    # Show products
    products = variety.products.all()
    print(f"\n--- Products ({products.count()}) ---")
    for p in products:
        print(f"  {p.sku_suffix or '--'}: {p.pkg_size or '--'}")

def print_var_sku_prefixes_and_categories():
    """Print table of SKU prefixes and categories"""
    varieties = Variety.objects.all().order_by('sku_prefix').values('sku_prefix', 'category')

    table = PrettyTable()
    table.field_names = ["SKU Prefix", "Category"]

    for v in varieties:
        table.add_row([v['sku_prefix'], v['category'] or ''])

    print(table)

def print_varieties_with_no_photo_path():
    """List varieties missing photos"""
    varieties = Variety.objects.filter(photo_path="")
    
    if not varieties:
        print("\n✅ All varieties have photos!")
        return
    
    print("\n" + "="*60)
    print(f"VARIETIES WITHOUT PHOTOS ({varieties.count()})")
    print("="*60)
    for var in varieties:
        print(f"{var.sku_prefix:<15} {var.var_name or '--'}")

def update_all_variety_photos():
    """Sets all variety 'photo' attributes to the correct file (webp or jpg)"""
    varieties = Variety.objects.all()
    updated_count = 0
    
    for variety in varieties:
        sku_prefix = variety.sku_prefix
        webp_file = os.path.join(settings.BASE_DIR, 'products', 'static', 'products', 'photos', f'{sku_prefix}.webp')
        jpg_file = os.path.join(settings.BASE_DIR, 'products', 'static', 'products', 'photos', f'{sku_prefix}.jpg')
        
        if os.path.exists(webp_file):
            variety.photo_path = f'products/photos/{sku_prefix}.webp'
            print(f"✓ Set webp photo for {sku_prefix}")
            variety.save()
            updated_count += 1
        elif os.path.exists(jpg_file):
            variety.photo_path = f'products/photos/{sku_prefix}.jpg'
            print(f"✓ Set jpg photo for {sku_prefix}")
            variety.save()
            updated_count += 1
    
    print(f"\n✅ Updated {updated_count} variety photos")

def delete_variety_by_sku():
    """Delete a variety"""
    sku_prefix = input("\nEnter SKU prefix to delete: ").strip().upper()
    
    try:
        variety = Variety.objects.get(sku_prefix=sku_prefix)
        print(f"\n⚠️  You are about to delete: {variety.sku_prefix} - {variety.var_name}")
        confirm = input("Type 'DELETE' to confirm: ").strip()
        
        if confirm == 'DELETE':
            variety.delete()
            print(f"✅ Deleted variety {sku_prefix}")
        else:
            print("Deletion cancelled")
    except Variety.DoesNotExist:
        print(f"\n❌ No variety found with SKU prefix {sku_prefix}")

def add_variety():
    """Add a new variety - PLACEHOLDER"""
    print("\n⚠️  ADD VARIETY - Function placeholder")
    print("This would allow you to:")
    print("  - Enter SKU prefix")
    print("  - Enter variety name and details")
    print("  - Set category and type")
    print("  - Upload photo")

def edit_variety():
    """Edit variety details - PLACEHOLDER"""
    print("\n⚠️  EDIT VARIETY - Function placeholder")
    print("This would allow you to:")
    print("  - Select variety by SKU prefix")
    print("  - Update any field")
    print("  - Change active status")
    print("  - Update photo path")

def variety_menu():
    """Variety management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("VARIETY MANAGEMENT")
        print("="*50)
        print("1.  View all varieties")
        print("2.  View variety details")
        print("3.  View SKU prefixes and categories (table)")
        print("4.  View varieties without photos")
        print("5.  Update all variety photos")
        print("6.  Add new variety")
        print("7.  Edit variety")
        print("8.  Delete variety")
        print("0.  Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5', '6', '7', '8'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_all_varieties()
            pause()
        elif choice == '2':
            view_variety_details()
            pause()
        elif choice == '3':
            print_var_sku_prefixes_and_categories()
            pause()
        elif choice == '4':
            print_varieties_with_no_photo_path()
            pause()
        elif choice == '5':
            update_all_variety_photos()
            pause()
        elif choice == '6':
            add_variety()
            pause()
        elif choice == '7':
            edit_variety()
            pause()
        elif choice == '8':
            delete_variety_by_sku()
            pause()


# ============================================================================
# PRODUCT MANAGEMENT
# ============================================================================

def view_all_products():
    """View all products"""
    products = Product.objects.all().select_related('variety').order_by('variety__sku_prefix', 'sku_suffix')
    
    if not products:
        print("\n❌ No products found.")
        return
    
    print("\n" + "="*120)
    print("ALL PRODUCTS")
    print("="*120)
    print(f"{'SKU Prefix':<15} {'Suffix':<10} {'Pkg Size':<12} {'Lineitem Name':<35} {'Print Back':<12} {'Lot':<15}")
    print("-"*120)
    
    for prod in products:
        lot_display = prod.lot.build_lot_code() if prod.lot else '--'
        print_back = "✓" if prod.print_back else "✗"
        print(f"{prod.variety.sku_prefix:<15} {(prod.sku_suffix or '--'):<10} {(prod.pkg_size or '--'):<12} "
              f"{(prod.lineitem_name or '--'):<35} {print_back:<12} {lot_display:<15}")
    
    print(f"\nTotal: {products.count()} products")

def view_product_details():
    """View detailed information for a specific product"""
    print("\nEnter product identifier:")
    sku_prefix = input("  SKU Prefix (e.g., BEA-RN): ").strip().upper()
    sku_suffix = input("  SKU Suffix (e.g., pkt): ").strip()
    
    try:
        product = Product.objects.get(variety__sku_prefix=sku_prefix, sku_suffix=sku_suffix)
    except Product.DoesNotExist:
        print(f"\n❌ No product found with {sku_prefix}-{sku_suffix}")
        return
    
    print("\n" + "="*80)
    print(f"PRODUCT DETAILS: {product.variety.sku_prefix}-{product.sku_suffix}")
    print("="*80)
    print(f"Variety: {product.variety.var_name or '--'}")
    print(f"Package Size: {product.pkg_size or '--'}")
    print(f"Alt SKU: {product.alt_sku or '--'}")
    print(f"Lineitem Name: {product.lineitem_name or '--'}")
    print(f"Rack Location: {product.rack_location or '--'}")
    print(f"Envelope Type: {product.env_type or '--'}")
    print(f"Envelope Multiplier: {product.env_multiplier or '--'}")
    print(f"Scoop Size: {product.scoop_size or '--'}")
    print(f"Print Back: {'Yes' if product.print_back else 'No'}")
    print(f"Is Sub Product: {'Yes' if product.is_sub_product else 'No'}")
    print(f"Bulk Pre-Pack: {product.bulk_pre_pack or 0}")
    print(f"Current Lot: {product.lot.build_lot_code() if product.lot else 'None assigned'}")
    
    # Show sales
    sales = product.sales.all().order_by('-year')
    print(f"\n--- Sales History ({sales.count()}) ---")
    for sale in sales:
        ws_label = " (Wholesale)" if sale.wholesale else ""
        print(f"  20{sale.year}: {sale.quantity} units{ws_label}")

def view_lineitems():
    """View all products with lineitem names"""
    import pandas as pd

    products = Product.objects.all().order_by(
        'variety__sku_prefix', 'sku_suffix'
    ).values('variety__sku_prefix', 'sku_suffix', 'lineitem_name')

    df = pd.DataFrame(list(products))
    print("\n")
    print(df)

def view_products_without_lineitem():
    """Display all products that do not have a lineitem name"""
    products = Product.objects.filter(
        is_sub_product=False
    ).filter(
        lineitem_name__isnull=True
    ) | Product.objects.filter(
        is_sub_product=False
    ).filter(
        lineitem_name=""
    )
    products = products.select_related('variety').order_by('variety__sku_prefix', 'sku_suffix')
    
    if not products:
        print("\n✅ All products have lineitem names assigned!")
        return
    
    print("\n" + "="*100)
    print(f"PRODUCTS WITHOUT LINEITEM NAMES ({products.count()})")
    print("="*100)
    print(f"{'SKU Prefix':<15} {'Suffix':<10} {'Pkg Size':<15} {'Variety Name':<40}")
    print("-"*100)
    
    for prod in products:
        variety_name = prod.variety.var_name or '--'
        print(f"{prod.variety.sku_prefix:<15} {(prod.sku_suffix or '--'):<10} "
              f"{(prod.pkg_size or '--'):<15} {variety_name:<40}")
    
    print(f"\nTotal: {products.count()} products without lineitem names")


def view_products_without_pkg_size():
    """Display all products that do not have a pkg_size"""
    products = Product.objects.filter(
        pkg_size__isnull=True
    ) | Product.objects.filter(
        pkg_size=""
    )
    products = products.select_related('variety').order_by('variety__sku_prefix', 'sku_suffix')
    
    if not products:
        print("\n✅ All products have pkg_size assigned!")
        return
    
    table = PrettyTable()
    table.field_names = ["SKU Prefix", "Suffix", "Lineitem Name", "Variety Name"]
    table.align["SKU Prefix"] = "l"
    table.align["Suffix"] = "l"
    table.align["Lineitem Name"] = "l"
    table.align["Variety Name"] = "l"
    
    for prod in products:
        variety_name = prod.variety.var_name or '--'
        lineitem = prod.lineitem_name or '--'
        suffix = prod.sku_suffix or '--'
        table.add_row([prod.variety.sku_prefix, suffix, lineitem, variety_name])
    
    print("\n" + "="*100)
    print(f"PRODUCTS WITHOUT PKG_SIZE ({products.count()})")
    print("="*100)
    print(table)
    print(f"\nTotal: {products.count()} products without pkg_size")


def reset_all_website_bulk():
    """Reset website_bulk to False for all varieties"""
    varieties = Variety.objects.filter(website_bulk=True)
    count = varieties.count()
    
    if count == 0:
        print("\n✅ All varieties already have website_bulk=False")
        return
    
    print(f"\n⚠️  You are about to reset website_bulk to False for {count} varieties")
    confirm = input("Type 'RESET' to confirm: ").strip()
    
    if confirm == 'RESET':
        varieties.update(website_bulk=False)
        print(f"✅ Reset website_bulk to False for {count} varieties")
    else:
        print("Reset cancelled")

def reset_all_wholesale():
    """Reset wholesale to False for all varieties"""
    varieties = Variety.objects.filter(wholesale=True)
    count = varieties.count()
    
    if count == 0:
        print("\n✅ All varieties already have wholesale=False")
        return
    
    print(f"\n⚠️  You are about to reset wholesale to False for {count} varieties")
    confirm = input("Type 'RESET' to confirm: ").strip()
    
    if confirm == 'RESET':
        varieties.update(wholesale=False)
        print(f"✅ Reset wholesale to False for {count} varieties")
    else:
        print("Reset cancelled")

def reset_bulk_pre_pack_to_zero():
    """Reset all NULL bulk_pre_pack values to 0"""
    products = Product.objects.filter(bulk_pre_pack__isnull=True)
    count = products.count()
    
    if count == 0:
        print("\n✅ All products already have bulk_pre_pack set")
        return
    
    confirm = input(f"\nReset {count} products to bulk_pre_pack=0? (y/n): ").strip().lower()
    if confirm == 'y':
        products.update(bulk_pre_pack=0)
        print(f"✅ Reset {count} products to bulk_pre_pack=0")
    else:
        print("Cancelled")

def view_products_with_bullet_in_pkg_size():
    """Display all products that have a bullet (•) in their pkg_size and remove them"""
    products = Product.objects.filter(
        pkg_size__contains="•"
    ).select_related('variety').order_by('variety__sku_prefix', 'sku_suffix')
    
    if not products:
        print("\n✅ No products have bullets in pkg_size!")
        return
    
    print("\n" + "="*100)
    print(f"PRODUCTS WITH BULLET (•) IN PKG_SIZE ({products.count()})")
    print("="*100)
    print(f"{'SKU Prefix':<15} {'Suffix':<10} {'Old Pkg Size':<25} {'New Pkg Size':<25}")
    print("-"*100)
    
    changes = []
    for prod in products:
        old_pkg_size = prod.pkg_size
        new_pkg_size = prod.pkg_size.replace("•", "").strip()
        changes.append((prod, old_pkg_size, new_pkg_size))
        print(f"{prod.variety.sku_prefix:<15} {(prod.sku_suffix or '--'):<10} "
              f"{old_pkg_size:<25} {new_pkg_size:<25}")
    
    print(f"\nTotal: {len(changes)} products to update")
    confirm = input("\nRemove bullets and save changes? (y/n): ").strip().lower()
    
    if confirm == 'y':
        updated_count = 0
        for prod, old, new in changes:
            prod.pkg_size = new
            prod.save()
            updated_count += 1
        print(f"✅ Updated {updated_count} products")
    else:
        print("Update cancelled")

def find_pkt_products_with_wrong_print_back_setting():
    """Find 'pkt' products with print_back=True but env_type not in Herb/Veg/Flower"""
    products = Product.objects.filter(
        sku_suffix='pkt',
        print_back=True
    ).exclude(
        env_type__in=['Herb', 'Veg', 'Flower']
    ).select_related('variety').order_by('variety__sku_prefix')
    
    if not products:
        print("\n✅ No pkt products found with incorrect env_type!")
        return
    
    print("\n" + "="*120)
    print(f"PKT PRODUCTS WITH PRINT_BACK=TRUE AND ENV_TYPE NOT IN [Herb, Veg, Flower] ({products.count()})")
    print("="*120)
    print(f"{'SKU Prefix':<15} {'Suffix':<10} {'Env Type':<15} {'Lineitem Name':<40} {'Print Back':<12}")
    print("-"*120)
    
    for prod in products:
        env_type_display = prod.env_type or '--'
        print_back = "✓" if prod.print_back else "✗"
        print(f"{prod.variety.sku_prefix:<15} {(prod.sku_suffix or '--'):<10} "
              f"{env_type_display:<15} {(prod.lineitem_name or '--'):<40} {print_back:<12}")
    
    print(f"\nTotal: {products.count()} products found")

def view_products_with_bulk_pre_pack():
    """Display all products with bulk_pre_pack > 0"""
    products = Product.objects.filter(
        bulk_pre_pack__gt=0
    ).select_related('variety').order_by('variety__sku_prefix', 'sku_suffix')
    
    if not products:
        print("\n✅ No products have bulk_pre_pack set!")
        return
    
    print("\n" + "="*100)
    print(f"PRODUCTS WITH BULK PRE-PACK ({products.count()})")
    print("="*100)
    print(f"{'SKU Prefix':<15} {'Variety Name':<40} {'Suffix':<10} {'Bulk Pre-Pack':<15}")
    print("-"*100)
    
    for prod in products:
        variety_name = prod.variety.var_name or '--'
        suffix = prod.sku_suffix or '--'
        print(f"{prod.variety.sku_prefix:<15} {variety_name:<40} {suffix:<10} {prod.bulk_pre_pack:<15}")
    
    print(f"\nTotal: {products.count()} products with bulk pre-pack")

def check_pkt_products_low_label_prints():
    """Check pkt products with low label prints that have active germination lots"""
    year_input = input("\nEnter year (2-digit, e.g., 25 for 2025): ").strip()
    # Prompt for threshold
    threshold_input = input("\nEnter label print threshold (e.g., 30): ").strip()
    
    if not threshold_input:
        print("❌ Threshold is required")
        return
    
    try:
        threshold = int(threshold_input)
    except ValueError:
        print("❌ Invalid threshold format")
        return
    
    if not year_input:
        print("❌ Year is required")
        return
    
    try:
        year = int(year_input)
    except ValueError:
        print("❌ Invalid year format")
        return
    
    # Import Germination model
    from lots.models import Germination
    
    # Get all pkt products
    pkt_products = Product.objects.filter(sku_suffix='pkt').select_related('variety')
    
    results = []
    
    for product in pkt_products:
        # Calculate total label prints for this product for the given year
        total_printed = product.label_prints.filter(for_year=year).aggregate(
            total=Sum('qty')
        )['total'] or 0
        
        # Only consider products with <= 30 labels printed
        if total_printed <= threshold:
            # Get lots for this variety
            variety_lots = Lot.objects.filter(variety=product.variety)
            
            # Check if any of these lots have valid germination records for this year
            valid_lot_count = 0
            for lot in variety_lots:
                # Check if this lot has germination records for the year with non-zero germination_rate
                has_valid_germ = Germination.objects.filter(
                    lot=lot,
                    for_year=year,
                    germination_rate__gt=0
                ).exists()
                
                if has_valid_germ:
                    valid_lot_count += 1
            
            # If variety has lots with valid germination for this year, include it
            if valid_lot_count > 0:
                results.append({
                    'sku_prefix': product.variety.sku_prefix,
                    'variety_name': product.variety.var_name or '--',
                    'pkg_size': product.pkg_size or '--',
                    'total_printed': total_printed,
                    'lot_count': valid_lot_count
                })
    
    if not results:
        print(f"\n✅ No pkt products with low label prints (≤{threshold}) found for year 20{year}")
        return
    
    # Sort by total printed (ascending)
    results.sort(key=lambda x: x['total_printed'])
    
    table = PrettyTable()
    table.field_names = ["SKU Prefix", "Variety Name", "Pkg Size", "Printed", "Active Lots"]
    table.align["SKU Prefix"] = "l"
    table.align["Variety Name"] = "l"
    table.align["Pkg Size"] = "l"
    table.align["Printed"] = "r"
    table.align["Active Lots"] = "r"
    
    for item in results:
        table.add_row([
            item['sku_prefix'],
            item['variety_name'][:38] if len(item['variety_name']) > 38 else item['variety_name'],
            item['pkg_size'],
            item['total_printed'],
            item['lot_count']
        ])
    
    print("\n" + "="*100)
    print(f"PKT PRODUCTS WITH LOW LABEL PRINTS (≤{threshold}) - YEAR 20{year}")
    print("="*100)
    print(table)
    print(f"\nTotal: {len(results)} products with active germination lots")


def check_pkt_products_below_sales_percentage():
    """Check pkt products with print qty > 0 but < threshold% of previous year's sales"""
    year_input = input("\nEnter current year (2-digit, e.g., 25 for 2025): ").strip()
    
    if not year_input:
        print("❌ Year is required")
        return
    
    try:
        current_year = int(year_input)
    except ValueError:
        print("❌ Invalid year format")
        return
    
    threshold_input = input("\nEnter percentage threshold (e.g., 50 for 50%): ").strip()
    
    if not threshold_input:
        print("❌ Threshold is required")
        return
    
    try:
        threshold_pct = float(threshold_input)
    except ValueError:
        print("❌ Invalid threshold format")
        return
    
    from lots.models import Germination
    
    most_recent_sales_year = Sales.objects.aggregate(
        max_year=Max('year')
    )['max_year']
    
    if not most_recent_sales_year:
        print("❌ No sales data found in Sales table")
        return
    
    print(f"\n📊 Using sales data from year 20{most_recent_sales_year} for comparison")
    
    pkt_products = Product.objects.filter(sku_suffix='pkt').select_related('variety')
    
    results = []
    
    for product in pkt_products:
        total_printed = product.label_prints.filter(for_year=current_year).aggregate(
            total=Sum('qty')
        )['total'] or 0
        
        if total_printed > 0:
            prev_year_sales = product.sales.filter(
                year=most_recent_sales_year
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            if prev_year_sales > 0:
                threshold_qty = (threshold_pct / 100) * prev_year_sales
                
                if total_printed < threshold_qty:
                    actual_pct = (total_printed / prev_year_sales) * 100
                    
                    variety_lots = Lot.objects.filter(variety=product.variety)
                    
                    valid_lot_count = 0
                    for lot in variety_lots:
                        has_valid_germ = Germination.objects.filter(
                            lot=lot,
                            for_year=current_year,
                            germination_rate__gt=0
                        ).exists()
                        
                        if has_valid_germ:
                            valid_lot_count += 1
                    
                    results.append({
                        'sku_prefix': product.variety.sku_prefix,
                        'variety_name': product.variety.var_name or '--',
                        'pkg_size': product.pkg_size or '--',
                        'total_printed': total_printed,
                        'prev_year_sales': prev_year_sales,
                        'percentage': actual_pct,
                        'threshold_qty': int(threshold_qty),
                        'lot_count': valid_lot_count
                    })
    
    if not results:
        print(f"\n✅ No pkt products found with prints > 0 but < {threshold_pct}% of 20{most_recent_sales_year} sales")
        return
    
    results.sort(key=lambda x: x['percentage'])
    
    table = PrettyTable()
    table.field_names = ["SKU", "Variety Name", "Printed", f"20{most_recent_sales_year} Sales", "Threshold", "%", "Lots"]
    table.align["SKU"] = "l"
    table.align["Variety Name"] = "l"
    table.align["Printed"] = "r"
    table.align[f"20{most_recent_sales_year} Sales"] = "r"
    table.align["Threshold"] = "r"
    table.align["%"] = "r"
    table.align["Lots"] = "r"
    
    for item in results:
        table.add_row([
            item['sku_prefix'],
            item['variety_name'][:28] if len(item['variety_name']) > 28 else item['variety_name'],
            item['total_printed'],
            item['prev_year_sales'],
            item['threshold_qty'],
            f"{item['percentage']:.1f}%",
            item['lot_count']
        ])
    
    print("\n" + "="*120)
    print(f"PKT PRODUCTS WITH PRINTS < {threshold_pct}% OF PREVIOUS YEAR SALES - YEAR 20{current_year}")
    print("="*120)
    print(table)
    print(f"\nTotal: {len(results)} products below threshold")
    print(f"\nNote: Threshold column shows {threshold_pct}% of previous year sales")


def add_product():
    """Add a new product - PLACEHOLDER"""
    print("\n⚠️  ADD PRODUCT - Function placeholder")
    print("This would allow you to:")
    print("  - Select variety")
    print("  - Enter SKU suffix and package size")
    print("  - Set envelope type and multiplier")
    print("  - Configure print settings")

def edit_product():
    """Edit product details - PLACEHOLDER"""
    print("\n⚠️  EDIT PRODUCT - Function placeholder")
    print("This would allow you to:")
    print("  - Select product")
    print("  - Update any field")
    print("  - Change lot assignment")
    print("  - Toggle print_back flag")

def delete_product():
    """Delete a product - PLACEHOLDER"""
    print("\n⚠️  DELETE PRODUCT - Function placeholder")
    print("This would allow you to:")
    print("  - Select product by SKU")
    print("  - Confirm deletion")
    print("  - Handle cascading deletes")

def product_menu():
    """Product management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("PRODUCT MANAGEMENT")
        print("="*50)
        print("1.  View all products")
        print("2.  View product details")
        print("3.  View lineitem names")
        print("4.  View products without lineitem names")  
        print("5.  Reset bulk pre-pack to zero")
        print("6.  Reset all website_bulk to False") 
        print("7.  Reset all wholesale to False") 
        print("8.  View products with bulk pre-pack")
        print("9.  Find pkt products with wrong print_back setting") 
        print("10. Add new product")
        print("11. Edit product")
        print("12. Delete product")
        print("13. View products without pkg_size")
        print("14. Check pkt products with low label prints")
        print("15. Check pkt products below % of prev year sales")
        print("0.  Back to main menu")

        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15'])

        if choice == '0':
            break
        elif choice == '1':
            view_all_products()
            pause()
        elif choice == '2':
            view_product_details()
            pause()
        elif choice == '3':
            view_lineitems()
            pause()
        elif choice == '4':
            view_products_without_lineitem()  
            pause()
        elif choice == '5':
            reset_bulk_pre_pack_to_zero()
            pause()
        elif choice == '6':
            reset_all_website_bulk()
            pause()
        elif choice == '7':
            reset_all_wholesale()
            pause()
        elif choice == '8':
            view_products_with_bulk_pre_pack() 
            pause()
        elif choice == '9':
            find_pkt_products_with_wrong_print_back_setting()
            pause()
        elif choice == '10':
            add_product()
            pause()
        elif choice == '11':
            edit_product()
            pause()
        elif choice == '12':
            delete_product()
            pause()
        elif choice == '13':
            view_products_without_pkg_size()
            pause()
        elif choice == '14':
            check_pkt_products_low_label_prints()
            pause()
        elif choice == '15':
            check_pkt_products_below_sales_percentage()
            pause()


# ============================================================================
# SALES MANAGEMENT
# ============================================================================

def view_all_sales():
    """View all sales records"""
    year = input("\nEnter year (2-digit, e.g., 25 for 2025) or press Enter for all: ").strip()
    
    if year:
        sales = Sales.objects.filter(year=int(year)).select_related('product__variety').order_by('-quantity')
    else:
        sales = Sales.objects.all().select_related('product__variety').order_by('-year', '-quantity')
    
    if not sales:
        print("\n❌ No sales records found.")
        return
    
    print("\n" + "="*100)
    print("SALES RECORDS")
    print("="*100)
    print(f"{'SKU':<20} {'Year':<8} {'Quantity':<12} {'Wholesale':<12}")
    print("-"*100)
    
    total_qty = 0
    for sale in sales:
        sku = f"{sale.product.variety.sku_prefix}-{sale.product.sku_suffix}"
        ws_label = "Yes" if sale.wholesale else "No"
        print(f"{sku:<20} 20{sale.year:<6} {sale.quantity:<12} {ws_label:<12}")
        total_qty += sale.quantity
    
    print(f"\nTotal: {sales.count()} records | Total Quantity: {total_qty:,}")

def view_sales_by_product():
    """View sales for a specific product"""
    print("\nEnter product identifier:")
    sku_prefix = input("  SKU Prefix (e.g., BEA-RN): ").strip().upper()
    sku_suffix = input("  SKU Suffix (e.g., pkt): ").strip()
    
    try:
        product = Product.objects.get(variety__sku_prefix=sku_prefix, sku_suffix=sku_suffix)
    except Product.DoesNotExist:
        print(f"\n❌ No product found with {sku_prefix}-{sku_suffix}")
        return
    
    sales = product.sales.all().order_by('-year')
    
    if not sales:
        print(f"\n❌ No sales records for {sku_prefix}-{sku_suffix}")
        return
    
    print("\n" + "="*80)
    print(f"SALES FOR {sku_prefix}-{sku_suffix}")
    print("="*80)
    print(f"{'Year':<10} {'Quantity':<15} {'Wholesale':<12}")
    print("-"*80)
    
    for sale in sales:
        ws_label = "Yes" if sale.wholesale else "No"
        print(f"20{sale.year:<8} {sale.quantity:<15} {ws_label:<12}")

def import_sales_csv():
    """Import sales from CSV - PLACEHOLDER"""
    print("\n⚠️  IMPORT SALES CSV - Function placeholder")
    print("This would allow you to:")
    print("  - Select CSV file")
    print("  - Map columns")
    print("  - Preview before import")
    print("  - Import with dry-run option")

def edit_sales_record():
    """Edit a sales record - PLACEHOLDER"""
    print("\n⚠️  EDIT SALES RECORD - Function placeholder")
    print("This would allow you to:")
    print("  - Select sales record")
    print("  - Update quantity")
    print("  - Change wholesale flag")

def delete_sales_record():
    """Delete a sales record - PLACEHOLDER"""
    print("\n⚠️  DELETE SALES RECORD - Function placeholder")
    print("This would allow you to:")
    print("  - Select sales record")
    print("  - Confirm deletion")

def generate_sales_report():
    """Generate sales report - PLACEHOLDER"""
    print("\n⚠️  GENERATE SALES REPORT - Function placeholder")
    print("This would allow you to:")
    print("  - Select date range")
    print("  - Filter by wholesale/retail")
    print("  - Export to CSV/PDF")
    print("  - Show top sellers")

def sales_menu():
    """Sales management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("SALES MANAGEMENT")
        print("="*50)
        print("1.  View all sales")
        print("2.  View sales by product")
        print("3.  Import sales from CSV")
        print("4.  Edit sales record")
        print("5.  Delete sales record")
        print("6.  Generate sales report")
        print("0.  Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5', '6'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_all_sales()
            pause()
        elif choice == '2':
            view_sales_by_product()
            pause()
        elif choice == '3':
            import_sales_csv()
            pause()
        elif choice == '4':
            edit_sales_record()
            pause()
        elif choice == '5':
            delete_sales_record()
            pause()
        elif choice == '6':
            generate_sales_report()
            pause()


# ============================================================================
# MISC PRODUCTS & SALES MANAGEMENT
# ============================================================================

def view_all_misc_products():
    """View all misc products"""
    misc_products = MiscProduct.objects.all().order_by('sku')
    
    if not misc_products:
        print("\n❌ No misc products found.")
        return
    
    print("\n" + "="*100)
    print("MISC PRODUCTS")
    print("="*100)
    print(f"{'SKU':<20} {'Lineitem Name':<40} {'Category':<20}")
    print("-"*100)
    
    for mp in misc_products:
        print(f"{mp.sku:<20} {mp.lineitem_name:<40} {(mp.category or '--'):<20}")
    
    print(f"\nTotal: {misc_products.count()} misc products")

def view_all_misc_sales():
    """View all misc sales records"""
    year = input("\nEnter year (2-digit, e.g., 25 for 2025) or press Enter for all: ").strip()
    
    if year:
        misc_sales = MiscSales.objects.filter(year=int(year)).select_related('product').order_by('-quantity')
    else:
        misc_sales = MiscSales.objects.all().select_related('product').order_by('-year', '-quantity')
    
    if not misc_sales:
        print("\n❌ No misc sales records found.")
        return
    
    print("\n" + "="*100)
    print("MISC SALES RECORDS")
    print("="*100)
    print(f"{'SKU':<20} {'Lineitem Name':<40} {'Year':<8} {'Quantity':<12}")
    print("-"*100)
    
    total_qty = 0
    for sale in misc_sales:
        print(f"{sale.product.sku:<20} {sale.product.lineitem_name:<40} 20{sale.year:<6} {sale.quantity:<12}")
        total_qty += sale.quantity
    
    print(f"\nTotal: {misc_sales.count()} records | Total Quantity: {total_qty:,}")

def clear_misc_sales_table():
    """Clear all misc sales records"""
    count = MiscSales.objects.count()
    
    if count == 0:
        print("\n✅ Misc sales table is already empty")
        return
    
    print(f"\n⚠️  You are about to delete {count} misc sales records")
    confirm = input("Type 'DELETE' to confirm: ").strip()
    
    if confirm == 'DELETE':
        deleted_count, _ = MiscSales.objects.all().delete()
        print(f"✅ Deleted {deleted_count} records from MiscSales table")
    else:
        print("Deletion cancelled")

def add_misc_product():
    """Add misc product - PLACEHOLDER"""
    print("\n⚠️  ADD MISC PRODUCT - Function placeholder")
    print("This would allow you to:")
    print("  - Enter SKU")
    print("  - Enter lineitem name")
    print("  - Set category")
    print("  - Add description")

def misc_menu():
    """Misc products/sales management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("MISC PRODUCTS & SALES MANAGEMENT")
        print("="*50)
        print("1.  View all misc products")
        print("2.  View all misc sales")
        print("3.  Add misc product")
        print("4.  Clear all misc sales")
        print("0.  Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_all_misc_products()
            pause()
        elif choice == '2':
            view_all_misc_sales()
            pause()
        elif choice == '3':
            add_misc_product()
            pause()
        elif choice == '4':
            clear_misc_sales_table()
            pause()


# ============================================================================
# LABEL PRINT MANAGEMENT
# ============================================================================

def view_all_label_prints():
    """View all label print records"""
    year = input("\nEnter year (2-digit, e.g., 25 for 2025) or press Enter for all: ").strip()
    
    if year:
        prints = LabelPrint.objects.filter(for_year=int(year)).select_related('product__variety', 'lot').order_by('-date')
    else:
        prints = LabelPrint.objects.all().select_related('product__variety', 'lot').order_by('-date')
    
    if not prints:
        print("\n❌ No label print records found.")
        return
    
    print("\n" + "="*120)
    print("LABEL PRINT RECORDS")
    print("="*120)
    print(f"{'Date':<12} {'SKU':<20} {'Lot':<15} {'Qty':<8} {'For Year':<10}")
    print("-"*120)
    
    total_qty = 0
    for lp in prints:
        sku = f"{lp.product.variety.sku_prefix}-{lp.product.sku_suffix}"
        lot_display = lp.lot.build_lot_code() if lp.lot else '--'
        print(f"{lp.date.strftime('%Y-%m-%d'):<12} {sku:<20} {lot_display:<15} {lp.qty:<8} 20{lp.for_year:<8}")
        total_qty += lp.qty
    
    print(f"\nTotal: {prints.count()} records | Total Labels Printed: {total_qty:,}")

def view_prints_by_product():
    """View label prints for a specific product"""
    print("\nEnter product identifier:")
    sku_prefix = input("  SKU Prefix (e.g., BEA-RN): ").strip().upper()
    sku_suffix = input("  SKU Suffix (e.g., pkt): ").strip()
    
    try:
        product = Product.objects.get(variety__sku_prefix=sku_prefix, sku_suffix=sku_suffix)
    except Product.DoesNotExist:
        print(f"\n❌ No product found with {sku_prefix}-{sku_suffix}")
        return
    
    prints = product.label_prints.all().order_by('-date')
    
    if not prints:
        print(f"\n❌ No label print records for {sku_prefix}-{sku_suffix}")
        return
    
    print("\n" + "="*80)
    print(f"LABEL PRINTS FOR {sku_prefix}-{sku_suffix}")
    print("="*80)
    print(f"{'Date':<12} {'Lot':<15} {'Qty':<8} {'For Year':<10}")
    print("-"*80)
    
    for lp in prints:
        lot_display = lp.lot.build_lot_code() if lp.lot else '--'
        print(f"{lp.date.strftime('%Y-%m-%d'):<12} {lot_display:<15} {lp.qty:<8} 20{lp.for_year:<8}")

def delete_print_label_table_contents():
    """Clear all label print records"""
    count = LabelPrint.objects.count()
    
    if count == 0:
        print("\n✅ Label print table is already empty")
        return
    
    print(f"\n⚠️  You are about to delete {count} label print records")
    confirm = input("Type 'DELETE' to confirm: ").strip()
    
    if confirm == 'DELETE':
        deleted_count, _ = LabelPrint.objects.all().delete()
        print(f"✅ Deleted {deleted_count} records from LabelPrint table")
    else:
        print("Deletion cancelled")

def print_summary_by_year():
    """Print summary by year - PLACEHOLDER"""
    print("\n⚠️  PRINT SUMMARY BY YEAR - Function placeholder")
    print("This would allow you to:")
    print("  - Select year")
    print("  - Show total labels printed")
    print("  - Break down by product")
    print("  - Export to CSV")

def label_print_menu():
    """Label print management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("LABEL PRINT MANAGEMENT")
        print("="*50)
        print("1.  View all label prints")
        print("2.  View prints by product")
        print("3.  Print summary by year")
        print("4.  Clear all label print records")
        print("0.  Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_all_label_prints()
            pause()
        elif choice == '2':
            view_prints_by_product()
            pause()
        elif choice == '3':
            print_summary_by_year()
            pause()
        elif choice == '4':
            delete_print_label_table_contents()
            pause()


# ============================================================================
# MIX MANAGEMENT
# ============================================================================

def set_mix_flags():
    """Set is_mix=True for all mix varieties"""
    mix_skus = ['CAR-RA', 'LET-MX', 'BEE-3B', 'MIX-SP', 'MIX-MI', 'MIX-BR', 'FLO-ED']
    
    print("\n" + "="*60)
    print("SETTING is_mix FLAG FOR MIX VARIETIES")
    print("="*60)
    
    updated_count = 0
    not_found = []
    
    for sku in mix_skus:
        try:
            variety = Variety.objects.get(sku_prefix=sku)
            variety.is_mix = True
            variety.save()
            print(f"✓ Set is_mix=True for {sku} - {variety.var_name}")
            updated_count += 1
        except Variety.DoesNotExist:
            not_found.append(sku)
            print(f"✗ Variety not found: {sku}")
    
    print(f"\n✅ Updated {updated_count} varieties")
    if not_found:
        print(f"⚠️  Not found: {', '.join(not_found)}")

def create_base_component_mixes():
    """Create base component mixes in Variety table"""
    base_mixes = [
        {'sku_prefix': 'MIX-LB', 'var_name': 'Lettuce Mix (Base Component)'},
        {'sku_prefix': 'MIX-SB', 'var_name': 'Spicy Mix (Base Component)'},
        {'sku_prefix': 'MIX-MB', 'var_name': 'Mild Mix (Base Component)'}
    ]
    
    print("\n" + "="*60)
    print("CREATING BASE COMPONENT MIXES")
    print("="*60)
    
    created_count = 0
    already_exists = []
    
    for mix in base_mixes:
        if Variety.objects.filter(sku_prefix=mix['sku_prefix']).exists():
            already_exists.append(mix['sku_prefix'])
            print(f"⚠️  {mix['sku_prefix']} already exists")
        else:
            Variety.objects.create(
                sku_prefix=mix['sku_prefix'],
                var_name=mix['var_name'],
                is_mix=True,
                active=True
            )
            print(f"✓ Created {mix['sku_prefix']} - {mix['var_name']}")
            created_count += 1
    
    print(f"\n✅ Created {created_count} base component mixes")
    if already_exists:
        print(f"⚠️  Already existed: {', '.join(already_exists)}")
# ============================================================================
# MAIN MENU
# ============================================================================

def main_menu():
    """Main menu for products management"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("🌱 PRODUCTS MANAGEMENT SYSTEM")
        print("="*50)
        print("1.  Variety Management")
        print("2.  Product Management")
        print("3.  Sales Management")
        print("4.  Misc Products & Sales")
        print("5.  Label Print Management")
        print("6.  Set mix flags for existing mixes")
        print("7.  Create base component mixes")
        print("0.  Exit")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5', '6', '7'])
        
        if choice == '0':
            print("\n👋 Goodbye!")
            break
        elif choice == '1':
            variety_menu()
        elif choice == '2':
            product_menu()
        elif choice == '3':
            sales_menu()
        elif choice == '4':
            misc_menu()
        elif choice == '5':
            label_print_menu()
        elif choice == '6':
            set_mix_flags()
            pause()
        elif choice == '7':
            create_base_component_mixes()
            pause()


# #### ||||| MAIN PROGRAM BEGINS HERE ||||| #### #
if __name__ == "__main__":
    main_menu()
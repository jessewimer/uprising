import os
from random import choice
import django
# import csv
import sys
from django.db import transaction
from datetime import datetime, date
from django.utils import timezone
from decimal import Decimal

# Get the current directory path
current_path = os.path.dirname(os.path.abspath(__file__))

# Get the project directory path by going up two levels from the current directory
project_path = os.path.abspath(os.path.join(current_path, '..'))

# Add the project directory to the sys.path
sys.path.append(project_path)

# Set the DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
django.setup()

from lots.models import Grower, Lot, StockSeed, Inventory, GermSamplePrint, Germination, GerminationBatch, RetiredLot, LotNote, Growout, MixLot
from products.models import Variety


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
# GROWER MANAGEMENT
# ============================================================================

def view_growers():
    """View all growers"""
    growers = Grower.objects.all().order_by('code')
    if not growers:
        print("\n❌ No growers found.")
        return
    
    print("\n" + "="*80)
    print("GROWERS")
    print("="*80)
    print(f"{'Code':<6} {'Name':<30} {'Contact':<25} {'Phone':<15}")
    print("-"*80)
    for grower in growers:
        print(f"{grower.code:<6} {grower.name:<30} {grower.contact_name or '-':<25} {grower.phone or '-':<15}")
    print(f"\nTotal: {growers.count()} growers")

def add_grower():
    """Add a new grower interactively"""
    print("\n=== Add New Grower ===")
    code = input("Enter grower code (2 letters): ").strip().upper()
    if len(code) != 2 or not code.isalpha():
        print("❌ Invalid code. Must be exactly 2 letters.")
        return

    name = input("Enter grower name: ").strip()
    if not name:
        print("❌ Grower name cannot be empty.")
        return

    contact_name = input("Enter contact name (optional): ").strip() or None
    phone = input("Enter phone (optional): ").strip() or None
    email = input("Enter email (optional): ").strip() or None

    if Grower.objects.filter(code=code).exists():
        print(f"❌ Grower with code '{code}' already exists.")
        return

    grower = Grower(code=code, name=name, contact_name=contact_name, phone=phone, email=email)
    grower.save()
    print(f"✅ Grower '{name}' with code '{code}' added successfully.")

def edit_grower():
    """Edit an existing grower"""
    growers = Grower.objects.all().order_by('code')
    if not growers:
        print("\n❌ No growers available to edit.")
        return
    
    print("\n--- Select a grower to edit ---")
    for idx, grower in enumerate(growers, start=1):
        print(f"{idx}. {grower.code} - {grower.name}")
    
    try:
        selection = int(input("\nEnter number (0 to cancel): ").strip())
        if selection == 0:
            return
        grower = growers[selection - 1]
    except (ValueError, IndexError):
        print("❌ Invalid selection.")
        return
    
    print(f"\nEditing: {grower.name} ({grower.code})")
    print("(Press Enter to keep current value)")
    
    new_name = input(f"Name [{grower.name}]: ").strip()
    if new_name:
        grower.name = new_name
    
    new_contact = input(f"Contact [{grower.contact_name or 'None'}]: ").strip()
    if new_contact:
        grower.contact_name = new_contact
    
    new_phone = input(f"Phone [{grower.phone or 'None'}]: ").strip()
    if new_phone:
        grower.phone = new_phone
    
    new_email = input(f"Email [{grower.email or 'None'}]: ").strip()
    if new_email:
        grower.email = new_email
    
    grower.save()
    print("✅ Grower updated successfully.")

def delete_grower():
    """Delete a grower"""
    print("\n⚠️  WARNING: This will delete the grower and may affect related lots!")
    growers = Grower.objects.all().order_by('code')
    if not growers:
        print("\n❌ No growers available to delete.")
        return
    
    print("\n--- Select a grower to delete ---")
    for idx, grower in enumerate(growers, start=1):
        lot_count = grower.lots.count()
        print(f"{idx}. {grower.code} - {grower.name} ({lot_count} lots)")
    
    try:
        selection = int(input("\nEnter number (0 to cancel): ").strip())
        if selection == 0:
            return
        grower = growers[selection - 1]
    except (ValueError, IndexError):
        print("❌ Invalid selection.")
        return
    
    confirm = input(f"Delete '{grower.name}'? (type YES to confirm): ").strip()
    if confirm == "YES":
        grower.delete()
        print("✅ Grower deleted.")
    else:
        print("❌ Delete cancelled.")

def grower_menu():
    """Grower management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("GROWER MANAGEMENT")
        print("="*50)
        print("1. View all growers")
        print("2. Add new grower")
        print("3. Edit grower")
        print("4. Delete grower")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_growers()
            pause()
        elif choice == '2':
            add_grower()
            pause()
        elif choice == '3':
            edit_grower()
            pause()
        elif choice == '4':
            delete_grower()
            pause()


# ============================================================================
# LOT MANAGEMENT
# ============================================================================

def view_lots():
    """View all lots"""
    lots = Lot.objects.all().select_related('variety', 'grower').order_by('variety__sku_prefix', 'year')
    if not lots:
        print("\n❌ No lots found.")
        return
    
    print("\n" + "="*100)
    print("LOTS")
    print("="*100)
    print(f"{'Lot Code':<20} {'Variety':<30} {'Grower':<10} {'Year':<6} {'Status':<12} {'Inventory'}")
    print("-"*100)
    for lot in lots:
        status = lot.get_lot_status()
        inv = lot.get_most_recent_inventory()
        print(f"{lot.build_lot_code():<20} {lot.variety.var_name[:28]:<30} {lot.grower.name[:8] if lot.grower else '-':<10} {lot.year:<6} {status:<12} {inv}")
    print(f"\nTotal: {lots.count()} lots")

def view_lot_details():
    """View detailed information for a specific lot"""
    lot_code = input("\nEnter lot code (e.g., CAR-DR-TR23): ").strip().upper()
    
    try:
        parsed = Lot.parse_lot_code(lot_code)
        variety = Variety.objects.get(sku_prefix=parsed['sku_prefix'])
        lot = Lot.objects.get(
            variety=variety,
            grower_id=parsed['grower_id'],
            year=parsed['year'],
            harvest=parsed['harvest']
        )
    except (ValueError, Variety.DoesNotExist, Lot.DoesNotExist):
        print("❌ Lot not found.")
        return
    
    print("\n" + "="*80)
    print(f"LOT DETAILS: {lot.build_lot_code()}")
    print("="*80)
    print(f"Variety: {lot.variety.var_name}")
    print(f"Grower: {lot.grower.name if lot.grower else 'Unknown'}")
    print(f"Year: {lot.year}")
    print(f"Harvest: {lot.harvest or 'N/A'}")
    print(f"Status: {lot.get_lot_status()}")
    print(f"Low Inventory Flag: {'Yes' if lot.low_inv else 'No'}")
    
    print(f"\n--- Inventory ---")
    inventories = lot.inventory.all().order_by('-inv_date')
    if inventories:
        for inv in inventories[:3]:  # Show last 3
            print(f"  {inv.inv_date}: {inv.weight} lbs, {inv.smarties_ct} smarties")
    else:
        print("  No inventory records")
    
    print(f"\n--- Germinations ---")
    germinations = lot.germinations.filter(test_date__isnull=False).order_by('-test_date')
    if germinations:
        for germ in germinations[:3]:  # Show last 3
            print(f"  {germ.test_date}: {germ.germination_rate}% for 20{germ.for_year} - {germ.status}")
    else:
        print("  No germination records")
    
    print(f"\n--- Stock Seed ---")
    stock_seeds = lot.stock_seeds.all().order_by('-date')
    if stock_seeds:
        for ss in stock_seeds:
            print(f"  {ss.date}: {ss.qty} - {ss.notes or 'No notes'}")
    else:
        print("  No stock seed records")

def add_lot():
    """Add a new lot - PLACEHOLDER"""
    print("\n⚠️  ADD LOT - Function placeholder")
    print("This would allow you to:")
    print("  - Select variety")
    print("  - Select grower")
    print("  - Enter year and harvest")
    print("  - Set initial inventory")

def edit_lot():
    """Edit lot details - PLACEHOLDER"""
    print("\n⚠️  EDIT LOT - Function placeholder")
    print("This would allow you to:")
    print("  - Change grower")
    print("  - Update harvest designation")
    print("  - Toggle low inventory flag")
    print("  - Update external lot ID")

def retire_lot():
    """Retire a lot - PLACEHOLDER"""
    print("\n⚠️  RETIRE LOT - Function placeholder")
    print("This would allow you to:")
    print("  - Mark lot as retired")
    print("  - Enter remaining pounds")
    print("  - Add retirement notes")


def find_lots_without_germ_for_year():
    """Find all non-retired lots that don't have a germination entry for a specific year"""
    year_input = input("\nEnter 2-digit year (e.g., 25 for 2025): ").strip()
    
    if not year_input.isdigit() or len(year_input) != 2:
        print("❌ Invalid year. Must be exactly 2 digits.")
        return
    
    year = int(year_input)
    
    # Get all non-retired lots
    lots_without_germ = []
    all_lots = Lot.objects.all().select_related('variety', 'grower').order_by('variety__sku_prefix', 'year')
    
    for lot in all_lots:
        # Skip retired lots
        if hasattr(lot, 'retired_info'):
            continue
        
        # Skip lots from the previous year (year - 1)
        if lot.year == (year - 1):
            continue
        
        # Check if lot has any germination record for this year
        has_germ_for_year = lot.germinations.filter(for_year=year).exists()
        
        if not has_germ_for_year:
            lots_without_germ.append(lot)
    
    if not lots_without_germ:
        print(f"\n✅ All non-retired lots (excluding 20{year-1} lots) have germination entries for 20{year}")
        return
    
    print("\n" + "="*100)
    print(f"LOTS WITHOUT GERMINATION ENTRY FOR 20{year} (excluding 20{year-1} lots)")
    print("="*100)
    print(f"{'Lot Code':<20} {'Variety':<40} {'Lot':<10} {'Status'}")
    print("-"*100)
    
    for lot in lots_without_germ:
        status = lot.get_lot_status()
        lot_short = lot.get_four_char_lot_code()
        print(f"{lot.build_lot_code():<20} {lot.variety.var_name[:38]:<40} {lot_short:<10} {status}")
    
    print(f"\nTotal: {len(lots_without_germ)} lots without germ entry for 20{year}")

def delete_mix_variety_lots():
    """Delete all lots associated with mix varieties"""
    
    mix_sku_prefixes = ['CAR-RA', 'BEE-3B', 'LET-MX', 'MIX-SP', 'MIX-MI', 'MIX-BR', 'FLO-ED']
    
    # Get all lots associated with mix varieties
    lots_to_delete = Lot.objects.filter(variety__sku_prefix__in=mix_sku_prefixes)
    
    count = lots_to_delete.count()
    
    if count == 0:
        print("No lots found for mix varieties.")
        return
    
    print(f"Found {count} lots associated with mix varieties:")
    for lot in lots_to_delete:
        grower_code = lot.grower.code if lot.grower else 'UNK'
        lot_code = f"{grower_code}{lot.year}"
        print(f"  - {lot.variety.var_name} ({lot.variety.sku_prefix}) - Lot: {lot_code}")
    
    confirm = input(f"\nAre you sure you want to delete these {count} lots? (yes/no): ")
    
    if confirm.lower() == 'yes':
        lots_to_delete.delete()
        print(f"✓ Successfully deleted {count} lots.")
    else:
        print("Deletion cancelled.")

def find_lots_with_pending_germs():
    """Find all lots with pending germination records for a specific year."""
    year_input = input("\nEnter year (e.g., 25 or 26): ").strip()
    
    if not year_input.isdigit():
        print("Invalid year format.")
        return
    
    year = int(year_input)
    
    # Find all lots that have pending germinations for this year
    lots_with_pending = Lot.objects.filter(
        germinations__for_year=year,
        germinations__status='pending',
        germinations__test_date__isnull=False 
    ).distinct().select_related('variety', 'grower').prefetch_related('germinations')
    
    if not lots_with_pending.exists():
        print(f"\nNo lots found with pending germinations for 20{year}")
        return
    
    print(f"\n{'='*80}")
    print(f"Lots with Pending Germinations for 20{year}")
    print(f"{'='*80}")
    
    for lot in lots_with_pending:
        pending_germs = lot.germinations.filter(for_year=year, status='pending', test_date__isnull=False)
        
        print(f"\nLot: {lot.build_lot_code()}")
        print(f"Variety: {lot.variety.name if hasattr(lot.variety, 'name') else lot.variety}")
        print(f"Grower: {lot.grower}")
        print(f"Pending Germs: {pending_germs.count()}")
        
        for germ in pending_germs:
            print(f"  - Rate: {germ.germination_rate}%, Test Date: {germ.test_date or 'Not set'}")
            if germ.notes:
                print(f"    Notes: {germ.notes}")
    
    print(f"\nTotal lots with pending germs: {lots_with_pending.count()}")



# ============================================================================
# MIXED LOT MANAGEMENT
# ============================================================================

def view_and_delete_mix_lot():
    """View mix lot details and optionally delete it"""
    from lots.models import MixLotComponent
    
    mix_lots = MixLot.objects.all().select_related('variety').prefetch_related(
        'components__lot__variety',
        'components__lot__grower',
        'components__sub_mix_lot__variety',
        'batches'
    ).order_by('variety__sku_prefix', '-created_date')
    
    if not mix_lots:
        print("\n❌ No mix lots found.")
        return
    
    print("\n--- Select a mix lot to view/delete ---")
    for idx, mix_lot in enumerate(mix_lots, start=1):
        is_retired = hasattr(mix_lot, 'retired_mix_info') and mix_lot.retired_mix_info is not None
        status = " [RETIRED]" if is_retired else ""
        print(f"{idx}. {mix_lot.variety.sku_prefix} - {mix_lot.lot_code} - {mix_lot.variety.var_name}{status}")
    
    try:
        selection = int(input("\nEnter number (0 to cancel): ").strip())
        if selection == 0:
            return
        mix_lot = mix_lots[selection - 1]
    except (ValueError, IndexError):
        print("❌ Invalid selection.")
        return
    
    # Display detailed information
    is_retired = hasattr(mix_lot, 'retired_mix_info') and mix_lot.retired_mix_info is not None
    
    print("\n" + "="*80)
    print(f"MIX LOT DETAILS")
    print("="*80)
    print(f"Database ID: {mix_lot.id}")
    print(f"Mix Variety: {mix_lot.variety.var_name} ({mix_lot.variety.sku_prefix})")
    print(f"Lot Code: {mix_lot.lot_code}")
    print(f"Created Date: {mix_lot.created_date.strftime('%Y-%m-%d')}")
    print(f"Status: {'RETIRED' if is_retired else 'Active'}")
    print(f"Germination Rate: {mix_lot.get_current_germ_rate() or 'N/A'}")
    
    # Show components
    print(f"\n--- Components ({mix_lot.components.count()}) ---")
    for comp in mix_lot.components.all():
        if comp.lot:
            # Regular lot component
            print(f"  • Regular Lot: {comp.lot.build_lot_code()} - {comp.lot.variety.var_name} ({comp.parts} parts)")
        elif comp.sub_mix_lot:
            # Sub-mix lot component
            print(f"  • Mix Lot: {comp.sub_mix_lot.lot_code} - {comp.sub_mix_lot.variety.var_name} ({comp.parts} parts)")
    
    # Show batches
    print(f"\n--- Batches ({mix_lot.batches.count()}) ---")
    if mix_lot.batches.exists():
        for batch in mix_lot.batches.all():
            print(f"  • {batch.date.strftime('%Y-%m-%d')}: {batch.final_weight} lbs")
            if batch.notes:
                print(f"    Notes: {batch.notes}")
    else:
        print("  (No batches recorded)")
    
    print("="*80)
    
    # Confirm deletion
    print("\n⚠️  WARNING: This will permanently delete this mix lot!")
    print("This will also delete:")
    print(f"  - {mix_lot.components.count()} component record(s)")
    print(f"  - {mix_lot.batches.count()} batch record(s)")
    if is_retired:
        print(f"  - The retired lot record")
    
    confirm = input("\nType 'DELETE' to permanently remove this mix lot: ").strip()
    
    if confirm == "DELETE":
        lot_info = f"{mix_lot.variety.sku_prefix} - {mix_lot.lot_code}"
        mix_lot.delete()  # Django will cascade delete components, batches, and retired info
        print(f"\n✅ Mix lot '{lot_info}' has been deleted.")
    else:
        print("\n❌ Deletion cancelled.")





def sync_existing_lots_to_growout_prep():
    """
    Sync existing lots to growout_prep table.
    Finds all lots for a given year (or higher) and creates corresponding
    growout_prep records with lot_created=True.
    """
    from lots.models import Lot, GrowoutPrep, Grower
    from products.models import Variety
    from django.db.models import Q
    
    print("\n" + "="*60)
    print("SYNC EXISTING LOTS TO GROWOUT PREP")
    print("="*60)
    
    # Prompt for year
    while True:
        year_input = input("\nEnter 2-digit year (e.g., 26 for 2026) or higher: ").strip()
        try:
            year = int(year_input)
            if year < 0 or year > 99:
                print("Please enter a valid 2-digit year (00-99)")
                continue
            break
        except ValueError:
            print("Please enter a valid number")
    
    # Find all lots with this year or higher
    lots = Lot.objects.filter(year__gte=year).select_related('variety', 'grower')
    
    if not lots.exists():
        print(f"\nNo lots found with year >= {year}")
        return
    
    print(f"\nFound {lots.count()} lots with year >= {year}")
    
    # Show preview
    print("\nPreview of lots to sync:")
    preview_count = min(10, lots.count())
    for lot in lots[:preview_count]:
        print(f"  - {lot.build_lot_code()} ({lot.variety.var_name})")
    
    if lots.count() > preview_count:
        print(f"  ... and {lots.count() - preview_count} more")
    
    # Confirm
    confirm = input(f"\nCreate/update growout_prep records for these {lots.count()} lots? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("Cancelled.")
        return
    
    # Process lots
    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []
    
    print("\nProcessing...")
    
    for lot in lots:
        try:
            # Convert 2-digit year to 4-digit year for growout_prep
            # Assume years 00-49 are 2000s, 50-99 are 1900s
            full_year = 2000 + lot.year if lot.year < 50 else 1900 + lot.year
            
            # First check: Is this lot already linked to ANY growout_prep record?
            already_linked = GrowoutPrep.objects.filter(created_lot=lot).exists()
            
            if already_linked:
                skipped_count += 1
                print(f"  - Skipped (lot already linked): {lot.build_lot_code()}")
                continue
            
            # Second check: Does a growout_prep record exist for this variety/grower/year?
            existing_prep = GrowoutPrep.objects.filter(
                variety=lot.variety,
                grower=lot.grower,
                year=full_year
            ).first()
            
            if existing_prep:
                # Update existing record to link this lot
                existing_prep.created_lot = lot
                existing_prep.lot_created = True
                existing_prep.save()
                updated_count += 1
                print(f"  ✓ Updated existing prep: {lot.build_lot_code()}")
            else:
                # Create new growout_prep record
                GrowoutPrep.objects.create(
                    variety=lot.variety,
                    grower=lot.grower,
                    year=full_year,
                    quantity='',
                    price_per_lb=None,
                    lot_created=True,
                    created_lot=lot
                )
                created_count += 1
                print(f"  ✓ Created new prep: {lot.build_lot_code()}")
        
        except Exception as e:
            error_msg = f"Error processing {lot.build_lot_code()}: {str(e)}"
            errors.append(error_msg)
            print(f"  ✗ {error_msg}")
    
    # Summary
    print("\n" + "="*60)
    print("SYNC COMPLETE")
    print("="*60)
    print(f"Created: {created_count} new growout_prep records")
    print(f"Updated: {updated_count} existing records (linked lot)")
    print(f"Skipped: {skipped_count} (lot already linked to prep)")
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")
    
    print()



def mix_lot_menu():
    """Mix lot management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("MIX LOT MANAGEMENT")
        print("="*50)
        print("1. View/Delete a mix lot")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_and_delete_mix_lot()
            pause()




def lot_menu():
    """Lot management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("LOT MANAGEMENT")
        print("="*50)
        print("1. View all lots")
        print("2. View lot details")
        print("3. Add new lot")
        print("4. Edit lot")
        print("5. Retire lot")
        print("6. Find lots without germ entry for year")
        print("7. Delete all mix variety lots")
        print("8. Find lots with pending germination")
        print("9. View/delete mixed lots")
        print("10. Sync existing lots to growout prep (ADMIN)")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_lots()
            pause()
        elif choice == '2':
            view_lot_details()
            pause()
        elif choice == '3':
            add_lot()
            pause()
        elif choice == '4':
            edit_lot()
            pause()
        elif choice == '5':
            retire_lot()
            pause()
        elif choice == '6':
            find_lots_without_germ_for_year()
            pause()
        elif choice == '7':
            delete_mix_variety_lots()
            pause()
        elif choice == '8':
            find_lots_with_pending_germs()
            pause()
        elif choice == '9':
            view_and_delete_mix_lot()
            pause()
        elif choice == '10':
            sync_existing_lots_to_growout_prep()
            pause()


# ============================================================================
# STOCK SEED MANAGEMENT
# ============================================================================

def manage_stock_seed():
    """Interactive menu for viewing and deleting stock seed entries"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("STOCK SEED MANAGER")
        print("="*50)
        print("1. View stock seed entries")
        print("2. Delete a stock seed entry")
        print("3. Edit stock seed notes")
        print("0. Back to main menu")
       
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3'])
        
        if choice == '0':
            break
        elif choice == "1":
            stock_seeds = StockSeed.objects.all().select_related('lot__variety', 'lot__grower').order_by('-date')
            if not stock_seeds:
                print("\n❌ No stock seed entries found.")
            else:
                print("\n" + "-"*100)
                print(f"{'#':<4} {'Lot Code':<20} {'Qty':<15} {'Date':<12} {'Notes':<40}")
                print("-"*100)
                for idx, ss in enumerate(stock_seeds, start=1):
                    print(f"{idx:<4} {ss.lot.build_lot_code():<20} {ss.qty:<15} {ss.date:<12} {ss.notes or '-':<40}")
                print(f"\nTotal: {stock_seeds.count()} entries")
            pause()
        
        elif choice == "2":
            stock_seeds = StockSeed.objects.all().select_related('lot__variety', 'lot__grower')
            if not stock_seeds:
                print("\n❌ No stock seed entries available to delete.")
                pause()
                continue
            print("\n--- Select an entry to delete ---")
            for idx, ss in enumerate(stock_seeds, start=1):
                print(f"{idx}. Lot: {ss.lot.build_lot_code()} | "
                      f"Qty: {ss.qty} | Date: {ss.date} | Notes: {ss.notes or '-'}")
            try:
                selection = int(input("Enter the number of the entry to delete (0 to cancel): ").strip())
                if selection == 0:
                    print("Delete canceled.")
                    pause()
                    continue
                entry_to_delete = stock_seeds[selection - 1]
            except (ValueError, IndexError):
                print("❌ Invalid selection. Please try again.")
                pause()
                continue
            confirm = input(f"Are you sure you want to delete Lot {entry_to_delete.lot.build_lot_code()}? (y/n): ").strip().lower()
            if confirm == "y":
                entry_to_delete.delete()
                print("✅ Entry deleted successfully.")
            else:
                print("❌ Delete canceled.")
            pause()
        
        elif choice == "3":
            stock_seeds = StockSeed.objects.all().select_related('lot__variety', 'lot__grower')
            if not stock_seeds:
                print("\n❌ No stock seed entries available to edit.")
                pause()
                continue
            print("\n--- Select an entry to edit ---")
            for idx, ss in enumerate(stock_seeds, start=1):
                print(f"{idx}. Lot: {ss.lot.build_lot_code()} | "
                      f"Qty: {ss.qty} | Date: {ss.date} | Notes: {ss.notes or '-'}")
            try:
                selection = int(input("Enter the number of the entry to edit (0 to cancel): ").strip())
                if selection == 0:
                    print("Edit canceled.")
                    pause()
                    continue
                entry_to_edit = stock_seeds[selection - 1]
            except (ValueError, IndexError):
                print("❌ Invalid selection. Please try again.")
                pause()
                continue
            
            # Show current notes
            print(f"\nCurrent notes: {entry_to_edit.notes or '(empty)'}")
            print("Enter new notes (or type 'CLEAR' to remove notes, or press Enter to cancel):")
            new_notes = input().strip()
            
            if new_notes == "":
                print("Edit canceled.")
            elif new_notes.upper() == "CLEAR":
                entry_to_edit.notes = None
                entry_to_edit.save()
                print("✅ Notes cleared successfully.")
            else:
                entry_to_edit.notes = new_notes
                entry_to_edit.save()
                print("✅ Notes updated successfully.")
            pause()


# ============================================================================
# INVENTORY MANAGEMENT
# ============================================================================

def view_all_inventory():
    """View inventory for all lots"""
    inventories = Inventory.objects.all().select_related('lot__variety', 'lot__grower').order_by('-inv_date')
    if not inventories:
        print("\n❌ No inventory records found.")
        return
    
    print("\n" + "="*100)
    print("INVENTORY RECORDS")
    print("="*100)
    print(f"{'Lot Code':<20} {'Weight (lbs)':<15} {'Smarties':<12} {'Date':<12} {'Notes':<30}")
    print("-"*100)
    for inv in inventories[:50]:  # Show latest 50
        notes = inv.notes[:27] + '...' if inv.notes and len(inv.notes) > 30 else (inv.notes or '-')
        print(f"{inv.lot.build_lot_code():<20} {inv.weight:<15} {inv.smarties_ct:<12} {inv.inv_date:<12} {notes:<30}")
    if inventories.count() > 50:
        print(f"\n(Showing 50 of {inventories.count()} records)")

def add_inventory():
    """Add inventory record - PLACEHOLDER"""
    print("\n⚠️  ADD INVENTORY - Function placeholder")
    print("This would allow you to:")
    print("  - Select lot")
    print("  - Enter weight in pounds")
    print("  - Enter smarties count")
    print("  - Add notes")


def edit_inventory_record():
    """Edit an existing inventory record for a lot"""
    
    # Step 1: Get SKU prefix
    sku_prefix = input("\nEnter SKU prefix (e.g., CAR-DR): ").strip().upper()
    if not sku_prefix:
        print("No SKU prefix entered. Returning to menu.")
        return
    
    # Step 2: Find all lots with this SKU prefix
    try:
        variety = Variety.objects.get(sku_prefix=sku_prefix)
    except Variety.DoesNotExist:
        print(f"No variety found with SKU prefix '{sku_prefix}'")
        return
    
    lots = Lot.objects.filter(variety=variety).order_by('-year', 'grower__code', 'harvest')
    
    if not lots.exists():
        print(f"No lots found for {sku_prefix}")
        return
    
    # Step 3: Display lots and let user select
    print(f"\nDisplaying lots for {variety.var_name}")
    print(f"{'#':<4} {'Lot Code':<20}")
    print("-" * 30)
    for idx, lot in enumerate(lots, 1):
        print(f"{idx:<4} {lot.build_lot_code():<20}")
    
    lot_choice = input("\nSelect lot number (or 'q' to quit): ").strip()
    if lot_choice.lower() == 'q':
        return
    
    try:
        lot_idx = int(lot_choice) - 1
        selected_lot = lots[lot_idx]
    except (ValueError, IndexError):
        print("Invalid selection")
        return
    
    # Step 4: Display inventory records for this lot
    inventory_records = Inventory.objects.filter(lot=selected_lot).order_by('-inv_date')
    
    if not inventory_records.exists():
        print(f"\nNo inventory records found for {selected_lot.build_lot_code()}")
        return
    
    print(f"\nInventory records for {selected_lot.build_lot_code()}:")
    print(f"{'#':<4} {'Date':<12} {'Weight (lbs)':<15} {'Notes'}")
    print("-" * 60)
    for idx, inv in enumerate(inventory_records, 1):
        notes_display = (inv.notes[:30] + '...') if inv.notes and len(inv.notes) > 30 else (inv.notes or '--')
        print(f"{idx:<4} {inv.inv_date.strftime('%m/%d/%Y'):<12} {inv.weight:<15} {notes_display}")
    
    inv_choice = input("\nSelect inventory record number to edit (or 'q' to quit): ").strip()
    if inv_choice.lower() == 'q':
        return
    
    try:
        inv_idx = int(inv_choice) - 1
        selected_inv = inventory_records[inv_idx]
    except (ValueError, IndexError):
        print("Invalid selection")
        return
    
    # Step 5: Walk through edit process
    print(f"\nEditing inventory record from {selected_inv.inv_date.strftime('%m/%d/%Y')}")
    print("Press Enter to keep current value, or type new value:\n")
    
    # Weight
    current_weight = selected_inv.weight
    weight_input = input(f"Weight in lbs (current: {current_weight}): ").strip()
    new_weight = Decimal(weight_input) if weight_input else current_weight
    
    # Inventory date
    current_date = selected_inv.inv_date.strftime('%m/%d/%Y')
    date_input = input(f"Inventory date MM/DD/YYYY (current: {current_date}): ").strip()
    if date_input:
        try:
            new_date = datetime.strptime(date_input, "%m/%d/%Y").date()
        except ValueError:
            print("Invalid date format. Keeping current date.")
            new_date = selected_inv.inv_date
    else:
        new_date = selected_inv.inv_date
    
    # Notes
    current_notes = selected_inv.notes or 'None'
    print(f"Current notes: {current_notes}")
    notes_input = input("New notes (or Enter to keep current): ").strip()
    new_notes = notes_input if notes_input else selected_inv.notes
    
    # Step 6: Confirm changes
    print("\n" + "="*60)
    print("CONFIRM CHANGES:")
    print("="*60)
    print(f"Lot: {selected_lot.build_lot_code()}")
    print(f"Weight: {current_weight} lbs → {new_weight} lbs")
    print(f"Date: {current_date} → {new_date.strftime('%m/%d/%Y')}")
    print(f"Notes: {current_notes} → {new_notes or 'None'}")
    print("="*60)
    
    confirm = input("\nSave these changes? (y/n): ").strip().lower()
    if confirm == 'y':
        selected_inv.weight = new_weight
        selected_inv.inv_date = new_date
        selected_inv.notes = new_notes
        selected_inv.save()
        print(f"✓ Inventory record updated successfully!")
    else:
        print("Changes discarded.")

def inventory_menu():
    """Inventory management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("INVENTORY MANAGEMENT")
        print("="*50)
        print("1. View all inventory")
        print("2. Add inventory record")
        print("3. Edit inventory record")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_all_inventory()
            pause()
        elif choice == '2':
            add_inventory()
            pause()
        elif choice == '3':
            edit_inventory_record()
            pause()


# ============================================================================
# GERMINATION MANAGEMENT
# ============================================================================

def view_germination_batches():
    """View all germination batches"""
    batches = GerminationBatch.objects.all().order_by('-date')
    if not batches:
        print("\n❌ No germination batches found.")
        return
    
    print("\n" + "="*100)
    print("GERMINATION BATCHES")
    print("="*100)
    for batch in batches:
        print(f"\nBatch {batch.batch_number} - {batch.date} (Tracking: {batch.tracking_number or 'N/A'})")
        print("-"*100)
        germinations = batch.germinations.all().select_related('lot__variety', 'lot__grower')
        if germinations:
            for germ in germinations:
                print(f"  {germ.lot.build_lot_code():<20} {germ.germination_rate}% for 20{germ.for_year} - Status: {germ.status}")
        else:
            print("  No germinations in this batch")

def view_all_germinations():
    """View all germination records"""
    germinations = Germination.objects.filter(test_date__isnull=False).select_related('lot__variety', 'lot__grower').order_by('-test_date')
    if not germinations:
        print("\n❌ No germination records found.")
        return
    
    print("\n" + "="*100)
    print("GERMINATION RECORDS")
    print("="*100)
    print(f"{'Lot Code':<20} {'Rate':<8} {'For Year':<10} {'Test Date':<12} {'Status':<12} {'Batch'}")
    print("-"*100)
    for germ in germinations[:50]:  # Show latest 50
        batch_num = germ.batch.batch_number if germ.batch else '-'
        print(f"{germ.lot.build_lot_code():<20} {germ.germination_rate}%{'':<6} 20{germ.for_year:<8} {germ.test_date or '-':<12} {germ.status:<12} {batch_num}")
    if germinations.count() > 50:
        print(f"\n(Showing 50 of {germinations.count()} records)")

def add_germination_batch():
    """Add a germination batch - PLACEHOLDER"""
    print("\n⚠️  ADD GERMINATION BATCH - Function placeholder")
    print("This would allow you to:")
    print("  - Create new batch number")
    print("  - Set date")
    print("  - Enter tracking number")
    print("  - Add lots to batch")

def clear_germination_batch_and_test_germinations():
    """Clear all germination batches and test germinations"""
    confirm = input("\n⚠️  WARNING: This will delete ALL germination batches and test germinations for 2026!\nType 'DELETE' to confirm: ").strip()
    if confirm != "DELETE":
        print("❌ Operation cancelled.")
        return
    
    GerminationBatch.objects.all().delete()
    print("✅ All germination batches cleared.")
    
    Germination.objects.filter(for_year=26).delete()
    print("✅ All test germinations cleared for 2026.")

def add_single_germination():
    """Add a germination record for a single lot."""
    sku_prefix = input("\nEnter SKU prefix: ").strip().upper()
    
    # Get all active (non-retired) lots for this variety
    lots = Lot.objects.filter(
        variety__sku_prefix=sku_prefix
    ).exclude(
        retired_info__isnull=False  # Exclude retired lots
    ).select_related('variety', 'grower').order_by('-year', 'harvest')
    
    if not lots.exists():
        print(f"❌ No active lots found for {sku_prefix}")
        return
    
    # Display lots
    print(f"\n📦 Active lots for {sku_prefix}:")
    print("-" * 60)
    for idx, lot in enumerate(lots, 1):
        recent_germ = lot.get_most_recent_germ_percent_with_year()
        print(f"{idx}. {lot.build_lot_code()} - Recent germ: {recent_germ or 'None'}")
    
    # Select lot
    try:
        choice = int(input("\nSelect lot number (0 to cancel): ").strip())
        if choice == 0:
            return
        if choice < 1 or choice > len(lots):
            print("❌ Invalid selection")
            return
        selected_lot = lots[choice - 1]
    except ValueError:
        print("❌ Invalid input")
        return
    
    print(f"\n🧪 Adding germination record for {selected_lot.build_lot_code()}")
    print("-" * 60)
    
    # Get germination_rate
    while True:
        try:
            germ_rate = int(input("Germination rate (0-100): ").strip())
            if 0 <= germ_rate <= 100:
                break
            print("❌ Must be between 0 and 100")
        except ValueError:
            print("❌ Invalid number")
    
    # Get test_date (MM DD YY format)
    while True:
        try:
            month = input("Test date - Month (MM): ").strip().zfill(2)
            day = input("Test date - Day (DD): ").strip().zfill(2)
            year = input("Test date - Year (YY): ").strip().zfill(2)
            
            # Convert to full year
            full_year = f"20{year}"
            test_date_str = f"{full_year}-{month}-{day}"
            test_date = date.fromisoformat(test_date_str)
            break
        except ValueError:
            print("❌ Invalid date format. Try again.")
    
    # Get for_year
    while True:
        try:
            for_year = int(input("For year (YY, e.g., 26 for 2026): ").strip())
            if 0 <= for_year <= 99:
                break
            print("❌ Must be 2-digit year")
        except ValueError:
            print("❌ Invalid number")
    
    # Get notes (optional)
    notes = input("Notes (optional, press Enter to skip): ").strip()
    
    # Confirm
    print("\n" + "=" * 60)
    print(f"Lot: {selected_lot.build_lot_code()}")
    print(f"Germination rate: {germ_rate}%")
    print(f"Test date: {test_date}")
    print(f"For year: 20{for_year}")
    print(f"Status: pending")
    print(f"Batch: None (in-house test)")
    if notes:
        print(f"Notes: {notes}")
    print("=" * 60)
    
    confirm = input("\nSave this germination record? (y/n): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        try:
            Germination.objects.create(
                lot=selected_lot,
                batch=None,
                status='pending',
                germination_rate=germ_rate,
                test_date=test_date,
                for_year=for_year,
                notes=notes if notes else None
            )
            print(f"✅ Successfully added germination record for {selected_lot.build_lot_code()}")
        except Exception as e:
            print(f"❌ Error saving germination: {e}")
    else:
        print("❌ Cancelled")

def edit_germination():
    """Edit an existing germination record."""
    sku_prefix = input("\nEnter SKU prefix: ").strip().upper()
    
    # Get all lots (including retired) for this variety
    lots = Lot.objects.filter(
        variety__sku_prefix=sku_prefix
    ).select_related('variety', 'grower').order_by('-year', 'harvest')
    
    if not lots.exists():
        print(f"❌ No lots found for {sku_prefix}")
        return
    
    # Display lots
    print(f"\n📦 Lots for {sku_prefix}:")
    print("-" * 60)
    for idx, lot in enumerate(lots, 1):
        germ_count = lot.germinations.count()
        print(f"{idx}. {lot.build_lot_code()} - {germ_count} germination record(s)")
    
    # Select lot
    try:
        choice = int(input("\nSelect lot number (0 to cancel): ").strip())
        if choice == 0:
            return
        if choice < 1 or choice > len(lots):
            print("❌ Invalid selection")
            return
        selected_lot = lots[choice - 1]
    except ValueError:
        print("❌ Invalid input")
        return
    
    # Get germination records for this lot
    germinations = selected_lot.germinations.all().order_by('-test_date', '-for_year')
    
    if not germinations.exists():
        print(f"❌ No germination records found for {selected_lot.build_lot_code()}")
        return
    
    # Display germination records
    print(f"\n🧪 Germination records for {selected_lot.build_lot_code()}:")
    print("-" * 60)
    for idx, germ in enumerate(germinations, 1):
        test_date_str = germ.test_date.strftime('%m/%d/%y') if germ.test_date else "No date"
        batch_str = f"Batch {germ.batch.batch_number}" if germ.batch else "In-house"
        print(f"{idx}. {germ.germination_rate}% - For 20{germ.for_year} - {test_date_str} - {germ.status} - {batch_str}")
    
    # Select germination record
    try:
        germ_choice = int(input("\nSelect germination record (0 to cancel): ").strip())
        if germ_choice == 0:
            return
        if germ_choice < 1 or germ_choice > len(germinations):
            print("❌ Invalid selection")
            return
        selected_germ = germinations[germ_choice - 1]
    except ValueError:
        print("❌ Invalid input")
        return
    
    print(f"\n📝 Editing germination record")
    print("Press Enter to keep current value, or enter new value\n")
    
    # Edit germination_rate
    current_rate = selected_germ.germination_rate
    rate_input = input(f"Germination rate (0-100) [{current_rate}]: ").strip()
    if rate_input:
        try:
            new_rate = int(rate_input)
            if 0 <= new_rate <= 100:
                selected_germ.germination_rate = new_rate
            else:
                print("⚠️  Invalid rate, keeping current value")
        except ValueError:
            print("⚠️  Invalid number, keeping current value")
    
    # Edit test_date
    current_date_str = selected_germ.test_date.strftime('%m/%d/%y') if selected_germ.test_date else "None"
    print(f"Current test date: {current_date_str}")
    change_date = input("Change test date? (y/n): ").strip().lower()
    if change_date in ['y', 'yes']:
        while True:
            try:
                month = input("Test date - Month (MM): ").strip().zfill(2)
                day = input("Test date - Day (DD): ").strip().zfill(2)
                year = input("Test date - Year (YY): ").strip().zfill(2)
                
                full_year = f"20{year}"
                test_date_str = f"{full_year}-{month}-{day}"
                new_test_date = date.fromisoformat(test_date_str)
                selected_germ.test_date = new_test_date
                break
            except ValueError:
                print("❌ Invalid date format. Try again.")
    
    # Edit for_year
    current_for_year = selected_germ.for_year
    for_year_input = input(f"For year (YY) [{current_for_year}]: ").strip()
    if for_year_input:
        try:
            new_for_year = int(for_year_input)
            if 0 <= new_for_year <= 99:
                selected_germ.for_year = new_for_year
            else:
                print("⚠️  Invalid year, keeping current value")
        except ValueError:
            print("⚠️  Invalid number, keeping current value")
    
    # Edit status
    current_status = selected_germ.status
    print(f"Current status: {current_status}")
    status_input = input("Status (pending/active) or Enter to skip: ").strip().lower()
    if status_input in ['pending', 'active']:
        selected_germ.status = status_input
    elif status_input and status_input not in ['', 'skip']:
        print("⚠️  Invalid status, keeping current value")
    
    # Edit notes
    current_notes = selected_germ.notes or "(none)"
    notes_input = input(f"Notes [{current_notes}]: ").strip()
    if notes_input:
        selected_germ.notes = notes_input
    
    # Confirm save
    print("\n" + "=" * 60)
    print(f"Lot: {selected_lot.build_lot_code()}")
    print(f"Germination rate: {selected_germ.germination_rate}%")
    print(f"Test date: {selected_germ.test_date}")
    print(f"For year: 20{selected_germ.for_year}")
    print(f"Status: {selected_germ.status}")
    print(f"Batch: {selected_germ.batch.batch_number if selected_germ.batch else 'None (in-house)'}")
    print(f"Notes: {selected_germ.notes or '(none)'}")
    print("=" * 60)
    
    confirm = input("\nSave changes? (y/n): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        try:
            selected_germ.save()
            print(f"✅ Successfully updated germination record")
        except Exception as e:
            print(f"❌ Error saving: {e}")
    else:
        print("❌ Changes discarded")

def germination_menu():
    """Germination management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("GERMINATION MANAGEMENT")
        print("="*50)
        print("1. View germination batches")
        print("2. View all germination records")
        print("3. Add germination batch")
        print("4. Clear batches & 2026 test germinations")
        print("5. Add single germination record")
        print("6. Edit germination record")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5', '6'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_germination_batches()
            pause()
        elif choice == '2':
            view_all_germinations()
            pause()
        elif choice == '3':
            add_germination_batch()
            pause()
        elif choice == '4':
            clear_germination_batch_and_test_germinations()
            pause()
        elif choice == '5':
            add_single_germination()
            pause()
        elif choice == '6':
            edit_germination()
            pause()


# ============================================================================
# GERM SAMPLE PRINT MANAGEMENT
# ============================================================================

def view_germ_sample_prints():
    """View germ sample print records"""
    prints = GermSamplePrint.objects.all().select_related('lot__variety', 'lot__grower').order_by('-print_date')
    if not prints:
        print("\n❌ No germ sample print records found.")
        return
    
    print("\n" + "="*80)
    print("GERM SAMPLE PRINTS")
    print("="*80)
    print(f"{'Lot Code':<20} {'For Year':<12} {'Print Date':<15}")
    print("-"*80)
    for p in prints[:50]:  # Show latest 50
        print(f"{p.lot.build_lot_code():<20} 20{p.for_year:<10} {p.print_date}")
    if prints.count() > 50:
        print(f"\n(Showing 50 of {prints.count()} records)")

def clear_germ_sample_print_table():
    """Clear all entries in the GermSamplePrint table"""
    confirm = input("\n⚠️  WARNING: This will delete ALL germ sample prints!\nType 'DELETE' to confirm: ").strip()
    if confirm != "DELETE":
        print("❌ Operation cancelled.")
        return
    
    GermSamplePrint.objects.all().delete()
    print("✅ All germ sample prints cleared.")

def clear_september_2025_germ_sample_prints():
    """Clear all entries in the GermSamplePrint table with print_date in September 2025"""
    september_2025_prints = GermSamplePrint.objects.filter(print_date__year=2025, print_date__month=9)
    count = september_2025_prints.count()
    
    if count == 0:
        print("\n❌ No September 2025 prints found.")
        return
    
    confirm = input(f"\n⚠️  This will delete {count} prints from September 2025. Continue? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Operation cancelled.")
        return
    
    september_2025_prints.delete()
    print(f"✅ Cleared {count} germ sample prints from September 2025.")

def germ_sample_print_menu():
    """Germ sample print management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("GERM SAMPLE PRINT MANAGEMENT")
        print("="*50)
        print("1. View germ sample prints")
        print("2. Clear all germ sample prints")
        print("3. Clear September 2025 prints")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_germ_sample_prints()
            pause()
        elif choice == '2':
            clear_germ_sample_print_table()
            pause()
        elif choice == '3':
            clear_september_2025_germ_sample_prints()
            pause()


# ============================================================================
# RETIRED LOTS MANAGEMENT
# ============================================================================

def view_retired_lots():
    """View all retired lots"""
    retired = RetiredLot.objects.all().select_related('lot__variety', 'lot__grower').order_by('-retired_date')
    if not retired:
        print("\n❌ No retired lots found.")
        return
    
    print("\n" + "="*100)
    print("RETIRED LOTS")
    print("="*100)
    print(f"{'Lot Code':<20} {'Retired Date':<15} {'Lbs Remaining':<15} {'Notes':<40}")
    print("-"*100)
    for r in retired:
        notes = r.notes[:37] + '...' if r.notes and len(r.notes) > 40 else (r.notes or '-')
        # FIX: Convert date to string
        date_str = r.retired_date.strftime('%Y-%m-%d')
        print(f"{r.lot.build_lot_code():<20} {date_str:<15} {r.lbs_remaining:<15} {notes:<40}")

def add_retired_lot():
    """Retire a lot - PLACEHOLDER"""
    print("\n⚠️  RETIRE LOT - Function placeholder")


def remove_retired_status():
    """Un-retire a regular lot by deleting its RetiredLot entry"""
    
    # Step 1: Prompt for SKU prefix
    sku_prefix = input("\nEnter SKU prefix (e.g., BEA-CA, CAR-DR): ").strip().upper()
    
    if not sku_prefix:
        print("❌ SKU prefix cannot be empty.")
        return
    
    # Step 2: Check if variety exists
    try:
        variety = Variety.objects.get(sku_prefix=sku_prefix)
    except Variety.DoesNotExist:
        print(f"❌ Variety with SKU prefix '{sku_prefix}' not found.")
        return
    
    # Step 3: Get retired lots for this variety
    retired_lots = RetiredLot.objects.filter(
        lot__variety=variety
    ).select_related('lot', 'lot__grower').order_by('-retired_date')
    
    if not retired_lots.exists():
        print(f"\n✓ No retired lots found for {variety.var_name} ({sku_prefix})")
        return
    
    # Step 4: Display retired lots for this variety
    print("\n" + "="*80)
    print(f"RETIRED LOTS FOR: {variety.var_name} ({sku_prefix})")
    print("="*80)
    
    for i, retired in enumerate(retired_lots, 1):
        lot = retired.lot
        print(f"\n{i}. {lot.build_lot_code()}")
        print(f"   Grower: {lot.grower.name if lot.grower else 'Unknown'}")
        print(f"   Year: {lot.year}")
        print(f"   Retired Date: {retired.retired_date}")
        print(f"   Lbs Remaining: {retired.lbs_remaining} lbs")
        if retired.notes:
            print(f"   Notes: {retired.notes}")
    
    print("\n0. Cancel")
    
    # Step 5: Select lot to un-retire
    try:
        selection = int(input("\nSelect lot number to un-retire (0 to cancel): ").strip())
        if selection == 0:
            print("\n❌ Operation cancelled.")
            return
        
        if 1 <= selection <= len(retired_lots):
            retired = list(retired_lots)[selection - 1]
            lot = retired.lot
            
            # Step 6: Confirm un-retirement
            print(f"\n⚠️  You are about to un-retire: {lot.build_lot_code()}")
            confirm = input("Type 'YES' to confirm: ").strip()
            
            if confirm == 'YES':
                retired.delete()
                print(f"\n✅ {lot.build_lot_code()} has been un-retired successfully!")
            else:
                print("\n❌ Operation cancelled.")
        else:
            print("\n❌ Invalid selection!")
    except ValueError:
        print("\n❌ Invalid input! Please enter a number.")

def update_retired_lot_lbs():
    """Update lbs remaining for a retired lot"""
    retired_lots = RetiredLot.objects.all().select_related('lot__variety', 'lot__grower').order_by('lot__variety__sku_prefix')
    
    if not retired_lots:
        print("\n❌ No retired lots found.")
        return
    
    print("\n--- Select a retired lot to update ---")
    for idx, r in enumerate(retired_lots, start=1):
        print(f"{idx}. {r.lot.build_lot_code()} - Current: {r.lbs_remaining} lbs")
    
    try:
        selection = int(input("\nEnter number (0 to cancel): ").strip())
        if selection == 0:
            return
        retired_lot = retired_lots[selection - 1]
    except (ValueError, IndexError):
        print("❌ Invalid selection.")
        return
    
    print(f"\nUpdating: {retired_lot.lot.build_lot_code()}")
    print(f"Current lbs remaining: {retired_lot.lbs_remaining}")
    
    try:
        new_lbs = input("Enter new lbs remaining: ").strip()
        new_lbs = float(new_lbs)
        
        if new_lbs < 0:
            print("❌ Cannot set negative weight.")
            return
        
        retired_lot.lbs_remaining = new_lbs
        retired_lot.save()
        print(f"✅ Updated lbs remaining to {new_lbs} lbs.")
        
    except ValueError:
        print("❌ Invalid number entered.")


def retired_lots_menu():
    """Retired lots management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("RETIRED LOTS MANAGEMENT")
        print("="*50)
        print("1. View retired lots")
        print("2. Retire a lot")
        print("3. Un-retire a lot")
        print("4. Update lbs remaining")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_retired_lots()
            pause()
        elif choice == '2':
            add_retired_lot()
            pause()
        elif choice == '3':
            remove_retired_status()
            pause()
        elif choice == '4':
            update_retired_lot_lbs()
            pause()


# ============================================================================
# LOT NOTES MANAGEMENT
# ============================================================================

def view_lot_notes():
    """View lot notes"""
    notes = LotNote.objects.all().select_related('lot__variety', 'lot__grower').order_by('-date')
    if not notes:
        print("\n❌ No lot notes found.")
        return
    
    print("\n" + "="*100)
    print("LOT NOTES")
    print("="*100)
    for note in notes[:30]:  # Show latest 30
        print(f"\n{note.lot.build_lot_code()} - {note.date.strftime('%Y-%m-%d %H:%M')}")
        print(f"  {note.note}")
        print("-"*100)
    if notes.count() > 30:
        print(f"\n(Showing 30 of {notes.count()} notes)")

def add_lot_note():
    """Add a note to a lot - PLACEHOLDER"""
    print("\n⚠️  ADD LOT NOTE - Function placeholder")

def lot_notes_menu():
    """Lot notes management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("LOT NOTES MANAGEMENT")
        print("="*50)
        print("1. View lot notes")
        print("2. Add lot note")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_lot_notes()
            pause()
        elif choice == '2':
            add_lot_note()
            pause()


# ============================================================================
# GROWOUT MANAGEMENT
# ============================================================================

def view_growouts():
    """View growout information"""
    growouts = Growout.objects.all().select_related('lot__variety', 'lot__grower')
    if not growouts:
        print("\n❌ No growout records found.")
        return
    
    print("\n" + "="*100)
    print("GROWOUTS")
    print("="*100)
    for g in growouts:
        print(f"\nLot: {g.lot.build_lot_code()}")
        print(f"  Planted: {g.planted_date or '-'}")
        print(f"  Transplant: {g.transplant_date or '-'}")
        print(f"  Quantity: {g.quantity or '-'}")
        print(f"  Price/lb: {g.price_per_lb or '-'}")
        print(f"  Bed Ft: {g.bed_ft or '-'}")
        print(f"  Amt Sown: {g.amt_sown or '-'}")
        if g.notes:
            print(f"  Notes: {g.notes}")
        print("-"*100)

def add_growout():
    """Add growout information - PLACEHOLDER"""
    print("\n⚠️  ADD GROWOUT - Function placeholder")

def edit_growout():
    """Edit growout information - PLACEHOLDER"""
    print("\n⚠️  EDIT GROWOUT - Function placeholder")

def growout_menu():
    """Growout management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("GROWOUT MANAGEMENT")
        print("="*50)
        print("1. View growouts")
        print("2. Add growout")
        print("3. Edit growout")
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_growouts()
            pause()
        elif choice == '2':
            add_growout()
            pause()
        elif choice == '3':
            edit_growout()
            pause()


# ============================================================================
# MAIN MENU
# ============================================================================

def main_menu():
    """Main menu loop"""
    while True:
        clear_screen()
        print("\n" + "="*60)
        print(" "*15 + "UPRISING SEEDS - LOT MANAGER")
        print("="*60)
        print("\n1.  Grower Management")
        print("2.  Lot Management")
        print("3.  Stock Seed Management")
        print("4.  Inventory Management")
        print("5.  Germination Management")
        print("6.  Germ Sample Print Management")
        print("7.  Retired Lots Management")
        print("8.  Lot Notes Management")
        print("9.  Growout Management")
        print("0.  Exit")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])
        
        if choice == '0':
            print("\n👋 Goodbye!")
            break
        elif choice == '1':
            grower_menu()
        elif choice == '2':
            lot_menu()
        elif choice == '3':
            manage_stock_seed()
        elif choice == '4':
            inventory_menu()
        elif choice == '5':
            germination_menu()
        elif choice == '6':
            germ_sample_print_menu()
        elif choice == '7':
            retired_lots_menu()
        elif choice == '8':
            lot_notes_menu()
        elif choice == '9':
            growout_menu()


if __name__ == "__main__":
    main_menu()
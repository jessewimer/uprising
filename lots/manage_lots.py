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

from lots.models import Grower, Lot, StockSeed, Inventory, GermSamplePrint, Germination, GerminationBatch, RetiredLot, LotNote, Growout
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
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5'])
        
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

def edit_inventory():
    """Edit inventory record - PLACEHOLDER"""
    print("\n⚠️  EDIT INVENTORY - Function placeholder")

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
            edit_inventory()
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
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4'])
        
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
    """Un-retire a lot - PLACEHOLDER"""
    print("\n⚠️  UN-RETIRE LOT - Function placeholder")

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
        print("0. Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3'])
        
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
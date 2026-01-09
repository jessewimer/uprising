# import os
# import django
# import sys

# # Get the current directory path
# current_path = os.path.dirname(os.path.abspath(__file__))

# # Get the project directory path by going up two levels from the current directory
# project_path = os.path.abspath(os.path.join(current_path, '..'))

# # Add the project directory to the sys.path
# sys.path.append(project_path)

# # Set the DJANGO_SETTINGS_MODULE
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
# django.setup()

# from orders.models import OnlineOrder, OOIncludes, OOIncludesMisc, BatchMetadata, BulkBatch
# from stores.models import Store, StoreOrder




import os
import django
import sys

# Get the current directory path
current_path = os.path.dirname(os.path.abspath(__file__))
# Get the project directory path by going up two levels from the current directory
project_path = os.path.abspath(os.path.join(current_path, '..'))
# Add the project directory to the sys.path
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# Set the DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
django.setup()

from orders.models import OnlineOrder, OOIncludes, OOIncludesMisc, BatchMetadata, BulkBatch
from django.db import transaction


def print_header():
    """Print a clean header for the CLI"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print("  ONLINE ORDERS DATABASE CLEANUP UTILITY")
    print("=" * 60)
    print()


def get_table_counts():
    """Return current counts for all tables"""
    return {
        'OnlineOrder': OnlineOrder.objects.count(),
        'OOIncludes': OOIncludes.objects.count(),
        'OOIncludesMisc': OOIncludesMisc.objects.count(),
        'BatchMetadata': BatchMetadata.objects.count(),
        'BulkBatch': BulkBatch.objects.count(),
    }


def display_counts(counts):
    """Display current table counts"""
    print("\nCurrent Database Status:")
    print("-" * 60)
    for table, count in counts.items():
        print(f"  {table:20s}: {count:>6d} records")
    print("-" * 60)


def confirm_action(message):
    """Get user confirmation with y/n"""
    while True:
        response = input(f"\n{message} (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' or 'n'")


def clear_all_tables():
    """Clear all online order related tables"""
    print("\n⚠️  WARNING: This will delete ALL data from the following tables:")
    print("  - OnlineOrder")
    print("  - OOIncludes")
    print("  - OOIncludesMisc")
    print("  - BatchMetadata")
    print("  - BulkBatch")
    
    counts = get_table_counts()
    total_records = sum(counts.values())
    
    print(f"\n  Total records to be deleted: {total_records}")
    
    if total_records == 0:
        print("\n✓ All tables are already empty!")
        return
    
    if not confirm_action("Are you SURE you want to delete all records?"):
        print("\n✗ Operation cancelled.")
        return
    
    # Double confirmation for safety
    if not confirm_action("Type 'y' again to confirm deletion"):
        print("\n✗ Operation cancelled.")
        return
    
    try:
        with transaction.atomic():
            # Delete in reverse order of dependencies
            bulk_batch_count = BulkBatch.objects.all().delete()[0]
            batch_metadata_count = BatchMetadata.objects.all().delete()[0]
            oo_includes_misc_count = OOIncludesMisc.objects.all().delete()[0]
            oo_includes_count = OOIncludes.objects.all().delete()[0]
            online_order_count = OnlineOrder.objects.all().delete()[0]
            
        print("\n✓ Successfully deleted:")
        print(f"  - {online_order_count} OnlineOrder records")
        print(f"  - {oo_includes_count} OOIncludes records")
        print(f"  - {oo_includes_misc_count} OOIncludesMisc records")
        print(f"  - {batch_metadata_count} BatchMetadata records")
        print(f"  - {bulk_batch_count} BulkBatch records")
        print(f"\n  Total: {online_order_count + oo_includes_count + oo_includes_misc_count + batch_metadata_count + bulk_batch_count} records deleted")
        
    except Exception as e:
        print(f"\n✗ Error during deletion: {str(e)}")
        print("  No changes were made (transaction rolled back)")


def clear_specific_table():
    """Clear a specific table"""
    tables = {
        '1': ('OnlineOrder', OnlineOrder, ['OOIncludes', 'OOIncludesMisc']),
        '2': ('OOIncludes', OOIncludes, []),
        '3': ('OOIncludesMisc', OOIncludesMisc, []),
        '4': ('BatchMetadata', BatchMetadata, ['BulkBatch']),
        '5': ('BulkBatch', BulkBatch, []),
    }
    
    print("\nSelect table to clear:")
    print("  1. OnlineOrder (will also delete related OOIncludes & OOIncludesMisc)")
    print("  2. OOIncludes only")
    print("  3. OOIncludesMisc only")
    print("  4. BatchMetadata (will also delete related BulkBatch)")
    print("  5. BulkBatch only")
    print("  0. Cancel")
    
    choice = input("\nEnter choice (0-5): ").strip()
    
    if choice == '0':
        print("\n✗ Operation cancelled.")
        return
    
    if choice not in tables:
        print("\n✗ Invalid choice!")
        return
    
    table_name, model, related_tables = tables[choice]
    count = model.objects.count()
    
    if count == 0:
        print(f"\n✓ {table_name} is already empty!")
        return
    
    print(f"\n⚠️  This will delete {count} records from {table_name}")
    if related_tables:
        print(f"   (Related records in {', '.join(related_tables)} will also be deleted)")
    
    if not confirm_action(f"Delete {count} records from {table_name}?"):
        print("\n✗ Operation cancelled.")
        return
    
    try:
        with transaction.atomic():
            deleted_count = model.objects.all().delete()[0]
        print(f"\n✓ Successfully deleted {deleted_count} records from {table_name}")
    except Exception as e:
        print(f"\n✗ Error during deletion: {str(e)}")


def main_menu():
    """Display and handle main menu"""
    while True:
        print_header()
        counts = get_table_counts()
        display_counts(counts)
        
        print("\nOptions:")
        print("  1. Clear ALL tables")
        print("  2. Clear specific table")
        print("  3. Refresh counts")
        print("  0. Exit")
        
        choice = input("\nEnter choice (0-3): ").strip()
        
        if choice == '0':
            print("\nGoodbye!")
            break
        elif choice == '1':
            clear_all_tables()
            input("\nPress Enter to continue...")
        elif choice == '2':
            clear_specific_table()
            input("\nPress Enter to continue...")
        elif choice == '3':
            continue  # Loop will refresh counts
        else:
            print("\n✗ Invalid choice!")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
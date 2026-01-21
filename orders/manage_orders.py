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






def search_order():
    """Search for an order by order number and display details"""
    order_number = input("\nEnter order number to search: ").strip().upper()
    
    if not order_number:
        print("\n✗ Order number cannot be empty!")
        return
    
    try:
        order = OnlineOrder.objects.get(order_number=order_number)
    except OnlineOrder.DoesNotExist:
        print(f"\n✗ Order {order_number} not found!")
        return
    
    # Display order details
    print("\n" + "=" * 70)
    print(f"ORDER DETAILS: {order.order_number}")
    print("=" * 70)
    print(f"Customer Name:     {order.customer_name}")
    print(f"Shipping Company:  {order.shipping_company or 'N/A'}")
    print(f"Order Date:        {order.date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Subtotal:          ${order.subtotal}")
    print(f"Shipping:          ${order.shipping}")
    print(f"Tax:               ${order.tax}")
    print(f"Total:             ${order.total}")
    print(f"Bulk Order:        {'Yes' if order.bulk else 'No'}")
    print(f"Misc Items:        {'Yes' if order.misc else 'No'}")
    if order.note:
        print(f"Notes:             {order.note}")
    
    # Display shipping address
    print("\n--- Shipping Address ---")
    if order.address:
        print(f"  {order.address}")
        if order.address2:
            print(f"  {order.address2}")
        print(f"  {order.city}, {order.state} {order.postal_code}")
        print(f"  {order.country}")
    else:
        print("  No address on file")
    
    # Display order items (OOIncludes)
    items = OOIncludes.objects.filter(order=order).select_related('product', 'product__variety')
    if items.exists():
        print("\n--- Order Items (OOIncludes) ---")
        print(f"{'SKU':<15} {'Variety':<35} {'Qty':<8} {'Price':<10} {'Line Total'}")
        print("-" * 70)
        for item in items:
            sku = f"{item.product.variety.sku_prefix}-{item.product.sku_suffix}"
            var_name = item.product.variety.var_name[:33]
            line_total = item.qty * item.price
            print(f"{sku:<15} {var_name:<35} {item.qty:<8} ${item.price:<9.2f} ${line_total:.2f}")
        print("-" * 70)
        print(f"Total items: {items.count()}")
        total_qty = sum(item.qty for item in items)
        print(f"Total quantity: {total_qty}")
    else:
        print("\n--- Order Items (OOIncludes) ---")
        print("  No standard items in this order")
    
    # Display misc items (OOIncludesMisc)
    misc_items = OOIncludesMisc.objects.filter(order=order)
    if misc_items.exists():
        print("\n--- Misc Items (OOIncludesMisc) ---")
        print(f"{'SKU':<30} {'Qty':<8} {'Price':<10} {'Line Total'}")
        print("-" * 70)
        for item in misc_items:
            line_total = item.qty * item.price
            print(f"{item.sku:<30} {item.qty:<8} ${item.price:<9.2f} ${line_total:.2f}")
        print("-" * 70)
        print(f"Total misc items: {misc_items.count()}")
    else:
        print("\n--- Misc Items (OOIncludesMisc) ---")
        print("  No misc items in this order")
    
    print("=" * 70)




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



def find_hybrid_orders():
    """Find orders that have combinations of misc, bulk, and packet items"""
    print("\n" + "=" * 70)
    print("SEARCHING FOR HYBRID ORDERS")
    print("=" * 70)
    
    # Find orders with misc=True, bulk=True, and have packet items (OOIncludes)
    orders_with_all_three = OnlineOrder.objects.filter(
        misc=True,
        bulk=True,
        includes__isnull=False
    ).distinct()
    
    if orders_with_all_three.exists():
        print(f"\n✓ Found {orders_with_all_three.count()} orders with MISC + BULK + PACKETS:")
        print("-" * 70)
        for order in orders_with_all_three:
            pkt_count = order.includes.count()
            misc_count = order.includes_misc.count()
            print(f"  {order.order_number} - {pkt_count} pkt items, {misc_count} misc items")
    else:
        print("\n✗ No orders found with all three types")
    
    print("=" * 70)


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
        print("  4. Search for an order by order number")
        print("  5. Find hybrid orders (misc + bulk + packets)")
        print("  0. Exit")
        
        choice = input("\nEnter choice (0-5): ").strip()
        
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
        elif choice == '4':
            search_order()
            input("\nPress Enter to continue...")
        elif choice == '5':
            find_hybrid_orders()
            input("\nPress Enter to continue...")
        else:
            print("\n✗ Invalid choice!")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
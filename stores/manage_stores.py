import os
import django
import sys
import csv
from prettytable import PrettyTable

# Get the current directory path
current_path = os.path.dirname(os.path.abspath(__file__))

# Get the project directory path by going up two levels from the current directory
project_path = os.path.abspath(os.path.join(current_path, '..'))

# Add the project directory to the sys.path
sys.path.append(project_path)

# Set the DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
django.setup()

from stores.models import SOIncludes, Store, StoreOrder, StoreProduct
from products.models import Product
from django.contrib.auth.models import User
from django.db.models import Count
from django.db import connection


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
# STORE VIEWING & MANAGEMENT
# ============================================================================

def view_all_stores():
    """View all stores with key details"""
    stores = Store.objects.all().order_by('store_num')
    
    if not stores:
        print("\n❌ No stores found.")
        return
    
    print("\n" + "="*120)
    print("ALL STORES")
    print("="*120)
    print(f"{'Store #':<10} {'Store Name':<40} {'Slots':<8} {'Contact':<30}")
    print("-"*120)
    
    for store in stores:
        contact = store.store_contact_name or '--'
        print(f"{store.store_num:<10} {store.store_name:<40} {store.slots or 0:<8} {contact:<30}")
    
    print(f"\nTotal: {stores.count()} stores")

def view_store_details():
    """View detailed information for a specific store"""
    store_num = input("\nEnter store number: ").strip()
    
    try:
        store_num = int(store_num)
        store = Store.objects.get(store_num=store_num)
    except ValueError:
        print("\n❌ Invalid store number format")
        return
    except Store.DoesNotExist:
        print(f"\n❌ No store found with number {store_num}")
        return
    
    print("\n" + "="*80)
    print(f"STORE DETAILS: {store.store_num} - {store.store_name}")
    print("="*80)
    print(f"Contact Name: {store.store_contact_name or '--'}")
    print(f"Email: {store.store_contact_email or '--'}")
    print(f"Phone: {store.store_contact_phone or '--'}")
    print(f"Address: {store.store_address or '--'}")
    if store.store_address2:
        print(f"         {store.store_address2}")
    print(f"City: {store.store_city or '--'}")
    print(f"State: {store.store_state or '--'}")
    print(f"Zip: {store.store_zip or '--'}")
    print(f"\nSlots: {store.slots or 0}")
    print(f"Rack Material: {store.rack_material or '--'}")
    print(f"Rack Number: {store.rack_num or '--'}")
    print(f"Header: {store.header or '--'}")
    print(f"Velcro: {'Yes' if store.velcro else 'No'}")
    print(f"First Order: {store.first_order or '--'}")
    
    # Show username if available
    if store.store_user:
        print(f"\nUsername: {store.store_user.username}")

def create_new_store():
    """Create a new store instance"""
    print("\n" + "="*60)
    print("CREATE NEW STORE")
    print("="*60)
    
    try:
        store_num = int(input("Store number: ").strip())
        name = input("Store name: ").strip()
        email = input("Email: ").strip()
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        
        if not all([store_num, name, email, username, password]):
            print("\n❌ All fields are required")
            return
        
        # Check if store number already exists
        if Store.objects.filter(store_num=store_num).exists():
            print(f"\n❌ Store number {store_num} already exists")
            return
        
        # Create User instance
        user = User.objects.create_user(username=username, password=password)
        
        # Create Store instance
        store = Store.objects.create(
            store_num=store_num,
            store_name=name,
            store_contact_email=email,
            store_user=user,
        )
        
        print(f"\n✅ Store '{name}' created successfully")
        print(f"   Store #: {store_num}")
        print(f"   Username: {username}")
        
    except ValueError:
        print("\n❌ Invalid store number - must be an integer")
    except Exception as e:
        print(f"\n❌ Error creating store: {e}")

def update_store_slots():
    """Update slot count for a store"""
    try:
        store_num = int(input("\nEnter store number: ").strip())
        store = Store.objects.get(store_num=store_num)
        
        print(f"\nCurrent slots for {store.store_name}: {store.slots or 0}")
        slots = int(input("New slot count: ").strip())
        
        store.slots = slots
        store.save()
        print(f"\n✅ {store.store_name}'s slots updated to {store.slots}")
        
    except ValueError:
        print("\n❌ Invalid number format")
    except Store.DoesNotExist:
        print(f"\n❌ No store found with number {store_num}")

def update_store_username():
    """Update username for a store"""
    try:
        store_num = int(input("\nEnter store number: ").strip())
        store = Store.objects.get(store_num=store_num)
        
        if not store.store_user:
            print(f"\n❌ {store.store_name} has no associated user")
            return
        
        print(f"\nCurrent username: {store.store_user.username}")
        new_username = input("New username: ").strip()
        
        if not new_username:
            print("\n❌ Username cannot be empty")
            return
        
        store.store_user.username = new_username
        store.store_user.save()
        print(f"\n✅ {store.store_name}'s username updated to {new_username}")
        
    except ValueError:
        print("\n❌ Invalid store number format")
    except Store.DoesNotExist:
        print(f"\n❌ No store found with number {store_num}")

def update_store_name():
    """Update name for a store"""
    try:
        store_num = int(input("\nEnter store number: ").strip())
        store = Store.objects.get(store_num=store_num)
        
        print(f"\nCurrent name: {store.store_name}")
        new_name = input("New name: ").strip()
        
        if not new_name:
            print("\n❌ Name cannot be empty")
            return
        
        store.store_name = new_name
        store.save()
        print(f"\n✅ Store name updated to {new_name}")
        
    except ValueError:
        print("\n❌ Invalid store number format")
    except Store.DoesNotExist:
        print(f"\n❌ No store found with number {store_num}")


# ============================================================================
# STORE PRODUCT MANAGEMENT
# ============================================================================

def view_store_products():
    """View all products available at a specific store"""
    try:
        store_num = int(input("\nEnter store number: ").strip())
        store = Store.objects.get(store_num=store_num)
    except ValueError:
        print("\n❌ Invalid store number format")
        return
    except Store.DoesNotExist:
        print(f"\n❌ No store found with number {store_num}")
        return
    
    store_products = StoreProduct.objects.filter(
        store=store,
        is_available=True
    ).select_related('product__variety').order_by('product__item_number')
    
    if not store_products:
        print(f"\n❌ No products available at {store.store_name}")
        return
    
    print("\n" + "="*100)
    print(f"PRODUCTS AVAILABLE AT: {store.store_name}")
    print("="*100)
    print(f"{'Item #':<10} {'SKU':<20} {'Variety':<30} {'Package':<15}")
    print("-"*100)
    
    for sp in store_products:
        product = sp.product
        sku = f"{product.variety.sku_prefix}-{product.sku_suffix}"
        print(f"{product.item_number:<10} {sku:<20} {product.variety.var_name or '--':<30} {product.pkg_size or '--':<15}")
    
    print(f"\nTotal: {store_products.count()} products available")

def print_all_storeproducts():
    """Print complete StoreProduct table"""
    print("\n⚠️  This will print the ENTIRE StoreProduct table")
    confirm = input("Continue? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("Cancelled")
        return
    
    table = PrettyTable()
    table.field_names = ["Store #", "Store Name", "Item #", "Product", "Available"]
    
    storeproducts = StoreProduct.objects.select_related(
        'store', 'product__variety'
    ).order_by('store__store_num', 'product__item_number')
    
    for sp in storeproducts:
        table.add_row([
            sp.store.store_num,
            sp.store.store_name,
            sp.product.item_number,
            f"{sp.product.variety.sku_prefix}-{sp.product.sku_suffix}",
            "Yes" if sp.is_available else "No"
        ])
    
    print(table)
    print(f"\nTotal: {storeproducts.count()} StoreProduct records")

def set_products_availability():
    """Set product availability for specific stores"""
    print("\n" + "="*60)
    print("SET PRODUCT AVAILABILITY")
    print("="*60)
    print("1. Enter store numbers and item numbers manually")
    print("2. Enter store numbers and load items from CSV")
    
    choice = get_choice("\nSelect option: ", ['1', '2'])
    
    # Get store numbers
    store_input = input("\nEnter store number(s) (comma-separated): ").strip()
    try:
        store_nums = [int(s.strip()) for s in store_input.split(',')]
    except ValueError:
        print("\n❌ Invalid store number format")
        return
    
    # Get availability
    avail_input = input("Set as available? (y/n): ").strip().lower()
    availability = avail_input == 'y'
    
    # Get item numbers
    item_nums = None
    csv_filename = None
    
    if choice == '1':
        item_input = input("Enter item number(s) (comma-separated or range like 101-200): ").strip()
        try:
            # Check if it's a range
            if '-' in item_input and item_input.count('-') == 1:
                start, end = item_input.split('-')
                item_nums = list(range(int(start.strip()), int(end.strip()) + 1))
            else:
                item_nums = [int(i.strip()) for i in item_input.split(',')]
        except ValueError:
            print("\n❌ Invalid item number format")
            return
    else:
        csv_filename = input("Enter CSV filename (in csv/ subdirectory): ").strip()
    
    # Execute the update
    _set_items_availability_helper(store_nums, item_nums, availability, csv_filename)

def _set_items_availability_helper(store_nums, item_nums=None, availability=True, csv_filename=None):
    """Helper function to set product availability"""
    # Normalize store_nums to list
    if isinstance(store_nums, int):
        store_nums = [store_nums]
    
    # Load item_nums from CSV if filename given
    if csv_filename:
        csv_path = os.path.join(os.path.dirname(__file__), 'csv', csv_filename)
        try:
            with open(csv_path, newline='') as csvfile:
                reader = csv.reader(csvfile)
                item_nums = []
                for row in reader:
                    for val in row:
                        try:
                            item_nums.append(int(val.strip()))
                        except ValueError:
                            print(f"⚠️  Skipping non-integer value: {val}")
            print(f"✓ Loaded {len(item_nums)} item numbers from {csv_filename}")
        except FileNotFoundError:
            print(f"\n❌ CSV file not found: {csv_path}")
            return
    else:
        if isinstance(item_nums, int):
            item_nums = [item_nums]
        if item_nums is None:
            print("\n❌ No item numbers provided")
            return
    
    # Query stores
    stores = Store.objects.filter(store_num__in=store_nums)
    found_store_nums = set(stores.values_list('store_num', flat=True))
    missing_stores = set(store_nums) - found_store_nums
    
    for ms in missing_stores:
        print(f"⚠️  Store {ms} not found")
    
    if not stores.exists():
        print("\n❌ No valid stores found")
        return
    
    print(f"✓ Found {stores.count()} store(s)")
    
    # Query products
    products = Product.objects.filter(item_number__in=item_nums)
    product_item_numbers = set(products.values_list('item_number', flat=True))
    missing_products = set(item_nums) - product_item_numbers
    
    if missing_products:
        print(f"⚠️  {len(missing_products)} item numbers not found in database")
    
    print(f"✓ Found {products.count()} product(s)")
    
    # Perform update
    matching_storeproducts = StoreProduct.objects.filter(
        store__in=stores,
        product__in=products
    )
    updated_count = matching_storeproducts.update(is_available=availability)
    
    print(f"\n✅ Updated {updated_count} StoreProduct records to is_available={availability}")
    
    # Print affected stores
    for store in stores:
        print(f"   Updated products for: {store.store_name}")

def assign_wholesale_products_to_all_stores():
    """Assign all wholesale packet products to all stores"""
    print("\n" + "="*60)
    print("ASSIGN WHOLESALE PRODUCTS TO ALL STORES")
    print("="*60)
    
    products = Product.objects.filter(
        sku_suffix__endswith='pkt',
        variety__wholesale=True
    )
    
    if not products:
        print("\n❌ No wholesale packet products found")
        return
    
    print(f"Found {products.count()} wholesale packet products")
    confirm = input("Assign to all stores? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("Cancelled")
        return
    
    stores = Store.objects.all()
    created_count = 0
    updated_count = 0
    
    for store in stores:
        for product in products:
            obj, created = StoreProduct.objects.get_or_create(
                store=store,
                product=product,
                defaults={'is_available': True}
            )
            if created:
                created_count += 1
            else:
                if not obj.is_available:
                    obj.is_available = True
                    obj.save(update_fields=['is_available'])
                    updated_count += 1
    
    print(f"\n✅ Created {created_count} new assignments")
    print(f"✅ Updated {updated_count} existing assignments")


def reset_storeproduct_table():
    """Reset StoreProduct table - delete all and recreate with is_available=False"""
    print("\n" + "="*60)
    print("⚠️  RESET STOREPRODUCT TABLE")
    print("="*60)
    print("This will:")
    print("  1. Delete ALL StoreProduct records")
    print("  2. Reset auto-increment")
    print("  3. Create new records (all stores × all products)")
    print("  4. Set all is_available=False")
    print("\nThis operation cannot be undone!")
    
    confirm = input("\nType 'RESET' to confirm: ").strip()
    
    if confirm != 'RESET':
        print("Reset cancelled")
        return
    
    # Delete all records
    deleted_count = StoreProduct.objects.count()
    StoreProduct.objects.all().delete()
    print(f"✓ Deleted {deleted_count} StoreProduct records")
    
    # Reset auto-increment based on database backend
    with connection.cursor() as cursor:
        if connection.vendor == 'sqlite':
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='stores_storeproduct';")
        elif connection.vendor == 'mysql':
            cursor.execute("ALTER TABLE stores_storeproduct AUTO_INCREMENT = 1;")
        elif connection.vendor == 'postgresql':
            cursor.execute("ALTER SEQUENCE stores_storeproduct_id_seq RESTART WITH 1;")
    print("✓ Reset AUTO_INCREMENT")
    
    # Create all combinations
    stores = Store.objects.all()
    products = Product.objects.all()
    
    to_create = []
    for store in stores:
        for product in products:
            to_create.append(
                StoreProduct(store=store, product=product, is_available=False)
            )
    
    StoreProduct.objects.bulk_create(to_create)
    print(f"✓ Created {len(to_create)} StoreProduct entries")
    print(f"\n✅ StoreProduct table reset complete")
# def reset_storeproduct_table():
#     """Reset StoreProduct table - delete all and recreate with is_available=False"""
#     print("\n" + "="*60)
#     print("⚠️  RESET STOREPRODUCT TABLE")
#     print("="*60)
#     print("This will:")
#     print("  1. Delete ALL StoreProduct records")
#     print("  2. Reset auto-increment")
#     print("  3. Create new records (all stores × all products)")
#     print("  4. Set all is_available=False")
#     print("\nThis operation cannot be undone!")
    
#     confirm = input("\nType 'RESET' to confirm: ").strip()
    
#     if confirm != 'RESET':
#         print("Reset cancelled")
#         return
    
#     # Delete all records
#     deleted_count = StoreProduct.objects.count()
#     StoreProduct.objects.all().delete()
#     print(f"✓ Deleted {deleted_count} StoreProduct records")
    
#     # Reset auto-increment
#     with connection.cursor() as cursor:
#         cursor.execute("ALTER TABLE stores_storeproduct AUTO_INCREMENT = 1;")
#     print("✓ Reset AUTO_INCREMENT")
    
#     # Create all combinations
#     stores = Store.objects.all()
#     products = Product.objects.all()
    
#     to_create = []
#     for store in stores:
#         for product in products:
#             to_create.append(
#                 StoreProduct(store=store, product=product, is_available=False)
#             )
    
#     StoreProduct.objects.bulk_create(to_create)
#     print(f"✓ Created {len(to_create)} StoreProduct entries")
#     print(f"\n✅ StoreProduct table reset complete")


# ============================================================================
# STORE ORDER MANAGEMENT
# ============================================================================

def view_store_orders():
    """View store orders"""
    orders = StoreOrder.objects.all().select_related('store').order_by('-date')
    
    if not orders:
        print("\n❌ No store orders found")
        return
    
    print("\n" + "="*120)
    print("STORE ORDERS")
    print("="*120)
    print(f"{'Order #':<15} {'Date':<12} {'Store':<30} {'Total Cost':<12} {'Packets':<10}")
    print("-"*120)
    
    for order in orders:
        print(f"{order.order_number:<15} {order.date.strftime('%Y-%m-%d'):<12} "
              f"{order.store.store_name:<30} ${order.total_cost:<11.2f} {order.total_packets:<10}")
    
    print(f"\nTotal: {orders.count()} orders")


def reset_store_order_table():
    """Reset store order tables"""
    so_count = StoreOrder.objects.count()
    soi_count = SOIncludes.objects.count()
    
    if so_count == 0 and soi_count == 0:
        print("\n✅ Store order tables already empty")
        return
    
    print("\n" + "="*60)
    print("⚠️  RESET STORE ORDER TABLES")
    print("="*60)
    print(f"This will delete:")
    print(f"  - {so_count} StoreOrder records")
    print(f"  - {soi_count} SOIncludes records")
    
    confirm = input("\nType 'DELETE' to confirm: ").strip()
    
    if confirm == 'DELETE':
        StoreOrder.objects.all().delete()
        SOIncludes.objects.all().delete()
        print("\n✅ Store order tables reset")
    else:
        print("Reset cancelled")


# ============================================================================
# MENU FUNCTIONS
# ============================================================================

def store_management_menu():
    """Store management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("STORE MANAGEMENT")
        print("="*50)
        print("1.  View all stores")
        print("2.  View store details")
        print("3.  Create new store")
        print("4.  Update store slots")
        print("5.  Update store username")
        print("6.  Update store name")
        print("0.  Back to main menu")
        
        choice = get_choice("\nSelect option: ", 
                          ['0', '1', '2', '3', '4', '5', '6'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_all_stores()
            pause()
        elif choice == '2':
            view_store_details()
            pause()
        elif choice == '3':
            create_new_store()
            pause()
        elif choice == '4':
            update_store_slots()
            pause()
        elif choice == '5':
            update_store_username()
            pause()
        elif choice == '6':
            update_store_name()
            pause()


def store_product_menu():
    """Store product management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("STORE PRODUCT MANAGEMENT")
        print("="*50)
        print("1.  View products for a store")
        print("2.  Set product availability")
        print("3.  Assign wholesale products to all stores")
        print("4.  Print all StoreProduct records")
        print("5.  Reset StoreProduct table")
        print("0.  Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3', '4', '5'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_store_products()
            pause()
        elif choice == '2':
            set_products_availability()
            pause()
        elif choice == '3':
            assign_wholesale_products_to_all_stores()
            pause()
        elif choice == '4':
            print_all_storeproducts()
            pause()
        elif choice == '5':
            reset_storeproduct_table()
            pause()

def store_order_menu():
    """Store order management submenu"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("STORE ORDER MANAGEMENT")
        print("="*50)
        print("1.  View all store orders")
        print("2.  Reset store order tables")
        print("0.  Back to main menu")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3'])
        
        if choice == '0':
            break
        elif choice == '1':
            view_store_orders()
            pause()
        elif choice == '2':
            reset_store_order_table()
            pause()


# ============================================================================
# MAIN MENU
# ============================================================================

def main_menu():
    """Main menu for store management"""
    while True:
        clear_screen()
        print("\n" + "="*50)
        print("🏪 STORE MANAGEMENT SYSTEM")
        print("="*50)
        print("1.  Store Management")
        print("2.  Store Product Management")
        print("3.  Store Order Management")
        print("0.  Exit")
        
        choice = get_choice("\nSelect option: ", ['0', '1', '2', '3'])
        
        if choice == '0':
            print("\n👋 Goodbye!")
            break
        elif choice == '1':
            store_management_menu()
        elif choice == '2':
            store_product_menu()
        elif choice == '3':
            store_order_menu()


# ============================================================================
# MAIN PROGRAM
# ============================================================================

if __name__ == "__main__":
    main_menu()
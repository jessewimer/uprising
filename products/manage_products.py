# from tkinter import Image
from PIL import Image
from django.conf import settings
import os
import django
import sys
import csv
from prettytable import PrettyTable
from collections import Counter


# Get the current directory path
current_path = os.path.dirname(os.path.abspath(__file__))

# Get the project directory path by going up two levels from the current directory
project_path = os.path.abspath(os.path.join(current_path, '..'))

# Add the project directory to the sys.path
sys.path.append(project_path)

# Set the DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
django.setup()

from products.models import Product, Variety, Sales, MiscProduct
from django.db import transaction

def print_product_table():
    products = Product.objects.all().order_by('item_number').values('item_number', 'sku', 'variety')

    table = PrettyTable()
    table.field_names = ["Item Number", "SKU", "Variety"]

    for p in products:
        table.add_row([p['item_number'], p['sku'], p['variety']])

    print(table)


def check_duplicate_item_numbers():
    # Get all item_numbers from products
    item_numbers = Product.objects.values_list('item_number', flat=True)

    # Count occurrences of each item_number
    counts = Counter(item_numbers)

    # Find duplicates
    duplicates = {num: count for num, count in counts.items() if count > 1}

    if duplicates:
        print("Duplicate item_numbers found:")
        for item_num, count in duplicates.items():
            print(f"Item Number: {item_num} - Count: {count}")
    else:
        print("No duplicate item_numbers found.")


def update_notes_with_csv():

    with open('notes.csv', 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            item_num = row[0]
            note = row[1]
            product = Product.objects.get(item_number=item_num)

            if note == "B":
                product.notes = "Best Seller"
            elif note == "NR":
                product.notes = "New/Returning"
            elif note == "L":
                product.notes = "Limited Availability"
            else:
                product.notes = "-"

            product.save()
            print(f"{product.item_number} -- {product.notes}")


def check_categories():
    products = Product.objects.all()
    for product in products:
        if product.category == "":
            print(product.variety)


# Sets all product 'photo' attributes to the correct file (webp or jpg)
# Depending on the actual file name stored in the product/photos (STATIC_ROOT)
def update_all_product_photos():

    products = Product.objects.all()

    for product in products:
        item_number = str(product.item_number)
        webp_path = os.path.join('products', 'photos', f'{item_number}.webp')
        jpg_path = os.path.join('products', 'photos', f'{item_number}.jpg')

        # Check if the WebP image exists and set the photo attribute accordingly
        if product_has_image(webp_path):
            print('webp image')
            product.photo = f'{webp_path}'
        elif product_has_image(jpg_path):
            print('jpg image')
            product.photo = f'{jpg_path}'
        else:
            # If neither WebP nor JPG image exists, set it to a default image
            print('default image')
            product.photo = 'products/photos/default.jpg'

        product.save()


def product_has_image(image_path):
    # Use os.path.join to construct the absolute image path within STATIC_ROOT
    full_image_path = os.path.join(settings.STATIC_ROOT, image_path)
    return os.path.exists(full_image_path)


# # Function to change all backslashes to forward slashes in the photo attribute
def fix_slashes():
    products = Product.objects.all()
    for product in products:
        product.photo = product.photo.replace('\\', '/')
        product.save()

    print("slashes fixed")


def view_product_varieties():
    products = Product.objects.all()
    with open("ws_item_nums.csv", mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["item_number", "sku"])  # Write header row

        for product in products:
            cleaned_sku = product.sku.rstrip("w")  # Remove trailing 'w' if present
            writer.writerow([product.item_number, cleaned_sku])

    print("CSV file 'ws_item_nums.csv' created successfully.")
    return
    # Extract headers
    headers = ["Variety", "Category", "Super Type", "Veg Type", "Sub Type"]

    # Get all data and calculate the maximum width for each column
    data = [
        [product.variety, product.category, product.super_type, product.veg_type, product.sub_type]
        for product in products
    ]
    column_widths = [max(len(str(row[i])) for row in data + [headers]) for i in range(len(headers))]

    # Print the headers
    header_row = " | ".join(f"{headers[i]:<{column_widths[i]}}" for i in range(len(headers)))
    print(header_row)
    print("-" * len(header_row))  # Separator line

    # Print each product's details
    for row in data:
        print(" | ".join(f"{str(row[i]):<{column_widths[i]}}" for i in range(len(row))))

    # for product in products:

    #     print(product.variety, product.category, product.super_type, product.veg_type, product.sub_type)

def delete_duplicate_products():
    original_products = []
    products = Product.objects.all()
    for product in products:
        if product.item_number in original_products:
            print(product.variety, " deleted")
            product.delete()
        else:
            original_products.append(product.item_number)


def update_product_description(item_num, description):
   product = Product.objects.get(item_number=item_num)
   product.description = description
   product.save()
   print(f"The description for item number {product.item_number} has been updated to '{description}'")


def update_product_notes(item_num, notes):
   product = Product.objects.get(item_number=item_num)
   product.notes = notes
   product.save()
   print(f"The notes for item number {product.item_number} has been updated to '{notes}'")

def update_product_sub_type(item_num, sub_type):
   product = Product.objects.get(item_number=item_num)
   product.sub_type = sub_type
   product.save()
   print(f"The sub_type for item number {product.item_number} has been updated to '{product.sub_type}'")

def update_product_photo(item_num, photo):
    product = Product.objects.get(item_number=item_num)
    product.photo = photo
    product.save()
    print(f"The photo for item number {product.item_number} has been updated to '{product.photo}'")


def create_product_object(item_num,
                          sku,
                          notes,
                          category,
                          super_type,
                          veg_type,
                          sub_type,
                          variety,
                          description,
                          photo):

    product = Product.objects.create(
        item_number = item_num,
        sku = sku,
        notes = notes,
        active = '',
        category = category,
        super_type = super_type,
        veg_type = veg_type,
        sub_type = sub_type,
        variety = variety,
        description = description,
        quickbooks_code = '',
        photo = photo
    )

    product.save()
    print(f"{product.variety} added successfully")


def get_photo_path(sku_prefix):
    """
    Look in products/static/products/photos/ for an image file that matches sku_prefix.
    Priority: .webp, then .jpg, then .jpeg.
    Returns relative path (e.g. 'products/photos/LET001.webp') or '' if not found.
    """
    photos_dir = os.path.join("products", "static", "products", "photos")
    extensions = [".webp", ".jpg", ".jpeg"]

    for ext in extensions:
        filename = f"{sku_prefix}{ext}"
        filepath = os.path.join(photos_dir, filename)
        if os.path.exists(filepath):
            # Store relative to static/products (so it works with your static setup)
            return f"products/photos/{filename}"

    return ""


def import_varieties_from_csv(csv_file_path):
    with open(csv_file_path, newline='', encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            sku_prefix = row.get("SKU Prefix", "").strip()
            if not sku_prefix:
                continue  # skip empty rows

            photo_path = get_photo_path(sku_prefix)

            variety, created = Variety.objects.update_or_create(
                sku_prefix=sku_prefix,
                defaults={
                    "crop": row.get("Crop", "").strip(),
                    "common_name": row.get("Common Name", "").strip(),
                    "var_name": row.get("Variety", "").strip(),
                    "desc_line1": row.get("Description Line 1", "").strip(),
                    "desc_line2": row.get("Description Line 2", "").strip(),
                    "desc_line3": row.get("Description Line 3", "").strip(),
                    "group": row.get("Group", "").strip(),
                    "back1": row.get("BACK 1", "").strip(),
                    "back2": row.get("BACK 2", "").strip(),
                    "back3": row.get("BACK 3", "").strip(),
                    "back4": row.get("BACK 4", "").strip(),
                    "back5": row.get("BACK 5", "").strip(),
                    "back6": row.get("BACK 6", "").strip(),
                    "back7": row.get("BACK 7", "").strip(),
                    "days": row.get("Days", "").strip(),
                    "species": row.get("Species", "").strip(),
                    "veg_type": row.get("Radicchio Type", "").strip(),
                    "photo_path": photo_path,
                }
            )

            action = "Created" if created else "Updated"
            print(f"{action} variety {sku_prefix} (photo: {photo_path or 'none'})")



# import csv
# import unicodedata
# from django.db import transaction

def update_varieties_from_csv(csv_path):
    import csv
    import unicodedata
    from django.db import transaction

    """
    Updates Variety objects from a comma-delimited CSV.
    Handles common encoding issues (utf-8-sig or latin-1 fallback).
    Prints debug info for rows that don't match.
    """
    updated = 0
    not_found = []

    encodings_to_try = ["utf-8-sig", "latin-1"]

    for enc in encodings_to_try:
        try:
            with open(csv_path, newline='', encoding=enc) as csvfile:
                reader = csv.DictReader(csvfile)  # comma-delimited
                print("CSV headers:", reader.fieldnames)  # debug: confirm headers

                with transaction.atomic():
                    for row in reader:
                        raw_sku = row.get("SKU", "")
                        sku_prefix = unicodedata.normalize("NFKC", raw_sku[:6]).strip().upper()

                        if not sku_prefix:
                            print(f"⚠️ Empty SKU in row: {row}")
                            continue

                        try:
                            variety = Variety.objects.get(sku_prefix=sku_prefix)
                            variety.ws_notes = row.get("WS Notes", "").strip() or None
                            variety.category = row.get("Category", "").strip() or None
                            variety.supergroup = row.get("Supertype", "").strip() or None
                            variety.veg_type = row.get("Vegtype", "").strip() or None
                            variety.subtype = row.get("Subtype", "").strip() or None
                            variety.ws_description = row.get("WS Description", "").strip() or None
                            variety.save()
                            updated += 1
                            print(f"✅ Updated: {sku_prefix}")
                        except Variety.DoesNotExist:
                            not_found.append(sku_prefix)
                            print(f"❌ Not found in DB: {sku_prefix}")

            break  # successfully read, exit encoding loop
        except UnicodeDecodeError:
            print(f"⚠️ Failed to read with encoding {enc}, trying next...")

    print(f"\n✅ Total updated: {updated}")
    if not_found:
        print(f"⚠️ No match for {len(not_found)} SKUs: {', '.join(not_found[:10])}...")



from django.db import transaction
@transaction.atomic
def import_products_from_csv(filepath):
    with open(filepath, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            sku_prefix = row.get("SKU Prefix", "").strip()
            if not sku_prefix:
                continue  # skip rows with no prefix

            try:
                variety = Variety.objects.get(sku_prefix=sku_prefix)
            except Variety.DoesNotExist:
                print(f"⚠️ Variety with prefix {sku_prefix} not found, skipping row.")
                continue

            product, created = Product.objects.update_or_create(
                variety=variety,
                sku_suffix=row.get("SKU Suffix", "").strip(),
                defaults={
                    "pkg_size": row.get("Pkg Size", "").strip(),
                    "label": row.get("Label", "").strip(),
                    "env_type": row.get("ENV", "").strip(),
                    "print_back": str(row.get("Print Back", "")).strip().lower() in ["1", "true", "yes", "y"],
                    "env_multiplier": (
                        int(row["Multiplier"]) if row.get("Multiplier") and row["Multiplier"].isdigit() else None
                    ),
                    "alt_sku": row.get("ALT SKU", "").strip(),
                    "rack_location": row.get("Rack locations", "").strip(),
                    "bulk_pre_pack": (
                        int(row["Bulk Pre Pack"]) if row.get("Bulk Pre Pack") and row["Bulk Pre Pack"].isdigit() else None
                    ),
                },
            )

            print(f"{'✅ Created' if created else '🔄 Updated'} product for {sku_prefix} - {product.pkg_size}")

def mark_wholesale_based_on_photo():
    varieties = Variety.objects.all()
    for var in varieties:
        if var.photo_path:  # non-empty string evaluates as True
            if not var.wholesale:  # only update if needed
                var.wholesale = True
                var.save(update_fields=['wholesale'])
                print(f"Updated {var.sku_prefix}: set wholesale=True")
        else:
            print(f"Skipped {var.sku_prefix}: no photo_path")




def import_sales(csv_file, dry_run=False):
    """
    Import sales data from a CSV file with headers:
    sku_prefix, sku_suffix, quantity, year, wholesale

    Args:
        csv_file (str): Path to the CSV file
        dry_run (bool): If True, simulate import without saving
    """
    print(f"Starting import from {csv_file} (dry_run={dry_run})...")

    created_count = 0
    error_count = 0

    try:
        with open(csv_file, newline="", encoding="utf-8-sig") as f:
            sample = f.read(1024)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample)
            reader = csv.DictReader(f, dialect=dialect)
            required_headers = ["sku_prefix", "sku_suffix", "quantity", "year", "wholesale"]

            if not all(h in reader.fieldnames for h in required_headers):
                print(f"❌ CSV must contain headers: {', '.join(required_headers)}")
                return

            # Use a transaction so dry_run can rollback automatically
            with transaction.atomic():
                for row in reader:
                    sku_prefix = row["sku_prefix"].strip()
                    sku_suffix = row["sku_suffix"].strip()

                    try:
                        product = Product.objects.get(
                            variety=sku_prefix, sku_suffix=sku_suffix
                        )
                    except Product.DoesNotExist:
                        print(f"❌ Product not found (prefix={sku_prefix}, suffix={sku_suffix})")
                        error_count += 1
                        continue

                    try:
                        quantity = int(row["quantity"])
                        year = int(row["year"])
                        wholesale = row["wholesale"].strip().lower() in ("1", "true", "yes")
                    except Exception as e:
                        print(f"❌ Error parsing row {row}: {e}")
                        error_count += 1
                        continue

                    sale = Sales(
                        product=product,
                        quantity=quantity,
                        year=year,
                        wholesale=wholesale,
                    )

                    if not dry_run:
                        sale.save()

                    print(
                        f"✅ Imported {quantity} units "
                        f"({'Wholesale' if wholesale else 'Retail'}) "
                        f"for {sku_prefix}-{sku_suffix} ({year})"
                    )
                    created_count += 1

                if dry_run:
                    print("⚠️ Dry run enabled: rolling back transaction")
                    raise transaction.TransactionManagementError("Dry run rollback")

    except FileNotFoundError:
        print(f"❌ File not found: {csv_file}")
        return
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return

    print(f"🎉 Import complete. Created {created_count} sales records, {error_count} errors.")

def export_variety_csv(filepath="varieties_export.csv"):
    """
    Export all Variety records into a CSV file with sku_prefix and category.
    """
    varieties = Variety.objects.values_list("sku_prefix", "category")
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sku_prefix", "category"])  # header row
        for sku_prefix, category in varieties:
            writer.writerow([sku_prefix, category])
    print(f"✅ Exported {varieties.count()} varieties to {filepath}")


def import_variety_csv(filepath="varieties_export.csv"):
    """
    Import a CSV of sku_prefix and category into the Variety table.
    - Updates category if sku_prefix already exists.
    - Creates new Variety if sku_prefix does not exist.
    """
    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count_new, count_updated = 0, 0
        for row in reader:
            sku_prefix = row["sku_prefix"].strip()
            category = row["category"].strip() if row["category"] else None

            variety, created = Variety.objects.update_or_create(
                sku_prefix=sku_prefix,
                defaults={"category": category},
            )
            if created:
                count_new += 1
            else:
                count_updated += 1

    print(f"✅ Import complete: {count_new} new, {count_updated} updated")


def print_var_sku_prefixes_and_categories():
    varieties = Variety.objects.all().order_by('sku_prefix').values('sku_prefix', 'category')

    table = PrettyTable()
    table.field_names = ["SKU Prefix", "Category"]

    for v in varieties:
        table.add_row([v['sku_prefix'], v['category'] or ''])

    print(table)

def delete_print_label_table_contents():
    from products.models import LabelPrint
    count, _ = LabelPrint.objects.all().delete()
    print(f"Deleted {count} records from LabelPrint table.")

@transaction.atomic
def add_variety_and_product():
    from products.models import Variety, Product

    variety, created = Variety.objects.get_or_create(
        sku_prefix="SMA-BR",
        crop="RADICCHIO",
        common_name="",
        common_spelling="Bandarossa",
        var_name="Bandarossa",
        group="Greens",
        veg_type="Radicchio",
        species="Cichorium intybus",
        supergroup="Vegtable",
        days="110 Days",
        desc_line1="Late cycle Verona type with",
        desc_line2="striking blushed-red midribs.",
    )
    if created:
        print("Created new Variety: Bandarossa")
    else:
        print("Variety Bandarossa already exists")
    sku_suffixes = ["pkt", "500s", "1Ms"]
    pkg_sizes = ["Approx. 100 seeds", "Approx. 500 seeds", "Approx. 1000 seeds"]
    line_item_names = ["Bandarossa - pkt", "", ""]
    rack_locations = [6.2, 0, 0]
    index = 0
    for suffix in sku_suffixes:
        product, created = Product.objects.get_or_create(
            variety=variety,
            sku_suffix=suffix,
            env_type="Smarties Rad",
            env_multiplier=1,
            pkg_size=pkg_sizes[index],
            lineitem_name=line_item_names[index],
            rack_location=rack_locations[index]
        )
        index += 1



        if created:
            print("Created new Product for Bandrossa:", suffix)
        else:
            print("Product for BANDAR already exists")

@transaction.atomic
def import_misc_products(csv_file):
    with open(csv_file, newline='', encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            sku = row["sku"].strip()
            lineitem_name = row["lineitem_name"].strip()
            category = row["category"].strip()
            
            # create misc product object


            
            misc_product, created = MiscProduct.objects.update_or_create(
                sku=sku,
                lineitem_name=lineitem_name,
                category=category,
            )

def set_all_bulk_pre_pack_to_zero():
    products = Product.objects.all()
    for product in products:
        if product.bulk_pre_pack is None:
            product.bulk_pre_pack = 0
            product.save()
# ####  MAIN PROGRAM BEGINS HERE  #### #
set_all_bulk_pre_pack_to_zero()
add_variety_and_product()
misc_products_csv = os.path.join(os.path.dirname(__file__), "misc_products_export.csv")
import_misc_products(misc_products_csv)





# delete_print_label_table_contents()l
# export_variety_csv()
# import_variety_csv()
# print_var_sku_prefixes_and_categories()
# full_file_path = os.path.join(os.path.dirname(__file__), "ws_vars_new.csv")
# prev_sales_csv = os.path.join(os.path.dirname(__file__), "prev_sales_export.csv")
# import_sales_csv = os.path.join(os.path.dirname(__file__), "prev_sales_export.csv")


# import_sales(import_sales_csv)

# update_varieties_from_csv(full_file_path)
# import_products_from_csv(full_file_path)
# import_varieties_from_csv(full_file_path)
# mark_wholesale_based_on_photo()


# print_product_table()
# check_duplicate_item_numbers()

# update_notes_with_csv()
# check_categories()
# update_all_product_photos()
# fix_slashes()
# view_product_varieties()
# delete_duplicate_products()
# update_product_description(item_num, description)
# update_product_notes(item_num, notes)
# update_product_notes(383, '-')
# update_product_sub_type(341, 'PEONY')
# update_product_photo(item_num, photo)
# update_product_photo(203, "products/photos/203.jpg")

# create_product_object(440,
#                       "LET-SU-pktw",
#                       '-',
#                       'Vegetables',
#                       'LETTUCE',
#                       'LETTUCE',
#                       'CRISPHEAD',
#                       'Summertime',
#                       'Insanely crunchy iceberg variety that is the pinnacle of summer eating! Very slow to bolt.',
#                       'products/photos/443.jpg')



# EXAMPLE FOR CREATING PRODUCT OBJECT USING FUNCTION CALL ABOVE
# create_product_object(item_num,
                        # sku,
                        # notes,
                        # category,
                        # super_type,
                        # vegtype,
                        # sub_type,
                        # variety,
                        # description,
                        # photo)
# Examples:
    # category = 'VEGETABLES', 'FLOWERS', 'HERBS'
    # super_type = 'BEAN', 'BEET', 'BRASSICA', 'MISC', 'CARROT',
        # 'CORN & GRAIN', 'FLOWERS', 'TOMATO', 'PEPPER & EGGPLANT',
        # 'GREENS', 'SQUASH', 'CUKE & MELON', 'HERBS', 'PEA', 'ALLIUMS', 'LETTUCE'
    # veg_type = 'CABBAGE', 'SWEET PEA', 'FOUR O’CLOCK', 'TOMATO', 'LETTUCE', 'STRAWFLOWER', ETC
    # sub_type = 'DRY/BUSH', 'FAVA', 'NAPA', 'LOOSELEAF', ETC

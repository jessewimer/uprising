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


def import_growers(csv_file):
    created = 0
    updated = 0

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            code = row.get("Code", "").strip()
            name = row.get("Name", "").strip()
            contact_name = row.get("Contact Name", "").strip() or None

            if not name:
                print(f"⚠️ Skipping row, missing Name: {row}")
                continue

            grower, is_created = Grower.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "contact_name": contact_name,
                },
            )

            if is_created:
                created += 1
            else:
                updated += 1

    print(f"✅ Imported growers: {created} created, {updated} updated")

# from products.models import Variety, Lot

@transaction.atomic
def import_lots(CSV_FILE):
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            sku_prefix = row["sku_prefix"].strip()
            grower_code = row["grower_code"].strip()
            year = int(row["growout_year"]) if row["growout_year"] else None
            harvest = row["harvest"].strip() if row["harvest"] else None
            external_lot_id = row["external_lot_id"].strip() if row["external_lot_id"] else None
            low_inv = row["low_inv"].strip().lower() in ["true", "1", "yes"]

            try:
                variety = Variety.objects.get(pk=sku_prefix)
            except Variety.DoesNotExist:
                print(f"⚠️ Skipping: Variety {sku_prefix} not found")
                continue

            grower = None
            if grower_code:
                try:
                    grower = Grower.objects.get(pk=grower_code)
                except Grower.DoesNotExist:
                    print(f"⚠️ Skipping grower {grower_code} for lot {sku_prefix}-{year}{harvest or ''}")
                    continue

            lot, created = Lot.objects.get_or_create(
                variety=variety,
                grower=grower,
                year=year,
                harvest=harvest,
                defaults={
                    "external_lot_id": external_lot_id,
                    "low_inv": low_inv,
                }
            )

            if created:
                print(f"✅ Created lot {lot}")
            else:
                print(f"➡️ Skipped existing lot {lot}")



import csv
from datetime import datetime
from django.utils import timezone
from products.models import Variety
from lots.models import Lot, Germination, GerminationBatch
import csv
from datetime import datetime
from lots.models import Lot, RetiredLot, Grower

def import_germination_data(csv_file_path, dry_run=False):
    """
    Import germination data from CSV.
    CSV headers: received_date, germination, status, year, lot_identifier, sku_prefix

    :param csv_file_path: path to CSV file
    :param dry_run: if True, do not save to DB
    """
    print(f"{'Dry run' if dry_run else 'Actual run'} starting for CSV: {csv_file_path}")

    with open(csv_file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                received_date = row.get("received_date")
                germination_rate = row.get("germination")
                status = row.get("status")
                for_year = row.get("year")
                lot_identifier = row.get("lot_identifier")
                sku_prefix = row.get("sku_prefix")

                if not lot_identifier or not sku_prefix:
                    print(f"Missing lot_identifier or sku_prefix in row: {row}. Skipping.")
                    continue

                # Parse lot_identifier: assumed format GROWERYYHARVEST
                grower_code = lot_identifier[:2]        # first 2 chars = grower
                growout_year_str = lot_identifier[2:4]  # 3rd & 4th chars = growout year
                harvest_code = lot_identifier[4:] if len(lot_identifier) > 4 else None

                # Convert values
                germination_rate = int(germination_rate) if germination_rate else None
                for_year = int(for_year) if for_year else None
                if received_date:
                    try:
                        received_date = datetime.strptime(received_date, "%m/%d/%Y").date()
                    except ValueError:
                        print(f"Invalid date format for received_date: {received_date}, using None")
                        received_date = None
                else:
                    received_date = None

                # Find Variety
                try:
                    variety = Variety.objects.get(sku_prefix=sku_prefix)
                except Variety.DoesNotExist:
                    print(f"Variety with sku_prefix '{sku_prefix}' not found. Skipping row.")
                    continue

                # Match Lot by variety, grower, growout_year, and optionally harvest
                candidate_lots = Lot.objects.filter(
                    variety=variety,
                    grower=grower_code,  # adjust if grower is string instead of ID
                    year=int(growout_year_str)
                )
                if harvest_code:
                    candidate_lots = candidate_lots.filter(harvest=harvest_code)

                if not candidate_lots.exists():
                    print(f"No matching lot found for {lot_identifier}. Skipping row.")
                    continue
                elif candidate_lots.count() == 1:
                    lot = candidate_lots.first()
                else:
                    # Multiple lots: pick first as fallback
                    lot = candidate_lots.first()
                    print(f"Multiple lots matched {lot_identifier}, using Lot ID={lot.id} as fallback.")

                print(f"Processing row: Variety={variety.sku_prefix}, Lot ID={lot.id}, Year={for_year}, "
                      f"Germ Rate={germination_rate}, Status={status}, Received={received_date}")

                # Create Germination object
                germination = Germination(
                    lot=lot,
                    batch_id=None,
                    status=status.lower() if status else "pending",
                    germination_rate=germination_rate,
                    test_date=received_date,
                    for_year=for_year,
                    notes=""
                )

                if dry_run:
                    print(f"\nDRY RUN: Would save germination: {germination}\n")
                    print("-----------------------------------------------------------\n")
                    
                else:
                    germination.save()
                    print(f"Saved germination: {germination}")

            except Exception as e:
                print(f"Error processing row {row}: {e}")

    print("Import complete.")


def import_inventory_data(csv_file_path, dry_run=False):
    """
    Import inventory data from CSV into the Inventory table.

    CSV headers:
        weight, date, smarties_pkg_count, lot_identifier, sku_prefix

    lot_identifier format: {grower_code}{year}{harvest?}, e.g. UO24 or UO24A
    """

    with open(csv_file_path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                # Extract CSV fields
                weight = row["weight"].strip()
                inv_date_raw = row["date"].strip()
                smarties_pkg_count = row["smarties_pkg_count"].strip()
                lot_identifier = row["lot_identifier"].strip()
                sku_prefix = row["sku_prefix"].strip()

                # Parse date (assuming mm/dd/yyyy like "10/1/2022")
                try:
                    inv_date = datetime.strptime(inv_date_raw, "%m/%d/%Y").date()
                except ValueError:
                    print(f"⚠️  Invalid date format '{inv_date_raw}', skipping row.")
                    continue

                # Parse weight and smarties count
                weight = float(weight) if weight else 0
                smarties_pkg_count = int(smarties_pkg_count) if smarties_pkg_count else 0

                # Break apart lot_identifier
                grower_code = "".join(filter(str.isalpha, lot_identifier[:-2]))  # letters before year
                year = "".join(filter(str.isdigit, lot_identifier))[:2]     # first two digits
                harvest = lot_identifier[len(grower_code) + len(year):] or None

                # Find grower
                grower = Grower.objects.filter(code=grower_code).first()
                if not grower:
                    print(f"⚠️  Grower with code {grower_code} not found (row: {row})")
                    continue

                # Find lot
                lot = Lot.objects.filter(
                    variety__sku_prefix=sku_prefix,
                    grower=grower,
                    year=year,
                )
                if harvest:
                    lot = lot.filter(harvest=harvest)
                lot = lot.first()

                if not lot:
                    print(f"⚠️  Lot not found for identifier {lot_identifier}, sku_prefix {sku_prefix}")
                    continue

                # Check for duplicates
                if Inventory.objects.filter(lot=lot, inv_date=inv_date).exists():
                    print(f"⚠️  Inventory already exists for lot {lot} on {inv_date}, skipping.")
                    continue

                # Create inventory object
                inventory = Inventory(
                    lot=lot,
                    weight=weight,
                    smarties_ct=smarties_pkg_count,
                    inv_date=inv_date,
                )

                if dry_run:
                    print(f"DRY RUN → Would create Inventory: {inventory}")
                else:
                    inventory.save()
                    print(f"✅ Created Inventory for lot {lot} on {inv_date}")

            except Exception as e:
                print(f"❌ Error processing row {row}: {e}")


def import_retired_lots(csv_file_path, dry_run=False):
    """
    CSV headers:
      Lot   -> e.g. 'BEA-TP-UO22'  (sku_prefix='BEA-TP', grower='UO', year='22', optional harvest after year)
      Date  -> 'YYYY-MM-DD'
      Lbs   -> float-ish
      Notes -> text
    """
    created, skipped, errors = 0, 0, 0

    # utf-8-sig strips BOM so 'Lot' isn't read as 'ï»¿Lot'
    with open(csv_file_path, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            try:
                lot_str = (row.get("Lot") or "").strip()
                date_raw = (row.get("Date") or "").strip()
                lbs_raw = (row.get("Lbs") or "").strip()
                notes = (row.get("Notes") or "").strip()

                if not lot_str:
                    print("⚠️  Missing Lot column; skipping row:", row)
                    skipped += 1
                    continue

                # Parse retired date
                try:
                    retired_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
                except ValueError:
                    print(f"⚠️  Invalid Date '{date_raw}' for Lot '{lot_str}'; skipping.")
                    skipped += 1
                    continue

                # Parse lbs
                try:
                    lbs_remaining = float(lbs_raw) if lbs_raw else 0.0
                except ValueError:
                    print(f"⚠️  Invalid Lbs '{lbs_raw}' for Lot '{lot_str}'; skipping.")
                    skipped += 1
                    continue

                # ---- Correct parsing: split from the RIGHT ----
                # 'BEA-TP-UO22' -> sku_prefix='BEA-TP', tail='UO22'
                try:
                    sku_prefix, tail = lot_str.rsplit("-", 1)
                except ValueError:
                    print(f"⚠️  Lot format '{lot_str}' not 'AAA-AA-GGYY[H]'; skipping.")
                    skipped += 1
                    continue

                # Tail: first 2 letters = grower code; next 2 digits = 2-digit year; optional leftover = harvest
                grower_code = tail[:2]
                year_2 = tail[2:4]
                harvest = tail[4:] or None

                if len(grower_code) != 2 or not grower_code.isalpha() or len(year_2) != 2 or not year_2.isdigit():
                    print(f"⚠️  Tail '{tail}' not 'GGYY[H]' for Lot '{lot_str}'; skipping.")
                    skipped += 1
                    continue

                # Find grower
                grower = Grower.objects.filter(code=grower_code).first()
                if not grower:
                    print(f"⚠️  Grower with code '{grower_code}' not found (Lot '{lot_str}'); skipping.")
                    skipped += 1
                    continue

                # Match lot (year stored as 2-digit in your Lot.year)
                lot_qs = Lot.objects.filter(
                    variety__sku_prefix=sku_prefix,
                    grower=grower,
                    year=int(year_2),
                )
                if harvest:
                    lot_qs = lot_qs.filter(harvest=harvest)

                lot = lot_qs.first()
                if not lot:
                    print(f"⚠️  Lot not found for '{lot_str}' (sku_prefix={sku_prefix}, grower={grower_code}, year={year_2}, harvest={harvest}); skipping.")
                    skipped += 1
                    continue

                # Prevent duplicates (one RetiredLot per lot)
                if RetiredLot.objects.filter(lot=lot).exists():
                    print(f"ℹ️  Lot '{lot}' already retired; skipping.")
                    skipped += 1
                    continue

                retired_lot = RetiredLot(
                    lot=lot,
                    retired_date=retired_date,
                    notes=notes,
                    lbs_remaining=lbs_remaining,
                )

                if dry_run:
                    print(f"DRY RUN → Would create RetiredLot: lot={lot} date={retired_date} lbs={lbs_remaining} notes='{notes}'")
                else:
                    retired_lot.save()
                    print(f"✅ Retired lot {lot} on {retired_date} (lbs_remaining={lbs_remaining})")
                    created += 1

            except Exception as e:
                errors += 1
                print(f"❌ Error processing row {row}: {e}")

    print(f"Done. Created: {created}, Skipped: {skipped}, Errors: {errors}")

def clear_germination_batch_and_test_germinations():
    """Clear all germination batches and test germinations"""
    GerminationBatch.objects.all().delete()
    print("✅ All germination batches cleared.")
    # filter for germination objects with year == 26
    Germination.objects.filter(for_year=26).delete()
    print("✅ All test germinations cleared for 2026.")

def view_germination_batches():
    """View all germination batches"""
    batches = GerminationBatch.objects.all()
    for batch in batches:
        print(f"Batch {batch.batch_number} - {batch.date} (Tracking: {batch.tracking_number})")
        for germination in batch.germinations.all():
            print(f"{germination.lot.variety}-{germination.lot.grower.code}{germination.lot.year} - Status: {germination.status}")

def add_germ_batch_to_db():
    # add a germination batch to the db for testing with date 08/04/2025, use 2025-08-04
    batch1 = GerminationBatch(batch_number="001", date=datetime.strptime("08/04/2025", "%m/%d/%Y").date(), tracking_number="")
    batch1.save()
    batch2 = GerminationBatch(batch_number="002", date=datetime.strptime("08/18/2025", "%m/%d/%Y").date(), tracking_number="")
    batch2.save()
    batch3 = GerminationBatch(batch_number="003", date=datetime.strptime("08/25/2025", "%m/%d/%Y").date(), tracking_number="")
    batch3.save()
    # confirmation
    print("✅ Added 3 germination batches to the database.")

 # adjust if models are in different apps

def import_germs_26(csv_file_path, dry_run=False):
    print(f"{'Dry run' if dry_run else 'Actual run'} starting for CSV: {csv_file_path}")
    from django.utils.dateparse import parse_date

    with open(csv_file_path, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=",")

        for row in reader:
            try:
                # Extract row values
                germ_sent_date = row.get("germ_sent_date")
                status = row.get("status")
                year = int(row.get("year"))
                lot_code = row.get("lot")
                batch_id = int(row.get("batch_id"))

                # Parse batch number (001, 002, etc.)
                batch_number = f"{batch_id:03d}"
                batch = GerminationBatch.objects.filter(batch_number=batch_number).first()

                # Use the Lot.parse_lot_code helper
                try:
                    parsed = Lot.parse_lot_code(lot_code)
                    sku_prefix = parsed['sku_prefix']
                    grower_code = parsed['grower_id']
                    lot_year = parsed['year']
                    harvest = parsed.get('harvest')
                except Exception as e:
                    print(f"⚠️ Could not parse lot code '{lot_code}': {e}")
                    continue

                # Find the Lot object
                lot = Lot.objects.filter(
                    variety__sku_prefix=sku_prefix,
                    grower__code=grower_code,
                    year=lot_year
                ).first()

                if not lot:
                    print(f"❌ Lot not found for {lot_code}")
                    continue

                if dry_run:
                    print(f"Would create Germination: Lot={lot_code}, Batch={batch_number}, "
                          f"Status={status}, For Year=26")
                else:
                    Germination.objects.create(
                        lot=lot,
                        batch=batch,
                        status=status,
                        germination_rate=0,  # default, since not provided
                        test_date=parse_date(germ_sent_date) if germ_sent_date else None,
                        notes="Imported via CSV",
                        for_year=26,
                    )
                    print(f"✅ Created Germination for Lot={lot_code} in Batch={batch_number}")

            except Exception as e:
                print(f"❌ Error processing row {row}: {e}")



def import_germ_sample_prints_from_csv(csv_file_path, dry_run=False):
    """
    Imports a CSV of germ sample prints and creates GermSamplePrint objects.
    CSV columns: sku_prefix, lot, printed_date

    If dry_run=True, does not save to DB, just prints actions.
    """
    with open(csv_file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        processed_count = 0

        for row in reader:
            sku_prefix = row["sku_prefix"]
            lot_str = row["lot"]
            printed_date_str = row["printed_date"]

            # Parse grower_id and year from the 4-char lot string
            grower_id_part = lot_str[:2]
            year_part = lot_str[2:]

            try:
                grower_id = str(grower_id_part)
                lot_year = int(year_part)
            except ValueError:
                print(f"[SKIP] Invalid lot format: {lot_str}")
                continue

            # Find the Variety
            try:
                variety = Variety.objects.get(sku_prefix=sku_prefix)
            except Variety.DoesNotExist:
                print(f"[SKIP] No variety found for sku_prefix: {sku_prefix}")
                continue

            # Find the Lot
            try:
                lot = Lot.objects.get(variety=variety, grower_id=grower_id, year=lot_year)
            except Lot.DoesNotExist:
                print(f"[SKIP] No lot found for variety {sku_prefix}, grower {grower_id}, year {lot_year}")
                continue

            # Parse printed_date
            try:
                if "/" in printed_date_str:
                    printed_date = datetime.strptime(printed_date_str, "%m/%d/%Y").date()
                else:
                    printed_date = datetime.strptime(printed_date_str, "%Y-%m-%d").date()
            except ValueError:
                print(f"[SKIP] Invalid date: {printed_date_str}")
                continue

            if dry_run:
                print(f"[DRY RUN] Would create GermSamplePrint for Lot ID {lot.variety.sku_prefix}-{lot.grower}{lot.year}, print_date {printed_date}, for_year {printed_date.year}")
            else:
                GermSamplePrint.objects.create(
                    lot=lot,
                    print_date=printed_date,
                    for_year=26
                )
                print(f"[CREATED] GermSamplePrint for Lot ID {lot.id}, print_date {printed_date}")

            processed_count += 1

        print(f"Processing complete. {processed_count} rows processed.")
    
def clear_germ_sample_print_table():
    """Clear all entries in the GermSamplePrint table"""
    GermSamplePrint.objects.all().delete()
    print("✅ All germ sample prints cleared.")
def clear_september_2025_germ_sample_prints():
    """Clear all entries in the GermSamplePrint table with print_date in September 2025"""
    september_2025_prints = GermSamplePrint.objects.filter(print_date__year=2025, print_date__month=9)
    count = september_2025_prints.count()
    september_2025_prints.delete()
    print(f"✅ Cleared {count} germ sample prints from September 2025.")


def manage_stock_seed():
    """Interactive menu for viewing and deleting stock seed entries"""
    while True:
        print("\n=== Stock Seed Manager ===")
        print("1. View stock seed entries")
        print("2. Delete a stock seed entry")
        print("3. Edit stock seed notes")
        print("4. Quit")
       
        choice = input("Select an option (1–4): ").strip()
        
        if choice == "1":
            stock_seeds = StockSeed.objects.all()
            if not stock_seeds:
                print("\nNo stock seed entries found.")
            else:
                print("\n--- Stock Seed Entries ---")
                for idx, ss in enumerate(stock_seeds, start=1):
                    print(f"{idx}. Lot: {ss.lot.build_lot_code()} | "
                          f"Qty: {ss.qty} | Date: {ss.date} | Notes: {ss.notes or '-'}")
        
        elif choice == "2":
            stock_seeds = StockSeed.objects.all()
            if not stock_seeds:
                print("\nNo stock seed entries available to delete.")
                continue
            print("\n--- Select an entry to delete ---")
            for idx, ss in enumerate(stock_seeds, start=1):
                print(f"{idx}. Lot: {ss.lot.build_lot_code()} | "
                      f"Qty: {ss.qty} | Date: {ss.date} | Notes: {ss.notes or '-'}")
            try:
                selection = int(input("Enter the number of the entry to delete (0 to cancel): ").strip())
                if selection == 0:
                    print("Delete canceled.")
                    continue
                entry_to_delete = stock_seeds[selection - 1]
            except (ValueError, IndexError):
                print("Invalid selection. Please try again.")
                continue
            confirm = input(f"Are you sure you want to delete Lot {entry_to_delete.lot.build_lot_code()}? (y/n): ").strip().lower()
            if confirm == "y":
                entry_to_delete.delete()
                print("Entry deleted successfully.")
            else:
                print("Delete canceled.")
        
        elif choice == "3":
            stock_seeds = StockSeed.objects.all()
            if not stock_seeds:
                print("\nNo stock seed entries available to edit.")
                continue
            print("\n--- Select an entry to edit ---")
            for idx, ss in enumerate(stock_seeds, start=1):
                print(f"{idx}. Lot: {ss.lot.build_lot_code()} | "
                      f"Qty: {ss.qty} | Date: {ss.date} | Notes: {ss.notes or '-'}")
            try:
                selection = int(input("Enter the number of the entry to edit (0 to cancel): ").strip())
                if selection == 0:
                    print("Edit canceled.")
                    continue
                entry_to_edit = stock_seeds[selection - 1]
            except (ValueError, IndexError):
                print("Invalid selection. Please try again.")
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
                print("Notes cleared successfully.")
            else:
                entry_to_edit.notes = new_notes
                entry_to_edit.save()
                print("Notes updated successfully.")
        
        elif choice == "4":
            print("Exiting Stock Seed Manager. Goodbye!")
            break
        
        else:
            print("Invalid option. Please choose 1, 2, 3, or 4.")
# def manage_stock_seed():
#     """Interactive menu for viewing and deleting stock seed entries"""
#     while True:
#         print("\n=== Stock Seed Manager ===")
#         print("1. View stock seed entries")
#         print("2. Delete a stock seed entry")
#         print("3. Quit")
        
#         choice = input("Select an option (1–3): ").strip()

#         if choice == "1":
#             stock_seeds = StockSeed.objects.all()
#             if not stock_seeds:
#                 print("\nNo stock seed entries found.")
#             else:
#                 print("\n--- Stock Seed Entries ---")
#                 for idx, ss in enumerate(stock_seeds, start=1):
#                     print(f"{idx}. Lot: {ss.lot.build_lot_code()} | "
#                           f"Qty: {ss.qty} | Date: {ss.date} | Notes: {ss.notes or '-'}")

#         elif choice == "2":
#             stock_seeds = StockSeed.objects.all()
#             if not stock_seeds:
#                 print("\nNo stock seed entries available to delete.")
#                 continue

#             print("\n--- Select an entry to delete ---")
#             for idx, ss in enumerate(stock_seeds, start=1):
#                 print(f"{idx}. Lot: {ss.lot.build_lot_code()} | "
#                       f"Qty: {ss.qty} | Date: {ss.date} | Notes: {ss.notes or '-'}")

#             try:
#                 selection = int(input("Enter the number of the entry to delete (0 to cancel): ").strip())
#                 if selection == 0:
#                     print("Delete canceled.")
#                     continue
#                 entry_to_delete = stock_seeds[selection - 1]
#             except (ValueError, IndexError):
#                 print("Invalid selection. Please try again.")
#                 continue

#             confirm = input(f"Are you sure you want to delete Lot {entry_to_delete.lot.build_lot_code()}? (y/n): ").strip().lower()
#             if confirm == "y":
#                 entry_to_delete.delete()
#                 print("Entry deleted successfully.")
#             else:
#                 print("Delete canceled.")

#         elif choice == "3":
#             print("Exiting Stock Seed Manager. Goodbye!")
#             break
#         else:
#             print("Invalid option. Please choose 1, 2, or 3.")

def add_grower():
    """Add a new grower interactively"""
    print("\n=== Add New Grower ===")
    code = input("Enter grower code (2 letters): ").strip().upper()
    if len(code) != 2 or not code.isalpha():
        print("Invalid code. Must be exactly 2 letters.")
        return

    name = input("Enter grower name: ").strip()
    if not name:
        print("Grower name cannot be empty.")
        return

    contact_name = input("Enter contact name (optional): ").strip() or None

    if Grower.objects.filter(code=code).exists():
        print(f"Grower with code '{code}' already exists.")
        return

    grower = Grower(code=code, name=name, contact_name=contact_name)
    grower.save()
    print(f"✅ Grower '{name}' with code '{code}' added successfully.")


if __name__ == "__main__":
    add_grower()
    # manage_stock_seed()
#     germ_file_path = os.path.join(os.path.dirname(__file__), "germination_export.csv")
#     inv_file_path = os.path.join(os.path.dirname(__file__), "inventory_export.csv")
#     ret_file_path = os.path.join(os.path.dirname(__file__), "retired_lots.csv")
    # germ_print_file_path = os.path.join(os.path.dirname(__file__), "germ_sample_prints.csv")

    # import_growers(full_file_path)
    # import_lots(full_file_path)
    # import_germination_data(germ_file_path)
    # import_inventory_data(inv_file_path)
    # import_retired_lots(ret_file_path)
    # clear_germ_sample_print_table()
    # import_germ_sample_prints_from_csv(germ_print_file_path)
    # clear_germination_batch_and_test_germinations()
    # view_germination_batches()

    # clear_september_2025_germ_sample_prints()

    # THESE ADD 3 BATCHES TO THE DB AND POPULATE WITH 26 GERMS SENT VIA THE OTHER DB
    # add_germ_batch_to_db()
    # germ_26_file_path = os.path.join(os.path.dirname(__file__), "germ_26.csv")
    # import_germs_26(germ_26_file_path)
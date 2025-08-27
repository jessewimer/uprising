import os
import django
import csv
import sys
from django.db import transaction
# Get the current directory path
current_path = os.path.dirname(os.path.abspath(__file__))

# Get the project directory path by going up two levels from the current directory
project_path = os.path.abspath(os.path.join(current_path, '..'))

# Add the project directory to the sys.path
sys.path.append(project_path)

# Set the DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
django.setup()
from lots.models import Grower, Lot, StockSeed, Inventory, GermSamplePrint
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
    print("✅ All test germinations cleared.")

if __name__ == "__main__":
    germ_file_path = os.path.join(os.path.dirname(__file__), "germination_export.csv")
    inv_file_path = os.path.join(os.path.dirname(__file__), "inventory_export.csv")
    ret_file_path = os.path.join(os.path.dirname(__file__), "retired_lots.csv")
    
    # import_growers(full_file_path)
    # import_lots(full_file_path)
    # import_germination_data(germ_file_path)
    # import_inventory_data(inv_file_path)
    # import_retired_lots(ret_file_path)
    clear_germination_batch_and_test_germinations()
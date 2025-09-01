import os
import sys
import django
import csv
import sys
from django.db import connection

current_path = os.path.dirname(os.path.abspath(__file__))

# Get the project directory path by going up two levels from the current directory
project_path = os.path.abspath(os.path.join(current_path, '..'))

# Add the project directory to the sys.path
sys.path.append(project_path)

# Set the DJANGO_SETTINGS_MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uprising.settings")
django.setup()

from office.models import OfficeSupply
full_file_path = os.path.join(os.path.dirname(__file__), "office_supplies.csv")
CSV_FILE = full_file_path

def import_office_supplies(csv_file):
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            # Debugging: show each row as it comes in
            print(f"Row {i}: {row}")

            # Clean data (strip whitespace, convert empty strings → None)
            data = {k: (v.strip() if v and v.strip() else None) for k, v in row.items()}

            # Create a new OfficeSupply record
            supply = OfficeSupply(
                item=data.get("item"),
                item_num=data.get("item_num"),
                vendor=data.get("vendor"),
                description=data.get("description"),
                notes=data.get("notes"),
                url=data.get("url"),
            )
            supply.save()

            print(f"✅ Saved: {supply.item}")

    print("🎉 Import complete!")

    
if __name__ == "__main__":
    # import_office_supplies(CSV_FILE)
    print("This script is for importing office supplies. Uncomment the import line to run it.")

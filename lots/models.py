from django.db import models
from datetime import date
from django.utils import timezone


class Grower(models.Model):
    code = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    contact_name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    

    def __str__(self):
        return self.code


class Lot(models.Model):
    variety = models.ForeignKey("products.Variety", on_delete=models.CASCADE, related_name="lots")
    grower = models.ForeignKey(Grower, on_delete=models.SET_NULL, null=True, blank=True, related_name="lots")
    year = models.PositiveIntegerField()

    harvest = models.CharField(max_length=1, blank=True, null=True)
    external_lot_id = models.CharField(max_length=50, blank=True, null=True)
    low_inv = models.BooleanField(default=False)

    class Meta:
        unique_together = ("variety", "grower", "year", "harvest")

    def __str__(self):
        return f"{self.variety.sku_prefix}-{self.grower}{self.year}{self.harvest if self.harvest else ''}"
    
    # ✅ Build lot code from fields
    def build_lot_code(self):
        """
        Build lot code string like: 'CAR-DR-TR23' or 'CAR-DR-TR23A'
        """
        base_code = f"{self.sku_prefix}-{self.grower_id}{self.year:02d}"
        if self.harvest:
            base_code += str(self.harvest)
        return base_code

    # ✅ Parse lot code into parts
    @staticmethod
    def parse_lot_code(lot_code):
        """
        Parse a lot code string into its components.
        Returns dict: {sku_prefix, grower_id, year, harvest}
        """
        parts = lot_code.split("-")
        if len(parts) < 3:
            raise ValueError(f"Invalid lot code format: {lot_code}")

        sku_prefix = "-".join(parts[:2])      # everything before 2nd dash
        grower_and_year = parts[2]

        if len(grower_and_year) < 4:
            raise ValueError(f"Invalid grower/year section: {grower_and_year}")

        grower_id = grower_and_year[:2]       # first 2 chars
        year = int(grower_and_year[2:4])      # 3rd + 4th chars only
        harvest = grower_and_year[4:] if len(grower_and_year) > 4 else None

        return {
            "sku_prefix": sku_prefix,
            "grower_id": grower_id,
            "year": year,
            "harvest": harvest
        }

    # method to return most recent germination record that has a non null test date
    def get_most_recent_germination(self):
        return self.germinations.filter(test_date__isnull=False).order_by("-test_date").first()

    def get_germ_record_with_no_test_date(self):
        return self.germinations.filter(test_date__isnull=True).order_by("-for_year").first()
    
    def get_most_recent_germ_percent(self):
        germination = self.get_most_recent_germination()
        year = germination.for_year if germination else None
        return f"{germination.germination_rate}% (20{year})" if germination else None

    # method to return most recent inventory record
    def get_most_recent_inventory(self):
        inventory = self.inventory.order_by("-inv_date").first() if self.inventory.exists() else None
        if inventory: 
            inv_date = inventory.inv_date.strftime("%m/%Y")
            return f"{inventory.weight} lbs ({inv_date})"
        return "--"   

    def get_lot_status(self):
        # check to see if lot exists in retired lots
        if hasattr(self, "retired_info"):
            return "retired"
        # check the status attribute of the most recent germination record that has a non null test date
        most_recent_germination = self.get_most_recent_germination()
        if most_recent_germination:
            return most_recent_germination.status
        return "unknown"

    def check_stock_seed(self):
        return self.stock_seeds.exists()


class StockSeed(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="stock_seeds")
    qty = models.CharField(max_length=50)
    date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("lot", "date")


class Inventory(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="inventory")
    weight = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    smarties_ct = models.PositiveIntegerField(default=0)
    inv_date = models.DateField(default=timezone.now)

    class Meta:
        unique_together = ("lot", "inv_date")

    def __str__(self):
        return f"Inventory for {self.lot} ({self.weight} lbs on {self.inv_date})"


# this is used to keep track of what i have printed
class GermSamplePrint(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="germ_sample_prints")
    print_date = models.DateField(default=timezone.now)
    for_year = models.PositiveIntegerField()

    class Meta:
        unique_together = ("lot", "print_date")

    def __str__(self):
        return f"Germ Sample Print for {self.lot} on {self.print_date}"


class GerminationBatch(models.Model):
    batch_number = models.CharField(max_length=10)
    # date = models.DateField(auto_now_add=True)
    date = models.DateField(null=True, blank=True)
    tracking_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Germination Batch {self.batch_number}"


# these get instantiated when submitting germination tests
class Germination(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="germinations")
    batch = models.ForeignKey(GerminationBatch, on_delete=models.CASCADE, related_name="germinations", blank=True, null=True)
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("active", "Active")])
    germination_rate = models.PositiveIntegerField()
    test_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    for_year = models.PositiveIntegerField()

    class Meta:
        unique_together = ("lot", "test_date")

    def __str__(self):
        return f"Germination for {self.lot} on {self.test_date} for {self.for_year} is {self.germination_rate}%"


class RetiredLot(models.Model):
    lot = models.OneToOneField(Lot, on_delete=models.CASCADE, related_name="retired_info")
    retired_date = models.DateField(default=timezone.now)
    lbs_remaining = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Retired {self.lot}"


class LotNote(models.Model):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="notes")
    date = models.DateTimeField(auto_now_add=True)
    note = models.TextField()

    def __str__(self):
        return f"Note for {self.lot} ({self.date:%Y-%m-%d})"

# class Growout(models.Model):
#     variety = models.OneToOneField("products.Variety", on_delete=models.CASCADE, related_name="growout_info")
#     location = models.CharField(max_length=100, blank=True, null=True)
#     planted_date = models.DateField(blank=True, null=True)
#     expected_harvest_date = models.DateField(blank=True, null=True)
#     actual_harvest_date = models.DateField(blank=True, null=True)
#     notes = models.TextField(blank=True, null=True)

#     def __str__(self):
#         return f"Growout for {self.variety.name}"
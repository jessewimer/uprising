from django.conf import settings
from django.db import models
from lots.models import Lot
from django.contrib.auth import get_user_model
User = get_user_model()
from django.db.models import Sum
from django.utils import timezone
# from datetime import datetime

class Variety(models.Model):
    sku_prefix = models.CharField(max_length=50, primary_key=True)
    var_name = models.CharField(max_length=255, blank=True, null=True)
    crop = models.CharField(max_length=255, blank=True, null=True)
    common_spelling = models.CharField(max_length=255, blank=True, null=True)
    common_name = models.CharField(max_length=255, blank=True, null=True)
    group = models.CharField(max_length=255, blank=True, null=True)
    veg_type = models.CharField(max_length=255, blank=True, null=True)
    species = models.CharField(max_length=255, blank=True, null=True)
    # supergroup = models.CharField(max_length=255, blank=True, null=True)
    subtype = models.CharField(max_length=255, blank=True, null=True)
    days = models.CharField(max_length=50, blank=True, null=True)
    active = models.BooleanField(default=True)
    stock_qty = models.CharField(max_length=50, blank=True, null=True)
    photo_path = models.CharField(max_length=255, blank=True, null=True)
    wholesale = models.BooleanField(default=False)
    wholesale_rack_designation = models.CharField(max_length=1, blank=True, null=True)
    website_bulk = models.BooleanField(default=False)
    is_mix = models.BooleanField(default=False)
    growout_needed = models.CharField(max_length=10, blank=True, null=True)

    desc_line1 = models.TextField(blank=True, null=True)
    desc_line2 = models.TextField(blank=True, null=True)
    desc_line3 = models.TextField(blank=True, null=True)
    back1 = models.TextField(blank=True, null=True)
    back2 = models.TextField(blank=True, null=True)
    back3 = models.TextField(blank=True, null=True)
    back4 = models.TextField(blank=True, null=True)
    back5 = models.TextField(blank=True, null=True)
    back6 = models.TextField(blank=True, null=True)
    back7 = models.TextField(blank=True, null=True)

    ws_notes = models.TextField(blank=True, null=True)
    ws_description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.sku_prefix} - {self.var_name or ''}"

        
class Product(models.Model):
    variety = models.ForeignKey("Variety", on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    lot = models.ForeignKey("lots.Lot", on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    mix_lot = models.ForeignKey("lots.MixLot", on_delete=models.SET_NULL, null=True, blank=True, related_name="products") 
    pkg_size = models.CharField(max_length=50, blank=True, null=True)
    sku_suffix = models.CharField(max_length=50, blank=True, null=True)
    alt_sku = models.CharField(max_length=50, blank=True, null=True)
    lineitem_name = models.CharField(max_length=255, blank=True, null=True)

    rack_location = models.CharField(max_length=100, blank=True, null=True)
    env_type = models.CharField(max_length=50, blank=True, null=True)
    env_multiplier = models.IntegerField(blank=True, null=True)
    label = models.CharField(max_length=1, blank=True, null=True)

    num_printed = models.IntegerField(blank=True, null=True)
    num_printed_next_year = models.IntegerField(default=0)
    scoop_size = models.CharField(max_length=50, blank=True, null=True)
    print_back = models.BooleanField(default=False)
    bulk_pre_pack = models.IntegerField(blank=True, null=True, default=0)
    is_sub_product = models.BooleanField(default=False)

    class Meta:
        unique_together = ("variety", "sku_suffix")
        
    def __str__(self):
        return f"{self.variety.sku_prefix} - {self.pkg_size or ''}"

    def get_rad_type(self):
        if self.pkg_size != 'pkt':
            if hasattr(self.variety, 'rad_type'):
                return self.variety.rad_type.rad_type
        return None
    
    def get_ytd_sales(self):
        current_year = timezone.now().year
        
        # Get OOIncludes total for current year
        oo_total = self.ooincludes_set.filter(
            order__date__year=current_year
        ).aggregate(total=Sum('qty'))['total'] or 0
        
        if self.sku_suffix != 'pkt':
            return f"{oo_total}"
        
        # Get SOIncludes total for current year  
        so_total = self.soincludes_set.filter(
            store_order__date__year=current_year,
            store_order__fulfilled_date__isnull=False
        ).aggregate(total=Sum('quantity'))['total'] or 0
                
        if oo_total == 0 and so_total == 0:
            return None  # Will display as "--"
        
        return f"{oo_total} ({so_total})"
    
    def get_last_year_sales(self):
        last_year = settings.CURRENT_ORDER_YEAR - 1
        # Get total retail sales for last year
        retail_total = self.sales.filter(
            year=last_year,
            wholesale=False
        ).aggregate(total=Sum('quantity'))['total'] or 0

        if self.sku_suffix != 'pkt':
            return f"{retail_total}"
        
        # Get total wholesale sales for last year
        wholesale_total = self.sales.filter(
            year=last_year,
            wholesale=True
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return f"{retail_total} ({wholesale_total})"
        
    # CHANGED THIS SO THAT IT ONLY PULLS LABEL PRINTS FOR CURRENT ORDER YEAR... 
    def get_total_printed(self):
        total = self.label_prints.filter(for_year=settings.CURRENT_ORDER_YEAR).aggregate(
            total=Sum('qty')
        )['total'] or 0
        
        return total
    
    def get_last_print_date(self):
        last_print = self.label_prints.filter(for_year=settings.CURRENT_ORDER_YEAR).order_by('-date').first()
        if last_print:
            return last_print.date.strftime("%m/%d/%Y")
        return "--"
    

    

class VarNote(models.Model):
    variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name="notes")
    note = models.TextField()
    date = models.DateField(blank=True, null=True)


class VarWholeSaleNotes(models.Model):
    variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name="wholesale_notes_list")
    note = models.TextField()
    date = models.DateField(blank=True, null=True)


class ProductNote(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="notes")
    note = models.TextField()
    date = models.DateField(blank=True, null=True)


class RadType(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="rad_type")
    rad_type = models.CharField(max_length=100)


class InitialProductOffering(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="initial_offerings")
    year = models.IntegerField()
    tracked = models.BooleanField(default=False)
    initial_offering = models.IntegerField(default=0)


class Sales(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sales")
    quantity = models.IntegerField()
    year = models.IntegerField()
    wholesale = models.BooleanField(default=False)


# rethink this, maybe tie into lot??
class Growout(models.Model):
    variety = models.OneToOneField(Variety, on_delete=models.CASCADE, related_name="growout_info")
    sow_date = models.DateField()
    start_date = models.DateField()
    harvest_date = models.DateField()
    notes = models.TextField(blank=True, null=True)


class MiscSale(models.Model):
    variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name="misc_sales")
    lbs = models.FloatField()
    date = models.DateField()
    customer = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)


class MiscProduct(models.Model):
    lineitem_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)   

class MiscSales(models.Model):
    product = models.ForeignKey(MiscProduct, on_delete=models.CASCADE, related_name="sales")
    quantity = models.IntegerField()
    year = models.IntegerField()

class LastSelected(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    variety = models.ForeignKey(Variety, on_delete=models.CASCADE, related_name="last_selected_for")

    class Meta:
        verbose_name_plural = "Last Selected"


class LabelPrint(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="label_prints")
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="label_prints", null=True, blank=True)
    mix_lot = models.ForeignKey('lots.MixLot', on_delete=models.CASCADE, related_name="label_prints", null=True, blank=True) 
    date = models.DateField()
    qty = models.IntegerField()
    for_year = models.IntegerField()

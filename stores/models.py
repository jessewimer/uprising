from django.db import models
from products.models import Product
from django.contrib.auth.models import User
# import PKT_PRICE from settings
from django.conf import settings


class Store(models.Model):

    store_user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    store_num = models.IntegerField(primary_key=True)
    store_name = models.CharField(max_length=100, default="default")
    store_contact_name = models.CharField(max_length=100, blank=True, null=True)
    store_contact_phone = models.CharField(max_length=100, blank=True, null=True)
    store_contact_email = models.TextField(blank=True, null=True)
    store_address = models.TextField(blank=True, null=True)
    store_address2 = models.TextField(blank=True, null=True)
    store_city = models.CharField(max_length=100, blank=True, null=True)
    store_state = models.CharField(max_length=100, blank=True, null=True)
    store_zip = models.CharField(max_length=20, blank=True, null=True)
    store_country = models.CharField(max_length=100, blank=True, null=True)
    rack_material = models.CharField(max_length=100, blank=True, null=True)
    rack_num = models.CharField(max_length=100, blank=True, null=True)
    header = models.CharField(max_length=100, blank=True, null=True)
    velcro = models.BooleanField(default=False)
    first_order = models.CharField(max_length=100, blank=True, null=True)
    slots = models.IntegerField(default=0)
    available_products = models.ManyToManyField(
        'products.Product',
        through='StoreProduct',
        related_name='available_in_stores'
    )

    def __str__(self):
        return self.store_name

    
    @staticmethod
    def get_total_store_sales(year):
        from django.db.models import Sum, F
        year_suffix = str(year)[-2:]
        
        # Fulfilled orders (have fulfilled_date)
        fulfilled_sales = StoreOrder.objects.filter(
            order_number__endswith=f'-{year_suffix}',
            fulfilled_date__isnull=False
        ).aggregate(
            total=Sum(F('items__price') * F('items__quantity'))
        )['total']
        
        # Pending orders (no fulfilled_date)
        pending_sales = StoreOrder.objects.filter(
            order_number__endswith=f'-{year_suffix}',
            fulfilled_date__isnull=True
        ).aggregate(
            total=Sum(F('items__price') * F('items__quantity'))
        )['total']
        
        return fulfilled_sales if fulfilled_sales else 0, pending_sales if pending_sales else 0
    
    @staticmethod
    def get_total_store_packets(year):
        from django.db.models import Sum
        year_suffix = str(year)[-2:]
        
        # Fulfilled orders (have fulfilled_date)
        fulfilled_packets = StoreOrder.objects.filter(
            order_number__endswith=f'-{year_suffix}',
            fulfilled_date__isnull=False
        ).aggregate(total=Sum('items__quantity'))['total']
        
        # Pending orders (no fulfilled_date)
        pending_packets = StoreOrder.objects.filter(
            order_number__endswith=f'-{year_suffix}',
            fulfilled_date__isnull=True
        ).aggregate(total=Sum('items__quantity'))['total']
        
        return fulfilled_packets if fulfilled_packets else 0, pending_packets if pending_packets else 0
        


class StoreProduct(models.Model):
    store = models.ForeignKey('stores.Store', on_delete=models.CASCADE, to_field='store_num')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    is_available = models.BooleanField(default=False)

    class Meta:
        unique_together = ('store', 'product')


class StoreNote(models.Model):
    note_id = models.AutoField(primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="notes", to_field='store_num')
    note = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Note for {self.store.store_name} ({self.date:%Y-%m-%d})"


class StoreOrder(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="orders", to_field='store_num')
    order_number = models.CharField(max_length=100, unique=True, default="XXXXX-XX")
    date = models.DateTimeField(null=True, blank=True)
    fulfilled_date = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Order {self.order_number} for {self.store.store_name}" 


class SOIncludes(models.Model):
    store_order = models.ForeignKey(StoreOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    photo = models.BooleanField(default=False, blank=True, null=True)

    class Meta:
        verbose_name = "SO Include"
        verbose_name_plural = "SO Includes"
    def __str__(self):
        return f"{self.quantity} × {self.product} in Order {self.store_order}"


class LastSelectedStore(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="last_selected_store")
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, to_field='store_num',)

    def __str__(self):
        return f"{self.user.username} last selected {self.store.store_name if self.store else 'None'}"
    

class PickListPrinted(models.Model):
    """
    Track when pick lists have been printed for store orders
    """
    store_order = models.OneToOneField(
        StoreOrder, 
        on_delete=models.CASCADE, 
        related_name="pick_list_record",
        primary_key=True
    )
    
    class Meta:
        verbose_name = "Pick List Print Record"
        verbose_name_plural = "Pick List Print Records"
    
    def __str__(self):
        return f"Pick list for {self.store_order.order_number}"
    
class StoreReturns(models.Model):
    """
    Track seed packet returns from stores. 
    Credits auto-apply to first invoice of following year.
    """
    store = models.ForeignKey(
        Store, 
        on_delete=models.CASCADE, 
        related_name="returns",
        to_field='store_num'
    )
    return_year = models.IntegerField(
        help_text="Year the packets were returned (e.g., 2024)"
    )
    packets_returned = models.IntegerField(
        default=0,
        help_text="Number of packets returned by store"
    )

    class Meta:
        verbose_name = "Store Return"
        verbose_name_plural = "Store Returns"
        unique_together = ('store', 'return_year')
        ordering = ['-return_year']

    def __str__(self):
        return f"{self.store.store_name} - {self.return_year}: {self.packets_returned} packets"
    
    @classmethod
    def get_credit_for_first_invoice(cls, store_num, invoice_year):
        """
        Get credit for a store's first invoice based on previous year's returns.
        Returns (packets_returned, credit_amount) or (0, Decimal('0')) if no returns found.
        """
        from decimal import Decimal
        
        previous_year = invoice_year - 1
        
        print(f"\n--- get_credit_for_first_invoice DEBUG ---")
        print(f"Store num: {store_num}")
        print(f"Invoice year: {invoice_year}")
        print(f"Looking for returns from year: {previous_year}")
        
        try:
            return_record = cls.objects.get(
                store__store_num=store_num,
                return_year=previous_year
            )
            print(f"✓ Found return record: {return_record}")
            print(f"  Packets returned: {return_record.packets_returned}")
            
            # Calculate credit using the packet price from settings
            price = WholesalePktPrice.get_price_for_year(previous_year)
            print(f"  Price for year {previous_year}: {price}")
            
            if price is None:
                print(f"✗ No price found for year {previous_year}")
                return 0, Decimal('0')
            
            credit_amount = Decimal(str(return_record.packets_returned)) * price
            print(f"✓ Calculated credit: {credit_amount}")
            print(f"--- get_credit_for_first_invoice DEBUG END ---\n")
            return return_record.packets_returned, credit_amount
        except cls.DoesNotExist:
            print(f"✗ No return record found for store {store_num}, year {previous_year}")
            print(f"--- get_credit_for_first_invoice DEBUG END ---\n")
            return 0, Decimal('0')
    
class WholesalePktPrice(models.Model):
    """
    Model to track wholesale packet prices over different years.
    """
    year = models.IntegerField(unique=True)
    price_per_packet = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        verbose_name = "Wholesale Packet Price"
        verbose_name_plural = "Wholesale Packet Prices"
        ordering = ['-year']

    def __str__(self):
        return f"{self.year}: ${self.price_per_packet} per packet"
    
    @classmethod
    def get_price_for_year(cls, year):
        """
        Get the wholesale packet price for a given year.
        Returns the price as a Decimal or None if not found.
        """
        try:
            price_record = cls.objects.get(year=year)
            return price_record.price_per_packet
        except cls.DoesNotExist:
            return None

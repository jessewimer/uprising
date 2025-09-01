from django.db import models
from products.models import Product
from django.contrib.auth.models import User


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
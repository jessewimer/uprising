from django.db import models
from products.models import Product
from stores.models import Store
from django.contrib.auth.models import User


class OnlineOrder(models.Model):
    order_number = models.CharField(max_length=100, primary_key=True)
    customer_name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    address2 = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateTimeField()
    bulk = models.BooleanField(default=False)
    misc = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "online_order"

    def __str__(self):
        return f"OnlineOrder {self.order_number}"


class OOIncludes(models.Model):
    order = models.ForeignKey(OnlineOrder, on_delete=models.CASCADE, related_name="includes")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    qty = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "oo_includes"
        unique_together = ("order", "product")

    def __str__(self):
        return f"{self.qty} × {self.product} in {self.order}"


class OOIncludesMisc(models.Model):
    order = models.ForeignKey(OnlineOrder, on_delete=models.CASCADE, related_name="includes_misc")
    sku = models.CharField(max_length=100)
    qty = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "oo_includes_misc"
        unique_together = ("order", "sku")

    def __str__(self):
        return f"{self.qty} × {self.sku} in {self.order}"


# class PulledOrder(models.Model):
#     order_number = models.CharField(max_length=100)

#     class Meta:
#         db_table = "pulled_order"

#     def __str__(self):
#         return f"PulledOrder {self.order_number}"


class BatchMetadata(models.Model):
    batch_identifier = models.CharField(max_length=100, unique=True)
    batch_date = models.DateField()
    start_order_number = models.IntegerField()
    end_order_number = models.IntegerField()
    start_order_date = models.DateField()
    end_order_date = models.DateField()

    class Meta:
        db_table = "batch_metadata"

    def __str__(self):
        return f"Batch {self.batch_identifier}"


class BulkBatch(models.Model):
    batch_identifier = models.ForeignKey(BatchMetadata, on_delete=models.CASCADE, related_name="bulk_batches")
    bulk_type = models.CharField(max_length=50)  # 'print' or 'pull'
    # might need to make sku a foreign key to Product
    sku = models.CharField(max_length=100)
    quantity = models.IntegerField()

    class Meta:
        db_table = "bulk_batch"

    def __str__(self):
        return f"{self.quantity} × {self.sku} in {self.batch_identifier}"


class LastSelected(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="last_selected_order")
    order_number = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "last_selected"

    def __str__(self):
        return f"{self.user.username} last selected {self.order_number or 'None'}"

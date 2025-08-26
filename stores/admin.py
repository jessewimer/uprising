from django.contrib import admin
from .models import *

admin.site.register(Store)
admin.site.register(StoreProduct)
admin.site.register(StoreNote)
admin.site.register(StoreOrder)
admin.site.register(SOIncludes)
admin.site.register(LastSelectedStore)

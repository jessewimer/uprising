from django.contrib import admin
from lots.models import *

admin.site.register(Grower)
admin.site.register(Lot)
admin.site.register(StockSeed)
admin.site.register(Inventory)
admin.site.register(GermSamplePrint)
admin.site.register(GerminationBatch)
admin.site.register(Germination)
admin.site.register(RetiredLot)

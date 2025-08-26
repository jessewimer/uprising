from django.contrib import admin

from orders.models import *

# register all classes
admin.site.register(OnlineOrder)
admin.site.register(OOIncludes)
admin.site.register(OOIncludesMisc)
admin.site.register(BatchMetadata)
admin.site.register(BulkBatch)
admin.site.register(LastSelected)

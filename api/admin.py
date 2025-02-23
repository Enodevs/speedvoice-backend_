from django.contrib import admin # type:ignore
from . import models as api_models

class InvoiceItemAdminModel(admin.TabularInline):
    model = api_models.Invoice_item

class InvoiceAdminModel(admin.ModelAdmin):
    inlines = [InvoiceItemAdminModel]

admin.site.register(api_models.LoginToken)
admin.site.register(api_models.Business,)
admin.site.register(api_models.Category,)
admin.site.register(api_models.Customer,)
admin.site.register(api_models.Invoice, InvoiceAdminModel)
admin.site.register(api_models.Product)
admin.site.register(api_models.Receipt)
admin.site.register(api_models.Notification)
admin.site.register(api_models.InvoiceAccessToken)

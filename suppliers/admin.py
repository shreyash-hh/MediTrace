from django.contrib import admin
from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_number', 'email', 'created_at')
    search_fields = ('name', 'contact_number', 'email', 'address')
    list_filter = ('created_at',)
    ordering = ('name',)

from django.contrib import admin
from .models import Medicine, Batch, StockTransaction


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'unit', 'manufacturer', 'created_at')
    search_fields = ('name', 'category', 'manufacturer')
    list_filter = ('category', 'created_at')
    ordering = ('name',)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'medicine', 'expiry_date', 'quantity', 'cost_price', 'supplier', 'created_at')
    search_fields = ('batch_number', 'medicine__name', 'supplier__name')
    list_filter = ('expiry_date', 'supplier', 'created_at')
    ordering = ('expiry_date',)


@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch', 'transaction_type', 'quantity', 'timestamp', 'reason')
    search_fields = ('batch__batch_number', 'batch__medicine__name', 'reason')
    list_filter = ('transaction_type', 'timestamp')
    ordering = ('-timestamp',)

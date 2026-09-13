from django.db import models
from django.utils import timezone


class Medicine(models.Model):
    name = models.CharField(max_length=255, help_text="Brand or generic name of medicine")
    category = models.CharField(max_length=100, blank=True, help_text="e.g., Antibiotics, Analgesics, Antipyretics")
    unit = models.CharField(
        max_length=50,
        default='tablets',
        help_text="Unit of measure, e.g., tablets, strips, bottles, vials, boxes"
    )
    manufacturer = models.CharField(max_length=255, blank=True, help_text="Pharmaceutical manufacturer name")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Medicine"
        verbose_name_plural = "Medicines"

    def __str__(self):
        return f"{self.name} ({self.category})" if self.category else self.name


class Batch(models.Model):
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name='batches',
        help_text="Associated medicine"
    )
    batch_number = models.CharField(max_length=100, help_text="Unique batch/lot identifier")
    expiry_date = models.DateField(help_text="Expiry date for this batch")
    quantity = models.PositiveIntegerField(default=0, help_text="Current stock quantity in this batch")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Purchase cost price per unit")
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batches',
        help_text="Supplier who provided this batch"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['expiry_date', 'batch_number']
        verbose_name = "Batch"
        verbose_name_plural = "Batches"

    def __str__(self):
        return f"{self.medicine.name} - Batch #{self.batch_number} (Exp: {self.expiry_date})"

    @property
    def is_expired(self):
        return self.expiry_date < timezone.now().date()

    @property
    def days_until_expiry(self):
        return (self.expiry_date - timezone.now().date()).days


class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        IN = 'IN', 'Stock In'
        OUT = 'OUT', 'Stock Out'

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text="Target batch for this transaction"
    )
    transaction_type = models.CharField(
        max_length=3,
        choices=TransactionType.choices,
        help_text="Direction of stock movement (IN/OUT)"
    )
    quantity = models.PositiveIntegerField(help_text="Quantity added or removed")
    timestamp = models.DateTimeField(default=timezone.now, help_text="Date and time of transaction")
    reason = models.TextField(blank=True, null=True, help_text="Optional reason (e.g. Purchase, Sale, Dispense, Damaged, Adjustment)")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Stock Transaction"
        verbose_name_plural = "Stock Transactions"

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} on {self.batch.batch_number} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"

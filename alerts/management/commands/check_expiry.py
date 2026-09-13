from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.models import Batch


class Command(BaseCommand):
    help = "Check and report batches that are expired or expiring within a given threshold (default 30 days)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Expiry threshold in days (default: 30)'
        )

    def handle(self, *args, **options):
        threshold_days = options['days']
        today = timezone.now().date()
        cutoff_date = today + timedelta(days=threshold_days)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== MediTrace Expiry Alert Check (Threshold: {threshold_days} days | Cutoff: {cutoff_date}) ==="
        ))

        expiring_batches = Batch.objects.filter(
            expiry_date__lte=cutoff_date
        ).select_related('medicine', 'supplier').order_by('expiry_date')

        if not expiring_batches.exists():
            self.stdout.write(self.style.SUCCESS(
                f"\n[OK] All good! No batches are expired or expiring within the next {threshold_days} days.\n"
            ))
            return

        expired_count = 0
        expiring_soon_count = 0

        self.stdout.write(
            f"\n{'STATUS':<12} | {'MEDICINE':<25} | {'BATCH #':<12} | {'EXPIRY DATE':<12} | {'DAYS':<10} | {'QTY':<8} | {'SUPPLIER':<20}"
        )
        self.stdout.write("-" * 105)

        for batch in expiring_batches:
            days_diff = (batch.expiry_date - today).days
            supplier_name = batch.supplier.name if batch.supplier else "N/A"
            medicine_name = batch.medicine.name[:24]

            if days_diff < 0:
                expired_count += 1
                status = "EXPIRED"
                days_str = f"{abs(days_diff)}d ago"
                formatted_row = f"{status:<12} | {medicine_name:<25} | {batch.batch_number:<12} | {str(batch.expiry_date):<12} | {days_str:<10} | {batch.quantity:<8} | {supplier_name:<20}"
                self.stdout.write(self.style.ERROR(formatted_row))
            else:
                expiring_soon_count += 1
                status = "EXPIRING"
                days_str = f"in {days_diff}d"
                formatted_row = f"{status:<12} | {medicine_name:<25} | {batch.batch_number:<12} | {str(batch.expiry_date):<12} | {days_str:<10} | {batch.quantity:<8} | {supplier_name:<20}"
                self.stdout.write(self.style.WARNING(formatted_row))

        self.stdout.write("-" * 105)
        self.stdout.write(
            f"Summary: {self.style.ERROR(f'{expired_count} Expired')} | {self.style.WARNING(f'{expiring_soon_count} Expiring Soon')} | Total flagged: {len(expiring_batches)}\n"
        )

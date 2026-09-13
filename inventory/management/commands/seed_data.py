from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from suppliers.models import Supplier
from inventory.models import Medicine, Batch, StockTransaction


class Command(BaseCommand):
    help = "Populate realistic test data for MediTrace inventory, expiry tracking, and dashboard aggregates."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Clearing existing records...")
            StockTransaction.objects.all().delete()
            Batch.objects.all().delete()
            Medicine.objects.all().delete()
            Supplier.objects.all().delete()

        self.stdout.write(self.style.MIGRATE_HEADING("Populating realistic MediTrace pharmacy data..."))

        # 1. Suppliers
        s1, _ = Supplier.objects.get_or_create(
            name="Novartis Healthcare Ltd",
            defaults={'contact_number': "+1-800-555-0101", 'email': "orders@novartis.com", 'address': "456 Pharma Plaza, Basel"}
        )
        s2, _ = Supplier.objects.get_or_create(
            name="Pfizer Global Supply",
            defaults={'contact_number': "+1-800-555-0202", 'email': "supply@pfizer.com", 'address': "235 E 42nd St, New York"}
        )
        s3, _ = Supplier.objects.get_or_create(
            name="Sun Pharma Distributors",
            defaults={'contact_number': "+91-22-555-0303", 'email': "dispatch@sunpharma.com", 'address': "Mumbai, India"}
        )
        s4, _ = Supplier.objects.get_or_create(
            name="Sanofi India Pvt Ltd",
            defaults={'contact_number': "+91-22-555-0404", 'email': "contact@sanofi.com", 'address': "Powai, Mumbai"}
        )

        # 2. Medicines (4 distinct therapeutic categories)
        m1, _ = Medicine.objects.get_or_create(
            name="Amoxicillin 500mg",
            defaults={'category': 'Antibiotics', 'unit': 'capsules', 'manufacturer': 'Novartis'}
        )
        m2, _ = Medicine.objects.get_or_create(
            name="Paracetamol 650mg",
            defaults={'category': 'Analgesics / Antipyretics', 'unit': 'tablets', 'manufacturer': 'Sun Pharma'}
        )
        m3, _ = Medicine.objects.get_or_create(
            name="Metformin 500mg",
            defaults={'category': 'Antidiabetic', 'unit': 'tablets', 'manufacturer': 'Sanofi'}
        )
        m4, _ = Medicine.objects.get_or_create(
            name="Atorvastatin 20mg",
            defaults={'category': 'Cardiovascular', 'unit': 'tablets', 'manufacturer': 'Pfizer'}
        )

        today = timezone.now().date()
        now = timezone.now()

        # 3. Batches (Multiple per medicine with diverse expiry dates)
        batches_def = [
            # Medicine 1: Amoxicillin (1 expired, 1 expiring in 14 days, 1 safe in 6 months)
            (m1, "AMX-EXP-01", today - timedelta(days=5), 25, Decimal("12.50"), s1),
            (m1, "AMX-NEAR-02", today + timedelta(days=14), 120, Decimal("12.50"), s1),
            (m1, "AMX-SAFE-03", today + timedelta(days=180), 450, Decimal("11.80"), s1),

            # Medicine 2: Paracetamol (1 expiring in 8 days, 1 safe in 10 months)
            (m2, "PARA-NEAR-01", today + timedelta(days=8), 80, Decimal("3.20"), s3),
            (m2, "PARA-SAFE-02", today + timedelta(days=300), 600, Decimal("2.90"), s3),

            # Medicine 3: Metformin (1 expiring in 24 days, 1 safe in 1.5 years)
            (m3, "MET-NEAR-01", today + timedelta(days=24), 150, Decimal("5.50"), s4),
            (m3, "MET-SAFE-02", today + timedelta(days=550), 800, Decimal("5.00"), s4),

            # Medicine 4: Atorvastatin (1 expiring in 45 days, 1 safe in 1+ years)
            (m4, "ATOR-MID-01", today + timedelta(days=45), 200, Decimal("15.75"), s2),
            (m4, "ATOR-SAFE-02", today + timedelta(days=400), 350, Decimal("14.50"), s2),
        ]

        created_batches = []
        for med, b_num, exp_d, qty, cp, sup in batches_def:
            batch, created = Batch.objects.get_or_create(
                batch_number=b_num,
                defaults={
                    'medicine': med,
                    'expiry_date': exp_d,
                    'quantity': qty,
                    'cost_price': cp,
                    'supplier': sup,
                }
            )
            if not created:
                batch.expiry_date = exp_d
                batch.quantity = qty
                batch.save()
            created_batches.append(batch)

        # 4. Stock Transactions across different dates
        # Clear previous transactions for fresh timestamp distribution if needed
        StockTransaction.objects.all().delete()

        transactions_plan = [
            # Day -10: Initial Purchase Delivery for Batch 1 & 2
            (created_batches[0], 'IN', 100, now - timedelta(days=10), "Supplier delivery intake"),
            (created_batches[1], 'IN', 200, now - timedelta(days=10), "Supplier delivery intake"),
            # Day -8: Patient Prescriptions
            (created_batches[0], 'OUT', 50, now - timedelta(days=8), "Prescription dispensing"),
            (created_batches[1], 'OUT', 40, now - timedelta(days=8), "Prescription dispensing"),
            # Day -7: Intake for Paracetamol & Metformin
            (created_batches[3], 'IN', 150, now - timedelta(days=7), "Emergency stock replenishment"),
            (created_batches[5], 'IN', 300, now - timedelta(days=7), "Monthly bulk order"),
            # Day -5: OPD Sales
            (created_batches[3], 'OUT', 40, now - timedelta(days=5), "OPD pharmacy sales"),
            (created_batches[5], 'OUT', 90, now - timedelta(days=5), "Clinic orders"),
            (created_batches[0], 'OUT', 25, now - timedelta(days=5), "Ward distribution"),
            # Day -4: Safe Batches Delivery
            (created_batches[2], 'IN', 500, now - timedelta(days=4), "Quarterly bulk order"),
            (created_batches[4], 'IN', 700, now - timedelta(days=4), "Bulk shipment from Sun Pharma"),
            (created_batches[6], 'IN', 900, now - timedelta(days=4), "Bulk shipment from Sanofi"),
            (created_batches[7], 'IN', 250, now - timedelta(days=4), "Routine intake"),
            (created_batches[8], 'IN', 400, now - timedelta(days=4), "Routine intake"),
            # Day -3: Daily Dispenses
            (created_batches[2], 'OUT', 50, now - timedelta(days=3), "Prescription dispensing"),
            (created_batches[4], 'OUT', 100, now - timedelta(days=3), "OPD sales"),
            (created_batches[6], 'OUT', 100, now - timedelta(days=3), "Prescription dispensing"),
            (created_batches[7], 'OUT', 50, now - timedelta(days=3), "Cardiology clinic order"),
            (created_batches[8], 'OUT', 50, now - timedelta(days=3), "Cardiology clinic order"),
            # Day -2: Dispensing
            (created_batches[1], 'OUT', 40, now - timedelta(days=2), "Prescription dispensing"),
            (created_batches[3], 'OUT', 30, now - timedelta(days=2), "Walk-in patient sale"),
            (created_batches[5], 'OUT', 60, now - timedelta(days=2), "Monthly diabetic package refill"),
            # Today: Current Transactions
            (created_batches[1], 'IN', 20, now, "Supplier exchange replacement"),
            (created_batches[1], 'OUT', 20, now, "Emergency ward request"),
        ]

        for b, t_type, qty, ts, reason in transactions_plan:
            StockTransaction.objects.create(
                batch=b,
                transaction_type=t_type,
                quantity=qty,
                timestamp=ts,
                reason=reason
            )

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Seeded 4 Medicines, {len(created_batches)} Batches, and {len(transactions_plan)} Stock Transactions!"
        ))

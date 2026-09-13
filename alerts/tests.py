import io
from datetime import date, timedelta
from decimal import Decimal
from django.core.management import call_command
from django.test import TestCase
from inventory.models import Medicine, Batch
from suppliers.models import Supplier


class CheckExpiryCommandTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="PharmaCore Global")
        self.med1 = Medicine.objects.create(name="Paracetamol 500mg", category="Analgesics")
        self.med2 = Medicine.objects.create(name="Ciprofloxacin 250mg", category="Antibiotics")
        self.med3 = Medicine.objects.create(name="Vitamin C 1000mg", category="Supplements")

        # Expired batch
        self.batch_expired = Batch.objects.create(
            medicine=self.med1,
            batch_number="PARA-OLD",
            expiry_date=date.today() - timedelta(days=5),
            quantity=50,
            cost_price=Decimal("2.00"),
            supplier=self.supplier
        )
        # Expiring soon (10 days)
        self.batch_expiring_soon = Batch.objects.create(
            medicine=self.med2,
            batch_number="CIPRO-SOON",
            expiry_date=date.today() + timedelta(days=10),
            quantity=80,
            cost_price=Decimal("5.50"),
            supplier=self.supplier
        )
        # Safe batch (120 days)
        self.batch_safe = Batch.objects.create(
            medicine=self.med3,
            batch_number="VITC-SAFE",
            expiry_date=date.today() + timedelta(days=120),
            quantity=200,
            cost_price=Decimal("4.00"),
            supplier=self.supplier
        )

    def test_check_expiry_default_30_days(self):
        out = io.StringIO()
        call_command('check_expiry', stdout=out)
        output = out.getvalue()
        
        # Should flag expired and expiring soon
        self.assertIn("EXPIRED", output)
        self.assertIn("EXPIRING", output)
        self.assertIn("PARA-OLD", output)
        self.assertIn("CIPRO-SOON", output)
        # Should NOT flag the safe batch expiring in 120 days
        self.assertNotIn("VITC-SAFE", output)

    def test_check_expiry_custom_days(self):
        out = io.StringIO()
        call_command('check_expiry', '--days', '150', stdout=out)
        output = out.getvalue()
        
        # When threshold is 150 days, safe batch should also be included
        self.assertIn("VITC-SAFE", output)

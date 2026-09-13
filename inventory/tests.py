from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from suppliers.models import Supplier
from inventory.models import Medicine, Batch, StockTransaction


class InventoryModelTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name="Apex Pharma Ltd",
            contact_number="+1-555-0199",
            email="supply@apexpharma.com",
            address="100 Medical Blvd, Healthcare City"
        )
        self.medicine = Medicine.objects.create(
            name="Amoxicillin 500mg",
            category="Antibiotics",
            unit="capsules",
            manufacturer="GlaxoSmithKline"
        )
        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number="AMX-2026-001",
            expiry_date=date.today() + timedelta(days=20),
            quantity=150,
            cost_price=Decimal("12.50"),
            supplier=self.supplier
        )

    def test_supplier_creation(self):
        self.assertEqual(str(self.supplier), "Apex Pharma Ltd")
        self.assertEqual(self.supplier.email, "supply@apexpharma.com")

    def test_medicine_creation(self):
        self.assertEqual(str(self.medicine), "Amoxicillin 500mg (Antibiotics)")
        self.assertEqual(self.medicine.unit, "capsules")

    def test_batch_creation_and_properties(self):
        self.assertEqual(self.batch.medicine, self.medicine)
        self.assertEqual(self.batch.supplier, self.supplier)
        self.assertEqual(self.batch.quantity, 150)
        self.assertFalse(self.batch.is_expired)
        self.assertGreater(self.batch.days_until_expiry, 0)

    def test_stock_transactions(self):
        tx_in = StockTransaction.objects.create(
            batch=self.batch,
            transaction_type=StockTransaction.TransactionType.IN,
            quantity=100,
            reason="Initial stock intake"
        )
        tx_out = StockTransaction.objects.create(
            batch=self.batch,
            transaction_type=StockTransaction.TransactionType.OUT,
            quantity=25,
            reason="Prescription dispensed"
        )

        self.assertEqual(self.batch.transactions.count(), 2)
        self.assertIn("IN 100", str(tx_in))
        self.assertIn("OUT 25", str(tx_out))

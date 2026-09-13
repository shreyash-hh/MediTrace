from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
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


class CustomFrontendViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.today = timezone.now().date()
        self.supplier = Supplier.objects.create(name="Global Med Supplier")
        self.medicine = Medicine.objects.create(
            name="Azithromycin 500mg",
            category="Antibiotics",
            unit="tablets"
        )

    def test_stock_overview_view(self):
        Batch.objects.create(
            medicine=self.medicine,
            batch_number="AZI-01",
            expiry_date=self.today + timedelta(days=45),
            quantity=200,
            cost_price=Decimal("15.00"),
            supplier=self.supplier
        )
        response = self.client.get(reverse('inventory:stock_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Azithromycin 500mg")
        self.assertContains(response, "200")

    def test_add_stock_valid_existing_medicine(self):
        future_date = (self.today + timedelta(days=90)).strftime('%Y-%m-%d')
        post_data = {
            'medicine_id': str(self.medicine.id),
            'batch_number': 'AZI-NEW-01',
            'expiry_date': future_date,
            'quantity': '300',
            'cost_price': '14.50',
            'supplier_id': str(self.supplier.id),
            'reason': 'Bulk replenishment'
        }
        response = self.client.post(reverse('inventory:add_stock'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Batch should exist
        batch = Batch.objects.get(batch_number='AZI-NEW-01')
        self.assertEqual(batch.quantity, 300)
        self.assertEqual(batch.medicine, self.medicine)

        # StockTransaction (IN) should be created
        tx = StockTransaction.objects.get(batch=batch)
        self.assertEqual(tx.transaction_type, StockTransaction.TransactionType.IN)
        self.assertEqual(tx.quantity, 300)

    def test_add_stock_inline_new_medicine(self):
        future_date = (self.today + timedelta(days=120)).strftime('%Y-%m-%d')
        post_data = {
            'is_new_medicine': 'on',
            'new_name': 'Cefixime 200mg',
            'new_category': 'Antibiotics',
            'new_unit': 'capsules',
            'new_manufacturer': 'Pfizer',
            'batch_number': 'CEF-001',
            'expiry_date': future_date,
            'quantity': '150',
            'cost_price': '22.00',
            'supplier_id': str(self.supplier.id),
            'reason': 'New item addition'
        }
        response = self.client.post(reverse('inventory:add_stock'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # New medicine and batch must exist
        new_med = Medicine.objects.get(name='Cefixime 200mg')
        self.assertEqual(new_med.unit, 'capsules')
        batch = Batch.objects.get(batch_number='CEF-001')
        self.assertEqual(batch.medicine, new_med)
        self.assertEqual(batch.quantity, 150)

    def test_add_stock_rejects_past_or_today_expiry_date(self):
        past_date = (self.today - timedelta(days=1)).strftime('%Y-%m-%d')
        post_data = {
            'medicine_id': str(self.medicine.id),
            'batch_number': 'INVALID-EXP',
            'expiry_date': past_date,
            'quantity': '100',
            'cost_price': '10.00',
        }
        response = self.client.post(reverse('inventory:add_stock'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expiry date must be in the future")
        self.assertFalse(Batch.objects.filter(batch_number='INVALID-EXP').exists())

    def test_record_usage_fefo_multi_batch_deduction(self):
        # Create Batch 1: Expiring in 10 days, Qty = 30
        b1 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="AZI-EXP-EARLY",
            expiry_date=self.today + timedelta(days=10),
            quantity=30,
            cost_price=Decimal("15.00"),
            supplier=self.supplier
        )
        # Create Batch 2: Expiring in 60 days, Qty = 50
        b2 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="AZI-EXP-LATER",
            expiry_date=self.today + timedelta(days=60),
            quantity=50,
            cost_price=Decimal("15.00"),
            supplier=self.supplier
        )

        # Dispense 45 units (should deplete all 30 of b1, and 15 from b2)
        post_data = {
            'medicine_id': str(self.medicine.id),
            'quantity': '45',
            'reason': 'Patient Prescription'
        }
        response = self.client.post(reverse('inventory:record_usage'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        b1.refresh_from_db()
        b2.refresh_from_db()

        self.assertEqual(b1.quantity, 0)
        self.assertEqual(b2.quantity, 35)

        # Check transactions: 2 separate OUT transactions
        txs = StockTransaction.objects.filter(batch__medicine=self.medicine, transaction_type='OUT').order_by('id')
        self.assertEqual(txs.count(), 2)
        self.assertEqual(txs[0].batch, b1)
        self.assertEqual(txs[0].quantity, 30)
        self.assertEqual(txs[1].batch, b2)
        self.assertEqual(txs[1].quantity, 15)

    def test_record_usage_rejects_insufficient_stock(self):
        b1 = Batch.objects.create(
            medicine=self.medicine,
            batch_number="AZI-ONLY",
            expiry_date=self.today + timedelta(days=30),
            quantity=20,
            cost_price=Decimal("15.00"),
            supplier=self.supplier
        )

        # Attempt to deduct 50 when only 20 is available
        post_data = {
            'medicine_id': str(self.medicine.id),
            'quantity': '50',
            'reason': 'Over-deduction attempt'
        }
        response = self.client.post(reverse('inventory:record_usage'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Insufficient active stock")

        # Stock should remain unchanged
        b1.refresh_from_db()
        self.assertEqual(b1.quantity, 20)
        self.assertFalse(StockTransaction.objects.filter(batch=b1).exists())

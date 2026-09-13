from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from inventory.models import Medicine, Batch, StockTransaction
from suppliers.models import Supplier
from dashboard.services import get_reorder_recommendations, get_wastage_analytics


class ReorderRecommendationServiceTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="PharmaCore Supply")
        today = timezone.now().date()
        now = timezone.now()

        # Medicine 1: High Consumption -> Projected days < 7 -> REORDER NOW
        # Active stock: 50 units. Consumption: 300 units in last 30 days => avg 10/day => 5 days left.
        self.med_urgent = Medicine.objects.create(
            name="Amoxicillin 500mg",
            category="Antibiotics",
            unit="capsules"
        )
        self.batch_urgent = Batch.objects.create(
            medicine=self.med_urgent,
            batch_number="AMX-01",
            expiry_date=today + timedelta(days=90),
            quantity=50,
            cost_price=Decimal("10.00"),
            supplier=self.supplier
        )
        StockTransaction.objects.create(
            batch=self.batch_urgent,
            transaction_type=StockTransaction.TransactionType.OUT,
            quantity=300,
            timestamp=now - timedelta(days=5),
            reason="Hospital dispensing"
        )

        # Medicine 2: Moderate Consumption -> Projected days between 7 and 14 -> REORDER SOON
        # Active stock: 100 units. Consumption: 300 units in 30 days => avg 10/day => 10 days left.
        self.med_soon = Medicine.objects.create(
            name="Paracetamol 650mg",
            category="Analgesics",
            unit="tablets"
        )
        self.batch_soon = Batch.objects.create(
            medicine=self.med_soon,
            batch_number="PARA-01",
            expiry_date=today + timedelta(days=120),
            quantity=100,
            cost_price=Decimal("2.50"),
            supplier=self.supplier
        )
        StockTransaction.objects.create(
            batch=self.batch_soon,
            transaction_type=StockTransaction.TransactionType.OUT,
            quantity=300,
            timestamp=now - timedelta(days=10),
            reason="OPD dispensing"
        )

        # Medicine 3: Safe Stock -> Projected days >= 14 -> OK
        # Active stock: 1000 units. Consumption: 300 units in 30 days => avg 10/day => 100 days left.
        self.med_ok = Medicine.objects.create(
            name="Atorvastatin 20mg",
            category="Cardiovascular",
            unit="tablets"
        )
        self.batch_ok = Batch.objects.create(
            medicine=self.med_ok,
            batch_number="ATOR-01",
            expiry_date=today + timedelta(days=365),
            quantity=1000,
            cost_price=Decimal("15.00"),
            supplier=self.supplier
        )
        StockTransaction.objects.create(
            batch=self.batch_ok,
            transaction_type=StockTransaction.TransactionType.OUT,
            quantity=300,
            timestamp=now - timedelta(days=12),
            reason="Prescriptions"
        )

        # Medicine 4: Zero Consumption Edge Case -> INSUFFICIENT DATA
        self.med_zero = Medicine.objects.create(
            name="Rare Orphan Drug",
            category="Specialty",
            unit="vials"
        )
        self.batch_zero = Batch.objects.create(
            medicine=self.med_zero,
            batch_number="ROD-01",
            expiry_date=today + timedelta(days=200),
            quantity=50,
            cost_price=Decimal("150.00"),
            supplier=self.supplier
        )
        # No OUT StockTransactions

        # Medicine 5: Expired Batch Exclusion Test
        # Batch is expired 10 days ago with 40 units; Active batch has 0 units.
        self.med_expired = Medicine.objects.create(
            name="Expired Insulin",
            category="Endocrine",
            unit="vials"
        )
        self.batch_expired = Batch.objects.create(
            medicine=self.med_expired,
            batch_number="INS-EXP",
            expiry_date=today - timedelta(days=10),
            quantity=40,
            cost_price=Decimal("25.00"),
            supplier=self.supplier
        )

    def test_reorder_recommendations_normal_and_edge_cases(self):
        recs = get_reorder_recommendations(consumption_window_days=30)
        recs_dict = {r['medicine_name']: r for r in recs}

        # 1. Urgent reorder check (<7 days)
        amx = recs_dict['Amoxicillin 500mg']
        self.assertEqual(amx['current_stock'], 50)
        self.assertEqual(amx['avg_daily_consumption'], 10.0)
        self.assertEqual(amx['projected_days_remaining'], 5.0)
        self.assertEqual(amx['status'], "REORDER NOW")

        # 2. Reorder soon check (7-14 days)
        para = recs_dict['Paracetamol 650mg']
        self.assertEqual(para['current_stock'], 100)
        self.assertEqual(para['avg_daily_consumption'], 10.0)
        self.assertEqual(para['projected_days_remaining'], 10.0)
        self.assertEqual(para['status'], "REORDER SOON")

        # 3. OK stock check (>=14 days)
        ator = recs_dict['Atorvastatin 20mg']
        self.assertEqual(ator['current_stock'], 1000)
        self.assertEqual(ator['projected_days_remaining'], 100.0)
        self.assertEqual(ator['status'], "OK")

        # 4. Zero consumption edge case
        rare = recs_dict['Rare Orphan Drug']
        self.assertEqual(rare['current_stock'], 50)
        self.assertEqual(rare['avg_daily_consumption'], 0.0)
        self.assertIsNone(rare['projected_days_remaining'])
        self.assertEqual(rare['status'], "INSUFFICIENT DATA")

        # 5. Expired stock exclusion check
        ins = recs_dict['Expired Insulin']
        self.assertEqual(ins['current_stock'], 0)  # Expired batch excluded from active stock
        self.assertEqual(ins['status'], "REORDER NOW")

    def test_custom_consumption_window(self):
        # When evaluating over a 15-day window, daily consumption doubles
        recs = get_reorder_recommendations(consumption_window_days=15)
        recs_dict = {r['medicine_name']: r for r in recs}
        amx = recs_dict['Amoxicillin 500mg']
        self.assertEqual(amx['avg_daily_consumption'], 20.0)  # 300 / 15
        self.assertEqual(amx['projected_days_remaining'], 2.5)  # 50 / 20

    def test_wastage_analytics(self):
        wastage = get_wastage_analytics()
        self.assertEqual(wastage['total_expired_units'], 40)
        self.assertEqual(wastage['total_expired_batches'], 1)
        self.assertEqual(wastage['total_estimated_loss'], 1000.0)  # 40 * 25.00
        self.assertEqual(len(wastage['by_medicine']), 1)
        self.assertEqual(wastage['by_medicine'][0]['medicine_name'], "Expired Insulin")


class DashboardViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.supplier = Supplier.objects.create(name="HealthCare Supply")
        self.medicine = Medicine.objects.create(name="Ibuprofen 400mg", category="Anti-inflammatory")
        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number="IBU-001",
            expiry_date=date.today() + timedelta(days=60),
            quantity=500,
            cost_price=Decimal("8.00"),
            supplier=self.supplier
        )
        StockTransaction.objects.create(
            batch=self.batch,
            transaction_type=StockTransaction.TransactionType.IN,
            quantity=500,
            reason="Direct intake from supplier"
        )
        StockTransaction.objects.create(
            batch=self.batch,
            transaction_type=StockTransaction.TransactionType.OUT,
            quantity=50,
            reason="Customer dispensing"
        )

    def test_dashboard_api_returns_reorder_and_wastage(self):
        url = reverse('dashboard:stock_summary_api')
        response = self.client.get(url, {'window': 30})
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('reorder_recommendations', data)
        self.assertIn('wastage', data)
        self.assertIn('timeline', data)
        self.assertIn('net_stock_level', data['timeline'][0])
        self.assertEqual(data['consumption_window_days'], 30)

    def test_dashboard_index_renders_template(self):
        url = reverse('dashboard:index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/index.html')

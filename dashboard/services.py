from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from inventory.models import Medicine, Batch, StockTransaction


def get_reorder_recommendations(consumption_window_days=30):
    """
    Computes stock consumption velocity and projected days of inventory remaining
    for every registered Medicine.

    Args:
        consumption_window_days (int): Period in days over which OUT transactions are evaluated.

    Returns:
        list[dict]: [
            {
                'medicine_id': int,
                'medicine_name': str,
                'category': str,
                'unit': str,
                'current_stock': int,
                'total_consumption': int,
                'avg_daily_consumption': float,
                'projected_days_remaining': float or None,
                'status': str ('REORDER NOW' | 'REORDER SOON' | 'OK' | 'INSUFFICIENT DATA')
            },
            ...
        ]
    """
    if consumption_window_days <= 0:
        consumption_window_days = 30

    today = timezone.now().date()
    cutoff_datetime = timezone.now() - timedelta(days=consumption_window_days)

    medicines = Medicine.objects.all().order_by('name')
    recommendations = []

    for medicine in medicines:
        # 1. Total OUT transactions within consumption window for this medicine
        total_out = StockTransaction.objects.filter(
            batch__medicine=medicine,
            transaction_type=StockTransaction.TransactionType.OUT,
            timestamp__gte=cutoff_datetime
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # 2. Average daily consumption
        avg_daily_consumption = round(total_out / consumption_window_days, 2)

        # 3. Current active stock (quantity > 0 and batch not expired)
        active_stock = Batch.objects.filter(
            medicine=medicine,
            quantity__gt=0,
            expiry_date__gte=today
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # 4. Projected days remaining (handle zero consumption edge case gracefully)
        if avg_daily_consumption > 0:
            projected_days = round(active_stock / avg_daily_consumption, 1)
            if projected_days < 7:
                status = "REORDER NOW"
            elif projected_days < 14:
                status = "REORDER SOON"
            else:
                status = "OK"
        else:
            projected_days = None
            # If there's 0 active stock and 0 consumption, it needs attention, else insufficient data
            if active_stock == 0:
                status = "REORDER NOW"
            else:
                status = "INSUFFICIENT DATA"

        recommendations.append({
            'medicine_id': medicine.id,
            'medicine_name': medicine.name,
            'category': medicine.category or 'General',
            'unit': medicine.unit,
            'current_stock': active_stock,
            'total_consumption': total_out,
            'avg_daily_consumption': avg_daily_consumption,
            'projected_days_remaining': projected_days,
            'status': status
        })

    # Sort so urgent reorders appear first
    status_priority = {'REORDER NOW': 0, 'REORDER SOON': 1, 'INSUFFICIENT DATA': 2, 'OK': 3}
    recommendations.sort(key=lambda x: (status_priority.get(x['status'], 4), x['projected_days_remaining'] if x['projected_days_remaining'] is not None else 999999))

    return recommendations


def get_wastage_analytics():
    """
    Computes stock wastage: batches where expiry_date has passed (expiry_date < today)
    and quantity > 0 (unused stock that expired).

    Returns:
        dict: {
            'total_expired_units': int,
            'total_expired_batches': int,
            'total_estimated_loss': float,
            'by_medicine': list[dict],
            'by_month': list[dict]
        }
    """
    today = timezone.now().date()

    expired_batches = Batch.objects.filter(
        expiry_date__lt=today,
        quantity__gt=0
    ).select_related('medicine')

    total_expired_units = 0
    total_estimated_loss = 0.0
    medicine_wastage_map = {}
    month_wastage_map = {}

    for batch in expired_batches:
        qty = batch.quantity
        loss = float(batch.cost_price * qty)
        total_expired_units += qty
        total_estimated_loss += loss

        # Group by medicine
        med_name = batch.medicine.name
        if med_name not in medicine_wastage_map:
            medicine_wastage_map[med_name] = {
                'medicine_name': med_name,
                'expired_units': 0,
                'batch_count': 0,
                'estimated_loss': 0.0
            }
        medicine_wastage_map[med_name]['expired_units'] += qty
        medicine_wastage_map[med_name]['batch_count'] += 1
        medicine_wastage_map[med_name]['estimated_loss'] = round(
            medicine_wastage_map[med_name]['estimated_loss'] + loss, 2
        )

        # Group by month of expiry
        month_str = batch.expiry_date.strftime('%Y-%m')
        if month_str not in month_wastage_map:
            month_wastage_map[month_str] = {
                'month': month_str,
                'expired_units': 0,
                'estimated_loss': 0.0
            }
        month_wastage_map[month_str]['expired_units'] += qty
        month_wastage_map[month_str]['estimated_loss'] = round(
            month_wastage_map[month_str]['estimated_loss'] + loss, 2
        )

    by_medicine = sorted(medicine_wastage_map.values(), key=lambda x: x['expired_units'], reverse=True)
    by_month = sorted(month_wastage_map.values(), key=lambda x: x['month'])

    return {
        'total_expired_units': total_expired_units,
        'total_expired_batches': expired_batches.count(),
        'total_estimated_loss': round(total_estimated_loss, 2),
        'by_medicine': by_medicine,
        'by_month': by_month
    }

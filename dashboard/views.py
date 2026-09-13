from django.http import JsonResponse
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render

from inventory.models import StockTransaction, Batch, Medicine
from .services import get_reorder_recommendations, get_wastage_analytics


def stock_summary_api(request):
    """
    API view that returns comprehensive inventory telemetry:
    - Overall metrics (medicines, batches, total stock, in/out)
    - Time-series stock movements (daily IN, OUT, and running cumulative stock)
    - Reorder recommendations based on dynamic consumption window
    - Stock wastage analytics (expired unused stock grouped by medicine & month)
    - Recent transactions list
    """
    # Parse configurable consumption window from query params (default 30 days)
    try:
        consumption_window_days = int(request.GET.get('window', 30))
    except (ValueError, TypeError):
        consumption_window_days = 30

    # 1. Total aggregate IN vs OUT
    total_in = StockTransaction.objects.filter(
        transaction_type=StockTransaction.TransactionType.IN
    ).aggregate(total=Sum('quantity'))['total'] or 0

    total_out = StockTransaction.objects.filter(
        transaction_type=StockTransaction.TransactionType.OUT
    ).aggregate(total=Sum('quantity'))['total'] or 0

    # 2. Total active batch stock
    total_current_stock = Batch.objects.aggregate(total=Sum('quantity'))['total'] or 0
    total_medicines = Medicine.objects.count()
    total_batches = Batch.objects.count()

    # 3. Time-series aggregation (daily IN vs OUT with cumulative level)
    daily_aggregates = (
        StockTransaction.objects.annotate(date=TruncDate('timestamp'))
        .values('date', 'transaction_type')
        .annotate(total_quantity=Sum('quantity'))
        .order_by('date')
    )

    timeline_data = {}
    for entry in daily_aggregates:
        date_str = entry['date'].strftime('%Y-%m-%d')
        if date_str not in timeline_data:
            timeline_data[date_str] = {'date': date_str, 'in': 0, 'out': 0}
        if entry['transaction_type'] == 'IN':
            timeline_data[date_str]['in'] = entry['total_quantity']
        elif entry['transaction_type'] == 'OUT':
            timeline_data[date_str]['out'] = entry['total_quantity']

    sorted_timeline = sorted(timeline_data.values(), key=lambda x: x['date'])

    # Compute running net stock balance across time
    running_balance = 0
    for day in sorted_timeline:
        running_balance += (day['in'] - day['out'])
        day['net_stock_level'] = running_balance

    # 4. Reorder Recommendations from service
    reorder_recommendations = get_reorder_recommendations(consumption_window_days=consumption_window_days)

    # 5. Wastage Analytics from service
    wastage_data = get_wastage_analytics()

    # 6. Recent transactions list (last 10)
    recent_transactions = [
        {
            'id': tx.id,
            'medicine': tx.batch.medicine.name,
            'batch_number': tx.batch.batch_number,
            'type': tx.transaction_type,
            'quantity': tx.quantity,
            'timestamp': tx.timestamp.strftime('%Y-%m-%d %H:%M'),
            'reason': tx.reason or ''
        }
        for tx in StockTransaction.objects.select_related('batch__medicine')[:10]
    ]

    response_data = {
        'status': 'success',
        'metrics': {
            'total_medicines': total_medicines,
            'total_batches': total_batches,
            'total_current_stock': total_current_stock,
            'total_in': total_in,
            'total_out': total_out,
            'net_flow': total_in - total_out,
            'reorder_urgent_count': sum(1 for r in reorder_recommendations if r['status'] == 'REORDER NOW'),
            'reorder_soon_count': sum(1 for r in reorder_recommendations if r['status'] == 'REORDER SOON'),
            'total_expired_loss': wastage_data['total_estimated_loss']
        },
        'timeline': sorted_timeline,
        'reorder_recommendations': reorder_recommendations,
        'wastage': wastage_data,
        'recent_transactions': recent_transactions,
        'consumption_window_days': consumption_window_days
    }

    return JsonResponse(response_data)


def dashboard_index(request):
    """
    Renders the Chart.js MediTrace interactive dashboard.
    """
    return render(request, 'dashboard/index.html')

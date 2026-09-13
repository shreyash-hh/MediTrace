from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Min
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Medicine, Batch, StockTransaction
from suppliers.models import Supplier


def stock_overview(request):
    """
    Displays the stock overview table for all registered medicines:
    - Current active unexpired stock
    - Number of active batches
    - Nearest expiry date & countdown
    - Real-time stock status flag
    """
    today = timezone.now().date()
    cutoff_expiring = today + timedelta(days=30)

    medicines = Medicine.objects.all().order_by('name')
    medicine_list = []

    total_active_units = 0
    expiring_soon_count = 0
    low_stock_count = 0

    for med in medicines:
        active_batches = Batch.objects.filter(
            medicine=med,
            quantity__gt=0,
            expiry_date__gte=today
        ).order_by('expiry_date')

        stock = active_batches.aggregate(total=Sum('quantity'))['total'] or 0
        total_active_units += stock
        batch_count = active_batches.count()
        nearest_batch = active_batches.first()

        nearest_expiry = nearest_batch.expiry_date if nearest_batch else None
        days_until_expiry = (nearest_expiry - today).days if nearest_expiry else None

        # Determine status
        if stock == 0:
            status = "Out of Stock"
            low_stock_count += 1
        elif nearest_expiry and nearest_expiry <= cutoff_expiring:
            status = "Expiring Soon"
            expiring_soon_count += 1
        elif stock < 50:
            status = "Low Stock"
            low_stock_count += 1
        else:
            status = "OK"

        medicine_list.append({
            'medicine': med,
            'total_stock': stock,
            'active_batches_count': batch_count,
            'nearest_expiry': nearest_expiry,
            'days_until_expiry': days_until_expiry,
            'status': status
        })

    context = {
        'medicine_list': medicine_list,
        'total_medicines': len(medicines),
        'total_active_stock': total_active_units,
        'expiring_soon_count': expiring_soon_count,
        'low_stock_count': low_stock_count,
    }
    return render(request, 'inventory/stock_overview.html', context)


def add_stock(request):
    """
    Form view to add a new Batch delivery for an existing or newly registered medicine.
    Creates a Batch record AND a corresponding StockTransaction (IN).
    Strictly validates that expiry_date is in the future.
    """
    today = timezone.now().date()
    medicines = Medicine.objects.all().order_by('name')
    suppliers = Supplier.objects.all().order_by('name')

    if request.method == 'GET':
        selected_medicine_id = None
        try:
            if 'medicine_id' in request.GET:
                selected_medicine_id = int(request.GET.get('medicine_id'))
        except (ValueError, TypeError):
            pass

        return render(request, 'inventory/add_stock.html', {
            'medicines': medicines,
            'suppliers': suppliers,
            'selected_medicine_id': selected_medicine_id,
            'form_data': {}
        })

    # POST Handling with server-side validation
    is_new_medicine = request.POST.get('is_new_medicine') == 'on'
    medicine_id = request.POST.get('medicine_id', '').strip()
    new_name = request.POST.get('new_name', '').strip()
    new_category = request.POST.get('new_category', '').strip()
    new_unit = request.POST.get('new_unit', 'tablets').strip()
    new_manufacturer = request.POST.get('new_manufacturer', '').strip()

    batch_number = request.POST.get('batch_number', '').strip()
    expiry_date_str = request.POST.get('expiry_date', '').strip()
    quantity_str = request.POST.get('quantity', '').strip()
    cost_price_str = request.POST.get('cost_price', '').strip()
    supplier_id = request.POST.get('supplier_id', '').strip()
    reason = request.POST.get('reason', 'Initial supplier delivery intake').strip()

    form_data = request.POST.dict()

    # 1. Validate Medicine
    target_medicine = None
    if is_new_medicine:
        if not new_name:
            messages.error(request, "Medicine Name is required when creating a new medicine.")
            return render(request, 'inventory/add_stock.html', {
                'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
            })
    else:
        if not medicine_id:
            messages.error(request, "Please select an existing medicine or check 'Register New Medicine'.")
            return render(request, 'inventory/add_stock.html', {
                'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
            })
        try:
            target_medicine = Medicine.objects.get(id=int(medicine_id))
        except (Medicine.DoesNotExist, ValueError):
            messages.error(request, "Selected medicine does not exist.")
            return render(request, 'inventory/add_stock.html', {
                'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
            })

    # 2. Validate Batch Number
    if not batch_number:
        messages.error(request, "Batch number is required.")
        return render(request, 'inventory/add_stock.html', {
            'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
        })

    # 3. Validate Expiry Date (Must be future)
    if not expiry_date_str:
        messages.error(request, "Expiry date is required.")
        return render(request, 'inventory/add_stock.html', {
            'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
        })
    try:
        parsed_expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Invalid date format. Use YYYY-MM-DD.")
        return render(request, 'inventory/add_stock.html', {
            'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
        })

    if parsed_expiry_date <= today:
        messages.error(request, f"Expiry date must be in the future (after {today}). Received {parsed_expiry_date}.")
        return render(request, 'inventory/add_stock.html', {
            'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
        })

    # 4. Validate Quantity
    try:
        quantity = int(quantity_str)
        if quantity <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        messages.error(request, "Quantity must be a positive whole number greater than 0.")
        return render(request, 'inventory/add_stock.html', {
            'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
        })

    # 5. Validate Cost Price
    try:
        cost_price = Decimal(cost_price_str)
        if cost_price < 0:
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        messages.error(request, "Cost price must be a valid non-negative number.")
        return render(request, 'inventory/add_stock.html', {
            'medicines': medicines, 'suppliers': suppliers, 'form_data': form_data
        })

    # 6. Validate Supplier (Optional)
    supplier = None
    if supplier_id:
        try:
            supplier = Supplier.objects.get(id=int(supplier_id))
        except (Supplier.DoesNotExist, ValueError):
            pass

    # 7. Atomic Database Execution
    with transaction.atomic():
        if is_new_medicine:
            target_medicine = Medicine.objects.create(
                name=new_name,
                category=new_category,
                unit=new_unit or 'tablets',
                manufacturer=new_manufacturer
            )

        batch = Batch.objects.create(
            medicine=target_medicine,
            batch_number=batch_number,
            expiry_date=parsed_expiry_date,
            quantity=quantity,
            cost_price=cost_price,
            supplier=supplier
        )

        StockTransaction.objects.create(
            batch=batch,
            transaction_type=StockTransaction.TransactionType.IN,
            quantity=quantity,
            timestamp=timezone.now(),
            reason=reason or "Stock Intake"
        )

    messages.success(
        request,
        f"Successfully added Batch #{batch_number} with {quantity} {target_medicine.unit} of '{target_medicine.name}' (Exp: {parsed_expiry_date})."
    )
    return redirect('inventory:stock_overview')


def record_usage(request):
    """
    Form view to deduct medicine stock according to the FEFO (First Expiry First Out) protocol.
    Deducts quantity from earliest expiring active batches first.
    Strictly forbids negative stock.
    Creates separate StockTransaction (OUT) records for each touched batch.
    """
    today = timezone.now().date()
    medicines = Medicine.objects.all().order_by('name')

    # Build medicine stock summary list for dropdown selection
    medicine_stock_list = []
    for med in medicines:
        active_batches = Batch.objects.filter(
            medicine=med,
            quantity__gt=0,
            expiry_date__gte=today
        )
        total_stock = active_batches.aggregate(total=Sum('quantity'))['total'] or 0
        medicine_stock_list.append({
            'medicine': med,
            'total_stock': total_stock,
            'active_batches_count': active_batches.count()
        })

    if request.method == 'GET':
        selected_medicine_id = None
        try:
            if 'medicine_id' in request.GET:
                selected_medicine_id = int(request.GET.get('medicine_id'))
        except (ValueError, TypeError):
            pass

        return render(request, 'inventory/record_usage.html', {
            'medicine_stock_list': medicine_stock_list,
            'selected_medicine_id': selected_medicine_id,
            'form_data': {}
        })

    # POST Handling
    medicine_id_str = request.POST.get('medicine_id', '').strip()
    quantity_str = request.POST.get('quantity', '').strip()
    reason = request.POST.get('reason', 'Prescription dispensing').strip()
    form_data = request.POST.dict()

    # 1. Validate Medicine
    if not medicine_id_str:
        messages.error(request, "Please select a medicine.")
        return render(request, 'inventory/record_usage.html', {
            'medicine_stock_list': medicine_stock_list, 'form_data': form_data
        })

    try:
        medicine = Medicine.objects.get(id=int(medicine_id_str))
    except (Medicine.DoesNotExist, ValueError):
        messages.error(request, "Selected medicine does not exist.")
        return render(request, 'inventory/record_usage.html', {
            'medicine_stock_list': medicine_stock_list, 'form_data': form_data
        })

    # 2. Validate Quantity
    try:
        quantity_to_deduct = int(quantity_str)
        if quantity_to_deduct <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        messages.error(request, "Quantity to deduct must be a positive integer greater than 0.")
        return render(request, 'inventory/record_usage.html', {
            'medicine_stock_list': medicine_stock_list, 'form_data': form_data
        })

    # 3. Retrieve Active Batches ordered by FEFO (earliest expiry first)
    active_batches = list(
        Batch.objects.filter(
            medicine=medicine,
            quantity__gt=0,
            expiry_date__gte=today
        ).order_by('expiry_date', 'id')
    )

    total_available_stock = sum(b.quantity for b in active_batches)

    # 4. Check Stock Availability (No Negative Stock Allowed)
    if quantity_to_deduct > total_available_stock:
        messages.error(
            request,
            f"Insufficient active stock for '{medicine.name}'! "
            f"Requested: {quantity_to_deduct} {medicine.unit}, "
            f"Total Available: {total_available_stock} {medicine.unit}. "
            f"Negative stock is not permitted."
        )
        return render(request, 'inventory/record_usage.html', {
            'medicine_stock_list': medicine_stock_list, 'form_data': form_data
        })

    # 5. Execute FEFO Deduction in Atomic Transaction
    deducted_batches_summary = []
    remaining = quantity_to_deduct
    now = timezone.now()

    with transaction.atomic():
        for batch in active_batches:
            if remaining <= 0:
                break

            deduct_qty = min(batch.quantity, remaining)
            batch.quantity -= deduct_qty
            batch.save(update_fields=['quantity'])

            # Log OUT transaction for this batch
            StockTransaction.objects.create(
                batch=batch,
                transaction_type=StockTransaction.TransactionType.OUT,
                quantity=deduct_qty,
                timestamp=now,
                reason=reason or "Prescription dispensing"
            )

            deducted_batches_summary.append(
                f"{deduct_qty} from Batch #{batch.batch_number} (Exp: {batch.expiry_date})"
            )
            remaining -= deduct_qty

    remaining_stock_after = total_available_stock - quantity_to_deduct
    messages.success(
        request,
        f"Successfully dispensed {quantity_to_deduct} {medicine.unit} of '{medicine.name}' via FEFO: "
        f"{', '.join(deducted_batches_summary)}. Remaining active stock: {remaining_stock_after} {medicine.unit}."
    )
    return redirect('inventory:stock_overview')

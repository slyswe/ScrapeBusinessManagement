from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q
import logging
from .models import Store, Stock, StockEntry, Expense, ScrapType, PriceChangeLog, Alert, SCRAP_TYPES
from .forms import StoreForm, StockEntryForm, ExpenseForm, StockEntryEditForm
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import timedelta
from django.conf import settings  # Import settings for PHP dashboard URL

# Set up logging
logger = logging.getLogger(__name__)

# Initialize ScrapType objects if they don't exist
def initialize_scrap_types():
    for name, _ in SCRAP_TYPES:
        ScrapType.objects.get_or_create(name=name, defaults={'selling_price': 0.00})

@login_required
def dashboard(request):
    initialize_scrap_types()
    stores = Store.objects.filter(owner=request.user)
    logger.debug(f"Dashboard stores for user {request.user.username}: {list(stores)}")
    store_summaries = []
    alerts = []
    current_date = timezone.now()

    if not stores:
        logger.warning(f"No stores found for user {request.user.username}")
        return redirect('add_store')

    for store in stores:
        current_stock = Stock.objects.filter(store=store, is_active=True).first()
        if not current_stock:
            try:
                current_stock = Stock.objects.create(store=store)
                logger.debug(f"Created stock for store {store.name}: {current_stock}")
            except Exception as e:
                logger.error(f"Failed to create stock for store {store.name}: {e}")
                continue
        entries = current_stock.entries.all().order_by('date')
        expenses = store.expenses.filter(date__lte=current_date.date()).all()
        total_weight = sum(sum(float(weight) for weight in entry.weights.values()) for entry in entries) or 0
        total_revenue = sum(float(entry.calculate_revenue()) for entry in entries) or 0
        total_expenses = sum(float(expense.amount) for expense in expenses) + sum(float(entry.amount_used) for entry in entries) or 0
        total_profit = total_revenue - total_expenses

        if (current_date - current_stock.created_date).days > 30:
            Alert.objects.get_or_create(
                alert_type='OVERDUE_STOCK',
                store=store,
                message=f"Stock {current_stock.stock_number} in {store.name} is overdue for clearing.",
                defaults={'created_at': current_date}
            )

        previous_stock = Stock.objects.filter(store=store, is_active=False).order_by('-created_date').first()
        if previous_stock:
            prev_entries = previous_stock.entries.all()
            prev_expenses = store.expenses.filter(date__lte=previous_stock.created_date).all()
            prev_revenue = sum(float(entry.calculate_revenue()) for entry in prev_entries) or 0
            prev_total_expenses = sum(float(expense.amount) for expense in prev_expenses) + sum(float(entry.amount_used) for entry in prev_entries) or 0
            prev_profit = prev_revenue - prev_total_expenses
            if prev_profit != 0 and abs((total_profit - prev_profit) / prev_profit) > 0.1:
                Alert.objects.get_or_create(
                    alert_type='PROFIT_LOSS',
                    store=store,
                    message=f"Significant profit/loss change in {store.name}: {total_profit} vs {prev_profit}.",
                    defaults={'created_at': current_date}
                )

        store_summaries.append({
            'store': store,
            'total_weight': total_weight,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'total_profit': total_profit,
        })

    alerts = Alert.objects.filter(store__owner=request.user, is_read=False)

    total_revenue_all = sum(float(s['total_revenue']) for s in store_summaries)
    total_expenses_all = sum(float(s['total_expenses']) for s in store_summaries)
    net_profit_all = total_revenue_all - total_expenses_all

    context = {
        'store_summaries': store_summaries,
        'net_profit_all': net_profit_all,
        'total_revenue_all': total_revenue_all,
        'total_expenses_all': total_expenses_all,
        'alerts': alerts,
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def mark_alert_read(request, alert_id):
    alert = get_object_or_404(Alert, id=alert_id, store__owner=request.user)
    alert.is_read = True
    alert.save()
    return redirect('dashboard')

@login_required
def store_detail(request, store_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    current_stock = Stock.objects.filter(store=store, is_active=True).first()
    if not current_stock:
        current_stock = Stock.objects.create(store=store)
    logger.debug(f"Store detail for store {store_id}: {store}, stock: {current_stock}")

    entries = current_stock.entries.all().order_by('date')
    expenses = store.expenses.filter(date__lte=timezone.now().date()).all()

    total_weight = sum(sum(float(weight) for weight in entry.weights.values()) for entry in entries) or 0
    total_revenue = sum(float(entry.calculate_revenue()) for entry in entries) or 0
    total_expenses = sum(float(expense.amount) for expense in expenses) + sum(float(entry.amount_used) for entry in entries) or 0
    total_profit = total_revenue - total_expenses

    context = {
        'store': store,
        'current_stock': current_stock,
        'entries': entries,
        'total_weight': total_weight,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
        'scrap_types': SCRAP_TYPES,
        'expenses': expenses,
        'php_dashboard_url': getattr(settings, 'PHP_DASHBOARD_URL', None),  # Pass PHP dashboard URL
    }
    return render(request, 'core/store_detail.html', context)

@login_required
def financial_report(request):
    stores = Store.objects.filter(owner=request.user)
    total_revenue = 0
    total_expenses = 0
    current_date = timezone.now().date()
    previous_period_revenue = 0

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    store_id = request.GET.get('store')

    stock_filter = Q()
    if date_from:
        stock_filter &= Q(created_date__gte=date_from)
    if date_to:
        stock_filter &= Q(created_date__lte=date_to)
    if store_id:
        stock_filter &= Q(store__id=store_id)

    store_breakdown = []
    for store in stores:
        store_total_revenue = 0
        store_total_expenses = 0
        stocks = store.stocks.filter(stock_filter)
        for stock in stocks:
            entries = stock.entries.all()
            expenses = store.expenses.filter(date__lte=current_date).all()
            stock_revenue = sum(float(entry.calculate_revenue()) for entry in entries) or 0
            stock_expenses = sum(float(expense.amount) for expense in expenses) + sum(float(entry.amount_used) for entry in entries) or 0
            store_total_revenue += stock_revenue
            store_total_expenses += stock_expenses
            store_breakdown.append({
                'store': store,
                'stock': stock,
                'revenue': stock_revenue,
                'expenses': stock_expenses,
                'profit': stock_revenue - stock_expenses,
            })
        total_revenue += store_total_revenue
        total_expenses += store_total_expenses

        prev_stocks = store.stocks.filter(created_date__lt=current_date - timedelta(days=30))
        for stock in prev_stocks:
            entries = stock.entries.all()
            previous_period_revenue += sum(float(entry.calculate_revenue()) for entry in entries) or 0

    net_profit = total_revenue - total_expenses
    revenue_growth = ((total_revenue - previous_period_revenue) / previous_period_revenue * 100) if previous_period_revenue else 0

    context = {
        'stores': stores,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'revenue_growth': revenue_growth,
        'date_from': date_from,
        'date_to': date_to,
        'selected_store': store_id,
        'store_breakdown': store_breakdown,
    }
    return render(request, 'core/financial_report.html', context)

@login_required
def export_financial_report(request):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, "Financial Report - Scrape Business Management System")
    p.drawString(100, 730, f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y = 700

    stores = Store.objects.filter(owner=request.user)
    total_revenue = 0
    total_expenses = 0
    current_date = timezone.now().date()

    for store in stores:
        for stock in store.stocks.all():
            entries = stock.entries.all()
            expenses = store.expenses.filter(date__lte=current_date).all()
            stock_revenue = sum(float(entry.calculate_revenue()) for entry in entries) or 0
            stock_expenses = sum(float(expense.amount) for expense in expenses) + sum(float(entry.amount_used) for entry in entries) or 0
            total_revenue += stock_revenue
            total_expenses += stock_expenses
            p.drawString(100, y, f"Store: {store.name}, Stock: {stock.stock_number}")
            p.drawString(100, y-20, f"Revenue: KSH {stock_revenue:.2f}, Expenses: KSH {stock_expenses:.2f}")
            y -= 40

    p.drawString(100, y, f"Total Revenue: KSH {total_revenue:.2f}")
    p.drawString(100, y-20, f"Total Expenses: KSH {total_expenses:.2f}")
    p.drawString(100, y-40, f"Net Profit: KSH {(total_revenue - total_expenses):.2f}")
    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="financial_report.pdf"'
    return response

@login_required
def update_selling_price(request):
    initialize_scrap_types()
    if request.method == 'POST':
        scrap_type_id = request.POST['scrap_type']
        new_price = request.POST['selling_price']
        scrap_type = ScrapType.objects.get(id=scrap_type_id)
        old_price = scrap_type.selling_price
        scrap_type.selling_price = new_price
        scrap_type.save()
        PriceChangeLog.objects.create(
            scrap_type=scrap_type,
            old_price=old_price,
            new_price=new_price,
            changed_by=request.user
        )
        return redirect('update_selling_price')
    scrap_types = ScrapType.objects.all()
    logger.debug(f"Scrap types for update: {list(scrap_types)}")
    context = {'scrap_types': scrap_types}
    return render(request, 'core/update_selling_price.html', context)

@login_required
def clear_stock(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id, store__owner=request.user)
    if request.method == 'POST':
        stock.is_active = False
        stock.save()
        Stock.objects.create(store=stock.store)
        return redirect('dashboard')
    return render(request, 'core/clear_stock.html', {'stock': stock})

@login_required
def add_store(request):
    if request.method == 'POST':
        form = StoreForm(request.POST)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user
            store.save()
            logger.debug(f"Added store: {store} for user {request.user.username}")
            return redirect('dashboard')
    else:
        form = StoreForm()
    return render(request, 'core/add_store.html', {'form': form})

@login_required
def add_entry(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id, store__owner=request.user)
    if request.method == 'POST':
        form = StockEntryForm(request.POST)
        if form.is_valid():
            entry_date = form.cleaned_data['date']
            if StockEntry.objects.filter(stock=stock, date=entry_date).exists():
                form.add_error('date', f"An entry for stock {stock.stock_number} on {entry_date} already exists.")
                logger.error(f"Duplicate entry for stock {stock.stock_number} on {entry_date}")
            elif not all([form.cleaned_data['entered_amount_given'], form.cleaned_data['balance']]):
                form.add_error(None, "All fields (Amount Given, Balance) are required.")
                logger.error("Missing required fields in StockEntryForm")
            else:
                entry = form.save(commit=False)
                entry.stock = stock
                weights = {scrap_type: float(request.POST.get(scrap_type, 0)) for scrap_type, _ in SCRAP_TYPES}
                entry.weights = weights
                entry.entered_amount_given = form.cleaned_data['entered_amount_given']
                entry.balance = form.cleaned_data['balance']
                entry.save()
                logger.debug(f"Successfully added entry for stock {stock.stock_number} on {entry_date}")
                return redirect('store_detail', store_id=stock.store.id)
        else:
            logger.error(f"Form validation failed: {form.errors}")
    else:
        form = StockEntryForm()
    return render(request, 'core/add_entry.html', {'form': form, 'stock': stock, 'scrap_types': SCRAP_TYPES})

@login_required
def edit_entry(request, entry_id):
    entry = get_object_or_404(StockEntry, id=entry_id, stock__store__owner=request.user)
    if request.method == 'POST':
        if 'delete' in request.POST:
            store_id = entry.stock.store.id
            stock = entry.stock
            deleted_date = entry.date
            entry.delete()
            subsequent_entries = StockEntry.objects.filter(stock=stock, date__gt=deleted_date).order_by('date')
            previous_entry = StockEntry.objects.filter(stock=stock, date__lt=deleted_date).order_by('-date').first()
            previous_balance = float(previous_entry.balance) if previous_entry else 0
            for sub_entry in subsequent_entries:
                sub_entry.amount_given = float(sub_entry.entered_amount_given) + previous_balance
                sub_entry.amount_used = float(sub_entry.amount_given) - float(sub_entry.balance)
                if sub_entry.amount_used < 0:
                    sub_entry.amount_used = 0
                    sub_entry.balance = float(sub_entry.amount_given)
                sub_entry.save()
                previous_balance = float(sub_entry.balance)
            return redirect('store_detail', store_id=store_id)
        form = StockEntryEditForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            stock = entry.stock
            edited_date = entry.date
            subsequent_entries = StockEntry.objects.filter(stock=stock, date__gt=edited_date).order_by('date')
            previous_balance = float(entry.balance)
            for sub_entry in subsequent_entries:
                sub_entry.amount_given = float(sub_entry.entered_amount_given) + previous_balance
                sub_entry.amount_used = float(sub_entry.amount_given) - float(sub_entry.balance)
                if sub_entry.amount_used < 0:
                    sub_entry.amount_used = 0
                    sub_entry.balance = float(sub_entry.amount_given)
                sub_entry.save()
                previous_balance = float(sub_entry.balance)
            return redirect('store_detail', store_id=entry.stock.store.id)
    else:
        form = StockEntryEditForm(instance=entry)
    context = {
        'form': form,
        'stock': entry.stock,
        'scrap_types': SCRAP_TYPES,
        'entry': entry,
    }
    return render(request, 'core/edit_entry.html', context)

@login_required
def add_expense(request, store_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.store = store
            expense.save()
            return redirect('store_detail', store_id=store.id)
    else:
        form = ExpenseForm()
    return render(request, 'core/add_expense.html', {'form': form, 'store': store})

@login_required
def edit_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id, store__owner=request.user)
    if request.method == 'POST':
        if 'delete' in request.POST:
            store_id = expense.store.id
            expense.delete()
            logger.debug(f"Deleted expense {expense.id} for store {store_id}")
            return redirect('store_detail', store_id=store_id)
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            logger.debug(f"Updated expense {expense.id} for store {expense.store.id}")
            return redirect('store_detail', store_id=expense.store.id)
        else:
            logger.error(f"Form validation failed for expense {expense.id}: {form.errors}")
    else:
        form = ExpenseForm(instance=expense)
    context = {
        'form': form,
        'expense': expense,
        'store': expense.store,
    }
    return render(request, 'core/edit_expense.html', context)
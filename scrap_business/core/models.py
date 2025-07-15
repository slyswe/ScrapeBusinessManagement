from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Constants
SCRAP_TYPES = [
    ('Heavy', 'Heavy'),
    ('Light', 'Light'),
    ('Cast', 'Cast'),
    ('Soft', 'Soft'),
    ('Hard', 'Hard'),
    ('Brass', 'Brass'),
    ('Copper', 'Copper'),
    ('Battery', 'Battery'),
    ('Radiator', 'Radiator'),
    ('Boots', 'Boots'),
    ('Yellow', 'Yellow'),
    ('Black', 'Black'),
    ('Sandals', 'Sandals'),
    ('Basins', 'Basins'),
]

class ScrapType(models.Model):
    name = models.CharField(max_length=50, choices=SCRAP_TYPES)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.name

class PriceChangeLog(models.Model):
    scrap_type = models.ForeignKey(ScrapType, on_delete=models.CASCADE)
    old_price = models.DecimalField(max_digits=10, decimal_places=2)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.scrap_type.name}: {self.old_price} -> {self.new_price}"

class Store(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Stock(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='stocks')
    stock_number = models.CharField(max_length=20, unique=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.stock_number:
            last_stock = Stock.objects.filter(store=self.store).order_by('-id').first()
            if last_stock:
                try:
                    # Try to extract the numeric part after the last hyphen
                    parts = last_stock.stock_number.split('-')
                    last_number = int(parts[-1])
                    self.stock_number = f"STK-{self.store.id}-{last_number + 1:04d}"
                except (ValueError, IndexError):
                    # Handle invalid stock_number format
                    self.stock_number = f"STK-{self.store.id}-0001"
            else:
                # No previous stock, start with 0001
                self.stock_number = f"STK-{self.store.id}-0001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.stock_number

class StockEntry(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='entries')
    date = models.DateField()
    weights = models.JSONField(default=dict)
    amount_given = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    entered_amount_given = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_used = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ['stock', 'date']

    def calculate_revenue(self):
        total = 0
        for scrap_type, weight in self.weights.items():
            price = ScrapType.objects.get(name=scrap_type).selling_price
            total += float(weight) * float(price)
        return total

    def save(self, *args, **kwargs):
        # Ensure all fields have valid values
        if self.entered_amount_given is None:
            self.entered_amount_given = 0
        if self.balance is None:
            self.balance = 0

        # Find the previous entry (if any) for this stock
        previous_entry = StockEntry.objects.filter(
            stock=self.stock,
            date__lt=self.date
        ).order_by('-date').first()

        # Calculate the new amount_given based on the previous balance
        if previous_entry:
            previous_balance = float(previous_entry.balance)
            self.amount_given = float(self.entered_amount_given) + previous_balance
        else:
            self.amount_given = float(self.entered_amount_given)

        # Calculate amount_used based on the entered balance
        self.amount_used = float(self.amount_given) - float(self.balance)

        # Ensure amount_used is not negative
        if self.amount_used < 0:
            self.amount_used = 0
            self.balance = float(self.amount_given)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Entry {self.stock.stock_number} on {self.date}"

class Expense(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.description} - {self.amount}"

class Alert(models.Model):
    ALERT_TYPES = [
        ('OVERDUE_STOCK', 'Overdue Stock'),
        ('PROFIT_LOSS', 'Profit/Loss Alert'),
    ]
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    message = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.alert_type} - {self.store.name}"
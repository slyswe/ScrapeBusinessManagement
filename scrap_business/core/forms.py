from django import forms
from .models import Store, StockEntry, Expense, SCRAP_TYPES

class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'location']

class StockEntryForm(forms.ModelForm):
    class Meta:
        model = StockEntry
        fields = ['date', 'entered_amount_given', 'balance']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['entered_amount_given'].label = "Amount Given"
        self.fields['entered_amount_given'].required = True
        self.fields['balance'].required = True

    def save(self, *args, **kwargs):
        instance = super().save(commit=False)
        # Do not call instance.save() here; let the view handle it
        return instance

class StockEntryEditForm(forms.ModelForm):
    class Meta:
        model = StockEntry
        fields = ['date', 'entered_amount_given', 'balance']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['entered_amount_given'].label = "Amount Given"
        self.fields['entered_amount_given'].required = True
        self.fields['balance'].required = True
        for scrap_type, label in SCRAP_TYPES:
            self.fields[scrap_type] = forms.FloatField(
                label=label,
                required=False,
                initial=lambda s, t=scrap_type: s.instance.weights.get(t, 0)
            )

    def save(self, *args, **kwargs):
        instance = super().save(commit=False)
        weights = {scrap_type: float(self.cleaned_data.get(scrap_type, 0)) for scrap_type, _ in SCRAP_TYPES}
        instance.weights = weights
        # Do not call instance.save() here; let the view handle it
        return instance

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['description', 'amount', 'date']
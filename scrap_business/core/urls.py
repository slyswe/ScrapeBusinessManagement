from django.urls import path
from . import views
from .views import export_entries_pdf, export_entries_csv

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('store/<int:store_id>/', views.store_detail, name='store_detail'),
    path('financial-report/', views.financial_report, name='financial_report'),
    path('export-financial-report/', views.export_financial_report, name='export_financial_report'),
    path('update-selling-price/', views.update_selling_price, name='update_selling_price'),
    path('clear-stock/<int:stock_id>/', views.clear_stock, name='clear_stock'),
    path('add-store/', views.add_store, name='add_store'),
    path('add-entry/<int:stock_id>/', views.add_entry, name='add_entry'),
    path('add-expense/<int:store_id>/', views.add_expense, name='add_expense'),
    path('mark-alert-read/<int:alert_id>/', views.mark_alert_read, name='mark_alert_read'),
    path('edit-entry/<int:entry_id>/', views.edit_entry, name='edit_entry'),
    path('expense/<int:expense_id>/edit/', views.edit_expense, name='edit_expense'),
    path('store/<int:store_id>/stock/<int:stock_id>/export-pdf/', export_entries_pdf, name='export_entries_pdf'),
    path('store/<int:store_id>/stock/<int:stock_id>/export-csv/', export_entries_csv, name='export_entries_csv'),
]

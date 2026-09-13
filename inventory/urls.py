from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.stock_overview, name='stock_overview'),
    path('add-stock/', views.add_stock, name='add_stock'),
    path('record-usage/', views.record_usage, name='record_usage'),
]

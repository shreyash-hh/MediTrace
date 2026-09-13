from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='index'),
    path('api/stock-summary/', views.stock_summary_api, name='stock_summary_api'),
]

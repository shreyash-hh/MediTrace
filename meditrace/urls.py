"""
URL configuration for meditrace project.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls')),
    path('inventory/', include('inventory.urls')),
    # Redirect root URL to inventory stock overview
    path('', lambda request: redirect('inventory:stock_overview', permanent=False)),
]

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
    # Redirect root URL to admin for easy navigation during v1 skeleton phase
    path('', lambda request: redirect('admin/', permanent=False)),
]

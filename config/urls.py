from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('kassa.urls')),
    # UI жоқ (frontend — бөлек репо): түбір API құжаттамасына бағыттайды
    path('', RedirectView.as_view(url='/api/docs/', permanent=False)),
]

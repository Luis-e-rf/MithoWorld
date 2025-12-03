from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView  # <--- IMPORTANTE: No olvides esta línea

urlpatterns = [
    # Esta es la línea que arregla ese 404 y te manda al login
    path('', RedirectView.as_view(url='admin/', permanent=False)),

    path('admin/', admin.site.urls),
    path('api/', include('criaturas.urls')),
]
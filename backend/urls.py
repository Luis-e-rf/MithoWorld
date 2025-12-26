# backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

# IMPORTACIONES NUEVAS NECESARIAS
from django.conf import settings
from django.conf.urls.static import static
from criaturas.views import home  # <--- Importamos la vista

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('criaturas.urls')),
]

# LÓGICA MÁGICA:
# Si estamos en modo Debug (Desarrollo), le decimos a Django:
# "Oye, si alguien pide una URL que empiece por MEDIA_URL (/media/),
# búscalo en la carpeta física MEDIA_ROOT y entrégaselo".
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
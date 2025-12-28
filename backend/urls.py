# backend/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.views.generic import RedirectView

# IMPORTACIONES NUEVAS NECESARIAS
from django.conf import settings
from django.conf.urls.static import static
from criaturas.views import home  # <--- Importamos la vista
from oraculo.views import arena_view

urlpatterns = [
    path('', home, name='home'),
    path('arena/', arena_view, name='arena'),
    path('admin/', admin.site.urls),
    path('api/', include('criaturas.urls')),
    path('api/oraculo/', include('oraculo.urls')),
]

# BLOQUE DE MEDIA FILES (Fuerza bruta para producción)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]

# LÓGICA MÁGICA:
# Si estamos en modo Debug (Desarrollo), le decimos a Django:
# "Oye, si alguien pide una URL que empiece por MEDIA_URL (/media/),
# búscalo en la carpeta física MEDIA_ROOT y entrégaselo".
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
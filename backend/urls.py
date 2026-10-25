# backend/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve

from django.conf import settings
from apps.game.views import home, detalle_criatura
from apps.ml.views import arena_view

# Personalización del Admin
admin.site.site_header = "Panel de Control MithoWorld"
admin.site.site_title = "Admin MithoWorld"
admin.site.index_title = "Bienvenido al Gestor de Criaturas"

urlpatterns = [
    path('', home, name='home'),
    path('criatura/<int:id>/', detalle_criatura, name='detalle'),
    path('arena/', arena_view, name='arena'),
    path('admin/', admin.site.urls),
    path('api/', include('apps.game.urls')),
    path('api/oraculo/', include('apps.ml.urls')),
]

# Servicio de archivos multimedia (/media/) en TODOS los entornos.
# WhiteNoise solo gestiona /static/; las imágenes de MEDIA_ROOT (volumen
# persistente en producción) se sirven vía django.views.static.serve para
# que estén disponibles incluso con DEBUG=False.
urlpatterns += [
    re_path(
        r'^media/(?P<path>.*)$',
        serve,
        {'document_root': settings.MEDIA_ROOT},
    ),
]

# criaturas/urls.py
"""
Configuración de URLs para la aplicación de criaturas.
Este archivo define cómo se mapean las URLs a las vistas correspondientes
utilizando el sistema de enrutamiento de Django REST Framework.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CriaturaViewSet

# Creamos una instancia del DefaultRouter
# DefaultRouter automáticamente crea una API navegable con patrones de URL
# para todas las acciones estándar (list, create, retrieve, update, delete)
router = DefaultRouter()

# Registramos el ViewSet en el enrutador
# Argumentos:
# - 'criaturas': el prefijo de la URL para este conjunto de rutas
# - CriaturaViewSet: la clase ViewSet que manejará las peticiones
# - basename='criatura': el nombre base para las URLs generadas
# Esto generará automáticamente las siguientes URLs:
# - GET /criaturas/ - lista todas las criaturas
# - GET /criaturas/{id}/ - obtiene una criatura específica
router.register(r'criaturas', CriaturaViewSet, basename='criatura')

# Define los patrones de URL para la aplicación
# El include(router.urls) añade todas las URLs generadas por el router
# a los patrones de URL de la aplicación
urlpatterns = [
    path('', include(router.urls)),
]
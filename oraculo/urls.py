# oraculo/urls.py
# Configuración de URLs para la app del oráculo (predicción de combates con IA)
from django.urls import path
from .views import PrediccionCombateView

urlpatterns = [
    # Endpoint de predicción de combate:
    # URL final: /api/oraculo/predecir/ (porque backend/urls.py agrega el prefijo 'api/oraculo/')
    # Método: POST con body JSON: {"luchador_1_id": 5, "luchador_2_id": 12}
    # Respuesta: JSON con ganador_id, ganador_nombre, probabilidad y mensaje
    # .as_view() convierte la clase APIView en una función vista callable por Django
    path('predecir/', PrediccionCombateView.as_view(), name='predecir_combate'),
]
# criaturas/views.py
from rest_framework import viewsets
from .models import Criatura
from .serializers import CriaturaSerializer

# ViewSet para el manejo de las Criaturas en la API
class CriaturaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet que proporciona operaciones de solo lectura para el modelo Criatura.
    Hereda de ReadOnlyModelViewSet, lo que significa que solo permite operaciones
    de GET (listar y recuperar detalles), pero no permite modificaciones (POST, PUT, DELETE).
    
    Este ViewSet automáticamente proporciona las siguientes acciones:
    - list: GET /criaturas/ - Lista todas las criaturas
    - retrieve: GET /criaturas/{id}/ - Obtiene una criatura específica
    """
    
    # Conjunto de consultas base que define qué objetos estarán disponibles en la vista
    # .all() recupera todas las instancias del modelo Criatura de la base de datos
    queryset = Criatura.objects.all()
    
    # Especifica qué serializador se utilizará para convertir las instancias
    # del modelo a JSON y viceversa
    serializer_class = CriaturaSerializer
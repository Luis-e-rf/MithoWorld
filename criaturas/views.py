# criaturas/views.py
from rest_framework import viewsets
from .models import Criatura
from .serializers import CriaturaSerializer
from django.shortcuts import render, get_object_or_404

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


# criaturas/views.py

def home(request):
    return render(request, 'index.html')

def detalle_criatura(request, id):
    # Busca la criatura o lanza error 404 si no existe
    criatura = get_object_or_404(Criatura, id=id)
    return render(request, 'detalle.html', {'criatura': criatura})
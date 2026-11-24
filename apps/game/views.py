# apps/game/views.py
from decimal import ROUND_HALF_UP, Decimal

from django.http import Http404
from django.shortcuts import get_object_or_404, render
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


# apps/game/views.py

def home(request):
    return render(request, 'index.html')


def arena_view(request):
    return render(request, 'arena.html')


def _filas_comparacion(perfil):
    filas = []
    for stat in ('ataque', 'defensa', 'velocidad', 'salud'):
        delta = Decimal(str(perfil[f'delta_{stat}'])).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        filas.append({
            'nombre': stat.capitalize(),
            'valor': perfil[stat],
            'media': perfil[f'media_{stat}'],
            'delta': delta or 0,  # Tanto -0,0 como +0,0 se presentan sin signo.
        })
    escala = max(abs(fila['delta']) for fila in filas)
    for fila in filas:
        # Cada semieje ocupa el 50 % de la pista. Un grupo uniforme tiene escala cero.
        fila['ancho'] = 50 * abs(fila['delta']) / escala if escala else 0
    return filas


def detalle_criatura(request, id, obtener_perfil):
    criatura = get_object_or_404(Criatura, id=id)
    perfil = obtener_perfil(id)
    if perfil is None:
        raise Http404('La criatura ya no está en el catálogo.')
    return render(request, 'detalle.html', {
        'criatura': criatura,
        'perfil': {
            **perfil,
            'percentil_visible': 100 * perfil['percentil_global'],
            'filas': _filas_comparacion(perfil),
        },
    })

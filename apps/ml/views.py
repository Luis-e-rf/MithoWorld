import logging
import threading
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline
from django.db import DatabaseError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.game.models import CombatLog, Criatura
from apps.ml.features import FEATURES
from apps.ml.serializers import CombateSerializer, LuchadoresSerializer
from apps.ml.services import ProbabilidadNoFinita, predecir_combate
from apps.ml.throttling import OraculoThrottle

logger = logging.getLogger(__name__)

_ruta_modelos = Path(__file__).resolve().parent / 'ml_models'
MODELO_COMBATE = None
_ORACULO_CARGADO = False
_carga_lock = threading.Lock()


def get_oraculo_model():
    """Carga el pipeline v2 una vez por worker, incluso si falta el artefacto."""
    global MODELO_COMBATE, _ORACULO_CARGADO
    with _carga_lock:
        if not _ORACULO_CARGADO:
            try:
                modelo = joblib.load(_ruta_modelos / 'modelo_combate.pkl')
                if (not isinstance(modelo, Pipeline)
                        or list(getattr(modelo, 'feature_names_in_', ())) != FEATURES
                        or set(getattr(modelo, 'classes_', ())) != {0, 1}):
                    raise ValueError('El artefacto no cumple el contrato del pipeline v2.')
                MODELO_COMBATE = modelo
            except (OSError, ValueError, EOFError) as exc:
                logger.warning('Oráculo no disponible: %s', exc)
                MODELO_COMBATE = None
            _ORACULO_CARGADO = True
    return MODELO_COMBATE


class PrediccionCombateView(APIView):
    """
    Recibe los IDs de dos criaturas y predice el ganador usando ML.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OraculoThrottle]
    throttle_scope = 'oraculo'

    def post(self, request):
        # 1. Validar IDs ANTES de invocar get_oraculo_model(): un body
        # inválido devuelve 400 aunque los artefactos ML no estén disponibles.
        entrada = LuchadoresSerializer(data=request.data)
        if not entrada.is_valid():
            mensaje = 'Los IDs de los luchadores deben ser enteros positivos.'
            if isinstance(request.data, dict) and not all(request.data.get(k) for k in entrada.fields):
                mensaje = 'Faltan IDs de luchadores'
            return Response({'error': mensaje}, status=status.HTTP_400_BAD_REQUEST)
        id_1 = entrada.validated_data['luchador_1_id']
        id_2 = entrada.validated_data['luchador_2_id']
        if id_1 == id_2:
            return Response({'error': 'Elige dos criaturas distintas.'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Asegurar disponibilidad del Oráculo (cache de una sola carga).
        modelo_combate = get_oraculo_model()
        if modelo_combate is None:
            return Response(
                {"detail": "Oráculo no disponible por falta de un pipeline v2 válido."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 3. Buscar estadísticas reales en la Base de Datos
        try:
            c1 = Criatura.objects.get(id=id_1)
            c2 = Criatura.objects.get(id=id_2)
        except Criatura.DoesNotExist:
            return Response({'error': 'Una de las criaturas no existe'}, status=status.HTTP_404_NOT_FOUND)

        try:
            prediccion = predecir_combate(c1, c2, modelo_combate)
        except ProbabilidadNoFinita as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        ganador = prediccion.ganador
        confianza = prediccion.probabilidad
        metricas = {
            'diferencial': prediccion.diferencial,
            'ventaja_elemental': prediccion.ventaja_elemental,
            'latencia_ms': prediccion.latencia_ms,
        }
        try:
            CombatLog.objects.create(
                luchador_1=c1, luchador_2=c2, ganador_predicho=ganador,
                probabilidad=confianza, **metricas,
            )
        except DatabaseError:
            logger.exception('No se pudo guardar la predicción en CombatLog.')
            return Response({'detail': 'No se pudo guardar la predicción.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({
            'resultado': {
                'ganador_id': ganador.id,
                'ganador_nombre': ganador.nombre,
                'probabilidad': f"{confianza:.1%}",
                'mensaje': f"El oráculo predice que {ganador.nombre} ganaría con un {confianza:.0%} de probabilidad.",
            },
            'metricas': metricas,
        })


class HistorialCombatesView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        recientes = CombatLog.objects.select_related(
            'luchador_1', 'luchador_2', 'ganador_predicho',
        ).order_by('-creado_en', '-id')[:10]
        return Response({'combates': CombateSerializer(recientes, many=True).data})

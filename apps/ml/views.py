import logging
import threading
from pathlib import Path

import joblib
from django.db import DatabaseError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.game.models import CombatLog, Criatura
from apps.ml.serializers import CombateSerializer, LuchadoresSerializer
from apps.ml.services import ProbabilidadNoFinita, predecir_combate
from apps.ml.throttling import OraculoThrottle

logger = logging.getLogger(__name__)

# Artefactos ML (Singleton). Se cargan una única vez por proceso via
# get_oraculo_models(). MODELO_GANE / ENCODER_TIPOS siguen siendo globals
# de módulo para poder ser mockeados directamente en los tests.
_ruta_modelos = Path(__file__).resolve().parent / 'ml_models'
MODELO_COMBATE = None
ENCODER_TIPOS = None
_ORACULO_CARGADO = False
# Lock para evitar carga doble en requests concurrentes del mismo proceso.
_carga_lock = threading.Lock()


def get_oraculo_models():
    """Carga (y cachea) los artefactos ML. Tolerante a falta de archivos.

    Hardening (defensa preventiva), no corrección de un bug observado:
    se ejecuta `joblib.load` UNA vez por proceso. Si el .pkl falta se
    cachea el resultado "None" para no reintentar la carga en cada request
    y evitar que la app crashee al import. El lock protege frente a la
    carga doble en requests simultáneas (double-checked locking).
    """
    global MODELO_COMBATE, ENCODER_TIPOS, _ORACULO_CARGADO

    if _ORACULO_CARGADO:
        return MODELO_COMBATE, ENCODER_TIPOS

    if MODELO_COMBATE is not None and ENCODER_TIPOS is not None:
        # Pre-cargados (p. ej. mockeados en tests); no sobrescribir.
        return MODELO_COMBATE, ENCODER_TIPOS

    with _carga_lock:
        # Double-check dentro del lock: otro request pudo cargar entre ambos checks.
        if _ORACULO_CARGADO:
            return MODELO_COMBATE, ENCODER_TIPOS
        if MODELO_COMBATE is not None and ENCODER_TIPOS is not None:
            return MODELO_COMBATE, ENCODER_TIPOS

        try:
            MODELO_COMBATE = joblib.load(_ruta_modelos / 'modelo_combate.pkl')
            ENCODER_TIPOS = joblib.load(_ruta_modelos / 'encoder_tipos.pkl')
        except FileNotFoundError as exc:
            logger.warning("Oráculo no disponible por falta de artefactos ML: %s", exc)
            MODELO_COMBATE = None
            ENCODER_TIPOS = None

        _ORACULO_CARGADO = True
        return MODELO_COMBATE, ENCODER_TIPOS


class PrediccionCombateView(APIView):
    """
    Recibe los IDs de dos criaturas y predice el ganador usando ML.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OraculoThrottle]
    throttle_scope = 'oraculo'

    def post(self, request):
        # 1. Validar IDs ANTES de invocar get_oraculo_models(): un body
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
        modelo_combate, encoder_tipos = get_oraculo_models()
        if modelo_combate is None or encoder_tipos is None:
            return Response(
                {"detail": "Oráculo no disponible por falta de artefactos ML."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 3. Buscar estadísticas reales en la Base de Datos
        try:
            c1 = Criatura.objects.get(id=id_1)
            c2 = Criatura.objects.get(id=id_2)
        except Criatura.DoesNotExist:
            return Response({'error': 'Una de las criaturas no existe'}, status=status.HTTP_404_NOT_FOUND)

        try:
            prediccion = predecir_combate(c1, c2, modelo_combate, encoder_tipos)
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

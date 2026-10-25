import logging
import os
import threading
import joblib
import pandas as pd
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.game.models import Criatura
from django.shortcuts import render
# Importamos permisos de DRF
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)

# Artefactos ML (Singleton). Se cargan una única vez por proceso via
# get_oraculo_models(). MODELO_GANE / ENCODER_TIPOS siguen siendo globals
# de módulo para poder ser mockeados directamente en los tests.
_ruta_modelos = os.path.join(settings.BASE_DIR, 'oraculo', 'ml_models')
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
            MODELO_COMBATE = joblib.load(os.path.join(_ruta_modelos, 'modelo_combate.pkl'))
            ENCODER_TIPOS = joblib.load(os.path.join(_ruta_modelos, 'encoder_tipos.pkl'))
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
    # === ESTAS DOS LÍNEAS SON LA SOLUCIÓN ===
    # Le dicen a DRF: "No intentes autenticar usuario ni busques cookies aquí".
    authentication_classes = []
    permission_classes = [AllowAny]
    # ========================================

    def post(self, request):
        # 1. Validar IDs ANTES de invocar get_oraculo_models(): un body
        # inválido devuelve 400 aunque los artefactos ML no estén disponibles.
        id_1 = request.data.get('luchador_1_id')
        id_2 = request.data.get('luchador_2_id')

        if not id_1 or not id_2:
            return Response({'error': 'Faltan IDs de luchadores'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Asegurar disponibilidad del Oráculo (cache de una sola carga).
        # Los hallazgos de NaN/vector vacío y la reubicación del clamp a una
        # capa de servicio quedan registrados como deuda técnica para Fase 2
        # (apps/ml/services.py); no se resuelven en esta fase.
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

        # 4. Preparar los datos para la IA (Ingeniería de Características)
        # Traducimos el texto "Fuego" a número usando el encoder guardado
        tipo_1_num = encoder_tipos.transform([c1.tipo_primario])[0]
        tipo_2_num = encoder_tipos.transform([c2.tipo_primario])[0]

        # Construimos el DataFrame de una sola fila para predecir
        datos_combate = pd.DataFrame([{
            'ataque_1': c1.ataque,
            'defensa_1': c1.defensa,
            'velocidad_1': c1.velocidad,
            'tipo_1_encoded': tipo_1_num,
            'ataque_2': c2.ataque,
            'defensa_2': c2.defensa,
            'velocidad_2': c2.velocidad,
            'tipo_2_encoded': tipo_2_num
        }])

        # 5. Preguntar al Oráculo
        # predict devuelve [1] (Gana el 1) o [0] (Gana el 2)
        prediccion = modelo_combate.predict(datos_combate)[0]

        # predict_proba devuelve algo como [0.2, 0.8] (20% gana el 2, 80% gana el 1).
        # La confianza debe ser la probabilidad de la clase EFECTIVAMENTE predicha,
        # no el máximo del vector: el índice de la clase viene de classes_.
        probabilidades = modelo_combate.predict_proba(datos_combate)[0]
        clases = getattr(modelo_combate, "classes_", None)
        if clases is not None:
            indice_clase = list(clases).index(prediccion)
        else:
            indice_clase = int(prediccion)
        confianza = float(probabilidades[indice_clase])
        # Hardening (defensa preventiva): acotar a [0,1] aunque sklearn ya
        # devuelve probabilidades en ese rango. No es parche de un bug real.
        confianza = max(0.0, min(1.0, confianza))

        ganador = c1 if prediccion == 1 else c2

        # 5. Responder
        return Response({
            'resultado': {
                'ganador_id': ganador.id,
                'ganador_nombre': ganador.nombre,
                'probabilidad': f"{confianza:.1%}",  # Formato porcentaje (ej: 80.5%)
                'mensaje': f"El oráculo predice que {ganador.nombre} ganaría con un {confianza:.0%} de probabilidad."
            }
        })


def arena_view(request):
    return render(request, 'arena.html')
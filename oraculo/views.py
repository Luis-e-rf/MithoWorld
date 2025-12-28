import os
import joblib
import pandas as pd
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from criaturas.models import Criatura
from django.shortcuts import render
# Importamos permisos de DRF
from rest_framework.permissions import AllowAny 

# Cargar modelos globalmente una sola vez al iniciar el servidor (Singleton)
ruta_modelos = os.path.join(settings.BASE_DIR, 'oraculo', 'ml_models')
MODELO_COMBATE = joblib.load(os.path.join(ruta_modelos, 'modelo_combate.pkl'))
ENCODER_TIPOS = joblib.load(os.path.join(ruta_modelos, 'encoder_tipos.pkl'))

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
        # 1. Recibir datos del Frontend (JSON)
        id_1 = request.data.get('luchador_1_id')
        id_2 = request.data.get('luchador_2_id')

        if not id_1 or not id_2:
            return Response({'error': 'Faltan IDs de luchadores'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Buscar estadísticas reales en la Base de Datos
        try:
            c1 = Criatura.objects.get(id=id_1)
            c2 = Criatura.objects.get(id=id_2)
        except Criatura.DoesNotExist:
            return Response({'error': 'Una de las criaturas no existe'}, status=status.HTTP_404_NOT_FOUND)

        # 3. Preparar los datos para la IA (Ingeniería de Características)
        # La IA espera exactamente las mismas columnas y orden que en el entrenamiento
        
        # Traducimos el texto "Fuego" a número usando el encoder guardado
        # Nota: transform espera una lista, por eso los corchetes []
        tipo_1_num = ENCODER_TIPOS.transform([c1.tipo_primario])[0]
        tipo_2_num = ENCODER_TIPOS.transform([c2.tipo_primario])[0]

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

        # 4. Preguntar al Oráculo
        # predict devuelve [1] (Gana el 1) o [0] (Gana el 2)
        prediccion = MODELO_COMBATE.predict(datos_combate)[0]
        
        # También podemos pedir la probabilidad (qué tan seguro está)
        # predict_proba devuelve algo como [0.2, 0.8] (20% gana el 2, 80% gana el 1)
        probabilidad = MODELO_COMBATE.predict_proba(datos_combate)[0]
        confianza = max(probabilidad) # Tomamos el valor más alto (ej: 0.80)

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
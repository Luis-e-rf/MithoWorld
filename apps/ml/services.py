import math
import time
from dataclasses import dataclass

import pandas as pd

from apps.game.models import Criatura
from apps.game.rules import VENTAJAS


class ProbabilidadNoFinita(ValueError):
    """El modelo devolvió una confianza no finita para la clase predicha."""


@dataclass
class Prediccion:
    ganador: Criatura
    probabilidad: float
    diferencial: dict[str, int]
    ventaja_elemental: dict[str, float]
    latencia_ms: float


def predecir_combate(luchador_1, luchador_2, modelo, encoder):
    inicio = time.perf_counter()
    tipo_1 = luchador_1.tipo_primario
    tipo_2 = luchador_2.tipo_primario
    datos = pd.DataFrame([{
        'ataque_1': luchador_1.ataque,
        'defensa_1': luchador_1.defensa,
        'velocidad_1': luchador_1.velocidad,
        'tipo_1_encoded': encoder.transform([tipo_1])[0],
        'ataque_2': luchador_2.ataque,
        'defensa_2': luchador_2.defensa,
        'velocidad_2': luchador_2.velocidad,
        'tipo_2_encoded': encoder.transform([tipo_2])[0],
    }])

    clase = modelo.predict(datos)[0]
    probabilidades = modelo.predict_proba(datos)[0]
    latencia_ms = (time.perf_counter() - inicio) * 1000
    clases = getattr(modelo, 'classes_', None)
    indice = list(clases).index(clase) if clases is not None else int(clase)
    confianza = float(probabilidades[indice])
    if not math.isfinite(confianza):
        raise ProbabilidadNoFinita('El modelo devolvió una probabilidad no finita.')

    return Prediccion(
        ganador=luchador_1 if clase == 1 else luchador_2,
        probabilidad=max(0.0, min(1.0, confianza)),
        latencia_ms=latencia_ms,
        diferencial={
            'ataque': luchador_1.ataque - luchador_2.ataque,
            'defensa': luchador_1.defensa - luchador_2.defensa,
            'velocidad': luchador_1.velocidad - luchador_2.velocidad,
        },
        ventaja_elemental={
            'luchador_1': VENTAJAS.get(tipo_1, {}).get(tipo_2, 1.0),
            'luchador_2': VENTAJAS.get(tipo_2, {}).get(tipo_1, 1.0),
        },
    )

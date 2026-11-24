import math
import time
from dataclasses import dataclass

import pandas as pd

from apps.game.models import Criatura
from apps.game.rules import multiplicador
from apps.ml.features import FEATURES, STATS, fila_combate


class ProbabilidadNoFinita(ValueError):
    """El modelo devolvió una confianza no finita para la clase predicha."""


@dataclass
class Prediccion:
    ganador: Criatura
    probabilidad: float
    diferencial: dict[str, int]
    ventaja_elemental: dict[str, float]
    latencia_ms: float


def predecir_combate(luchador_1, luchador_2, modelo):
    inicio = time.perf_counter()
    datos = pd.DataFrame([fila_combate(luchador_1, luchador_2)], columns=FEATURES)
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
            stat: getattr(luchador_1, stat) - getattr(luchador_2, stat) for stat in STATS
        },
        ventaja_elemental={
            'luchador_1': multiplicador(luchador_1, luchador_2),
            'luchador_2': multiplicador(luchador_2, luchador_1),
        },
    )

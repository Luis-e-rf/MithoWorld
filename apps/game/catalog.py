"""Catálogo canónico y columnas de intercambio de los combates simulados v2."""
import hashlib
import json

from apps.game.rules import normalizar_tipos

STATS = ('ataque', 'defensa', 'velocidad', 'salud')
TIPOS = ('tipo_primario', 'tipo_secundario')
FEATURES = [f'{campo}_{lado}' for lado in (1, 2) for campo in (*STATS, *TIPOS)]
IDS = ['luchador_1_id', 'luchador_2_id', 'ganador_id']
TARGET = 'gano_primero'
COLUMNAS = [*IDS, *FEATURES, TARGET]


def atributos(criatura):
    primario, secundario = normalizar_tipos(criatura.tipo_primario, criatura.tipo_secundario)
    return {**{stat: getattr(criatura, stat) for stat in STATS},
            'tipo_primario': primario, 'tipo_secundario': secundario}


def catalogo_sha256(criaturas):
    filas = [
        {'id': c.pk, 'nombre': c.nombre, **atributos(c)}
        for c in sorted(criaturas, key=lambda c: c.pk)
    ]
    return hashlib.sha256(json.dumps(filas, sort_keys=True).encode()).hexdigest()

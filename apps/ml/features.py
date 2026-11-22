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


def fila_combate(primero, segundo):
    return {f'{campo}_{lado}': valor
            for lado, criatura in enumerate((primero, segundo), start=1)
            for campo, valor in atributos(criatura).items()}

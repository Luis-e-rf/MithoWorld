from pathlib import Path

from django.db import connection


_SQL_DIR = Path(__file__).parent / 'sql'
_SQL_PERFIL = (_SQL_DIR / 'perfil_criatura.sql').read_text(encoding='utf-8')
_SQL_MATCHUPS = (_SQL_DIR / 'matchups_criatura.sql').read_text(encoding='utf-8')
_SQL_DASHBOARD = (_SQL_DIR / 'dashboard_universo.sql').read_text(encoding='utf-8')
MIN_MUESTRA = 8


def _consultar_fila(sql, parametros):
    with connection.cursor() as cursor:
        cursor.execute(sql, parametros)
        fila = cursor.fetchone()
        if fila is None:
            return None
        return dict(zip((columna[0] for columna in cursor.description), fila, strict=True))


def obtener_perfil_criatura(criatura_id):
    return _consultar_fila(_SQL_PERFIL, [criatura_id])


def obtener_matchups(criatura_id):
    fila = _consultar_fila(_SQL_MATCHUPS, {'criatura_id': criatura_id, 'min_muestra': MIN_MUESTRA})
    fila['min_muestra'] = MIN_MUESTRA
    if fila['win_rate'] is not None:
        fila['porcentaje'] = 100 * fila['win_rate']
    rivales = []
    elegibles = fila['n_rivales_elegibles']
    if elegibles == 1:
        etiquetas = [('counter', 'Único rival con muestra suficiente')]
    elif elegibles > 1 and fila['counter_tasa'] != fila['nemesis_tasa']:
        etiquetas = [('counter', 'Mejor Counter · rival más favorable'), ('nemesis', 'Némesis · rival más difícil')]
    else:
        etiquetas = []
    for clave, etiqueta in etiquetas:
        rivales.append({
            'etiqueta': etiqueta,
            'id': fila[f'{clave}_id'],
            'nombre': fila[f'{clave}_nombre'],
            'porcentaje': 100 * fila[f'{clave}_tasa'],
            'victorias': fila[f'{clave}_victorias'],
            'enfrentamientos': fila[f'{clave}_enfrentamientos'],
        })
    if elegibles > 1 and not rivales:
        fila['porcentaje_comun'] = 100 * fila['counter_tasa']
    fila['rivales'] = rivales
    return fila


def obtener_perfil_completo(criatura_id):
    perfil = obtener_perfil_criatura(criatura_id)
    if perfil is not None:
        perfil['matchups'] = obtener_matchups(criatura_id)
    return perfil


def obtener_dashboard():
    with connection.cursor() as cursor:
        cursor.execute(_SQL_DASHBOARD)
        columnas = [columna[0] for columna in cursor.description]
        filas = [dict(zip(columnas, fila, strict=True)) for fila in cursor.fetchall()]

    # El agregado de totales entrega una fila incluso con el catálogo vacío.
    campos = ('n_catalogo', 'n_predicciones', 'dataset_sha256', 'seed_simulacion',
              'n_simulados', 'n_espejos', 'n_sin_clasificar')
    resumen = {campo: filas[0][campo] for campo in campos}
    resumen['n_cruces'] = resumen['n_simulados'] - resumen['n_espejos'] - resumen['n_sin_clasificar']
    resumen['elementos'] = [
        {
            'nombre': fila['tipo'].capitalize() if fila['tipo'] else 'Sin tipo',
            'criaturas': fila['criaturas'],
            'porcentaje_catalogo': 100 * fila['proporcion_catalogo'],
            'victorias': fila['victorias'],
            'participaciones': fila['participaciones'],
            'porcentaje_victorias': 100 * fila['win_rate'] if fila['win_rate'] is not None else None,
        }
        for fila in filas if fila['criaturas'] is not None
    ]
    return resumen

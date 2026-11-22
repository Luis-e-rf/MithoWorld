from pathlib import Path

from django.db import connection


_SQL_PERFIL = (Path(__file__).parent / 'sql' / 'perfil_criatura.sql').read_text(encoding='utf-8')


def obtener_perfil_criatura(criatura_id):
    """Devuelve las métricas del catálogo actual o None si falta la criatura."""
    with connection.cursor() as cursor:
        cursor.execute(_SQL_PERFIL, [criatura_id])
        fila = cursor.fetchone()
        if fila is None:
            return None
        return dict(zip((columna[0] for columna in cursor.description), fila, strict=True))

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.analytics.models import CombateSimulado, LoteSimulacion
from apps.game.catalog import COLUMNAS, atributos, catalogo_sha256
from apps.game.models import Criatura


def leer_dataset(raiz):
    contenido = (raiz / 'dataset_batallas.csv').read_bytes()
    meta = json.loads((raiz / 'dataset_batallas.meta.json').read_text(encoding='utf-8'))
    enteros = ('schema_version', 'rules_version', 'seed_simulacion', 'n_combates')
    if not isinstance(meta, dict) or any(type(meta.get(k)) is not int for k in enteros):
        raise CommandError('Manifiesto incompleto o con tipos inválidos.')
    if meta['schema_version'] != 2 or meta['rules_version'] != 2:
        raise CommandError('Se requiere el esquema y las reglas v2.')
    if not re.fullmatch('[0-9a-f]{64}', str(meta.get('catalogo_sha256', ''))):
        raise CommandError('Huella del catálogo inválida.')
    if hashlib.sha256(contenido).hexdigest() != meta.get('dataset_sha256'):
        raise CommandError('El SHA-256 del CSV difiere del manifiesto.')

    lector = csv.DictReader(io.StringIO(contenido.decode('utf-8-sig'), newline=''), strict=True)
    if sorted(lector.fieldnames or []) != sorted(COLUMNAS):
        raise CommandError('Cabecera CSV v2 inválida.')
    filas = list(lector)
    if not filas or len(filas) != meta['n_combates']:
        raise CommandError('Recuento de combates incompatible con el manifiesto.')
    campos = (*enteros, 'catalogo_sha256', 'dataset_sha256')
    return {k: meta[k] for k in campos}, filas


def preparar_hechos(meta, filas, catalogo):
    valores = {c.pk: atributos(c) for c in catalogo}
    hechos = []
    for num, fila in enumerate(filas, 1):
        try:
            a, b, ganador = (int(fila[k]) for k in ('luchador_1_id', 'luchador_2_id', 'ganador_id'))
            if None in fila or a <= 0 or b <= 0 or a == b:
                raise ValueError('participantes o número de columnas inválidos')
            if ganador not in (a, b) or fila['gano_primero'] != str(int(ganador == a)):
                raise ValueError('ganador y resultado incompatibles')
            for lado, pk in enumerate((a, b), 1):
                if any(fila[f'{campo}_{lado}'] != str(valor) for campo, valor in valores[pk].items()):
                    raise ValueError(f'atributos distintos del catálogo para el luchador {lado}')
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandError(f'Fila de datos {num} inválida: {exc}') from exc
        hechos.append(CombateSimulado(
            lote_id=meta['dataset_sha256'], fila_num=num, luchador_1_id=a, luchador_2_id=b,
            luchador_1_origen_id=a, luchador_2_origen_id=b, gano_primero=ganador == a,
        ))
    return hechos


@transaction.atomic
def cargar_lote(meta, filas):
    # Orden fijo entre cargadores. SHARE también bloquea inserciones en el catálogo.
    with connection.cursor() as cursor:
        cursor.execute('LOCK TABLE analytics_lotesimulacion IN SHARE ROW EXCLUSIVE MODE')
        cursor.execute('LOCK TABLE criaturas_criatura IN SHARE MODE')
    catalogo = list(Criatura.objects.order_by('pk'))
    if catalogo_sha256(catalogo) != meta['catalogo_sha256']:
        raise CommandError('La huella del catálogo actual difiere del manifiesto.')
    hechos = preparar_hechos(meta, filas, catalogo)
    lote = LoteSimulacion.objects.filter(pk=meta['dataset_sha256']).first()
    if lote is None:
        lote = LoteSimulacion.objects.create(**meta)
        CombateSimulado.objects.bulk_create(hechos, batch_size=1000)
        if lote.combates.count() != len(hechos):
            raise CommandError('La carga no alcanzó el total declarado.')
        accion = 'Cargado'
    else:
        if any(getattr(lote, k) != v for k, v in meta.items()):
            raise CommandError('Metadatos incompatibles con el lote existente.')
        campos = ('fila_num', 'luchador_1_origen_id', 'luchador_2_origen_id', 'gano_primero')
        guardados = list(lote.combates.order_by('fila_num').values_list(*campos))
        if guardados != [tuple(getattr(h, k) for k in campos) for h in hechos]:
            raise CommandError('El lote existente está incompleto o difiere del CSV.')
        if lote.activo:
            return 'Ya cargado'
        accion = 'Reactivado'
    LoteSimulacion.objects.filter(activo=True).update(activo=False)
    lote.activo = True
    lote.save(update_fields=['activo'])
    return accion


class Command(BaseCommand):
    help = 'Valida los combates simulados v2 y publica el lote en la ficha analítica.'

    def handle(self, *args, **options):
        try:
            meta, filas = leer_dataset(Path(settings.BASE_DIR))
            accion = cargar_lote(meta, filas)
        except (OSError, ValueError, csv.Error) as exc:
            raise CommandError(f'No se pudo cargar el dataset: {exc}') from exc
        self.stdout.write(f"{accion} · semilla {meta['seed_simulacion']} · {meta['n_combates']} combates "
                          f"· SHA-256 {meta['dataset_sha256']}")

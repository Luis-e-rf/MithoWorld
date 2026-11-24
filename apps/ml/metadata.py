import hashlib
import json
import logging
import math
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)
DIRECTORIO_MODELOS = Path(__file__).resolve().parent / 'ml_models'


def _identidad(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


@lru_cache(maxsize=1)
def _sha256_modelo(ruta, identidad):
    with ruta.open('rb') as archivo:
        huella = hashlib.file_digest(archivo, 'sha256').hexdigest()
        if _identidad(os.fstat(archivo.fileno())) != identidad:
            raise ValueError('El pipeline cambió durante su verificación.')
    return huella


def leer_metricas_modelo():
    try:
        meta = json.loads((DIRECTORIO_MODELOS / 'modelo_metadata.json').read_text(encoding='utf-8'))
        if type(meta['schema_version']) is not int or meta['schema_version'] != 2:
            raise ValueError('Versión de metadatos incompatible.')
        if type(meta['seed']) is not int:
            raise ValueError('Semilla de entrenamiento inválida.')
        for campo in ('dataset_sha256', 'modelo_sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}', meta[campo]):
                raise ValueError(f'Huella inválida en {campo}.')
        fecha = datetime.fromisoformat(meta['entrenado_en_utc'])
        if fecha.tzinfo is None:
            raise ValueError('La fecha de entrenamiento carece de zona horaria.')
        accuracy = meta['metricas_test']['accuracy']
        roc_auc = meta['metricas_test']['roc_auc']
        for valor in (accuracy, roc_auc):
            if type(valor) not in (float, int) or not 0 <= valor <= 1 or not math.isfinite(valor):
                raise ValueError('Métrica de evaluación fuera de rango.')
        ruta = DIRECTORIO_MODELOS / 'modelo_combate.pkl'
        if _sha256_modelo(ruta, _identidad(ruta.stat())) != meta['modelo_sha256']:
            raise ValueError('La huella del pipeline difiere de la publicada.')
        return {
            'accuracy_pct': 100 * accuracy, 'roc_auc': roc_auc,
            'fecha': fecha.astimezone(timezone.utc), 'seed': meta['seed'],
            'dataset_sha256': meta['dataset_sha256'],
        }
    except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as exc:
        logger.warning('Evaluación del modelo no disponible: %s', exc)
        return None

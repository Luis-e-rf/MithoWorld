import hashlib
import json
import os
from unittest.mock import patch

import pytest

from apps.ml import metadata


@pytest.fixture
def publicacion(tmp_path, monkeypatch):
    monkeypatch.setattr(metadata, 'DIRECTORIO_MODELOS', tmp_path)
    modelo = tmp_path / 'modelo_combate.pkl'
    modelo.write_bytes(b'modelo A')
    meta = {
        'schema_version': 2, 'seed': 11, 'dataset_sha256': 'd' * 64,
        'modelo_sha256': hashlib.sha256(modelo.read_bytes()).hexdigest(),
        'entrenado_en_utc': '2026-11-20T22:34:00-05:00',
        'metricas_test': {'accuracy': 0, 'roc_auc': 1},
    }
    archivo = tmp_path / 'modelo_metadata.json'
    archivo.write_text(json.dumps(meta))
    return modelo, archivo, meta


def test_cache_por_identidad_y_publicacion_nueva(publicacion):
    modelo, archivo, meta = publicacion
    with patch.object(metadata.hashlib, 'file_digest', wraps=hashlib.file_digest) as calcular:
        resultado = metadata.leer_metricas_modelo()
        assert resultado == metadata.leer_metricas_modelo()
        assert (resultado['accuracy_pct'], resultado['roc_auc'], resultado['seed']) == (0, 1, 11)
        assert resultado['fecha'].isoformat() == '2026-11-21T03:34:00+00:00'
        assert calcular.call_count == 1

        # Reemplazo atómico con igual tamaño y marca de modificación.
        nuevo = modelo.with_suffix('.tmp')
        nuevo.write_bytes(b'modelo B')
        stat = modelo.stat()
        os.utime(nuevo, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        nuevo.replace(modelo)
        assert metadata.leer_metricas_modelo() is None
        assert calcular.call_count == 2
        meta['modelo_sha256'] = hashlib.sha256(modelo.read_bytes()).hexdigest()
        meta['metricas_test']['accuracy'] = 0.75
        archivo.write_text(json.dumps(meta))
        assert metadata.leer_metricas_modelo()['accuracy_pct'] == 75
        assert calcular.call_count == 2


@pytest.mark.parametrize('campo, valor', [
    ('schema_version', 1), ('schema_version', 2.0), ('seed', True),
    ('entrenado_en_utc', '2026-11-20'), ('entrenado_en_utc', 'ayer'),
    ('dataset_sha256', 'digest'), ('modelo_sha256', 'a' * 64),
    ('metricas_test', {'accuracy': float('nan'), 'roc_auc': 0.5}),
    ('metricas_test', {'accuracy': 0.5, 'roc_auc': float('inf')}),
    ('metricas_test', {'accuracy': 2, 'roc_auc': 0}),
    ('metricas_test', {'accuracy': True, 'roc_auc': 0}), ('metricas_test', {}),
])
def test_manifiesto_invalido(publicacion, campo, valor):
    _, archivo, meta = publicacion
    archivo.write_text(json.dumps({**meta, campo: valor}))
    assert metadata.leer_metricas_modelo() is None


def test_publicacion_incompleta_o_ilegible(publicacion):
    modelo, archivo, meta = publicacion
    archivo.unlink()
    assert metadata.leer_metricas_modelo() is None
    archivo.write_text('{')
    assert metadata.leer_metricas_modelo() is None
    archivo.write_bytes(b'\xff')
    assert metadata.leer_metricas_modelo() is None
    archivo.write_text(json.dumps(meta))
    modelo.unlink()
    assert metadata.leer_metricas_modelo() is None

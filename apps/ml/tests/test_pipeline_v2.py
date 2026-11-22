import hashlib
import json
import random
from unittest import mock

import joblib
import numpy as np
import pandas as pd
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.cache.backends.locmem import LocMemCache
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

from apps.game.models import Criatura
from apps.game.rules import multiplicador, normalizar_tipos, score_base
from apps.ml import views
from apps.ml.features import COLUMNAS, FEATURES, IDS, TARGET
from apps.ml.management.commands import simular_batallas
from apps.ml.management.commands.entrenar_oraculo import leer_dataset
from apps.ml.services import predecir_combate


def test_reglas_doble_tipo_salud_y_empate():
    stats = dict(ataque=50, defensa=50, velocidad=50, salud=50)
    a = Criatura(tipo_primario='Oscuridad', tipo_secundario=' AIRE ', **stats)
    b = Criatura(tipo_primario='luz', tipo_secundario='plasma', **stats)
    assert multiplicador(a, b) == pytest.approx(7 / 9)
    assert multiplicador(b, a) == pytest.approx(13 / 9)
    base = score_base(a, b)
    a.salud += 4
    assert score_base(a, b) == pytest.approx(base + 1)
    for secundario in (None, '', '  ', ' OSCURIDAD '):
        assert normalizar_tipos('Oscuridad', secundario) == ('oscuridad', '')
    a.tipo_secundario, b.tipo_secundario = None, ''
    assert multiplicador(a, b) == 0.5
    a.ataque = b.ataque = a.defensa = b.defensa = 0
    a.salud = b.salud = a.velocidad = b.velocidad = 0
    rng = random.Random(42)
    assert {id(simular_batallas.ganador_simulado(a, b, rng)) for _ in range(30)} == {id(a), id(b)}


@pytest.mark.django_db
def test_pipeline_reproducible_y_paridad_monotipo(tmp_path, settings, monkeypatch):
    settings.BASE_DIR = tmp_path
    monkeypatch.setattr(simular_batallas, 'N_COMBATES', 400)
    catalogo = {}
    for i in range(10):
        criatura = Criatura.objects.create(
            nombre=f'Criatura {i}', ataque=40+i, defensa=50, velocidad=70, salud=60+i,
            tipo_primario='Fuego', tipo_secundario=' Aire ' if i % 2 else None,
        )
        catalogo[criatura.pk] = criatura
    call_command('simular_batallas', seed=42)
    dataset = tmp_path / 'dataset_batallas.csv'
    contenido = dataset.read_bytes()
    call_command('simular_batallas', seed=42)
    assert dataset.read_bytes() == contenido
    datos, origen = leer_dataset(tmp_path)
    assert list(datos) == COLUMNAS
    assert len(datos) == origen['n_combates'] == 400
    a, b = (datos[k] for k in IDS[:2])
    assert a.ne(b).all()
    assert datos.ganador_id.eq(a.where(datos[TARGET].eq(1), b)).all()
    call_command('entrenar_oraculo', seed=42)
    destino = tmp_path / 'apps/ml/ml_models'
    modelo = joblib.load(destino / 'modelo_combate.pkl')
    meta = json.loads((destino / 'modelo_metadata.json').read_text())
    assert meta['dataset_sha256'] == hashlib.sha256(contenido).hexdigest()
    assert meta['modelo_sha256'] == hashlib.sha256((destino / 'modelo_combate.pkl').read_bytes()).hexdigest()
    assert list(modelo.feature_names_in_) == meta['features'] == FEATURES
    parejas = list(zip(np.minimum(a, b), np.maximum(a, b)))
    _, grupos = np.unique(parejas, axis=0, return_inverse=True)
    train, test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(datos, groups=grupos))
    assert set(grupos[train]).isdisjoint(grupos[test])
    assert meta['split']['parejas_test'] == len(set(grupos[test]))
    assert meta['metricas_test']['accuracy'] == modelo.score(datos.iloc[test][FEATURES], datos.iloc[test][TARGET])
    probas = modelo.predict_proba(datos.iloc[test][FEATURES])[:, list(modelo.classes_).index(1)]
    assert meta['metricas_test']['roc_auc'] == roc_auc_score(datos.iloc[test][TARGET], probas)

    fila = datos.loc[datos.tipo_secundario_1.eq('')].iloc[[0]]
    primero, segundo = (catalogo[fila[k].iloc[0]] for k in IDS[:2])
    with mock.patch.object(modelo, 'predict', wraps=modelo.predict) as llamada:
        resultado = predecir_combate(primero, segundo, modelo)
    entrada = llamada.call_args.args[0]
    pd.testing.assert_frame_equal(entrada, fila[FEATURES].reset_index(drop=True))
    assert entrada.tipo_secundario_1.iloc[0] == ''
    encoder = modelo.named_steps['preproceso'].named_transformers_['tipos']
    assert '' in encoder.categories_[1]
    assert resultado.probabilidad == pytest.approx(modelo.predict_proba(entrada).max())
    segundo.tipo_secundario = 'nuevo'
    assert predecir_combate(primero, segundo, modelo).latencia_ms >= 0


def test_csv_v1_falla_antes_de_reemplazar_modelo(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    (tmp_path / 'dataset_batallas.csv').write_text(
        'ataque_1,defensa_1,velocidad_1,tipo_1,ataque_2,defensa_2,velocidad_2,tipo_2,gano_primero\n'
    )
    modelo = tmp_path / 'apps/ml/ml_models/modelo_combate.pkl'
    modelo.parent.mkdir(parents=True)
    modelo.write_bytes(b'anterior')
    with pytest.raises(CommandError, match='CSV v2'):
        call_command('entrenar_oraculo')
    assert modelo.read_bytes() == b'anterior'


def test_bosque_v1_devuelve_503(client, monkeypatch):
    cache = LocMemCache('test-bosque-v1', {})
    cache.clear()
    monkeypatch.setattr(views.OraculoThrottle, 'cache', cache)
    monkeypatch.setattr(views, '_ORACULO_CARGADO', False)
    monkeypatch.setattr(views, 'MODELO_COMBATE', None)
    with mock.patch.object(views.joblib, 'load', return_value=RandomForestClassifier()) as cargar:
        respuesta = client.post('/api/oraculo/predecir/', {'luchador_1_id': 1, 'luchador_2_id': 2},
                                content_type='application/json')
        assert respuesta.status_code == 503
        assert views.get_oraculo_model() is None
        cargar.assert_called_once()

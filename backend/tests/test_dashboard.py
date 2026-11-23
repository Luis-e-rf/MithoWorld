import hashlib
import json

import pytest
from django.urls import reverse

from apps.analytics.models import CombateSimulado, LoteSimulacion
from apps.game.models import CombatLog, Criatura
from apps.ml import metadata


def criatura(nombre, tipo):
    return Criatura.objects.create(nombre=nombre, tipo_primario=tipo, ataque=20, defensa=30,
                                   salud=40, velocidad=50)


def lote(sha, seed, duelos, activo=True):
    lote = LoteSimulacion.objects.create(
        dataset_sha256=sha, catalogo_sha256='c' * 64, seed_simulacion=seed,
        schema_version=2, rules_version=2, n_combates=len(duelos), activo=activo,
    )
    CombateSimulado.objects.bulk_create([
        CombateSimulado(lote=lote, fila_num=i, luchador_1=a, luchador_2=b, gano_primero=gano,
                        luchador_1_origen_id=a.pk, luchador_2_origen_id=b.pk)
        for i, (a, b, gano) in enumerate(duelos, 1)
    ])
    return lote


@pytest.fixture
def visitar(db, client, django_assert_num_queries, monkeypatch, tmp_path, settings):
    # El dashboard debe funcionar sin CSV y con el proveedor real compuesto por el router.
    settings.BASE_DIR = tmp_path
    monkeypatch.setattr(metadata, 'DIRECTORIO_MODELOS', tmp_path)

    def get():
        with django_assert_num_queries(1):
            respuesta = client.get(reverse('analytics'))
        assert respuesta.status_code == 200
        return respuesta
    return get


def test_dashboard_vacio_y_exclusiones(visitar):
    pagina = visitar()
    assert pagina.context['universo']['n_simulados'] == 0
    assert pagina.context['universo']['n_predicciones'] == 0
    for texto in ('Catálogo vacío', 'Sin lote activo', 'Evaluación del modelo no disponible', 'Linaje de datos'):
        assert texto in pagina.content.decode()
    a, b = criatura('A', 'fuego'), criatura('B', 'fuego')
    pagina = visitar()
    assert pagina.context['universo']['n_catalogo'] == 2 and 'Fuego' in pagina.content.decode()
    lote('f' * 64, 0, [(a, b, True)])
    pagina = visitar()
    assert pagina.context['universo']['n_espejos'] == 1
    assert 'Sin cruces entre tipos clasificables' in pagina.content.decode()
    a.delete()
    pagina = visitar()
    assert pagina.context['universo']['n_sin_clasificar'] == 1
    assert pagina.context['universo']['n_espejos'] == 0


def test_balance_por_participacion_y_tipo_actual(visitar):
    a, b = criatura('A', ' FUEGO '), criatura('B', 'agua')
    c, d = criatura('C', 'luz'), criatura('D', 'fuego')
    criatura('E', 'oscuridad')
    f = criatura('F', 'aire')
    lote('f' * 64, 42, [(a, b, True), (b, a, False), (b, c, True), (a, d, True), (f, a, False)])
    f.delete()
    pagina = visitar()
    u = pagina.context['universo']
    assert (u['n_simulados'], u['n_espejos'], u['n_sin_clasificar'], u['n_cruces']) == (5, 1, 1, 3)
    por_tipo = {r['nombre']: r for r in u['elementos']}
    assert {k: (r['victorias'], r['participaciones']) for k, r in por_tipo.items()} == {
        'Agua': (1, 3), 'Fuego': (2, 2), 'Luz': (0, 1), 'Oscuridad': (0, 0),
    }
    assert sum(r['victorias'] for r in u['elementos']) == u['n_cruces']
    assert sum(r['participaciones'] for r in u['elementos']) == 2 * u['n_cruces']
    assert por_tipo['Fuego']['porcentaje_catalogo'] == 40
    assert por_tipo['Luz']['porcentaje_victorias'] == 0
    assert por_tipo['Oscuridad']['porcentaje_victorias'] is None
    for texto in ('0,0 %', 'Sin cruces', 'Oscuridad'):
        assert texto in pagina.content.decode()
    CombatLog.objects.create(probabilidad=0.5, ventaja_elemental={}, diferencial={}, latencia_ms=1)
    assert visitar().context['universo'] == {**u, 'n_predicciones': 1}
    d.tipo_primario = 'agua'
    d.save(update_fields=['tipo_primario'])
    assert visitar().context['universo']['n_cruces'] == 4


def test_lote_activo_y_procedencia_del_modelo(visitar, tmp_path):
    # Dos SHA con prefijo visible idéntico comprueban que se comparan los 64 caracteres.
    sha = 'a' * 64
    (tmp_path / 'modelo_combate.pkl').write_bytes(b'artefacto')
    archivo = tmp_path / 'modelo_metadata.json'
    archivo.write_text(json.dumps({
        'schema_version': 2, 'seed': 17, 'dataset_sha256': sha,
        'modelo_sha256': hashlib.sha256(b'artefacto').hexdigest(),
        'entrenado_en_utc': '2026-11-20T13:00:00+00:00',
        'metricas_test': {'accuracy': 0.72, 'roc_auc': 0.6123},
    }))
    assert '72,00 %' in visitar().content.decode()
    a, b = criatura('A', 'agua'), criatura('B', 'aire')
    anterior = lote(sha, 42, [(a, b, True)])
    siguiente = lote('a' * 63 + 'b', 13, [(a, b, False)] * 2, activo=False)
    pagina = visitar()
    assert not pagina.context['otro_lote'] and pagina.context['universo']['n_simulados'] == 1
    assert pagina.context['universo']['elementos'][0]['victorias'] == 1
    anterior.activo = False
    anterior.save(update_fields=['activo'])
    siguiente.activo = True
    siguiente.save(update_fields=['activo'])
    pagina = visitar()
    u = pagina.context['universo']
    assert (u['dataset_sha256'], u['seed_simulacion'], u['n_simulados']) == (siguiente.pk, 13, 2)
    assert u['elementos'][0]['victorias'] == 0
    assert pagina.context['otro_lote'] and 'Entrenado con otro lote' in pagina.content.decode()
    archivo.write_text('{')
    pagina = visitar()
    assert pagina.context['universo'] == u and 'Evaluación del modelo no disponible' in pagina.content.decode()

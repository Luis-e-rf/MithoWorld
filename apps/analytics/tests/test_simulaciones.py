import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier

import pytest
from django.contrib import admin
from django.core.management import CommandError, call_command
from django.db import IntegrityError, connections, transaction
from django.urls import reverse

from apps.analytics.models import CombateSimulado, LoteSimulacion
from apps.analytics.services import obtener_matchups
from apps.game.catalog import COLUMNAS, atributos, catalogo_sha256
from apps.game.models import Criatura


@pytest.fixture
def catalogo(db):
    return [Criatura.objects.create(nombre=n, tipo_primario='agua', salud=40, ataque=50,
                                    defensa=60, velocidad=70) for n in ('A', 'B', 'C', 'D', 'E')]


def dataset(raiz, catalogo, duelos, seed=42):
    """Cada duelo indica los índices de los participantes y si ganó el primero."""
    archivo = raiz / 'dataset_batallas.csv'
    with archivo.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS)
        writer.writeheader()
        for a, b, gana in duelos:
            primero, segundo = catalogo[a], catalogo[b]
            fila = {f'{k}_{lado}': v for lado, c in enumerate((primero, segundo), 1)
                    for k, v in atributos(c).items()}
            writer.writerow({**fila, 'luchador_1_id': primero.pk, 'luchador_2_id': segundo.pk,
                             'ganador_id': primero.pk if gana else segundo.pk, 'gano_primero': int(gana)})
    meta = {'schema_version': 2, 'rules_version': 2, 'seed_simulacion': seed, 'n_combates': len(duelos),
            'catalogo_sha256': catalogo_sha256(catalogo), 'dataset_sha256': hashlib.sha256(archivo.read_bytes()).hexdigest()}
    (raiz / 'dataset_batallas.meta.json').write_text(json.dumps(meta))
    return meta


def cargar():
    salida = StringIO()
    call_command('cargar_combates_simulados', stdout=salida)
    return salida.getvalue()


def test_huella_conserva_la_serializacion_de_fase_6():
    stats = dict(salud=40, ataque=50, defensa=60, velocidad=70)
    rio = Criatura(pk=1, nombre='Río', tipo_primario=' Agua ', tipo_secundario=None, **stats)
    sol = Criatura(pk=2, nombre='Sol', tipo_primario='luz', tipo_secundario=' AIRE ', **stats)
    assert catalogo_sha256([sol, rio]) == 'f1149c6064475a86f57ee1bc8944c6266e4964979e06b8edcb0e0660a65c120a'


def test_idempotencia_swap_reactivacion_y_auditoria(settings, tmp_path, catalogo, rf, admin_user):
    settings.BASE_DIR = tmp_path
    duelos = [(0, 1, True)] * 10000
    original = dataset(tmp_path, catalogo, duelos)
    assert 'Cargado' in cargar()
    assert 'Ya cargado' in cargar()
    assert CombateSimulado.objects.count() == 10000
    nuevo = dataset(tmp_path, catalogo, [(1, 0, True)], seed=84)
    cargar()
    assert LoteSimulacion.objects.get(activo=True).pk == nuevo['dataset_sha256']
    assert obtener_matchups(catalogo[0].pk)['victorias'] == 0
    dataset(tmp_path, catalogo, duelos)
    assert 'Reactivado' in cargar()
    assert LoteSimulacion.objects.get(activo=True).pk == original['dataset_sha256']
    assert CombateSimulado.objects.count() == 10001
    auditoria = admin.site.get_model_admin(LoteSimulacion)
    request = rf.get('/')
    request.user = admin_user
    assert auditoria.has_view_permission(request)
    assert not any(f(request) for f in (auditoria.has_add_permission, auditoria.has_change_permission,
                                        auditoria.has_delete_permission))


@pytest.mark.parametrize('defecto', ['hash_csv', 'catalogo', 'cabecera', 'atributo', 'repetido', 'ganador', 'target', 'total'])
def test_datos_invalidos_no_publican(settings, tmp_path, catalogo, defecto):
    settings.BASE_DIR = tmp_path
    anterior = dataset(tmp_path, catalogo, [(1, 0, True)])
    cargar()
    meta = dataset(tmp_path, catalogo, [(0, 1, True)], seed=77)
    archivo = tmp_path / 'dataset_batallas.csv'
    with archivo.open(newline='') as f:
        fila = next(csv.DictReader(f))
    if defecto == 'catalogo':
        Criatura.objects.filter(pk=catalogo[-1].pk).update(salud=80)
    elif defecto == 'total':
        meta['n_combates'] += 1
    else:
        if defecto == 'cabecera':
            del fila['salud_1']
        elif defecto == 'atributo':
            fila['tipo_secundario_1'] = 'aire'
        elif defecto == 'repetido':
            fila['luchador_2_id'] = fila['luchador_1_id']
        elif defecto == 'ganador':
            fila['ganador_id'] = str(catalogo[-1].pk)
        elif defecto == 'target':
            fila['gano_primero'] = '0'
        with archivo.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(fila))
            writer.writeheader()
            writer.writerow(fila)
        meta['dataset_sha256'] = '0' * 64 if defecto == 'hash_csv' else hashlib.sha256(archivo.read_bytes()).hexdigest()
    (tmp_path / 'dataset_batallas.meta.json').write_text(json.dumps(meta))
    with pytest.raises(CommandError):
        cargar()
    assert LoteSimulacion.objects.get().pk == anterior['dataset_sha256']
    assert LoteSimulacion.objects.get().activo and CombateSimulado.objects.count() == 1


def test_rollback_tras_primer_bloque_y_lote_incompleto(settings, tmp_path, catalogo, monkeypatch):
    settings.BASE_DIR = tmp_path
    original = dataset(tmp_path, catalogo, [(0, 1, True)])
    cargar()
    dataset(tmp_path, catalogo, [(1, 2, False)] * 1001, seed=7)
    insertar = CombateSimulado.objects.bulk_create

    def fallar(hechos, batch_size):
        insertar(hechos[:batch_size], batch_size=batch_size)
        raise RuntimeError('Interrupción de carga')

    with monkeypatch.context() as m:
        m.setattr(CombateSimulado.objects, 'bulk_create', fallar)
        with pytest.raises(RuntimeError, match='Interrupción'):
            cargar()
    assert CombateSimulado.objects.count() == 1
    assert LoteSimulacion.objects.get(activo=True).pk == original['dataset_sha256']
    dataset(tmp_path, catalogo, [(0, 1, True)], seed=123)
    with pytest.raises(CommandError, match='Metadatos'):
        cargar()
    dataset(tmp_path, catalogo, [(0, 1, True)])
    CombateSimulado.objects.all().delete()
    with pytest.raises(CommandError, match='incompleto'):
        cargar()


@pytest.mark.django_db(transaction=True)
def test_dos_cargas_concurrentes(settings, tmp_path, catalogo):
    settings.BASE_DIR = tmp_path
    dataset(tmp_path, catalogo, [(0, 1, True)] * 1001)
    barrera = Barrier(2)

    def ejecutar():
        try:
            barrera.wait(timeout=10)
            return cargar().split(' · ')[0]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros = [pool.submit(ejecutar) for _ in range(2)]
        assert sorted(f.result(timeout=30) for f in futuros) == ['Cargado', 'Ya cargado']
    assert LoteSimulacion.objects.filter(activo=True).count() == 1
    assert CombateSimulado.objects.count() == 1001


def test_matchups_empates_borrado_y_ficha_sin_csv(settings, tmp_path, catalogo, client, django_assert_num_queries):
    settings.BASE_DIR = tmp_path
    a, b, c, d, e = catalogo
    duelos = [(0, 1, True)] * 8 + [(2, 0, False)] * 9 + [(0, 3, True)] * 9 + [(4, 0, True)] * 8
    dataset(tmp_path, catalogo, duelos)
    cargar()
    (tmp_path / 'dataset_batallas.csv').unlink()
    (tmp_path / 'dataset_batallas.meta.json').unlink()
    with django_assert_num_queries(3):
        respuesta = client.get(reverse('detalle', args=[a.pk]))
    m = respuesta.context['perfil']['matchups']
    assert (m['victorias'], m['n_combates']) == (26, 34)
    assert (m['counter_id'], m['counter_enfrentamientos'], m['nemesis_id']) == (c.pk, 9, e.pk)
    assert m['nemesis_tasa'] == 0
    assert reverse('detalle', args=[c.pk]) in respuesta.content.decode()
    origen = c.pk
    c.delete()
    m = obtener_matchups(a.pk)
    assert m['counter_id'] == d.pk and m['n_combates'] == 34 and m['victorias'] == 26
    h = CombateSimulado.objects.filter(luchador_1_origen_id=origen).first()
    assert h.luchador_1_id is None and not h.gano_primero
    with pytest.raises(IntegrityError, match='inmutables'), transaction.atomic():
        CombateSimulado.objects.filter(pk=h.pk).update(luchador_1_origen_id=b.pk)


def test_estados_de_muestra_en_html(settings, tmp_path, catalogo, client):
    settings.BASE_DIR = tmp_path
    url = reverse('detalle', args=[catalogo[0].pk])

    def html():
        return client.get(url).content.decode()

    assert 'Aún no se han cargado combates simulados' in html()
    dataset(tmp_path, catalogo, [(2, 1, True)])
    cargar()
    assert 'Esta criatura no participó' in html()
    duelos = [(0, 1, False)] * 7
    dataset(tmp_path, catalogo, duelos)
    cargar()
    assert 'Ningún rival alcanza los 8' in html() and '0,0 %' in html()
    duelos += [(0, 1, False)]
    dataset(tmp_path, catalogo, duelos)
    cargar()
    assert 'Único rival con muestra suficiente' in html()
    dataset(tmp_path, catalogo, duelos + [(0, 2, False)] * 8)
    cargar()
    assert 'Misma tasa (0,0 %) frente a los 2 rivales' in html()


def test_recarga_conserva_el_origen_si_se_reutiliza_una_pk(settings, tmp_path, catalogo):
    settings.BASE_DIR = tmp_path
    dataset(tmp_path, catalogo, [(0, 1, True)])
    cargar()
    rival = catalogo[1]
    pk = rival.pk
    rival.delete()
    rival.pk = pk
    rival.save(force_insert=True)
    assert 'Ya cargado' in cargar()
    hecho = CombateSimulado.objects.get()
    assert hecho.luchador_2_origen_id == pk and hecho.luchador_2_id is None

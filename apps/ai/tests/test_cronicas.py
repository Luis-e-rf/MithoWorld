import asyncio
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from unittest.mock import patch

import httpx
import pytest
from django.core.cache.backends.locmem import LocMemCache
from django.db import connections
from django.urls import reverse
from django.utils import timezone

from apps.ai import cola, services
from apps.ai.models import CronicaCombate, PresupuestoDiario
from apps.ai.narrativa import hechos_duelo, realizar_plan
from apps.game.combates import contexto_duelo, firmar_combate
from apps.game.models import CombatLog, Criatura
from backend.throttling import CloudflareThrottle

PLAN = {'lineas': [{'hecho': 'salud', 'variante': 1}, {'hecho': 'pronostico', 'variante': 2}]}


def completion(plan=PLAN, fin='stop'):
    return httpx.Response(200, json={'choices': [{'finish_reason': fin, 'message': {'content': json.dumps(plan)}}]})


@pytest.fixture(autouse=True)
def offline(settings, monkeypatch):
    settings.CRONICA_API_KEY = 'demo-offline'
    settings.CRONICA_MODELO = 'modelo:free'
    settings.CRONICA_MAX_LLAMADAS_DIA = 100
    settings.CRONICA_TIMEOUT_S = 15
    settings.CRONICA_MAX_TOKENS = 256
    settings.CRONICA_FORMATO = 'json_object'
    settings.CRONICA_REQUIRE_PARAMETERS = False
    cache = LocMemCache('cronicas-test', {})
    cache.clear()
    monkeypatch.setattr(CloudflareThrottle, 'cache', cache)
    monkeypatch.setattr(CloudflareThrottle, 'THROTTLE_RATES', {'cronica': '30/min', 'cronica_lectura': '60/min'})
    def prohibir_red(*args, **kwargs):
        pytest.fail('Se intentó usar la red en una prueba offline.')
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', prohibir_red)


@pytest.fixture
def duelo(db):
    stats = dict(ataque=70, defensa=60, velocidad=25, salud=80)
    a = Criatura.objects.create(nombre='<b>Río</b>', tipo_primario='agua', tipo_secundario='luz', **stats)
    b = Criatura.objects.create(nombre='Sol', tipo_primario='fuego', **{**stats, 'salud': 90})
    return CombatLog.objects.create(
        luchador_1=a, luchador_2=b, ganador_predicho=b, probabilidad=.875, latencia_ms=1.5,
        diferencial={'ataque': 0, 'defensa': 0, 'velocidad': 0, 'salud': -10},
        ventaja_elemental={'luchador_1': 1.5, 'luchador_2': .5}, contexto_duelo=contexto_duelo(a, b, b),
    )


def peticion(client, duelo, metodo='post', **opciones):
    url = reverse('cronica_combate', args=[duelo.pk])
    headers = opciones.pop('headers', {'X-Combate-Referencia': firmar_combate(duelo.pk)})
    return client.generic(metodo.upper(), url, headers=headers, **opciones)


def test_contrato_persistencia_y_borrado(duelo, client, settings):
    assert peticion(client, duelo, 'get').status_code == 404
    for _ in range(2):
        r = peticion(client, duelo)
        assert r.status_code == 202 and r['Retry-After'] and 'no-store' in r['Cache-Control']
        assert r.json() == {'combate_id': duelo.pk, 'estado': 'pendiente', 'lineas': [], 'reintentable': False}
    duelo.luchador_1.delete()
    Criatura.objects.filter(pk=duelo.ganador_predicho_id).update(nombre='Nombre posterior')
    assert PresupuestoDiario.objects.count() == 0
    assert cola.procesar_uno(transport=httpx.MockTransport(lambda r: completion()))
    assert not cola.procesar_uno()
    settings.CRONICA_API_KEY = ''
    lineas = peticion(client, duelo, 'get').json()['lineas']
    assert 2 == len(lineas) and 'Sol' in lineas[-1] and '87,5 %' in lineas[-1]
    assert 'Nombre posterior' not in str(lineas)
    assert peticion(client, duelo).json()['lineas'] == lineas
    assert PresupuestoDiario.objects.get().llamadas == CronicaCombate.objects.get().intentos == 1


def test_referencia_cuerpo_y_demo(duelo, client, settings):
    for cabecera in ('', 'firma_invalida', firmar_combate(duelo.pk + 1)):
        assert peticion(client, duelo, headers={'X-Combate-Referencia': cabecera}).status_code == 403
    with patch('django.core.signing.time.time', return_value=1):
        vieja = firmar_combate(duelo.pk)
    assert peticion(client, duelo, headers={'X-Combate-Referencia': vieja}).status_code == 403
    assert peticion(client, duelo, data=b'{"prompt":"texto libre"}', content_type='application/json').status_code == 400
    assert peticion(client, duelo, QUERY_STRING='prompt=texto').status_code == 400
    settings.CRONICA_API_KEY = ''
    assert peticion(client, duelo).json()['estado'] == 'no_configurada'
    assert not cola.procesar_uno()
    settings.CRONICA_API_KEY = 'demo'
    CombatLog.objects.filter(pk=duelo.pk).update(contexto_duelo=None)
    assert peticion(client, duelo).status_code == 409
    assert not CronicaCombate.objects.exists() and not PresupuestoDiario.objects.exists()


def test_throttle_y_sondeo_independientes(duelo, client, monkeypatch):
    monkeypatch.setattr(CloudflareThrottle, 'THROTTLE_RATES', {'cronica': '1/min', 'cronica_lectura': '10/min'})
    headers = {'CF-Connecting-IP': '2001:db8::1', 'X-Combate-Referencia': firmar_combate(duelo.pk)}
    def pedir(metodo='post'):
        return peticion(client, duelo, metodo, headers=headers, REMOTE_ADDR='172.18.0.2')
    assert pedir().status_code == 202
    r = pedir()
    assert r.status_code == 429 and r.json()['estado'] == 'limite_ip' and int(r['Retry-After']) > 0
    assert pedir('get').status_code == 202
    headers['CF-Connecting-IP'] = 'invalid'
    assert pedir().status_code == 202
    del headers['CF-Connecting-IP']
    assert pedir().status_code == 429


@pytest.mark.parametrize('formato,estricto', [('json_object', False), ('json_schema', True)])
def test_transporte_y_fidelidad(duelo, settings, formato, estricto):
    settings.CRONICA_FORMATO, settings.CRONICA_REQUIRE_PARAMETERS = formato, estricto
    settings.CRONICA_MAX_TOKENS = 1000
    def proveedor(req):
        datos = json.loads(req.content)
        assert str(req.url) == services.URL and req.headers['authorization'] == 'Bearer demo-offline'
        assert datos['max_tokens'] == 512 and req.extensions['timeout']['connect'] == 3
        assert datos['model'] == 'modelo:free' and datos['provider']['require_parameters'] is estricto
        assert datos['response_format']['type'] == formato
        assert ('json_schema' in datos['response_format']) == estricto
        usuario = json.loads(datos['messages'][1]['content'])
        assert usuario['ganador'] == 'L2' and usuario['luchadores']['L1']['tipos'] == ['agua', 'luz']
        assert usuario['diferencial_L1_menos_L2']['salud'] == -10
        assert 'Río' not in str(usuario) and 'Sol' not in str(usuario) and usuario['factor_L2'] == .5
        return completion()
    lineas = asyncio.run(services.generar_cronica(duelo, transport=httpx.MockTransport(proveedor)))
    assert 'Sol' in lineas[0] and 'Sol' in lineas[1]
    # El mismo plan cambia de redacción en el siguiente combate, sin cambiar el ganador.
    duelo.pk += 1
    siguientes = realizar_plan(PLAN, duelo, hechos_duelo(duelo))
    assert lineas != siguientes and 'Sol' in siguientes[-1]


def test_empate_y_factores_segun_lado(duelo):
    hechos = hechos_duelo(duelo)
    plan = {'lineas': [{'hecho': hecho, 'variante': 0} for hecho in ('tipos', 'velocidad', 'elemento', 'pronostico')]}
    tipos, empate, elemental, cierre = realizar_plan(plan, duelo, hechos)
    assert 'agua y luz' in tipos and 'fuego' in tipos
    assert '25' in empate and 'velocidad' in empate
    assert '×1,5' in elemental and '×0,5' in elemental
    assert 'Sol' in cierre and '87,5 %' in cierre


@pytest.mark.parametrize('respuesta', [
    httpx.Response(401), httpx.Response(402), httpx.Response(429), httpx.Response(503),
    httpx.Response(200, content=b'invalido'), httpx.Response(200, content=b'x' * 32769),
    completion(fin='length'), completion({}), completion({'lineas': ['Sol perdió', 'fin']}),
    completion({'lineas': [PLAN['lineas'][1]] * 2}),
    completion({'lineas': [{'hecho': 'herida', 'variante': 1}, PLAN['lineas'][1]]}),
    completion({'lineas': [{'hecho': 'salud', 'variante': True}, PLAN['lineas'][1]]}),
])
def test_respuestas_rechazadas(duelo, respuesta):
    with pytest.raises(services.ErrorProveedor):
        asyncio.run(services.generar_cronica(duelo, transport=httpx.MockTransport(lambda r: respuesta)))


def test_timeout_total_y_dos_intentos_manuales(duelo, settings):
    settings.CRONICA_TIMEOUT_S = .02
    async def lento(req):
        await asyncio.Event().wait()
    for intento in (1, 2):
        assert cola.solicitar(duelo.pk).status == 202
        assert cola.procesar_uno(transport=httpx.MockTransport(lento))
        r = cola.consultar(duelo.pk)
        assert r.status == 503 and r.reintentable == (intento == 1)
        assert cola.solicitar(duelo.pk).status == 503
        assert not cola.procesar_uno()
        CronicaCombate.objects.update(disponible_en=timezone.now() - timedelta(seconds=1))
    assert cola.solicitar(duelo.pk).status == 503 and PresupuestoDiario.objects.get().llamadas == 2


def test_abandono_y_cola_limitada(duelo, monkeypatch):
    monkeypatch.setattr(cola, 'MAX_COLA', 1)
    assert cola.solicitar(duelo.pk).status == 202
    original = duelo.pk
    duelo.pk = None
    duelo.save()
    assert cola.solicitar(duelo.pk).estado == 'cola_llena'
    trabajo = cola._reclamar()
    assert trabajo.intentos == 1 and trabajo.pk == original
    CronicaCombate.objects.update(vence_en=timezone.now() - timedelta(seconds=1))
    assert cola.consultar(original).status == 503
    assert not cola.procesar_uno()
    assert cola.solicitar(original).status == 202
    assert cola.procesar_uno(transport=httpx.MockTransport(lambda r: completion()))
    assert CronicaCombate.objects.get().intentos == 2


@pytest.mark.django_db(transaction=True)
def test_respuesta_tardia_no_sobrescribe_el_reintento(duelo):
    recibido, liberar = Event(), Event()

    def proveedor_tardio(req):
        recibido.set()
        assert liberar.wait(timeout=10)
        return completion()

    def primer_consumidor():
        try:
            return cola.procesar_uno(transport=httpx.MockTransport(proveedor_tardio))
        finally:
            connections.close_all()

    cola.solicitar(duelo.pk)
    with ThreadPoolExecutor(1) as pool:
        primero = pool.submit(primer_consumidor)
        try:
            assert recibido.wait(timeout=10)
            assert cola.consultar(duelo.pk).estado == 'procesando'
            CronicaCombate.objects.update(vence_en=timezone.now() - timedelta(seconds=1))
            assert cola.solicitar(duelo.pk).status == 202
            otro_plan = {'lineas': [{'hecho': 'elemento', 'variante': 1}, PLAN['lineas'][1]]}
            assert cola.procesar_uno(transport=httpx.MockTransport(lambda r: completion(otro_plan)))
        finally:
            liberar.set()
        assert primero.result(timeout=10)
    assert '×' in cola.consultar(duelo.pk).lineas[0]
    assert PresupuestoDiario.objects.get().llamadas == 2


@pytest.mark.django_db(transaction=True)
def test_doble_solicitud_y_ultima_plaza_diaria(duelo, settings):
    settings.CRONICA_MAX_LLAMADAS_DIA = 1
    def paralelo(f):
        barrera = Barrier(2)
        def ejecutar():
            try:
                barrera.wait(timeout=10)
                return f()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            futuros = [pool.submit(ejecutar) for _ in range(2)]
            return [t.result(timeout=10) for t in futuros]

    assert paralelo(lambda: cola.solicitar(duelo.pk).status) == [202, 202]
    assert CronicaCombate.objects.count() == 1
    duelo.pk = None
    duelo.save()
    assert cola.solicitar(duelo.pk).status == 202
    transporte = httpx.MockTransport(lambda r: completion())
    assert sorted(paralelo(lambda: cola.procesar_uno(transport=transporte))) == [False, True]
    assert not cola.procesar_uno(transport=transporte)
    assert PresupuestoDiario.objects.get().llamadas == 1
    assert cola.consultar(duelo.pk).status == 429 and cola.solicitar(duelo.pk).espera > 0


def test_comando_sin_ml(settings):
    programa = """
import runpy, sys
def auditar(evento, args):
    if evento == 'open' and str(args[0]).endswith('.pkl'):
        raise AssertionError('Lectura de un pipeline desde el consumidor')
sys.addaudithook(auditar)
sys.argv = ['manage.py', 'procesar_cronicas', '--once']
runpy.run_path('manage.py', run_name='__main__')
assert not any(n.startswith(('apps.ml', 'sklearn', 'pandas', 'joblib', 'numpy')) for n in sys.modules)
"""
    entorno = {**os.environ, 'CRONICA_API_KEY': ''}
    entorno.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c', programa], cwd=settings.BASE_DIR, env=entorno, check=True, timeout=15)

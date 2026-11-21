from unittest import mock

import pytest
from django.core.cache.backends.locmem import LocMemCache
from django.urls import reverse
from rest_framework import status

import apps.ml.views as views
from apps.game.models import CombatLog, Criatura
from apps.ml.services import predecir_combate
from apps.ml.throttling import OraculoThrottle


@pytest.fixture(autouse=True)
def cache_de_throttling_aislada(monkeypatch):
    cache = LocMemCache('pruebas-oraculo', {})
    cache.clear()
    monkeypatch.setattr(OraculoThrottle, 'cache', cache)


@pytest.fixture
def criaturas_en_bd(db):
    c1 = Criatura.objects.create(
        nombre="Testeon", tipo_primario="fuego", tipo_secundario=None,
        salud=50, ataque=90, defensa=40, velocidad=95,
        descripcion="Criatura de prueba",
    )
    c2 = Criatura.objects.create(
        nombre="Testalia", tipo_primario="luz", tipo_secundario=None,
        salud=80, ataque=70, defensa=65, velocidad=70,
        descripcion="Criatura de prueba",
    )
    return c1, c2


def _falso_encoder():
    encoder = mock.Mock()
    encoder.transform.return_value = [0]
    return encoder


def _falso_modelo(prediccion, probabilidad, clases=None):
    modelo = mock.Mock()
    modelo.predict.return_value = [prediccion]
    modelo.predict_proba.return_value = [probabilidad]
    if clases is not None:
        modelo.classes_ = clases
    return modelo


@pytest.mark.django_db
def test_prediccion_oraculo_confianza_usa_clase_predicha(client, criaturas_en_bd):
    c1, c2 = criaturas_en_bd
    # La clase predicha es 0 (gana c2), pero su probabilidad (0.6) es la MENOR
    # del vector. max() devolvería 0.8 (clase 1), que NO corresponde al ganador.
    modelo = _falso_modelo(prediccion=0, probabilidad=[0.6, 0.8], clases=[0, 1])

    with mock.patch.object(
        views, "get_oraculo_models",
        return_value=(modelo, _falso_encoder()),
    ):
        respuesta = client.post(
            reverse("predecir_combate"),
            data={"luchador_1_id": c1.id, "luchador_2_id": c2.id},
            content_type="application/json",
        )

    assert respuesta.status_code == status.HTTP_200_OK
    resultado = respuesta.json()["resultado"]
    assert resultado["ganador_id"] == c2.id  # clase 0
    probabilidad_float = float(resultado["probabilidad"].rstrip("%")) / 100
    assert probabilidad_float == 0.6  # probabilidad de la clase predicha, no el max


@pytest.mark.django_db
def test_prediccion_oraculo_clamp_porcentaje_fuera_de_rango(client, criaturas_en_bd):
    c1, c2 = criaturas_en_bd
    # Clase predicha 1 (gana c1), probabilidad fuera de rango → debe clampearse a 1.0.
    modelo = _falso_modelo(prediccion=1, probabilidad=[0.2, 1.4], clases=[0, 1])

    with mock.patch.object(
        views, "get_oraculo_models",
        return_value=(modelo, _falso_encoder()),
    ):
        respuesta = client.post(
            reverse("predecir_combate"),
            data={"luchador_1_id": c1.id, "luchador_2_id": c2.id},
            content_type="application/json",
        )

    assert respuesta.status_code == status.HTTP_200_OK
    resultado = respuesta.json()["resultado"]
    assert resultado["ganador_id"] == c1.id
    probabilidad_float = float(resultado["probabilidad"].rstrip("%")) / 100
    assert probabilidad_float == 1.0


@pytest.mark.django_db
def test_oraculo_responde_503_cuando_modelo_ausente(client, criaturas_en_bd, monkeypatch):
    c1, c2 = criaturas_en_bd
    falta = FileNotFoundError("no existe modelo_combate.pkl")

    # Estado limpio del módulo, restaurado por monkeypatch al terminar.
    monkeypatch.setattr(views, "MODELO_COMBATE", None)
    monkeypatch.setattr(views, "ENCODER_TIPOS", None)
    monkeypatch.setattr(views, "_ORACULO_CARGADO", False)

    with mock.patch.object(views.joblib, "load", side_effect=falta) as mock_load:
        respuesta = client.post(
            reverse("predecir_combate"),
            data={"luchador_1_id": c1.id, "luchador_2_id": c2.id},
            content_type="application/json",
        )
        assert respuesta.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        # El primer joblib.load falla; el 2º artefacto ni se intenta.
        assert mock_load.call_count == 1

        # Segunda llamada NO reintenta la carga (1 sola vez por proceso).
        views.get_oraculo_models()
        assert mock_load.call_count == 1


@pytest.mark.django_db
def test_oraculo_body_invalido_devuelve_400_sin_modelos(client, criaturas_en_bd):
    c1, c2 = criaturas_en_bd

    # Sin mock de modelos: aunque los artefactos existan o falten, un body
    # sin IDs debe devolver 400 ANTES de invocar get_oraculo_models().
    with mock.patch.object(views, "get_oraculo_models") as mock_get:
        respuesta = client.post(
            reverse("predecir_combate"),
            data={},  # sin luchadores
            content_type="application/json",
        )

    assert respuesta.status_code == status.HTTP_400_BAD_REQUEST
    mock_get.assert_not_called()


@pytest.mark.django_db
def test_oraculo_carga_modelos_una_sola_vez(client, criaturas_en_bd, monkeypatch):
    c1, c2 = criaturas_en_bd
    monkeypatch.setattr(views, "MODELO_COMBATE", None)
    monkeypatch.setattr(views, "ENCODER_TIPOS", None)
    monkeypatch.setattr(views, "_ORACULO_CARGADO", False)

    modelo = _falso_modelo(prediccion=0, probabilidad=[0.8, 0.2], clases=[0, 1])
    encoder = _falso_encoder()

    def _carga_falsa(ruta):
        # 1ª llamada → modelo; 2ª llamada → encoder.
        if "encoder" in str(ruta):
            return encoder
        return modelo

    with mock.patch.object(views.joblib, "load", side_effect=_carga_falsa) as mock_load:
        # Primer POST exitoso dispara 2 joblib.load (modelo + encoder).
        respuesta = client.post(
            reverse("predecir_combate"),
            data={"luchador_1_id": c1.id, "luchador_2_id": c2.id},
            content_type="application/json",
        )
        assert respuesta.status_code == status.HTTP_200_OK
        assert mock_load.call_count == 2

        # Segundo POST: ya cacheado, 0 llamadas adicionales.
        respuesta = client.post(
            reverse("predecir_combate"),
            data={"luchador_1_id": c1.id, "luchador_2_id": c2.id},
            content_type="application/json",
        )
        assert respuesta.status_code == status.HTTP_200_OK
        assert mock_load.call_count == 2


@pytest.mark.django_db
def test_prediccion_oraculo_estructura_valida(client, criaturas_en_bd):
    c1, c2 = criaturas_en_bd
    modelo = _falso_modelo(prediccion=0, probabilidad=[0.8, 0.2], clases=[0, 1])

    with mock.patch.object(
        views, "get_oraculo_models",
        return_value=(modelo, _falso_encoder()),
    ):
        respuesta = client.post(
            reverse("predecir_combate"),
            data={"luchador_1_id": c1.id, "luchador_2_id": c2.id},
            content_type="application/json",
        )

    assert respuesta.status_code == status.HTTP_200_OK
    resultado = respuesta.json()["resultado"]
    assert set(resultado.keys()) == {"ganador_id", "ganador_nombre", "probabilidad", "mensaje"}
    assert resultado["ganador_id"] == c2.id
    assert resultado["ganador_nombre"] == c2.nombre


def test_servicio_desglosa_el_combate_en_orden_de_entrada():
    primero = Criatura(tipo_primario='fuego', ataque=90, defensa=40, velocidad=95)
    segundo = Criatura(tipo_primario='tierra', ataque=70, defensa=65, velocidad=70)
    modelo = _falso_modelo(prediccion=0, probabilidad=[0.2, 0.8], clases=[1, 0])

    prediccion = predecir_combate(primero, segundo, modelo, _falso_encoder())

    assert prediccion.ganador is segundo
    assert prediccion.probabilidad == 0.8
    assert prediccion.diferencial == {'ataque': 20, 'defensa': -25, 'velocidad': 25}
    assert prediccion.ventaja_elemental == {'luchador_1': 1.5, 'luchador_2': 1.0}


def test_throttling_del_oraculo_por_ip(client, criaturas_en_bd, monkeypatch):
    monkeypatch.setattr(OraculoThrottle, 'THROTTLE_RATES', {'oraculo': '2/min'})
    primero, segundo = criaturas_en_bd
    datos = {'luchador_1_id': primero.pk, 'luchador_2_id': segundo.pk}
    modelo = _falso_modelo(prediccion=1, probabilidad=[0.2, 0.8], clases=[0, 1])

    def predecir(ip):
        return client.post(
            reverse('predecir_combate'), data=datos, content_type='application/json', REMOTE_ADDR=ip,
        )

    with mock.patch.object(views, 'get_oraculo_models', return_value=(modelo, _falso_encoder())):
        primera = predecir('192.0.2.1')
        assert primera.status_code == 200
        assert primera.json()['metricas'] == {
            'diferencial': {'ataque': 20, 'defensa': -25, 'velocidad': 25},
            'ventaja_elemental': {'luchador_1': 1.0, 'luchador_2': 1.0},
        }
        assert predecir('192.0.2.1').status_code == 200
        limitada = predecir('192.0.2.1')
        assert limitada.status_code == 429
        assert int(limitada['Retry-After']) > 0
        assert modelo.predict_proba.call_count == 2
        assert predecir('192.0.2.2').status_code == 200
    assert not CombatLog.objects.exists()


@pytest.mark.parametrize('confianza', [float('nan'), float('inf'), float('-inf')])
def test_oraculo_responde_503_con_probabilidad_no_finita(client, criaturas_en_bd, confianza):
    primero, segundo = criaturas_en_bd
    modelo = _falso_modelo(prediccion=1, probabilidad=[0.2, confianza], clases=[0, 1])
    with mock.patch.object(views, 'get_oraculo_models', return_value=(modelo, _falso_encoder())):
        respuesta = client.post(
            reverse('predecir_combate'),
            data={'luchador_1_id': primero.pk, 'luchador_2_id': segundo.pk},
            content_type='application/json',
        )

    assert respuesta.status_code == 503
    assert respuesta.json() == {'detail': 'El modelo devolvió una probabilidad no finita.'}


@pytest.mark.parametrize(('origen', 'cabecera', 'identidad'), [
    ('172.18.0.2', '203.0.113.7', '203.0.113.7'),
    ('fd00::2', '2001:0db8::1', '2001:db8::1'),
    ('172.18.0.2', None, '172.18.0.2'),
    ('172.18.0.2', '203.0.113.7, 203.0.113.8', '172.18.0.2'),
    ('172.18.0.2', 'fe80::1%eth0', '172.18.0.2'),
    ('8.8.8.8', '203.0.113.7', '8.8.8.8'),
    ('invalida', '203.0.113.7', 'invalida'),
])
def test_identidad_del_oraculo_tras_el_proxy(rf, origen, cabecera, identidad):
    headers = {'CF-Connecting-IP': cabecera} if cabecera is not None else {}
    peticion = rf.get('/', REMOTE_ADDR=origen, headers=headers)
    assert OraculoThrottle().get_ident(peticion) == identidad

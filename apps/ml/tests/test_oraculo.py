from unittest import mock

import pytest
from django.urls import reverse
from rest_framework import status

import apps.ml.views as views
from apps.game.models import Criatura


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
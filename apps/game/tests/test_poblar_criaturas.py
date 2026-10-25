import csv
import io
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.game.models import Criatura

ENCABEZADO_CSV = [
    "Nombre", "Tipo Primario", "Tipo Secundario", "Salud", "Ataque",
    "Defensa", "Velocidad", "Descripcion", "NombreArchivo",
]

FILAS_CSV = [
    ["Testeon", "fuego", "aire", "50", "90", "40", "95", "Criatura de prueba", "1.png"],
    ["Testalia", "luz", "", "80", "70", "65", "70", "Criatura de prueba", "2.png"],
]

PNG_MINIMO = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def escenario(tmp_path):
    """Escenario aislado: CSV + carpeta de imagenes en un directorio temporal."""
    (tmp_path / "criaturas.csv").write_text(
        _csv_a_texto(FILAS_CSV), encoding="utf-8"
    )
    carpeta_imagenes = tmp_path / "imagenes_semilla"
    carpeta_imagenes.mkdir()
    (carpeta_imagenes / "1.png").write_bytes(PNG_MINIMO)

    with override_settings(BASE_DIR=tmp_path, MEDIA_ROOT=tmp_path / "media"):
        yield tmp_path


def _csv_a_texto(filas):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(ENCABEZADO_CSV)
    writer.writerows(filas)
    return buffer.getvalue()


@pytest.mark.django_db
def test_poblar_criaturas_crea_registros(escenario):
    call_command("poblar_criaturas")

    assert Criatura.objects.count() == 2
    criatura = Criatura.objects.get(nombre="Testeon")
    assert criatura.tipo_primario == "fuego"
    assert criatura.tipo_secundario == "aire"
    assert criatura.salud == 50
    assert criatura.ataque == 90
    assert criatura.defensa == 40
    assert criatura.velocidad == 95


@pytest.mark.django_db
def test_poblar_criaturas_es_idempotente(escenario):
    call_command("poblar_criaturas")
    cantidad_primera = Criatura.objects.count()
    assert cantidad_primera == 2

    # Verificar que el directorio de imágenes ya tiene un archivo copiado.
    media_criaturas = escenario / "media" / "criaturas"
    archivos_primera = sorted(p.name for p in media_criaturas.iterdir()) if media_criaturas.exists() else []
    assert len(archivos_primera) == 1  # solo "1.png" de Testeon

    call_command("poblar_criaturas")

    # Sin datos nuevos: el conteo de filas no varía.
    assert Criatura.objects.count() == cantidad_primera

    # Idempotencia de ARCHIVOS: no se generan copias (img_1, img_2, ...).
    archivos_segunda = sorted(p.name for p in media_criaturas.iterdir()) if media_criaturas.exists() else []
    assert archivos_segunda == archivos_primera


@pytest.mark.django_db
def test_poblar_criaturas_sincroniza_stats_al_alterar_csv(escenario):
    # Primera corrida con stats iniciales (Testeon: HP 50).
    call_command("poblar_criaturas")
    assert Criatura.objects.get(nombre="Testeon").salud == 50

    # Reescribir el CSV con un stat distinto para Testeon (HP 99).
    filas_alteradas = [
        ["Testeon", "fuego", "aire", "99", "90", "40", "95", "Criatura de prueba", "1.png"],
        ["Testalia", "luz", "", "80", "70", "65", "70", "Criatura de prueba", "2.png"],
    ]
    (escenario / "criaturas.csv").write_text(
        _csv_a_texto(filas_alteradas), encoding="utf-8"
    )

    call_command("poblar_criaturas")

    # update_or_create debe haber sincronizado el stat desde el CSV.
    assert Criatura.objects.get(nombre="Testeon").salud == 99
    assert Criatura.objects.count() == 2  # no crea filas duplicadas


@pytest.mark.django_db
def test_poblar_criaturas_maneja_imagenes_faltantes(escenario):
    salida = io.StringIO()

    # No debe lanzar excepción no controlada
    call_command("poblar_criaturas", stdout=salida)

    # Ambas criaturas se registran aunque "2.png" no exista en disco
    assert Criatura.objects.count() == 2

    # La imagen presente se asocia a su criatura
    assert Criatura.objects.get(nombre="Testeon").imagen.name == "criaturas/1.png"

    # La faltante se omite con warning en el log
    assert "Imagen no encontrada en disco: 2.png" in salida.getvalue()

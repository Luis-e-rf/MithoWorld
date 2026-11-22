import pytest

from apps.analytics.services import obtener_perfil_criatura
from apps.game.models import Criatura


pytestmark = pytest.mark.django_db


def criatura(nombre, ataque, defensa=0, velocidad=0, salud=0, tipo='fuego'):
    return Criatura.objects.create(
        nombre=nombre, tipo_primario=tipo, ataque=ataque, defensa=defensa,
        velocidad=velocidad, salud=salud,
    )


def test_ranking_y_percentil_global_con_empates():
    criaturas = [
        criatura('A', 10), criatura('B', 15, salud=5),
        criatura('C', 12, defensa=3, velocidad=5, tipo='agua'), criatura('D', 30),
    ]
    perfiles = [obtener_perfil_criatura(c.pk) for c in criaturas]
    assert [p['score_total'] for p in perfiles] == [10, 20, 20, 30]
    assert [p['puesto_global'] for p in perfiles] == [4, 2, 2, 1]
    assert [p['percentil_global'] for p in perfiles] == pytest.approx([0, 1 / 3, 1 / 3, 1])
    assert all(p['n_catalogo'] == 4 for p in perfiles)


def test_catalogo_unitario_y_escala_cero(client):
    unica = criatura('Única', 42, defensa=63, velocidad=12, salud=15)
    respuesta = client.get(f'/criatura/{unica.pk}/')
    perfil = respuesta.context['perfil']
    assert perfil['puesto_global'] == perfil['n_catalogo'] == perfil['n_elemento'] == 1
    assert perfil['percentil_global'] == 0
    assert 'Sin comparación' in respuesta.content.decode()
    assert len(perfil['filas']) == 4
    for fila in perfil['filas']:
        assert fila['valor'] == fila['media']
        assert fila['delta'] == fila['ancho'] == 0


def test_medias_y_diferencias_por_elemento():
    objetivo = criatura('A', 30, 50, 70, 100)
    criatura('B', 50, 50, 30, 81)
    criatura('C', 200, 200, 200, 200, tipo='aire')
    perfil = obtener_perfil_criatura(objetivo.pk)
    assert perfil['n_elemento'] == 2
    stats = ['ataque', 'defensa', 'velocidad', 'salud']
    assert [perfil[f'media_{s}'] for s in stats] == [40, 50, 50, 90.5]
    assert [perfil[f'delta_{s}'] for s in stats] == [-10, 0, 20, 9.5]

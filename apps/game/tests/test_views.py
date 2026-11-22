from django.test import override_settings
from django.urls import resolve, reverse

from apps.game.models import Criatura
from apps.game.views import arena_view


def test_arena_renderiza_desde_game(client):
    url = reverse('arena')
    assert url == '/arena/'
    assert resolve(url).func is arena_view

    respuesta = client.get(url)

    assert respuesta.status_code == 200
    assert 'arena.html' in [template.name for template in respuesta.templates]


@override_settings(DEBUG=False)
def test_detalle_analitico_sin_imagen_y_presupuesto_sql(db, client, django_assert_num_queries):
    stats = dict(tipo_primario='agua', ataque=50, defensa=50, velocidad=50, salud=50)
    objetivo = Criatura.objects.create(nombre='Nereo', **stats)
    # Desviaciones de -1/21 y +1/21. Ambas se presentan como cero.
    Criatura.objects.bulk_create([Criatura(nombre=f'Par {n}', **stats) for n in range(19)])
    Criatura.objects.create(nombre='Otro', **{**stats, 'ataque': 51, 'defensa': 49})
    url = reverse('detalle', kwargs={'id': objetivo.pk})
    assert url == f'/criatura/{objetivo.pk}/'
    with django_assert_num_queries(2):
        respuesta = client.get(url)
    assert respuesta.status_code == 200
    assert 'detalle.html' in [t.name for t in respuesta.templates]
    html = respuesta.content.decode()
    assert '<img ' not in html and '<span aria-hidden="true">N</span>' in html
    assert 'Comparación con Agua' in html
    assert html.count('<span>0,0</span>') == 4
    assert all(f['ancho'] == 0 for f in respuesta.context['perfil']['filas'])

    with django_assert_num_queries(1):
        assert client.get(reverse('detalle', kwargs={'id': 0})).status_code == 404

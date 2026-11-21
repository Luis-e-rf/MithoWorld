from django.urls import resolve, reverse

from apps.game.views import arena_view


def test_arena_renderiza_desde_game(client):
    url = reverse('arena')
    assert url == '/arena/'
    assert resolve(url).func is arena_view

    respuesta = client.get(url)

    assert respuesta.status_code == 200
    assert 'arena.html' in [template.name for template in respuesta.templates]

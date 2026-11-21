import pytest
from django.contrib import admin

from apps.game.models import CombatLog, Criatura


@pytest.mark.django_db
def test_combat_log_conserva_el_historial_al_borrar_luchadores():
    stats = dict(tipo_primario='agua', ataque=70, defensa=65, velocidad=70, salud=80)
    primero = Criatura.objects.create(nombre='Primero', **stats)
    segundo = Criatura.objects.create(nombre='Segundo', **stats)
    combate = CombatLog.objects.create(
        luchador_1=primero, luchador_2=segundo, ganador_predicho=segundo,
        probabilidad=0.75, ventaja_elemental={'luchador_1': 1.0, 'luchador_2': 1.0},
        diferencial={'ataque': 0, 'defensa': 0, 'velocidad': 0}, latencia_ms=1.25,
    )

    segundo.delete()
    combate.refresh_from_db()
    assert combate.luchador_1_id == primero.pk
    assert combate.luchador_2_id is None
    assert combate.ganador_predicho_id is None

    primero.delete()
    combate.refresh_from_db()
    assert combate.luchador_1_id is None
    assert combate.probabilidad == 0.75
    assert combate.ventaja_elemental == {'luchador_1': 1.0, 'luchador_2': 1.0}
    assert combate.diferencial == {'ataque': 0, 'defensa': 0, 'velocidad': 0}
    assert combate.latencia_ms == 1.25
    assert combate.creado_en is not None
    assert admin.site.is_registered(CombatLog)

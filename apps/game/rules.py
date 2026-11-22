"""Reglas v2 del combate. Cada cruce elemental ausente recibe el factor neutro."""

VENTAJAS = {
    'fuego': {'tierra': 1.5, 'plasma': 0.5, 'agua': 0.5},
    'agua': {'fuego': 1.5, 'tierra': 1.5, 'aire': 0.5},
    'tierra': {'plasma': 1.5, 'aire': 0.5, 'agua': 0.5},
    'aire': {'tierra': 1.5, 'fuego': 0.5, 'oscuridad': 0.5},
    'luz': {'oscuridad': 2.0, 'plasma': 0.5},
    'oscuridad': {'luz': 0.5, 'aire': 1.5},
    'plasma': {'agua': 1.5, 'luz': 1.5, 'tierra': 0.5},
}


def normalizar_tipos(primario, secundario):
    primario = (primario or '').strip().lower()
    secundario = (secundario or '').strip().lower()
    if not primario:
        raise ValueError('El tipo primario es obligatorio.')
    return primario, '' if secundario == primario else secundario


def _pesos(criatura):
    primario, secundario = normalizar_tipos(criatura.tipo_primario, criatura.tipo_secundario)
    return [(primario, 2), (secundario, 1)] if secundario else [(primario, 3)]


def multiplicador(atacante, defensor):
    ataque, defensa = _pesos(atacante), _pesos(defensor)
    return sum(
        peso_a * peso_d * VENTAJAS.get(a, {}).get(d, 1.0)
        for a, peso_a in ataque for d, peso_d in defensa
    ) / 9


def score_base(atacante, defensor):
    return (atacante.ataque * multiplicador(atacante, defensor)
            + 0.5 * atacante.velocidad + 0.25 * atacante.salud - 0.2 * defensor.defensa)

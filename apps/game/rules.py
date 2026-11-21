"""Multiplicadores ofensivos entre tipos primarios. Los cruces ausentes son neutros."""

VENTAJAS = {
    'fuego': {'tierra': 1.5, 'plasma': 0.5, 'agua': 0.5},
    'agua': {'fuego': 1.5, 'tierra': 1.5, 'aire': 0.5},
    'tierra': {'plasma': 1.5, 'aire': 0.5, 'agua': 0.5},
    'aire': {'tierra': 1.5, 'fuego': 0.5, 'oscuridad': 0.5},
    'luz': {'oscuridad': 2.0, 'plasma': 0.5},
    'oscuridad': {'luz': 0.5, 'aire': 1.5},
    'plasma': {'agua': 1.5, 'luz': 1.5, 'tierra': 0.5},
}

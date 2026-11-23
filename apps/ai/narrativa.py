"""Hechos disponibles para el narrador y realización en español del plan validado."""
import math

from apps.game.catalog import STATS
from apps.game.models import Criatura

VERSION_PROMPT = 1
HECHOS = (*STATS, 'tipos', 'elemento', 'pronostico')
TIPOS = dict(Criatura.TIPOS)
SUPERIOR = (
    '{mayor} aventaja a {menor} en {stat} por {delta} puntos.',
    'En {stat}, {mayor} marca {alto} frente a los {bajo} de {menor}.',
    'La diferencia de {stat} favorece a {mayor}: {delta} puntos sobre {menor}.',
    '{mayor} parte con {alto} puntos de {stat} y {menor} con {bajo}.',
)
IGUAL = (
    'En {stat}, ambos parten del mismo valor: {alto}.',
    'Los {alto} puntos de {stat} de cada rival dejan ese apartado igualado.',
    '{primero} y {segundo} llegan a la par en {stat}, con {alto} puntos.',
    'La comparación de {stat} termina en tablas: {alto} por lado.',
)
AFINIDAD = (
    '{primero} entra en el duelo con afinidad {tipo1} y {segundo} con {tipo2}.',
    'El cruce enfrenta los tipos de {primero} ({tipo1}) y {segundo} ({tipo2}).',
    'Por un lado, {primero} con {tipo1}. Por el otro, {segundo} con {tipo2}.',
    'En este emparejamiento, {primero} representa {tipo1} y {segundo}, {tipo2}.',
)
ELEMENTAL = (
    'Al atacar, las reglas asignan ×{m1} a {primero} y ×{m2} a {segundo}.',
    'El cruce elemental deja estos factores ofensivos: {primero} ×{m1} y {segundo} ×{m2}.',
    '{primero} cuenta con un factor elemental de ×{m1}. A la inversa, {segundo} tiene ×{m2}.',
    'Por afinidad elemental, el ataque de {primero} recibe ×{m1} y el de {segundo}, ×{m2}.',
)
CIERRE = (
    'El Oráculo pronostica la victoria de {ganador} con un {confianza} de confianza.',
    'Con un {confianza} de confianza, el modelo se inclina por {ganador}.',
    'Para el Oráculo, {ganador} parte como favorito con una confianza del {confianza}.',
    'El pronóstico final señala a {ganador}. La confianza del modelo es del {confianza}.',
)


class DatosInvalidos(ValueError):
    pass


def hechos_duelo(combate):
    contexto = combate.contexto_duelo
    try:
        if type(contexto['version']) is not int or contexto['version'] != 1 or contexto['ganador'] not in ('L1', 'L2'):
            raise DatosInvalidos
        a, b = contexto['luchadores']
        ganador = a if contexto['ganador'] == 'L1' else b
        if a['id'] == b['id'] or combate.ganador_predicho_id not in (None, ganador['id']):
            raise DatosInvalidos
        luchadores = {}
        for lado, c in zip(('L1', 'L2'), (a, b), strict=True):
            if not isinstance(c['nombre'], str) or not c['nombre'].strip():
                raise DatosInvalidos
            if not isinstance(c['tipo_primario'], str) or not c['tipo_primario'].strip():
                raise DatosInvalidos
            if any(type(c[stat]) is not int for stat in STATS):
                raise DatosInvalidos
            # El modelo solo recibe categorías conocidas y alias, nunca nombres editables.
            luchadores[lado] = {stat: c[stat] for stat in STATS}
            luchadores[lado]['tipos'] = [
                TIPOS.get(tipo, 'otro').lower() for tipo in (c['tipo_primario'], c['tipo_secundario']) if tipo
            ]
        diferencial = {stat: a[stat] - b[stat] for stat in STATS}
        if diferencial != combate.diferencial:
            raise DatosInvalidos
        factores = [combate.ventaja_elemental[f'luchador_{i}'] for i in (1, 2)]
        if not all(type(f) in (int, float) and math.isfinite(f) and f > 0 for f in factores):
            raise DatosInvalidos
        if not 0 <= combate.probabilidad <= 1:
            raise DatosInvalidos
        return {'luchadores': luchadores, 'diferencial_L1_menos_L2': diferencial,
                'factor_L1': factores[0], 'factor_L2': factores[1], 'ganador': contexto['ganador'],
                'confianza': combate.probabilidad}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise DatosInvalidos('Instantánea incompleta o incompatible.') from exc


def realizar_plan(plan, combate, hechos):
    if not isinstance(plan, dict) or set(plan) != {'lineas'}:
        raise DatosInvalidos('Plan inválido.')
    lineas = plan['lineas']
    if not isinstance(lineas, list) or not 2 <= len(lineas) <= 4:
        raise DatosInvalidos('Longitud de crónica inválida.')
    primero, segundo = [' '.join(c['nombre'].split()) for c in combate.contexto_duelo['luchadores']]
    a, b = (hechos['luchadores'][lado] for lado in ('L1', 'L2'))
    datos = {
        'primero': primero, 'segundo': segundo, 'tipo1': ' y '.join(a['tipos']), 'tipo2': ' y '.join(b['tipos']),
        'm1': f"{hechos['factor_L1']:.2f}".rstrip('0').rstrip('.').replace('.', ','),
        'm2': f"{hechos['factor_L2']:.2f}".rstrip('0').rstrip('.').replace('.', ','),
        'ganador': primero if hechos['ganador'] == 'L1' else segundo,
        'confianza': f"{hechos['confianza']:.1%}".replace('.', ',').replace('%', ' %'),
    }
    usadas = set()
    narracion = []
    for i, linea in enumerate(lineas):
        if not isinstance(linea, dict) or set(linea) != {'hecho', 'variante'}:
            raise DatosInvalidos('Campos de línea inválidos.')
        hecho, variante = linea['hecho'], linea['variante']
        if hecho not in HECHOS or hecho in usadas or type(variante) is not int or not 0 <= variante <= 3:
            raise DatosInvalidos('Hecho o variante inadmisible.')
        if (hecho == 'pronostico') != (i == len(lineas) - 1):
            raise DatosInvalidos('Cierre inválido.')
        usadas.add(hecho)
        if hecho in STATS:
            delta = hechos['diferencial_L1_menos_L2'][hecho]
            variantes = SUPERIOR if delta else IGUAL
            datos.update(stat=hecho, mayor=primero if delta > 0 else segundo,
                         menor=segundo if delta > 0 else primero, delta=abs(delta),
                         alto=max(a[hecho], b[hecho]), bajo=min(a[hecho], b[hecho]))
        else:
            variantes = {'tipos': AFINIDAD, 'elemento': ELEMENTAL, 'pronostico': CIERRE}[hecho]
        # Una misma selección del proveedor alterna la redacción entre duelos consecutivos.
        narracion.append(variantes[(variante + combate.pk) % len(variantes)].format(**datos))
    return narracion

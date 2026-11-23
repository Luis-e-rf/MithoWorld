from django.core.signing import BadSignature, TimestampSigner

from .catalog import atributos


def contexto_duelo(primero, segundo, ganador):
    return {
        'version': 1,
        'luchadores': [{'id': c.pk, 'nombre': c.nombre, **atributos(c)} for c in (primero, segundo)],
        'ganador': 'L1' if ganador.pk == primero.pk else 'L2',
    }


def firmar_combate(pk):
    return TimestampSigner(salt='game.combate.cronica.v1').sign(str(pk))


def referencia_valida(pk, referencia):
    try:
        valor = TimestampSigner(salt='game.combate.cronica.v1').unsign(referencia, max_age=900)
    except BadSignature:
        return False
    return valor == str(pk)

"""Cola PostgreSQL. Las transacciones terminan antes de cualquier espera de red."""
import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone as tz_utc

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.game.models import CombatLog
from . import services
from .models import CronicaCombate, PresupuestoDiario
from .narrativa import DatosInvalidos, VERSION_PROMPT, hechos_duelo

logger = logging.getLogger(__name__)
Estado = CronicaCombate.Estado
MAX_COLA = 4
MAX_INTENTOS = 2
PAUSA = timedelta(seconds=30)


@dataclass
class Resultado:
    estado: str
    status: int
    reintentable: bool = False
    espera: int = 0
    lineas: list = field(default_factory=list)


def _bloquear_cola():
    # Exclusión entre admisiones y reservas (incluido el primer intento del día).
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(73508, 1)")


def _manana(ahora):
    dia = ahora.astimezone(tz_utc.utc).date() + timedelta(days=1)
    return datetime.combine(dia, time.min, tzinfo=tz_utc.utc)


def _estado(fila, ahora):
    if fila.estado == Estado.LISTA:
        return Resultado('lista', 200, lineas=fila.lineas)
    if fila.estado in (Estado.PENDIENTE, Estado.PROCESANDO) and fila.vence_en > ahora:
        return Resultado(fila.estado, 202, espera=2)
    espera = max(0, math.ceil((fila.disponible_en - ahora).total_seconds())) if fila.disponible_en else 0
    if fila.estado == Estado.CUOTA:
        return Resultado('cuota', 429, True, espera)
    return Resultado('fallida', 503, fila.intentos < MAX_INTENTOS, espera)


def consultar(pk):
    fila = CronicaCombate.objects.filter(pk=pk).first()
    if fila:
        return _estado(fila, timezone.now())
    return Resultado('sin_solicitud', 404, True)


@transaction.atomic
def solicitar(pk):
    _bloquear_cola()
    ahora = timezone.now()
    fila = CronicaCombate.objects.filter(pk=pk).first()
    if fila:
        actual = _estado(fila, ahora)
        if not actual.reintentable or actual.espera:
            return actual
    combate = CombatLog.objects.select_for_update().filter(pk=pk).first()
    if combate is None:
        return Resultado('combate_ausente', 404)
    if not services.configurado():
        return Resultado('no_configurada', 200)
    try:
        hechos_duelo(combate)
    except DatosInvalidos:
        return Resultado('sin_contexto', 409)
    limite = settings.CRONICA_MAX_LLAMADAS_DIA
    if limite <= 0 or PresupuestoDiario.objects.filter(dia=ahora.date(), llamadas__gte=limite).exists():
        return Resultado('cuota', 429, True, math.ceil((_manana(ahora) - ahora).total_seconds()))
    activas = CronicaCombate.objects.filter(estado__in=[Estado.PENDIENTE, Estado.PROCESANDO], vence_en__gt=ahora)
    if activas.count() >= MAX_COLA:
        return Resultado('cola_llena', 429, True, 5)
    if fila is None:
        fila = CronicaCombate(combate=combate)
    fila.estado = Estado.PENDIENTE
    fila.vence_en = ahora + timedelta(seconds=MAX_COLA * (settings.CRONICA_TIMEOUT_S + 3))
    fila.disponible_en = None
    fila.save()
    return _estado(fila, ahora)


@transaction.atomic
def _reclamar():
    _bloquear_cola()
    ahora = timezone.now()
    activas = CronicaCombate.objects.filter(estado__in=[Estado.PENDIENTE, Estado.PROCESANDO])
    activas.filter(vence_en__lte=ahora).update(estado=Estado.FALLIDA, vence_en=None)
    if activas.filter(estado=Estado.PROCESANDO).exists():
        return None
    fila = activas.filter(estado=Estado.PENDIENTE).select_related('combate').order_by('actualizado_en', 'pk').first()
    if fila is None:
        return None
    presupuesto, _ = PresupuestoDiario.objects.get_or_create(dia=ahora.date())
    if presupuesto.llamadas >= settings.CRONICA_MAX_LLAMADAS_DIA:
        fila.estado = Estado.CUOTA
        fila.vence_en = None
        fila.disponible_en = _manana(ahora)
        fila.save()
        return None
    presupuesto.llamadas += 1
    presupuesto.save(update_fields=['llamadas'])
    fila.estado = Estado.PROCESANDO
    fila.intentos += 1
    fila.vence_en = ahora + timedelta(seconds=settings.CRONICA_TIMEOUT_S + 5)
    fila.modelo = settings.CRONICA_MODELO
    fila.version_prompt = VERSION_PROMPT
    fila.save()
    return fila


def procesar_uno(*, transport=None):
    if not services.configurado():
        return False
    fila = _reclamar()
    if fila is None:
        return False
    try:
        lineas = asyncio.run(services.generar_cronica(fila.combate, transport=transport))
        cambios = dict(estado=Estado.LISTA, lineas=lineas, disponible_en=None)
    except (services.ErrorProveedor, DatosInvalidos) as exc:
        logger.warning('Crónica %s intento %s: %s', fila.pk, fila.intentos, exc)
        cambios = dict(estado=Estado.FALLIDA, disponible_en=timezone.now() + PAUSA)
    ahora = timezone.now()
    CronicaCombate.objects.filter(pk=fila.pk, estado=Estado.PROCESANDO, intentos=fila.intentos,
                                  vence_en__gt=ahora).update(**cambios, vence_en=None, actualizado_en=ahora)
    return True

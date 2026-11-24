from django.db import models


class CronicaCombate(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente'
        PROCESANDO = 'procesando'
        LISTA = 'lista'
        FALLIDA = 'fallida'
        CUOTA = 'cuota'

    combate = models.OneToOneField('criaturas.CombatLog', primary_key=True, on_delete=models.CASCADE)
    estado = models.CharField(max_length=12, choices=Estado, default=Estado.PENDIENTE)
    lineas = models.JSONField(default=list)
    modelo = models.CharField(max_length=200, blank=True)
    version_prompt = models.PositiveSmallIntegerField(default=1)
    intentos = models.PositiveSmallIntegerField(default=0)
    actualizado_en = models.DateTimeField(auto_now=True)
    disponible_en = models.DateTimeField(null=True)
    vence_en = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=['estado', 'actualizado_en'], name='cronica_cola')]


class PresupuestoDiario(models.Model):
    dia = models.DateField(primary_key=True)
    llamadas = models.PositiveIntegerField(default=0)

from django.db import models
from django.db.models import F, Q


class LoteSimulacion(models.Model):
    dataset_sha256 = models.CharField(max_length=64, primary_key=True)
    catalogo_sha256 = models.CharField(max_length=64)
    seed_simulacion = models.BigIntegerField()
    schema_version = models.PositiveSmallIntegerField()
    rules_version = models.PositiveSmallIntegerField()
    n_combates = models.PositiveIntegerField()
    cargado_en = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['activo'], condition=Q(activo=True), name='sim_un_lote_activo'),
            models.CheckConstraint(condition=Q(n_combates__gt=0), name='sim_lote_no_vacio'),
        ]

    def __str__(self):
        return f'Semilla {self.seed_simulacion} · {self.pk[:12]}'


class CombateSimulado(models.Model):
    lote = models.ForeignKey(LoteSimulacion, on_delete=models.CASCADE, db_column='dataset_sha256',
                             db_index=False, related_name='combates')
    fila_num = models.PositiveIntegerField()
    luchador_1 = models.ForeignKey('criaturas.Criatura', on_delete=models.SET_NULL, null=True,
                                   related_name='+', db_index=False)
    luchador_2 = models.ForeignKey('criaturas.Criatura', on_delete=models.SET_NULL, null=True,
                                   related_name='+', db_index=False)
    luchador_1_origen_id = models.PositiveBigIntegerField(editable=False)
    luchador_2_origen_id = models.PositiveBigIntegerField(editable=False)
    gano_primero = models.BooleanField()

    class Meta:
        indexes = [
            models.Index(fields=['luchador_1', 'lote'], name='sim_luchador1_lote'),
            models.Index(fields=['luchador_2', 'lote'], name='sim_luchador2_lote'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['lote', 'fila_num'], name='sim_fila_unica'),
            models.CheckConstraint(condition=Q(fila_num__gte=1), name='sim_fila_positiva'),
            models.CheckConstraint(condition=Q(luchador_1_origen_id__gt=0, luchador_2_origen_id__gt=0)
                                   & ~Q(luchador_1_origen_id=F('luchador_2_origen_id')), name='sim_origen_valido'),
            models.CheckConstraint(condition=Q(luchador_1__isnull=True) | Q(luchador_1=F('luchador_1_origen_id')),
                                   name='sim_luchador1_origen'),
            models.CheckConstraint(condition=Q(luchador_2__isnull=True) | Q(luchador_2=F('luchador_2_origen_id')),
                                   name='sim_luchador2_origen'),
        ]

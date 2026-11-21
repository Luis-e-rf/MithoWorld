from django.db import models

class Criatura(models.Model):
    TIPOS = [
        ('aire', 'Aire'),
        ('agua', 'Agua'),
        ('tierra', 'Tierra'),
        ('fuego', 'Fuego'),
        ('luz', 'Luz'),
        ('oscuridad', 'Oscuridad'),
        ('plasma', 'Plasma'),
    ]

    nombre = models.CharField(max_length=100, unique=True)
    tipo_primario = models.CharField(max_length=20, choices=TIPOS)
    tipo_secundario = models.CharField(max_length=20, choices=TIPOS, null=True, blank=True)
    descripcion = models.TextField()
    ataque = models.IntegerField()
    defensa = models.IntegerField()
    velocidad = models.IntegerField()
    salud = models.IntegerField()

    # NUEVO CAMPO DE IMAGEN
    # upload_to: Django creará automáticamente una subcarpeta 'criaturas' dentro de 'media'.
    # null=True: Permite que la base de datos acepte que el campo esté vacío.
    # blank=True: Permite que el formulario del admin te deje guardar sin subir foto obligatoriamente.
    imagen = models.ImageField(upload_to='criaturas/', null=True, blank=True)
    
    
    # Esto es útil para ver un nombre legible en el panel de administrador
    def __str__(self):
        return self.nombre


class CombatLog(models.Model):
    luchador_1 = models.ForeignKey(
        Criatura, on_delete=models.SET_NULL, null=True, related_name='combates_como_primero',
    )
    luchador_2 = models.ForeignKey(
        Criatura, on_delete=models.SET_NULL, null=True, related_name='combates_como_segundo',
    )
    ganador_predicho = models.ForeignKey(
        Criatura, on_delete=models.SET_NULL, null=True, related_name='victorias_predichas',
    )
    probabilidad = models.FloatField(help_text='Confianza en el ganador predicho, de 0 a 1.')
    ventaja_elemental = models.JSONField(help_text='Multiplicador ofensivo de cada luchador.')
    diferencial = models.JSONField(help_text='Diferencias por stat entre el primer luchador y el segundo.')
    latencia_ms = models.FloatField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(probabilidad__gte=0, probabilidad__lte=1),
                name='combate_probabilidad_valida',
            ),
            models.CheckConstraint(
                condition=models.Q(latencia_ms__gte=0), name='combate_latencia_no_negativa',
            ),
        ]

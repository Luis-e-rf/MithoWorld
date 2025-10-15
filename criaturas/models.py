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
    
    # Esto es útil para ver un nombre legible en el panel de administrador
    def __str__(self):
        return self.nombre
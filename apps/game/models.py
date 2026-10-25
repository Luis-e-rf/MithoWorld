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
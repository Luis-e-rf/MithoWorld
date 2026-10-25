from django.contrib import admin
from .models import Criatura

# Registra el modelo Criatura en el panel de administración de Django (/admin/).
# Con esta sola línea, Django genera automáticamente:
#   - Una vista de lista con todas las criaturas de la BD
#   - Un formulario de creación/edición basado en los campos del modelo
#   - Botones de eliminar, buscar y filtrar
# Para personalizar (ej: mostrar columnas específicas, filtros), se puede
# crear una clase CriaturaAdmin(admin.ModelAdmin) y pasarla como segundo argumento.
admin.site.register(Criatura)

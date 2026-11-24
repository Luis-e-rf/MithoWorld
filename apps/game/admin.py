from django.contrib import admin
from .models import CombatLog, Criatura

# Registra el modelo Criatura en el panel de administración de Django (/admin/).
# Con esta sola línea, Django genera automáticamente:
#   - Una vista de lista con todas las criaturas de la BD
#   - Un formulario de creación/edición basado en los campos del modelo
#   - Botones de eliminar, buscar y filtrar
# Para personalizar (ej: mostrar columnas específicas, filtros), se puede
# crear una clase CriaturaAdmin(admin.ModelAdmin) y pasarla como segundo argumento.
admin.site.register(Criatura)


@admin.register(CombatLog)
class CombatLogAdmin(admin.ModelAdmin):
    list_display = ('creado_en', 'luchador_1', 'luchador_2', 'ganador_predicho', 'probabilidad', 'latencia_ms')

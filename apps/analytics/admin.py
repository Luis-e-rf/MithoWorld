from django.contrib import admin

from .models import LoteSimulacion


@admin.register(LoteSimulacion)
class LoteSimulacionAdmin(admin.ModelAdmin):
    list_display = ('dataset_sha256', 'seed_simulacion', 'n_combates', 'activo', 'cargado_en')
    ordering = ('-cargado_en',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

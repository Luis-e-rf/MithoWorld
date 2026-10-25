from django.apps import AppConfig


class MlConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ml'
    label = 'oraculo'  # Mantiene compatibilidad con migraciones e historial previo

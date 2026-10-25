from django.apps import AppConfig


class GameConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.game'
    label = 'criaturas'  # Obligatorio para preservar tabla django_migrations y modelos existentes

from django.apps import AppConfig


class CriaturasConfig(AppConfig):
    # Tipo de campo por defecto para las claves primarias auto-generadas (id).
    # BigAutoField = entero de 64 bits auto-incremental (soporta más de 2 mil millones de registros)
    default_auto_field = 'django.db.models.BigAutoField'
    # Nombre de la app. Debe coincidir EXACTAMENTE con el nombre de la carpeta
    # y con lo que está en INSTALLED_APPS de settings.py
    name = 'criaturas'

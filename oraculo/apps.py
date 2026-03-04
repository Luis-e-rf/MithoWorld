from django.apps import AppConfig


class OraculoConfig(AppConfig):
    # BigAutoField: IDs auto-incrementales de 64 bits para cualquier modelo de esta app
    default_auto_field = 'django.db.models.BigAutoField'
    # Nombre de la app del oráculo (predicción de combates con IA).
    # Esta app no define modelos propios (models.py vacío), solo usa
    # el modelo Criatura de la app 'criaturas' para las predicciones.
    name = 'oraculo'

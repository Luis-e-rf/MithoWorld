"""
WSGI config for backend project.

WSGI (Web Server Gateway Interface) es el estándar para servir apps Python en producción.
Este archivo expone la variable 'application' que servidores como Gunicorn usan como punto de entrada.
Comando de producción: gunicorn backend.wsgi:application --bind 0.0.0.0:8000

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Configura la variable de entorno que Django necesita para encontrar settings.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Crea la aplicación WSGI que Gunicorn (o cualquier servidor WSGI) ejecutará
application = get_wsgi_application()

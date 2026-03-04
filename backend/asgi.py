"""
ASGI config for backend project.

ASGI (Asynchronous Server Gateway Interface) es la evolución de WSGI.
Soporta peticiones asíncronas, WebSockets y HTTP2.
Actualmente este proyecto NO usa funcionalidades async, pero el archivo
está listo por si se necesitan en el futuro (ej: chat en tiempo real con WebSockets).

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Crea la aplicación ASGI (usada por servidores como Daphne o Uvicorn)
application = get_asgi_application()

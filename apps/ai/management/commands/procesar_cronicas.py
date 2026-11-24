import time

from django.core.management.base import BaseCommand
from django.db import OperationalError, ProgrammingError, close_old_connections

from apps.ai.cola import procesar_uno


class Command(BaseCommand):
    help = 'Atiende una generación a la vez desde la cola PostgreSQL.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Intenta procesar un trabajo y termina.')

    def handle(self, *args, once, **options):
        while True:
            close_old_connections()
            try:
                procesado = procesar_uno()
            except (OperationalError, ProgrammingError) as exc:
                # El perfil puede arrancar mientras el servicio web aún aplica las migraciones.
                if once or (isinstance(exc, ProgrammingError) and getattr(exc.__cause__, 'pgcode', None) != '42P01'):
                    raise
                self.stderr.write('Cola PostgreSQL no disponible. Se reintentará la lectura.')
                time.sleep(5)
                continue
            if once:
                return
            if not procesado:
                time.sleep(2)

import csv
import hashlib
import json
import random
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.game.catalog import COLUMNAS, catalogo_sha256
from apps.game.models import Criatura
from apps.game.rules import score_base
from apps.ml.features import fila_combate

N_COMBATES = 10_000


def ganador_simulado(primero, segundo, rng):
    a = score_base(primero, segundo) * rng.uniform(0.9, 1.1)
    b = score_base(segundo, primero) * rng.uniform(0.9, 1.1)
    if a == b:
        return rng.choice((primero, segundo))
    return primero if a > b else segundo


class Command(BaseCommand):
    help = 'Simula 10 000 combates y registra su procedencia.'

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=int, default=42)

    def handle(self, *args, seed, **options):
        criaturas = list(Criatura.objects.order_by('pk'))
        if len(criaturas) < 2:
            raise CommandError('Se necesitan al menos dos criaturas.')
        huella = catalogo_sha256(criaturas)
        rng = random.Random(seed)
        destino = Path(settings.BASE_DIR)
        with TemporaryDirectory(dir=destino) as temporal:
            csv_path = Path(temporal) / 'dataset_batallas.csv'
            with csv_path.open('w', encoding='utf-8', newline='') as archivo:
                writer = csv.DictWriter(archivo, fieldnames=COLUMNAS, lineterminator='\n')
                writer.writeheader()
                for _ in range(N_COMBATES):
                    a, b = rng.sample(criaturas, 2)
                    ganador = ganador_simulado(a, b, rng)
                    writer.writerow({'luchador_1_id': a.pk, 'luchador_2_id': b.pk,
                                     'ganador_id': ganador.pk, **fila_combate(a, b),
                                     'gano_primero': int(ganador == a)})
            meta = {'schema_version': 2, 'rules_version': 2, 'seed_simulacion': seed,
                    'n_combates': N_COMBATES, 'catalogo_sha256': huella,
                    'dataset_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest()}
            manifest = Path(temporal) / 'dataset_batallas.meta.json'
            manifest.write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
            csv_path.replace(destino / csv_path.name)
            manifest.replace(destino / manifest.name)
        self.stdout.write(f'{N_COMBATES} combates generados con semilla {seed}.')

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import numpy as np
import pandas as pd
import sklearn
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from apps.game.rules import normalizar_tipos
from apps.ml.features import COLUMNAS, FEATURES, IDS, STATS, TARGET

NUMERICAS = [f'{stat}_{lado}' for lado in (1, 2) for stat in STATS]
CATEGORICAS = [campo for campo in FEATURES if campo not in NUMERICAS]


def leer_dataset(raiz):
    contenido = (raiz / 'dataset_batallas.csv').read_bytes()
    cabecera = next(csv.reader(io.StringIO(contenido.decode('utf-8-sig'))), [])
    if sorted(cabecera) != sorted(COLUMNAS):
        raise CommandError('Se requieren las 16 columnas del CSV v2. Regenera el dataset con simular_batallas.')
    meta = json.loads((raiz / 'dataset_batallas.meta.json').read_text(encoding='utf-8'))
    if (not isinstance(meta, dict) or type(meta.get('seed_simulacion')) is not int
            or not re.fullmatch(r'[a-f0-9]{64}', str(meta.get('catalogo_sha256', '')))):
        raise CommandError('Falta la procedencia del catálogo o la semilla de simulación.')
    if (meta['schema_version'] != 2 or meta['rules_version'] != 2
            or meta['dataset_sha256'] != hashlib.sha256(contenido).hexdigest()):
        raise CommandError('El manifiesto v2 no corresponde al CSV.')
    df = pd.read_csv(io.BytesIO(contenido), keep_default_na=False, dtype={c: str for c in CATEGORICAS})
    if len(df) != meta['n_combates'] or not isinstance(df.index, pd.RangeIndex):
        raise CommandError('Número de filas o columnas inesperado.')
    for col in [*IDS, *NUMERICAS, TARGET]:
        if not pd.api.types.is_integer_dtype(df[col]):
            raise CommandError(f'{col} debe contener enteros.')
    for lado in (1, 2):
        tipos = df[[f'tipo_primario_{lado}', f'tipo_secundario_{lado}']].drop_duplicates()
        for par in tipos.itertuples(index=False, name=None):
            if par != normalizar_tipos(*par):
                raise CommandError('El CSV debe contener los tipos canónicos del simulador.')
    a, b = df['luchador_1_id'], df['luchador_2_id']
    if ((df[IDS] <= 0).any().any() or a.eq(b).any() or not df[TARGET].isin([0, 1]).all()
            or not df['ganador_id'].eq(a.where(df[TARGET].eq(1), b)).all()):
        raise CommandError('IDs o etiqueta de ganador incoherentes.')
    return df, meta


def distribucion(y):
    return {str(clase): int(y.eq(clase).sum()) for clase in (0, 1)}


class Command(BaseCommand):
    help = 'Entrena y evalúa el pipeline v2 con parejas disjuntas.'

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=int, default=42)

    def handle(self, *args, seed, **options):
        raiz = Path(settings.BASE_DIR)
        try:
            df, origen = leer_dataset(raiz)
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(f'Error al leer el dataset v2: {exc}') from exc
        # Un mismo grupo para A/B y B/A, incluso si se repite con otro ganador.
        pares = np.sort(df[IDS[:2]].to_numpy(), axis=1)
        _, grupos = np.unique(pares, axis=0, return_inverse=True)
        split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        try:
            train, test = next(split.split(df, groups=grupos))
        except ValueError as exc:
            raise CommandError(f'Partición inviable: {exc}') from exc
        x, y = df[FEATURES], df[TARGET]
        if any(y.iloc[idx].nunique() != 2 for idx in (train, test)):
            raise CommandError('Se necesitan ambas clases en train y test.')
        preproceso = ColumnTransformer([
            ('stats', 'passthrough', NUMERICAS),
            ('tipos', OneHotEncoder(handle_unknown='ignore'), CATEGORICAS),
        ])
        pipeline = Pipeline([
            ('preproceso', preproceso),
            ('bosque', RandomForestClassifier(n_estimators=100, random_state=seed)),
        ])
        pipeline.fit(x.iloc[train], y.iloc[train])
        pred = pipeline.predict(x.iloc[test])
        proba = pipeline.predict_proba(x.iloc[test])[:, list(pipeline.classes_).index(1)]
        metricas = {'accuracy': accuracy_score(y.iloc[test], pred),
                    'roc_auc': roc_auc_score(y.iloc[test], proba)}
        meta = {
            **origen,
            'features': FEATURES,
            'target': TARGET,
            'seed': seed,
            'entrenado_en_utc': datetime.now(timezone.utc).isoformat(),
            'sklearn_version': sklearn.__version__,
            'metricas_test': metricas,
            'distribucion_clases': {
                'dataset': distribucion(y),
                'train': distribucion(y.iloc[train]),
                'test': distribucion(y.iloc[test]),
            },
            'split': {
                'estrategia': 'GroupShuffleSplit_por_pareja',
                'test_size': split.test_size,
                'n_train': len(train),
                'n_test': len(test),
                'parejas_train': len(set(grupos[train])),
                'parejas_test': len(set(grupos[test])),
            },
        }
        destino = raiz / 'apps/ml/ml_models'
        destino.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=destino) as temporal:
            modelo = Path(temporal) / 'modelo_combate.pkl'
            joblib.dump(pipeline, modelo)
            recargado = joblib.load(modelo)
            if not np.array_equal(recargado.predict(x.iloc[test]), pred):
                raise CommandError('La predicción cambió al recargar el artefacto.')
            meta['modelo_sha256'] = hashlib.sha256(modelo.read_bytes()).hexdigest()
            manifest = Path(temporal) / 'modelo_metadata.json'
            manifest.write_text(json.dumps(meta, indent=2, allow_nan=False) + '\n', encoding='utf-8')
            modelo.replace(destino / modelo.name)
            manifest.replace(destino / manifest.name)
        self.stdout.write(f'Pipeline v2 validado. Métricas de test: {metricas}')

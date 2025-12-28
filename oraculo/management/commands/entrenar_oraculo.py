import pandas as pd
import joblib  # Para guardar el cerebro (modelo) en un archivo
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score

class Command(BaseCommand):
    help = 'Entrena el modelo de IA usando el dataset de batallas simuladas'

    def handle(self, *args, **options):
        # Rutas de archivos
        ruta_csv = os.path.join(settings.BASE_DIR, 'dataset_batallas.csv')
        ruta_modelos = os.path.join(settings.BASE_DIR, 'oraculo', 'ml_models')
        
        # Crear carpeta si no existe
        os.makedirs(ruta_modelos, exist_ok=True)

        self.stdout.write(self.style.NOTICE('Cargando dataset...'))
        
        # 1. Cargar Datos
        try:
            df = pd.read_csv(ruta_csv)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('No encuentro dataset_batallas.csv. Ejecuta simular_batallas primero.'))
            return

        # 2. Preprocesamiento (Traducir Texto a Números)
        # La IA no lee "Fuego", necesita un número. Usamos LabelEncoder.
        le = LabelEncoder()
        
        # Ajustamos el traductor con TODOS los tipos posibles (columna tipo_1 y tipo_2)
        tipos_unicos = pd.concat([df['tipo_1'], df['tipo_2']]).unique()
        le.fit(tipos_unicos)

        # Transformamos las columnas de texto a números
        df['tipo_1_encoded'] = le.transform(df['tipo_1'])
        df['tipo_2_encoded'] = le.transform(df['tipo_2'])

        # 3. Definir Features (X) y Target (y)
        # X: Los datos que la IA usa para pensar
        X = df[[
            'ataque_1', 'defensa_1', 'velocidad_1', 'tipo_1_encoded',
            'ataque_2', 'defensa_2', 'velocidad_2', 'tipo_2_encoded'
        ]]
        
        # y: La respuesta correcta (1 o 0)
        y = df['gano_primero']

        # 4. Dividir en Entrenamiento (80%) y Examen (20%)
        # Es vital guardar una parte de los datos que la IA NUNCA haya visto para probarla después.
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.stdout.write(self.style.NOTICE('Entrenando el Bosque Aleatorio (Random Forest)...'))

        # 5. Entrenar el Modelo
        modelo = RandomForestClassifier(n_estimators=100, random_state=42)
        modelo.fit(X_train, y_train)

        # 6. Evaluar
        predicciones = modelo.predict(X_test)
        precision = accuracy_score(y_test, predicciones)

        self.stdout.write(self.style.SUCCESS(f'✅ Entrenamiento completado.'))
        self.stdout.write(self.style.SUCCESS(f'🎯 Precisión del modelo: {precision:.2%}'))
        
        # Una precisión > 85% suele ser excelente para este tipo de problemas.
        # Si es 100%, sospecha (overfitting), pero como pusimos aleatoriedad, debería ser realista.

        # 7. Guardar el Cerebro y el Traductor
        # Guardamos el modelo (.pkl)
        joblib.dump(modelo, os.path.join(ruta_modelos, 'modelo_combate.pkl'))
        # Guardamos el encoder (.pkl) para poder traducir los tipos cuando usemos la API
        joblib.dump(le, os.path.join(ruta_modelos, 'encoder_tipos.pkl'))

        self.stdout.write(self.style.NOTICE('Archivos .pkl guardados en oraculo/ml_models/'))
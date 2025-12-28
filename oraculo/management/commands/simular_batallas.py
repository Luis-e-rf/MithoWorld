import random
import pandas as pd
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from criaturas.models import Criatura

class Command(BaseCommand):
    help = 'Simula miles de batallas para generar un Dataset de entrenamiento'

    def handle(self, *args, **options):
        # 1. Configuración de la Simulación
        NUM_BATALLAS = 10000  # Generaremos 10,000 peleas
        OUTPUT_FILE = os.path.join(settings.BASE_DIR, 'dataset_batallas.csv')
        
        criaturas = list(Criatura.objects.all())
        
        if len(criaturas) < 2:
            self.stdout.write(self.style.ERROR('Necesitas al menos 2 criaturas para pelear.'))
            return

        self.stdout.write(self.style.NOTICE(f'Iniciando simulación de {NUM_BATALLAS} batallas...'))

        data_batallas = []

        # 2. Definición de Reglas Elementales (Tabla de Tipos)
        # 1.0 = Neutro, 1.5 = Ventaja (Eficaz), 0.5 = Desventaja (Poco eficaz)
        VENTAJAS = {
            'fuego': {'tierra': 1.5, 'plasma': 0.5, 'agua': 0.5},
            'agua': {'fuego': 1.5, 'tierra': 1.5, 'aire': 0.5},
            'tierra': {'plasma': 1.5, 'aire': 0.5, 'agua': 0.5},
            'aire': {'tierra': 1.5, 'fuego': 0.5, 'oscuridad': 0.5},
            'luz': {'oscuridad': 2.0, 'plasma': 0.5},
            'oscuridad': {'luz': 0.5, 'aire': 1.5},
            'plasma': {'agua': 1.5, 'luz': 1.5, 'tierra': 0.5}
        }

        # 3. Bucle de Batallas
        for i in range(NUM_BATALLAS):
            # Escogemos 2 luchadores al azar
            c1, c2 = random.sample(criaturas, 2)

            # Calculamos el resultado
            ganador = self.determinar_ganador(c1, c2, VENTAJAS)

            # 4. Guardamos los datos "crudos" para la IA
            # La IA no necesita nombres, necesita NÚMEROS (stats)
            registro = {
                # Datos Luchador 1
                'ataque_1': c1.ataque,
                'defensa_1': c1.defensa,
                'velocidad_1': c1.velocidad,
                'tipo_1': c1.tipo_primario, # La IA tendrá que aprender a leer texto luego
                
                # Datos Luchador 2
                'ataque_2': c2.ataque,
                'defensa_2': c2.defensa,
                'velocidad_2': c2.velocidad,
                'tipo_2': c2.tipo_primario,

                # TARGET (Lo que queremos predecir)
                # 1 si gana el Luchador 1, 0 si gana el Luchador 2
                'gano_primero': 1 if ganador == c1 else 0
            }
            data_batallas.append(registro)
            
            # Barra de progreso simple
            if i % 1000 == 0:
                self.stdout.write(f'... {i} batallas simuladas')

        # 5. Exportar a CSV usando Pandas
        df = pd.DataFrame(data_batallas)
        df.to_csv(OUTPUT_FILE, index=False)

        self.stdout.write(self.style.SUCCESS(f'✅ Dataset generado: {OUTPUT_FILE}'))

    def determinar_ganador(self, c1, c2, ventajas):
        """
        Calcula un 'Score' de combate para cada uno. El score más alto gana.
        Fórmula: (Ataque * Multiplicador) + Velocidad - (Defensa Oponente * 0.5) + Aleatoriedad
        """
        # Calcular Multiplicadores de Tipo
        # .get(clave, valor_por_defecto)
        mult_1 = ventajas.get(c1.tipo_primario, {}).get(c2.tipo_primario, 1.0)
        mult_2 = ventajas.get(c2.tipo_primario, {}).get(c1.tipo_primario, 1.0)

        # Factor Aleatorio (La suerte del combate +/- 10%)
        # Esto es vital para que la IA no aprenda una fórmula matemática perfecta,
        # sino que aprenda tendencias y probabilidades.
        suerte_1 = random.uniform(0.9, 1.1)
        suerte_2 = random.uniform(0.9, 1.1)

        # Cálculo de Puntuación de Batalla
        score_1 = (c1.ataque * mult_1) + (c1.velocidad * 0.5) - (c2.defensa * 0.2)
        score_1 *= suerte_1

        score_2 = (c2.ataque * mult_2) + (c2.velocidad * 0.5) - (c1.defensa * 0.2)
        score_2 *= suerte_2

        return c1 if score_1 > score_2 else c2
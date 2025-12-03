import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from criaturas.models import Criatura

class Command(BaseCommand):
    # 1. HELP: Texto que describe qué hace el comando (útil para documentación)
    help = 'Lee el archivo criaturas.csv y carga los datos en la base de datos PostgreSQL'

    def handle(self, *args, **options):
        # 2. RUTA DEL ARCHIVO: Construimos la ruta absoluta para evitar errores de "archivo no encontrado"
        # settings.BASE_DIR nos da la ruta a la carpeta del proyecto, sin importar dónde esté instalado.
        archivo_csv = os.path.join(settings.BASE_DIR, 'criaturas.csv')

        self.stdout.write(self.style.NOTICE(f'Iniciando lectura de: {archivo_csv}'))

        # 3. BLOQUE DE SEGURIDAD (Try/Except)
        try:
            # Abrimos el archivo en modo lectura ('r') con codificación UTF-8 (para tildes y ñ)
            with open(archivo_csv, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=';')
                
                # 4. SALTAR ENCABEZADO: next() consume la primera línea (títulos) para no intentar guardarla
                next(reader, None)

                contador_creados = 0
                contador_existentes = 0

                # 5. BUCLE PRINCIPAL: Procesamos fila por fila
                for i, row in enumerate(reader, start=2): # start=2 es solo para saber el número de línea real del Excel
                    try:
                        # Extraemos los datos por posición (índice) basándonos en tu Excel
                        # Usamos .strip() para limpiar espacios accidentales al inicio o final
                        nombre_raw = row[0].strip()
                        tipo_primario_raw = row[1].strip().lower() # Convertimos a minúscula para coincidir con el modelo
                        
                        # Lógica para Tipo Secundario: Si la celda está vacía, guardamos None (NULL)
                        tipo_sec_val = row[2].strip().lower()
                        tipo_secundario_clean = tipo_sec_val if tipo_sec_val else None

                        # 6. MÉTODO MÁGICO: get_or_create
                        # Busca una criatura por su 'nombre'.
                        # - Si existe: La trae y la guarda en la variable 'obj'. 'created' será False.
                        # - Si NO existe: Crea una nueva usando los datos en 'defaults'. 'created' será True.
                        obj, created = Criatura.objects.get_or_create(
                            nombre=nombre_raw,
                            defaults={
                                'tipo_primario': tipo_primario_raw,
                                'tipo_secundario': tipo_secundario_clean,
                                'salud': int(row[3]),
                                'ataque': int(row[4]),
                                'defensa': int(row[5]),
                                'velocidad': int(row[6]),
                                'descripcion': row[7].strip()
                            }
                        )

                        # 7. FEEDBACK EN TERMINAL
                        if created:
                            self.stdout.write(self.style.SUCCESS(f'✅ Creada: {nombre_raw}'))
                            contador_creados += 1
                        else:
                            self.stdout.write(self.style.WARNING(f'⚠️  Ya existe: {nombre_raw} (Saltada)'))
                            contador_existentes += 1

                    except IndexError:
                        self.stdout.write(self.style.ERROR(f'❌ Error en línea {i}: Faltan columnas en el CSV'))
                    except ValueError as e:
                        self.stdout.write(self.style.ERROR(f'❌ Error de datos en línea {i} ({row[0]}): {str(e)}'))

            # Resumen final
            self.stdout.write(self.style.SUCCESS(f'\nProceso finalizado. Nuevos: {contador_creados} | Existentes: {contador_existentes}'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('❌ ERROR FATAL: No se encuentra el archivo "criaturas.csv" en la raíz del proyecto.'))
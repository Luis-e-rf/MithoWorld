import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File  # [NUEVO] Importante: Wrapper para manejar archivos en Django
from criaturas.models import Criatura

class Command(BaseCommand):
    help = 'Lee criaturas.csv e importa datos + imágenes a la base de datos'

    def handle(self, *args, **options):
        # Rutas a los recursos
        archivo_csv = os.path.join(settings.BASE_DIR, 'criaturas.csv')
        # [NUEVO] Definimos dónde están las imágenes originales
        carpeta_imagenes = os.path.join(settings.BASE_DIR, 'imagenes_semilla')

        self.stdout.write(self.style.NOTICE(f'Iniciando lectura de CSV: {archivo_csv}'))
        self.stdout.write(self.style.NOTICE(f'Buscando imágenes en: {carpeta_imagenes}'))

        try:
            with open(archivo_csv, mode='r', encoding='utf-8') as file:
                # Recuerda: Usamos delimiter=';' porque así está tu Excel
                reader = csv.reader(file, delimiter=';')
                next(reader, None)  # Saltar encabezado

                for i, row in enumerate(reader, start=2):
                    try:
                        # 1. Extracción de Datos (Texto)
                        nombre_raw = row[0].strip()
                        tipo_primario_raw = row[1].strip().lower()
                        tipo_sec_val = row[2].strip().lower()
                        tipo_secundario_clean = tipo_sec_val if tipo_sec_val else None
                        
                        # [NUEVO] Leemos la última columna (Índice 8) que tiene el nombre del archivo
                        # Usamos un try/except simple por si alguna fila del CSV no tiene esa columna aún
                        try:
                            nombre_archivo_imagen = row[8].strip()
                        except IndexError:
                            nombre_archivo_imagen = None

                        # 2. Obtener o Crear la Criatura (Sin la imagen aún)
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

                        accion = "✅ Creada" if created else "sus Actualizada"

                        # 3. [NUEVO] Lógica de Procesamiento de Imagen
                        # Solo intentamos guardar imagen si el CSV tiene un nombre y la criatura no tiene foto todavía
                        # (O si quieres forzar actualización, quita el 'if not obj.imagen')
                        if nombre_archivo_imagen:
                            ruta_completa_imagen = os.path.join(carpeta_imagenes, nombre_archivo_imagen)

                            # Verificamos que el archivo físico exista en la carpeta imagenes_semilla
                            if os.path.exists(ruta_completa_imagen):
                                # Abrimos el archivo en modo binario de lectura ('rb')
                                with open(ruta_completa_imagen, 'rb') as f:
                                    # MAGIA DE DJANGO:
                                    # obj.imagen.save(nombre, contenido, save=True)
                                    # Django tomará este archivo, lo copiará a la carpeta MEDIA_ROOT/criaturas/
                                    # y guardará la referencia en la base de datos.
                                    obj.imagen.save(nombre_archivo_imagen, File(f), save=True)
                                    accion += " con Imagen"
                            else:
                                self.stdout.write(self.style.WARNING(f'   ⚠️  Imagen no encontrada en disco: {nombre_archivo_imagen}'))

                        self.stdout.write(self.style.SUCCESS(f'{accion}: {nombre_raw}'))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'❌ Error en línea {i} ({row[0] if row else "?"}): {str(e)}'))

            self.stdout.write(self.style.SUCCESS('\n¡Proceso finalizado con éxito!'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('❌ Error: No se encuentra criaturas.csv'))
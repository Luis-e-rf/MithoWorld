import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File  # [NUEVO] Importante: Wrapper para manejar archivos en Django
from apps.game.models import Criatura

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

                        # 2. Lógica de DATOS: sincronizar stats desde el CSV.
                        # update_or_create crea o actualiza las columnas de stats
                        # (HP, ataque, etc.) para que el CSV sea la fuente de verdad.
                        # El campo `imagen` NO va en `defaults`: la imagen se gestiona
                        # por separado en la lógica de archivos (punto 3) y no debe
                        # tocarse en cada corrida.
                        obj, created = Criatura.objects.update_or_create(
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

                        accion = "✅ Creada" if created else "🔄 Actualizada"

                        # 3. Lógica de ARCHIVO: asociar imagen solo si falta.
                        # Desacople: la lógica de datos (update_or_create) nunca
                        # referencia el campo `imagen`, y esta lógica nunca toca
                        # los stats. Separadas a propósito para que la protección
                        # contra duplicados de imagen sea independiente de la
                        # sincronización de datos.
                        self._procesar_imagen(obj, nombre_archivo_imagen, carpeta_imagenes)

                        self.stdout.write(self.style.SUCCESS(f'{accion}: {nombre_raw}'))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'❌ Error en línea {i} ({row[0] if row else "?"}): {str(e)}'))

            self.stdout.write(self.style.SUCCESS('\n¡Proceso finalizado con éxito!'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('❌ Error: No se encuentra criaturas.csv'))

    def _procesar_imagen(self, obj, nombre_archivo_imagen, carpeta_imagenes):
        """Asocia una imagen a la criatura SOLO si aún no tiene una.

        Protección contra duplicados: si el modelo ya tiene imagen asociada,
        no se llama a .save(), evitando que Django genere copias
        (img_1.png, img_2.png, ...) que saturan el disco.
        """
        if not nombre_archivo_imagen:
            return

        # Si ya hay imagen en la BD (nombre o archivo), no duplicar.
        if obj.imagen and obj.imagen.name:
            return

        ruta_completa_imagen = os.path.join(carpeta_imagenes, nombre_archivo_imagen)
        if not os.path.exists(ruta_completa_imagen):
            self.stdout.write(self.style.WARNING(f'   ⚠️  Imagen no encontrada en disco: {nombre_archivo_imagen}'))
            return

        with open(ruta_completa_imagen, 'rb') as f:
            # obj.imagen.save(nombre, contenido, save=True) copia el archivo
            # a MEDIA_ROOT/criaturas/ y guarda la referencia en la BD.
            obj.imagen.save(nombre_archivo_imagen, File(f), save=True)
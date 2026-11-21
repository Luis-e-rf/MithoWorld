import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.files import File  # [NUEVO] Importante: Wrapper para manejar archivos en Django
from apps.game.models import Criatura

class Command(BaseCommand):
    help = 'Lee criaturas.csv e importa datos + imágenes a la base de datos'

    COLUMNAS_REQUERIDAS = {
        'Nombre', 'Tipo Primario', 'Tipo Secundario', 'Salud',
        'Ataque', 'Defensa', 'Velocidad', 'Descripcion',
    }

    def handle(self, *args, **options):
        # Rutas a los recursos
        archivo_csv = os.path.join(settings.BASE_DIR, 'criaturas.csv')
        # [NUEVO] Definimos dónde están las imágenes originales
        carpeta_imagenes = os.path.join(settings.BASE_DIR, 'imagenes_semilla')

        self.stdout.write(self.style.NOTICE(f'Iniciando lectura de CSV: {archivo_csv}'))
        self.stdout.write(self.style.NOTICE(f'Buscando imágenes en: {carpeta_imagenes}'))

        try:
            with open(archivo_csv, mode='r', encoding='utf-8-sig', newline='') as file:
                # utf-8-sig admite el BOM del CSV exportado desde Excel.
                reader = csv.DictReader(file, delimiter=';')
                self._validar_encabezado(reader)

                for i, row in enumerate(reader, start=2):
                    try:
                        # 1. Extracción de Datos (Texto)
                        nombre_raw = row['Nombre'].strip()
                        tipo_primario_raw = row['Tipo Primario'].strip().lower()
                        tipo_sec_val = row['Tipo Secundario'].strip().lower()
                        tipo_secundario_clean = tipo_sec_val if tipo_sec_val else None
                        
                        # Las imágenes siguen siendo opcionales e independientes de los datos.
                        nombre_archivo_imagen = (row.get('NombreArchivo') or '').strip()

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
                                'salud': int(row['Salud']),
                                'ataque': int(row['Ataque']),
                                'defensa': int(row['Defensa']),
                                'velocidad': int(row['Velocidad']),
                                'descripcion': row['Descripcion'].strip()
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
                        self.stdout.write(self.style.ERROR(f'❌ Error en línea {i} ({row.get("Nombre", "?")}): {str(e)}'))

            self.stdout.write(self.style.SUCCESS('\n¡Proceso finalizado con éxito!'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('❌ Error: No se encuentra criaturas.csv'))

    def _validar_encabezado(self, reader):
        """Valida el esquema antes de escribir datos o copiar imágenes."""
        if not reader.fieldnames:
            raise CommandError('El CSV no tiene encabezado.')

        # Admitir el nombre del CSV real y el alias histórico usado en tests.
        columnas = [
            'Descripcion' if nombre.strip() == 'Descripción' else nombre.strip()
            for nombre in reader.fieldnames
        ]
        if any(not nombre for nombre in columnas):
            raise CommandError('El CSV contiene columnas sin nombre.')
        if len(columnas) != len(set(columnas)):
            raise CommandError('El CSV contiene columnas duplicadas.')

        faltantes = self.COLUMNAS_REQUERIDAS - set(columnas)
        if faltantes:
            raise CommandError(f'Faltan columnas requeridas en el CSV: {", ".join(sorted(faltantes))}')
        reader.fieldnames = columnas

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

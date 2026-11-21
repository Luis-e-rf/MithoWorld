# Bitácora de implementación incremental

Fecha: 2026-11-13. Alcance de esta entrega: fases 0 y 1 del plan de portafolio.
Esta numeración es independiente de las fases históricas de migración modular
documentadas en `ARCHITECTURE_MIGRATION.md`. Cambios pendientes de revisión, sin commit.

## Fase 0 — Configuración por entorno

### Especificación y decisiones

- Mantener `SECRET_KEY = config('SECRET_KEY')`, sin default. Documentar su
  generación y la obligación de completar el valor antes de iniciar Django.
- Leer `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` mediante `Csv()`, con defaults
  locales `localhost,127.0.0.1` y lista vacía, respectivamente.
- Incorporar `.env.example` sin secretos, con las variables de Django,
  PostgreSQL y el token opcional del túnel de producción.
- Pasar `CSRF_TRUSTED_ORIGINS` al contenedor web en Compose de producción:
  definir la variable en el `.env` de Compose no basta para exportarla al servicio.
- Documentar la configuración antes de arrancar PostgreSQL, porque Compose
  necesita las credenciales para inicializar su volumen.

La configuración del despliegue deja de estar acoplada a una IP o dominio en el
código. Para conservar el acceso público al desplegar, configurar explícitamente
`ALLOWED_HOSTS=mithoworld.yurack.com` y
`CSRF_TRUSTED_ORIGINS=https://mithoworld.yurack.com`, además de `DEBUG=False`.
No se modificó el `.env` existente.

### Validación

- `uv run python manage.py check`: sin incidencias.
- `uv run pytest --tb=short`: **10 passed**, conservando la suite original.
- Comprobación en procesos independientes de listas locales, múltiples dominios,
  espacios alrededor de las comas y orígenes vacíos.

## Fase 1 — Contrato de ingesta y responsabilidad de vistas

### Especificación y decisiones

- Sustituir índices posicionales por `csv.DictReader` con separador `;`.
- Abrir con `utf-8-sig` y `newline=''`: admitir el BOM presente en el CSV real
  y dejar al módulo `csv` la interpretación de saltos de línea.
- Exigir `Nombre`, `Tipo Primario`, `Tipo Secundario`, `Salud`, `Ataque`,
  `Defensa`, `Velocidad` y `Descripcion`. Admitir `Descripción` como alias,
  porque el dataset real usa tilde y los tests existentes no la usan.
- Eliminar espacios exteriores en encabezados y rechazar encabezado ausente,
  nombres vacíos, duplicados (incluidos los alias) o columnas requeridas faltantes
  mediante `CommandError`, antes de escribir en BD o copiar imágenes.
- Permitir columnas adicionales y cualquier orden. `NombreArchivo` sigue
  siendo opcional por compatibilidad con el importador previo.
- Preservar `update_or_create` y la lógica independiente de imágenes: volver a
  importar sincroniza estadísticas sin duplicar archivos.
- Retirar el bucle vacío de `detalle.html`.
- Trasladar `arena_view` a `apps/game/views.py` y actualizar el import del router.
  `/arena/`, su nombre `arena` y su plantilla se conservan.

La Arena es presentación del juego; su vista HTML pertenece a `game`. La API
de inferencia permanece en `ml`; `game` no necesita importar ese dominio.
La validación nueva cubre el esquema del CSV. El manejo previo de errores por
fila se conserva; esta fase no convierte toda la importación en una transacción
atómica.

### Validación

- `uv run python manage.py check`: sin incidencias.
- `uv run pytest`: **18 passed**, sin warnings.
- Los 10 casos originales siguen pasando, incluido el contrato JSON estricto.
- Ocho casos nuevos: cuatro encabezados inválidos, dos variantes de descripción
  con BOM y columnas reordenadas, ausencia de la columna de imagen y smoke test
  de `/arena/` (HTTP 200, plantilla correcta y resolución a la vista de `game`).
- `git diff --check`: sin errores de whitespace.

## Entorno de verificación y reproducción

La primera ejecución de `check` pasó, pero los 10 tests fallaron durante la
preparación de BD: no había PostgreSQL escuchando en `localhost:5432`. Docker
tampoco estaba operativo en esta sesión WSL.

Se extrajeron binarios de PostgreSQL **16.15** en un directorio temporal fuera
del repositorio, sin instalar paquetes del sistema. Se creó un clúster desechable,
accesible solo por socket Unix dentro de ese directorio privado, sin escucha TCP.
Las verificaciones usaron overrides de entorno `DB_HOST` (directorio del socket),
`DB_PORT=55432`, `DB_USER=luis`, `DB_NAME=postgres` y `DB_PASSWORD` vacío.
`pytest-django` creó y eliminó su propia base de pruebas. El servidor temporal
se detuvo al terminar. No se usó SQLite ni se accedió a producción.

Para reproducir con el entorno habitual, completar `.env` según el README y ejecutar:

```bash
docker compose up -d
uv run python manage.py check
uv run pytest
```

Las fases 2–8 quedan pendientes: esta entrega no incorpora modelos, migraciones,
telemetría, throttling, analítica ni cambios de entrenamiento.

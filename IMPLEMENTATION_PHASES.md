# Bitácora de implementación incremental

Esta numeración es independiente de las fases históricas de migración modular
documentadas en `ARCHITECTURE_MIGRATION.md`. Las fases 0 y 1, registradas el
13 de noviembre, corresponden a los commits `44afa9e` y `4a47ff5`.

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

## Entorno de verificación de las fases 0 y 1

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

## Fase 2 — Historial de predicciones (2026-11-21)

**Alcance y contrato.** `CombatLog`, definido en `apps/game`, conserva el orden de los dos luchadores y
el ganador predicho. Al borrar una criatura, cada referencia afectada pasa a
`NULL` y el registro conserva sus métricas. La probabilidad es la confianza del
ganador en escala 0–1. El diferencial por estadística y los multiplicadores por
luchador se guardan en dos campos JSON. La latencia se expresa en milisegundos y
`creado_en` lo asigna Django al insertar. La vista de lista del Admin muestra
los participantes, el ganador, la probabilidad, la latencia y la fecha.

**Criterio de salida y resultado.** La migración `criaturas.0003_combatlog`
se aplicó en PostgreSQL local y en la base de pytest. El test de historial
verifica las tres referencias, la conservación de las métricas y el registro
en Admin. `uv run pytest` pasó **19/19**, `uv run python manage.py check` pasó
y `uv run python manage.py makemigrations --check --dry-run` confirmó la
correspondencia entre modelo y migración.

## Fase 3 — Reglas compartidas, inferencia y throttling (2026-11-21)

**Alcance y contrato.** La simulación y la inferencia importan la matriz
`VENTAJAS` de `apps/game/rules.py`. Cada entrada indica el multiplicador del
atacante contra el defensor y un cruce ausente vale 1.0. El modelo sigue
aprendiendo un score sintético determinista al que el simulador aplica ruido
uniforme de ±10 % para cada luchador.

`apps/ml/services.py` prepara las ocho columnas en el orden de entrenamiento,
ejecuta la predicción y obtiene la confianza de la clase predicha. La vista
conserva la carga diferida de artefactos, los códigos HTTP y el formato de
`resultado`. La respuesta añade una clave hermana, `metricas`, con dos objetos.

- `diferencial` contiene ataque, defensa y velocidad, calculados como luchador 1
  menos luchador 2, independientemente del ganador.
- `ventaja_elemental` contiene los multiplicadores ofensivos `luchador_1` y
  `luchador_2`, calculados a partir de sus tipos primarios.

**Throttling.** El endpoint de predicción usa `OraculoThrottle`, derivado de
`ScopedRateThrottle`, con el ámbito `oraculo` y 30 solicitudes por minuto por IP.
Si `ipaddress` clasifica `REMOTE_ADDR` como privada, acepta una única dirección
IPv4 o IPv6 de `CF-Connecting-IP` y la normaliza. Para conexiones públicas,
orígenes inválidos o una cabecera ausente o inválida, delega en DRF. Con
`NUM_PROXIES=0`, DRF usa la dirección de conexión. Esta decisión presupone
que los pares internos con acceso al servicio web son de confianza.
Cada test del Oráculo empieza con una caché de throttling de pruebas vacía. Solo
el test del límite usa 2 solicitudes por minuto. Verifica dos predicciones, un
HTTP 429 con `Retry-After` antes de una tercera inferencia y una petición
aceptada desde otra IP.

**Criterio de salida y resultado.** Se mantuvieron las pruebas anteriores y se
añadieron dos casos para el desglose del servicio y el límite HTTP.
`uv run python manage.py check` pasó,
`uv run python manage.py makemigrations --check --dry-run` confirmó la correspondencia del esquema y `uv run pytest`
pasó **21/21**. Una petición adicional con los dos `.pkl` reales y dos criaturas
en una base de pruebas PostgreSQL devolvió HTTP 200, respetó el contrato JSON y
dejó el historial vacío. Medir la latencia, escribir desde el POST y consultar
el historial corresponden a la fase 4.

**Caché entre workers.** Con `DEBUG=False`, Django usa `FileBasedCache` en
`~/.cache/mithoworld/django`, dentro del directorio del usuario que ejecuta
Gunicorn y fuera de las rutas de estáticos y medios. Los workers del mismo
contenedor comparten ese directorio. El límite de DRF sigue siendo aproximado
bajo concurrencia porque la lectura y la actualización son operaciones separadas.
Con `DEBUG=True` se usa la caché en memoria de Django.

**Confianza no finita.** El servicio comprueba la probabilidad de la clase
predicha con `math.isfinite()` antes de acotarla a 0–1. Ante `NaN`, `inf` o
`-inf`, la vista responde HTTP 503 con un campo `detail`.

**Validación de los ajustes.** `uv run pytest` pasó **31/31** en PostgreSQL.
Los diez casos añadidos cubren las tres probabilidades no finitas y siete
combinaciones de origen y cabecera, incluida la normalización IPv6.
Con `DEBUG=False`, dos procesos independientes ejercitaron el throttle sobre
la caché de archivos. El primero consumió la cuota de prueba y el segundo
denegó otra solicitud del mismo visitante. `manage.py check` pasó y
`makemigrations --check --dry-run` confirmó que el esquema está al día.

## Fase 4 — Explicabilidad y telemetría de la Arena (2026-11-21)

**Alcance y contratos.** Un POST exitoso a `/api/oraculo/predecir/` guarda
un `CombatLog` antes de devolver HTTP 200. El objeto `resultado` conserva
sus cuatro claves. `metricas.latencia_ms` contiene el mismo número que el
historial. El servicio usa un único intervalo de `time.perf_counter()` desde
la preparación del vector hasta la salida de `predict_proba()`, incluyendo
`predict()`. La lectura de criaturas, la carga de artefactos, el cálculo del
desglose, la escritura y la serialización ocurren fuera del intervalo.

El POST normaliza ambos IDs y rechaza luchadores repetidos con HTTP 400 antes
de cargar el modelo. Los errores 400, 404, 429 y 503 dejan intacto el historial.
Un fallo de base de datos al insertar devuelve 503.

El GET público `/api/oraculo/combates/` devuelve `{"combates": []}` para un
historial vacío. Cada fila contiene `id`, `creado_en` en ISO 8601 UTC,
`luchador_1`, `luchador_2`, `ganador_predicho`, `probabilidad` en escala 0–1 y
`metricas` con `diferencial`, `ventaja_elemental` y `latencia_ms`. Cada
referencia se representa mediante `id` y nombre actual, o como `null` completo
tras el borrado. Las métricas proceden del registro. Una sola consulta con
`select_related` recupera hasta diez filas por fecha descendente y desempata por
ID descendente.

**Arena.** Las barras comparan ataque, defensa y velocidad con una escala común
para ambos luchadores en cada fila. La Arena preselecciona dos criaturas si
están disponibles y espera a que el visitante ejecute la predicción. El panel
muestra ganador, confianza, latencia, diferenciales y multiplicadores según las
reglas. La tabla carga al abrir la página y tras cada POST exitoso. Un fallo
del refresco conserva el resultado y las filas anteriores. «Reintentar
historial» repite únicamente el GET. JavaScript inserta texto dinámico con
`textContent` y presenta el plazo de `Retry-After` cuando el POST devuelve 429.

**Criterios de salida y resultados.**

- `uv run python manage.py check` pasó. `uv run python manage.py makemigrations --check --dry-run` confirmó la correspondencia del esquema.
- `uv run pytest` pasó **34/34** con PostgreSQL. Una prueba con reloj controlado verifica un solo intervalo, las dos llamadas de inferencia y el mismo valor en el POST y en la fila persistida. La prueba de throttling de fase 3 cuenta tres éxitos y verifica el recuento inmediatamente después del 429.
- El test del GET usa doce registros con fechas empatadas, verifica el límite y el orden, y exige exactamente **una consulta SQL** por petición, incluso al borrar al ganador y luego a ambos participantes.
- Chromium ejercitó la Arena en escritorio (1280 px) y móvil (375 px) con los artefactos reales y dos criaturas en una base PostgreSQL desechable. Se comprobaron el historial vacío, el retrato ausente, las selecciones repetidas, la actualización tras un éxito y el reintento del GET. Se simularon un fallo de refresco y respuestas 429 con y sin `Retry-After`.

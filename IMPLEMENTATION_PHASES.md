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

## Fase 5 — Perfil analítico de criatura (2026-11-21)

**Alcance y contrato SQL.** La ficha `/criatura/<id>/` muestra cuatro estadísticas
y su posición en el catálogo actual. `apps/analytics/services.py` carga
`sql/perfil_criatura.sql` una vez por proceso y ejecuta la consulta parametrizada
en cada visita. El filtro por ID se aplica después de las ventanas. La puntuación
suma ataque, defensa, velocidad y salud. `RANK()` descendente asigna el puesto 1
a la puntuación máxima y deja saltos tras los empates. `PERCENT_RANK()`
ascendente devuelve una fracción entre 0 y 1. Las cuatro medias usan la partición
completa de tipo primario e incluyen a la criatura consultada.

**Integración.** El router inyecta el servicio de lectura de `analytics` en la
vista de `game`. La ruta conserva el nombre `detalle`. La vista consulta primero
la entidad y luego el perfil. Una ficha existente cuesta dos consultas y un ID
ausente recibe HTTP 404 en una consulta. Los matchups históricos quedan para
la subfase 5B.

**Presentación.** La ficha muestra puesto, puntuación y percentil junto a una
comparativa elemental con barras divergentes. Las medias y diferencias se
presentan a una décima. La escala común usa el mayor valor absoluto de los
cuatro deltas visibles. Si todos valen cero, las cuatro barras tienen ancho
cero. Un delta redondeado a cero se muestra como `0,0` independientemente del
signo original. Un catálogo unitario muestra «1 de 1» y «Sin comparación».
La inicial sustituye al retrato cuando la criatura carece de imagen.

**Validación y criterios de salida.**

- `uv run pytest` pasó **38/38** en PostgreSQL. Las cuatro pruebas nuevas cubren ranking y percentil con empates, catálogo unitario, las cuatro medias y diferencias por elemento, e integración HTML con el presupuesto de consultas. El caso de integración incluye deltas de −1/21 y +1/21 y verifica el texto y el ancho de las barras.
- `uv run python manage.py check` pasó y `uv run python manage.py makemigrations --check --dry-run` confirmó la correspondencia del esquema.
- En Chromium se revisaron fichas con retrato y con inicial en escritorio (1280 px) y móvil (375 px), con 50 criaturas en PostgreSQL de prueba. Se verificaron los cuatro indicadores elementales, el sentido de las barras y el ajuste al ancho disponible. En móvil, cada estadística agrupa valor propio, media y diferencia.

## Fase 6 — Pipeline ML v2 y hechos de simulación para 5B (2026-11-21)

**Alcance y contrato.** `game.rules` normaliza ambos tipos, combina los cruces
dirigidos de la matriz y define el score base de A frente a B como
`ataque_A × multiplicador(A,B) + 0,50 × velocidad_A + 0,25 × salud_A − 0,20 × defensa_B`.
Una criatura monotipo asigna todo el peso al primario. Una de doble tipo asigna
2/3 al primario y 1/3 al secundario, tanto al atacar como al defender. Vacío,
nulo o duplicado del primario representa ausencia de secundario. Simulación y
Arena llaman a la misma función de ventaja. El simulador aplica ruido uniforme
independiente de ±10 % a cada score y sortea con la misma semilla los empates
exactos.

**Dataset.** Se contrastaron las 50 criaturas locales con el catálogo versionado
por nombre, cuatro stats y dos tipos. `uv run python manage.py simular_batallas
--seed 42` muestreó sobre las PK ordenadas y generó 10 000 filas. El CSV contiene
los IDs de los dos luchadores y del ganador, las seis entradas crudas de cada
lado y la etiqueta binaria `gano_primero`. El manifiesto
`dataset_batallas.meta.json` registra versiones, semilla, número de filas y
SHA-256 del CSV y del catálogo. Para 5B, los IDs corresponden a ese catálogo y
la pareja (huella del CSV, posición de fila) identifica cada simulación. Se
observaron 1 224 de las 1 225 parejas posibles.

**Entrenamiento e inferencia.** `uv run python manage.py entrenar_oraculo --seed 42`
valida la cabecera v2, el manifiesto y la coherencia de las filas antes de
entrenar. La lectura usa `keep_default_na=False`. Una prueba compara el DataFrame
que recibe el pipeline del servicio con la fila leída del CSV y comprueba la
categoría vacía del encoder ajustado. El constructor de features se comparte con
el simulador. El pipeline ajusta un ColumnTransformer con ocho enteros y cuatro
categóricas one-hot y un Random Forest de 100 árboles. El worker carga un solo
`modelo_combate.pkl`; el encoder v1 se retiró. El modelo se recarga y evalúa
antes de publicar los artefactos. `modelo_metadata.json` vincula huellas,
features, distribución de clases, partición, métricas, versión de sklearn y fecha UTC.

| Partición por pareja sin orientación | Combates | Parejas | Ganó L1 | Ganó L2 |
|---|---:|---:|---:|---:|
| Entrenamiento | 8 017 | 979 | 4 038 | 3 979 |
| Evaluación | 1 983 | 245 | 991 | 992 |

La evaluación sobre parejas reservadas dio **accuracy 0,851740** y **ROC AUC
0,934440** para la clase 1. Estas métricas miden la reproducción del simulador
sintético. Una segunda ejecución independiente con la misma semilla reprodujo
el CSV byte a byte, el split, las métricas y todas las probabilidades al evaluar
las 10 000 filas con los pipelines recargados.

**API y Arena.** El POST mantiene las cuatro claves de `resultado`. El
diferencial v2 incluye salud y la ventaja usa los dos tipos. La latencia sigue
cubriendo un intervalo desde la preparación del vector hasta completar las
dos llamadas del pipeline. El GET conserva cada JSON histórico, incluidos los
multiplicadores y los diferenciales de tres stats v1. La Arena muestra cuatro
barras y distingue salud ausente («Sin dato») de salud con diferencial cero.

**Criterios de salida.** `uv run pytest` aprobó 42/42 en PostgreSQL, incluyendo
reproducibilidad, paridad monotipo, rechazo de CSV y bosque v1, historial
mixto, confianza no finita, throttling y límites del cronómetro.
`uv run python manage.py check` pasó y `uv run python manage.py makemigrations
--check --dry-run` confirmó la correspondencia del esquema. En Chromium se
comprobaron el POST con el pipeline real, las cuatro barras, «Salud -30» y
los multiplicadores 0,78× y 1,44× para Vornskr y Kaelith, en escritorio
(1280 px) y móvil (375 px).

## Subfase 5B — Historial de combates simulados (2026-11-22)

**Procedencia y carga.** El simulador y el cargador comparten la función
`catalogo_sha256` de `apps/game/catalog.py`. Conserva el orden por PK y la
serialización de la Fase 6. `cargar_combates_simulados` verifica ambas huellas,
las versiones, la cabecera, el recuento, los atributos de los participantes y la
concordancia del ganador con la etiqueta antes de escribir.

**Publicación en PostgreSQL.** El SHA-256 del CSV identifica el lote y la
posición de cada fila dentro de él identifica el combate. La transacción toma
primero un bloqueo `SHARE ROW EXCLUSIVE` sobre los lotes para serializar las
cargas y luego `SHARE` sobre el catálogo para mantener estable su huella.
Inserta bloques de 1 000 hechos y verifica el total. Para publicar o reactivar un
lote, desactiva primero el anterior. Un índice único parcial admite un solo lote
activo. Repetir la carga comprueba los hechos existentes y conserva su fecha de
carga. El admin permite consultar los lotes archivados y el activo en modo de
solo lectura.

**Lectura en la ficha.** `matchups_criatura.sql` reúne con `UNION ALL` los dos
lados del duelo del lote activo. Cada lado tiene un índice compuesto por luchador
y lote. La tasa global incluye todos los combates de la criatura. Para destacar
un rival se exigen ocho enfrentamientos. A igual tasa prevalece el mayor volumen
y luego el menor ID. Si se borra un rival, la FK pasa a `NULL`, los IDs de
origen permanecen inmutables y los duelos siguen contando en la tasa global.
La ficha distingue entre ausencia de lote, criatura sin duelos, muestra
insuficiente, rival único y empate de tasas entre todos los rivales elegibles.
El router inyecta el servicio compuesto en la vista de `game`. Una ficha
existente cuesta tres consultas SQL y un 404 cuesta una. La petición lee los
hechos de PostgreSQL.

**Verificación local.** Se aplicó `analytics.0001_simulaciones` y se cargaron
los 10 000 hechos de la semilla 42 con el manifiesto publicado en la Fase 6.
Una segunda carga devolvió «Ya cargado». Vornskr obtuvo 235 victorias en 379
combates (62,0 %). Entre sus 21 rivales elegibles, ganó 18 de 18 frente a Gorvax
y 0 de 14 frente a Noktis. En Chromium se verificaron esas cifras y los enlaces
a ambas fichas en escritorio (1280 px, tres tarjetas en fila) y móvil (375 px,
tarjetas apiladas).

La suite incluye cargas concurrentes, rollback tras la inserción de un bloque,
reactivación, huellas inválidas, conservación de los IDs de origen y presupuesto
de consultas con el CSV ausente. Pasaron las 57 pruebas, `manage.py check`,
`makemigrations --check --dry-run` y `git diff --check`.

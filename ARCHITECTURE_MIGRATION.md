Complementa a ARCHITECTURE.md — ver ahí el contexto general del stack; este documento cubre específicamente el plan de migración a apps/.

# ARCHITECTURE_MIGRATION.md

> **Estado:** EN EJECUCIÓN — Fases 1 y 2 completadas; scaffolding de `apps/analytics` y `apps/ai` activo.
> **Tipo:** Blueprint, registro de ejecución y ADR del **Monolito Modular**.
> **Rama:** `v2-architecture`
> **Alcance:** Transición desde la estructura plana original (`criaturas/`, `oraculo/`) hacia dominios bajo `apps/`.

## 0. Estado de ejecución

| Fase | Dominio | Estado | Evidencia |
|---|---|---|---|
| 1 | `apps/game` | Completada e integrada | `git mv criaturas apps/game`, `label = 'criaturas'`, imports y URLs actualizados, migraciones preservadas. |
| 2 | `apps/ml` | Completada e integrada | `git mv oraculo apps/ml`, `label = 'oraculo'`, artefactos en `apps/ml/ml_models`, ruta de artefactos module-relative. |
| 3 | `apps/analytics` | Scaffolding activo | App registrada, paquete `management/commands/` y `tests/` creados; ELT/BigQuery y marts pendientes. |
| 4 | `apps/ai` | Scaffolding activo | App registrada, `services.py` documentado y paquete `tests/` creado; cliente LLM y MCP pendientes. |

**Validación actual:** `manage.py check` sin issues, `makemigrations --dry-run` → `No changes detected`,
`pytest` → **10 passed, 0 warnings**.

---

## 1. Contexto y Motivación

MithoWorld nació como una demo funcional: dos apps Django (`criaturas`, `oraculo`)
que combinan modelos, vistas, lógica de negocio y artefactos ML en la raíz del repo.

A medida que la plataforma evoluciona hacia un portafolio Enterprise (Data Engineering,
ML/MLOps, Analytics, AI Engineering), la estructura plana presenta problemas crecientes:

1. **Acoplamiento lógico difuso:** la app `oraculo` mezcla predicción ML (`views.py`),
   generación de datos sintéticos, entrenamiento y artefactos `.pkl`; no hay frontera
   clara entre "módulo ML" y "módulo de negocio del juego".
2. **Sin capa de servicios:** la lógica de negocio vive dentro de `views.py` (p. ej.
   el Battle Engine y la ingeniería de características en `PrediccionCombateView`),
   lo que dificulta testear y reutilizar en futuros jobs (ETL/dbt).
3. **Sin frontera de dominio:** no hay separación explícita entre datos del juego
   (`game`), modelado analítico (`analytics`), modelos ML (`ml`) y experiencia
   narrativa con IA (`ai`).
4. **Escalado de equipos/habilidades:** una estructura por dominios permite que cada
   skill (Data, ML, Analytics, AI) se desarrolle de forma semi-independiente.

El **Monolito Modular** conserva la ventaja de despliegue del monolito (un solo
proceso, un solo repo) mientras establece límites de responsabilidad claros por app,
habilitando una futura migración progresiva a servicios si fuera necesario.

> **Nota de ejecución:** el blueprint original (Paso 0) no movía código. Las Fases 1
> y 2 ya fueron aprobadas y ejecutadas; este documento ahora registra también su estado
> real. `apps/analytics` y `apps/ai` existen como scaffolding sin lógica de negocio.

---

## 2. Mapeo Origen → Target

### 2.1 Mapeo histórico de módulos/archivos (estado previo a la migración)

> Las rutas de origen de esta tabla (`criaturas/`, `oraculo/`) ya no existen en el
> árbol actual: fueron movidas en las Fases 1 y 2. La tabla se conserva como registro
> del alcance y de las decisiones de destino.

| Módulo/Archivo (origen histórico) | Contenido relevante | App destino | Justificación |
|---|---|---|---|
| `criaturas/models.py` | Modelo `Criatura` | `apps/game/` | Entidad central de reglas del juego (stats, tipos). |
| `criaturas/migrations/0001_initial.py`, `0002_criatura_imagen.py` | Migraciones de `Criatura` | `apps/game/migrations/` (movidas en la Fase 1) | Siguen al modelo; se preservaron los `CreateModel` históricos con su label `criaturas` (ver Matriz de Riesgos). |
| `criaturas/views.py` | `CriaturaViewSet`, `home`, `detalle_criatura` | `apps/game/views.py` | Vistas de exposición de datos del juego. |
| `criaturas/serializers.py` | `CriaturaSerializer` | `apps/game/serializers.py` | Serialización API del dominio game. |
| `criaturas/urls.py` | Rutas API de criaturas | `apps/game/urls.py` | Enrutamiento del dominio game. |
| `criaturas/admin.py` | Registro admin | `apps/game/admin.py` | Panel administrativo del dominio. |
| `criaturas/management/commands/poblar_criaturas.py` | Seed idempotente CSV+imágenes | `apps/game/management/commands/` | ETL de datos maestros del juego (fase inicial de ingesta). |
| `criaturas/tests/` | Pruebas pytest-django (idempotencia, imágenes) | `apps/game/tests/` | Siguen al código que prueban. |
| `oraculo/views.py` | `PrediccionCombateView`, `arena_view`, `get_oraculo_models` | `apps/ml/` (lógica de predicción y UI de arena) | La predicción es dominio ML. `arena_view` permanece en `apps/ml/views.py` por compatibilidad; su traslado a `apps/game` queda como deuda técnica. |
| `oraculo/urls.py` | Ruta `predecir/` | `apps/ml/urls.py` | API de predicción ML; la URL pública `/api/oraculo/` se mantiene intacta. |
| `oraculo/ml_models/*.pkl` | `modelo_combate.pkl`, `encoder_tipos.pkl` | `apps/ml/ml_models/` | Artefactos entrenados (registry v1 local); ruta resuelta de forma module-relative. |
| `oraculo/management/commands/simular_batallas.py` | Generación de dataset sintético (10k batallas) | `apps/ml/management/commands/` | Permanece en ML hasta que `apps/analytics` implemente el pipeline ELT; la decisión de moverlo sigue abierta. |
| `oraculo/management/commands/entrenar_oraculo.py` | Entrenamiento Random Forest | `apps/ml/` | Pipeline de entrenamiento (origen del registry). |
| `oraculo/tests/` | Pruebas pytest-django (clamp, 503, estructura) | `apps/ml/tests/` | Siguen al código que prueban. |
| `backend/settings.py` | `INSTALLED_APPS`, DB, media | `backend/settings.py` (sin mover) | Punto de configuración; solo cambia la lista de `INSTALLED_APPS`. |
| `backend/urls.py` | Enrutamiento raíz, include de apps | `backend/urls.py` (sin mover) | Se actualizan los `include(...)` a los nuevos `apps.X.urls`. |
| `criaturas.csv`, `imagenes_semilla/` | Datos maestros y binarios | `apps/game/data/` (opcional) o raíz | Fuente de ingesta; mover solo si aporta (el seed usa rutas relativas a `BASE_DIR`). |
| `templates/`, `static/` | Frontend (HTML, JS, CSS) | `templates/`/`static/` (sin mover) | Compartidos entre dominios; se mantienen en la raíz (decisión de diseño). |

> **Nota de decisión abierta (`simular_batallas`):** genera datos *del juego* (batallas)
> que alimentan el ML. Hoy permanece en `apps/ml`; su posible traslado a
> `apps/analytics` se decidirá al implementar el pipeline ELT.

### 2.2 Dependencias cruzadas históricas (análisis que ordenó las fases)

- `oraculo/views.py` importaba `criaturas.models.Criatura` → **`ml` depende de `game`**.
- `backend/urls.py` importaba vistas de `criaturas` y `oraculo`.
- `criaturas` no importaba `oraculo` → **`game` es el módulo de menor acoplamiento externo** (solo Django/DRF).
- `oraculo/ml_models/*.pkl` se cargaba vía `settings.BASE_DIR` → la ruta se ajustó a `Path(__file__).parent / 'ml_models'` al mover la app.

**Conclusión de orden:** `game` (menor riesgo) → `ml` (depende de `game`) → `analytics` (futuro, a partir de datos de `game`) → `ai` (futuro, consume `game` + `ml`).

---

## 3. Mapeo de Dominio Target (`apps/`)

Estructura actual implementada (monolito modular):

```
backend/
├── settings.py, urls.py            # Config raíz (sin mover)
apps/
├── game/                            # Reglas del juego (Battle Engine)
│   ├── models.py                    # Criatura (label histórico: criaturas)
│   ├── views.py / serializers.py / urls.py / admin.py
│   ├── management/commands/         # poblar_criaturas.py
│   ├── migrations/                  # migraciones históricas preservadas
│   └── tests/
├── ml/                              # Oráculo: ML/MLOps
│   ├── views.py / urls.py           # PrediccionCombateView, arena_view
│   ├── ml_models/                   # modelo_combate.pkl, encoder_tipos.pkl
│   ├── management/commands/         # entrenar_oraculo.py, simular_batallas.py
│   └── tests/
├── analytics/                       # Modelado dimensional (scaffolding)
│   ├── management/commands/         # futuro ELT hacia BigQuery
│   └── tests/
└── ai/                              # Narrador LLM (scaffolding)
    ├── services.py                  # futuro cliente OpenRouter/Gemini
    └── tests/
```

Notas de implementación:
- `apps/game` conserva `label = 'criaturas'` y `apps/ml` conserva `label = 'oraculo'`.
- `apps/ml/ml_models/` es la ubicación real de los artefactos; el `registry/` propuesto
  queda como evolución futura.
- `apps/analytics` y `apps/ai` están registradas en `INSTALLED_APPS`, pero todavía no
  implementan lógica de negocio.

### Responsabilidades por dominio

| Dominio | Responsabilidad | Prohibido incluir |
|---|---|---|
| `game` | Datos maestros, reglas de combate, CRUD API, UI de la arena | Lógica ML, entrenamiento, artefactos |
| `analytics` | Modelado dimensional, marts, métricas, BI | Lógica transaccional; solo lectura sobre `game` |
| `ml` | Predicción, entrenamiento, registry, validación sin leakage | Reglas de negocio del juego, datos de UI |
| `ai` | Generación narrativa, prompts, MCP | Modelos entrenados del oráculo |

---

## 4. Estrategia de Ejecución por Fases

Protocolo general por fase (aplicar en este orden estricto, de menor a mayor riesgo):

```
1. git mv <origen> apps/<dominio>/<destino>
2. Actualizar imports relativos/absolutos (oraculo.views -> apps.ml.views)
3. Actualizar include(...) en backend/urls.py y app_label en settings.INSTALLED_APPS
4. Ajustar rutas físicas de recursos (BASE_DIR, MEDIA_ROOT, artefactos .pkl)
5. uv run python manage.py check  &&  uv run pytest  (verify)
6. Solo entonces: siguiente fase
```

### Fase 1 — `apps/game` (COMPLETADA)
- `criaturas/*` movido a `apps/game/` mediante `git mv`, incluyendo migraciones y tests.
- `INSTALLED_APPS` actualizado a `apps.game`; `backend/urls.py` usa `include('apps.game.urls')`.
- `GameConfig.label = 'criaturas'` conserva `app_label`, tabla `criaturas_criatura`,
  `django_migrations`, `ContentType` y permisos existentes.
- Verificación: `check` sin issues, `makemigrations --dry-run` → `No changes detected`,
  `pytest` verde y smoke test de `/api/criaturas/`.

### Fase 2 — `apps/ml` (COMPLETADA)
- `oraculo/*` movido a `apps/ml/` mediante `git mv`, incluyendo tests y artefactos `.pkl`.
- `MlConfig.label = 'oraculo'` mantiene compatibilidad con el historial previo.
- Imports actualizados a `apps.ml.*`; la URL pública `/api/oraculo/` se mantiene intacta.
- `get_oraculo_models()` y `entrenar_oraculo.py` resuelven `apps/ml/ml_models/` de forma
  module-relative; el CSV de batallas permanece en `BASE_DIR`.
- `arena_view` sigue en `apps/ml/views.py` por compatibilidad (deuda técnica: moverlo a `game`).
- Verificación: `check`, `makemigrations --dry-run`, `pytest` y carga real de
  `RandomForestClassifier` + `LabelEncoder` desde los artefactos.

### Fase 3 — `apps/analytics` (SCAFFOLDING ACTIVO)
- Paquete creado y registrado en `INSTALLED_APPS` con `AnalyticsConfig` (`label = 'analytics'`).
- Estructura lista: `management/commands/` para jobs ELT y `tests/`.
- Pendiente: pipeline ELT hacia BigQuery, marts con dbt y decisión final sobre
  `simular_batallas` (hoy en `apps/ml`).

### Fase 4 — `apps/ai` (SCAFFOLDING ACTIVO)
- Paquete creado y registrado en `INSTALLED_APPS` con `AiConfig` (`label = 'ai'`).
- `services.py` documentado como punto de entrada para OpenRouter/Gemini y prompts.
- Pendiente: cliente LLM, narración de combates e integración MCP segura.

### Criterios de salida por fase
- `uv run pytest` 100% PASSED (estado actual: 10 passed, 0 warnings).
- `manage.py check` y `makemigrations --dry-run` sin cambios inesperados.
- Smoke test manual de los endpoints afectados.
- `manage.py check --deploy` sin errores nuevos antes del merge a `main`.

---

## 5. Matriz de Riesgos

| Riesgo | Severidad | Detalle | Mitigación |
|---|---|---|---|
| **`app_label` en migraciones** | **BAJO** | Al mover `models.py` a otra app, el `app_label` implícito cambiaría y Django generaría `DeleteModel` del viejo + `CreateModel` nuevo (recreando la tabla física). | **Mitigado con `GameConfig.label = 'criaturas'`:** Django resuelve el `app_label` desde `AppConfig.label`, no desde la ruta del paquete. El modelo conserva su label, por lo que tabla, migraciones, `ContentType` y permisos quedan intactos **sin tocar la BD**. Ver detalle abajo. |
| **Trade-off cosmético (ruta vs label)** | BAJO | Con `label = 'criaturas'` dentro de `name = 'apps.game'`, la ruta de importación (`apps.game`) no coincide con el `app_label` interno (`criaturas`) que Django usa para tablas/ContentTypes. | Solo afecta a quien inspeccione internals (nombres de tabla `criaturas_*`, `django_content_type.app_label`). No tiene impacto funcional ni de datos; documentarlo en el ADR para evitar confusión futura. |
| **`INSTALLED_APPS` mal actualizado** | ALTO | Dejar el nombre viejo (`criaturas`) provoca `AppRegistryNotReady` o modelos cargados dos veces (App label conflict). | Actualizar la lista completa en un solo commit por fase; verificar con `manage.py check` y `makemigrations --check --dry-run`. |
| **Rutas de importación rotas** | ALTO | Imports tipo `from criaturas.models import Criatura` repartidos por `oraculo/`, `backend/urls.py` y tests. | `rg -l "criaturas\.\|oraculo\."` global después de cada fase; actualizar en el mismo commit; CI/pytest como red de seguridad. |
| **Dependencias circulares** | MEDIO | `ml` importa `game`; si en el futuro `game` importa `ml` (p. ej. narrativa en batalla) se crea ciclo. | Regla de arquitectura: `game` nunca importa `ml/ai`; si necesita predicción, se inyecta por servicio (DI), nunca por import directo. |
| **Rutas físicas de recursos** | MEDIO | Al mover apps, las rutas construidas con `settings.BASE_DIR` dejan de existir. | Implementado: artefactos ML resueltos como `Path(__file__).parent / 'ml_models'`; el CSV de batallas permanece en `BASE_DIR`. Una futura constante `ML_ARTIFACTS_DIR` en settings sigue recomendada. |
| **Duplicación de modelos (double-registration)** | MEDIO | Si en una fase intermedia ambos módulos conviven, Django detecta dos `Criatura` (app labels distintos) → error al arrancar. | Mover siempre como transacción atómica (modelo + migración + INSTALLED_APPS juntos); nunca dejar el repo en estado intermedio. |
| **Migraciones huérfanas** | MEDIO | Mover las migraciones físicamente antes de tiempo puede romper el grafo o confundir a Django con dos rutas. | **NO se mueven de carpeta física hasta que el resto del código esté migrado.** Orden exacto: (1) mover `models.py`/vistas a `apps/game/` con `label = 'criaturas'`; (2) actualizar `INSTALLED_APPS`/imports; (3) verificar con `manage.py check` y `pytest` que todo sigue funcionando con las migraciones aún en `criaturas/migrations/`; (4) solo entonces `git mv criaturas/migrations apps/game/migrations` conservando nombres y dependencias. |
| **Datos de producción** | CRÍTICO | Migración mal hecha = pérdida de la tabla física en la VM de GCP. | Como no se crea tabla ni migración nueva (solo se mueve el paquete conservando el label), el riesgo es bajo; aun así, respaldar (`pg_dump`) antes de `migrate` en producción y verificar que el plan no pide DDL sobre `criaturas_criatura`. |

### Detalle: estrategia oficial para `app_label` (sin `db_table`, sin `SeparateDatabaseAndState`)

**Escenario concreto** (Fase 1, modelo `Criatura` movido de `criaturas/` a `apps/game/`):

1. En `apps/game/apps.py`, fijar explícitamente el label heredado:
   ```python
   from django.apps import AppConfig

   class GameConfig(AppConfig):
       default_auto_field = 'django.db.models.BigAutoField'
       name = 'apps.game'
       label = 'criaturas'   # conserva el app_label histórico del modelo
   ```
2. En `INSTALLED_APPS` de `settings.py`, registrar la app como `'apps.game'`
   (no `'criaturas'`). Django instanciará `GameConfig`, que declara `label = 'criaturas'`.
3. **Resultado:** `Criatura` se registra con `app_label = 'criaturas'`, sin cambios de
   `db_table` ni operaciones state-only. Las migraciones históricas se resuelven contra
   el mismo label, `ContentType` y permisos quedan intactos y **no se emite ningún
   `DROP TABLE`** sobre `criaturas_criatura`. Las migraciones **permanecen en
   `criaturas/migrations/`** durante este paso; solo se mueven físicamente en el
   sub-paso final (paso 4 del orden de la matriz "Migraciones huérfanas").
4. **Verificación en bases de test limpias:** crear la BD desde cero y confirmar que
   `manage.py migrate` sí ejecuta los `CreateModel` históricos **una sola vez**
   (creando `criaturas_criatura`), sin generar **ningún modelo/tabla adicional
   `game_*`** ni duplicar tablas. En una BD ya migrada (producción), el plan de
   migración debe mostrar **ningún DDL pendiente**.

> **Nota:** este mecanismo funciona en bases de datos de test limpias porque el
> `app_label` es una propiedad de *código* (config), no un estado físico de la BD;
> Migraciones y ContentTypes dependen del label, no de la ruta del paquete.
> La regla es: **el paquete se mueve, el label se hereda.**

---

## 6. Decisiones Registradas (ADR resumido)

- **D1:** Migrar a Monolito Modular con apps bajo `apps/`; sin microservicios todavía.
- **D2:** `game` es el dominio raíz y no depende de `ml`/`ai` (regla anti-ciclos).
- **D3:** El `app_label` histórico se hereda vía `label = 'criaturas'` en `apps/game/apps.py`;
  no se usa `db_table` ni `SeparateDatabaseAndState`. La tabla física no se toca.
- **D4:** Los artefactos ML se resuelven de forma module-relative (`apps/ml/ml_models`);
  el CSV de batallas permanece en `BASE_DIR`. La centralización en constantes de
  `settings.py` sigue como mejora futura.
- **D5:** Fases 1 y 2 ejecutadas y validadas con `check`, `makemigrations --dry-run`
  y `pytest` (10 passed, 0 warnings).
- **D6:** `apps/analytics` y `apps/ai` se crean como scaffolding registrado, sin lógica
  de negocio todavía, para completar la estructura del Monolito Modular antes del merge.
- **D7:** `arena_view` permanece temporalmente en `apps/ml`; su traslado a `apps/game`
  es deuda técnica documentada.
- **D8:** `simular_batallas` permanece en `apps/ml` hasta que el pipeline ELT de
  `apps/analytics` esté implementado.

---

## 7. Siguientes Pasos Propuestos

1. Implementar el pipeline ELT de `apps/analytics` hacia BigQuery y los marts con dbt.
2. Definir si `simular_batallas` se mueve a `analytics` o permanece en `ml`.
3. Extraer la lógica de `PrediccionCombateView` a `apps/ml/services.py`.
4. Trasladar `arena_view` a `apps/game/views.py`.
5. Implementar el narrador LLM y la integración MCP segura en `apps/ai`.
6. Ejecutar `check --deploy`, smoke tests y merge de `v2-architecture` a `main`.

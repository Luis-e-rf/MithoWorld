Complementa a ARCHITECTURE.md — ver ahí el contexto general del stack; este documento cubre específicamente el plan de migración a apps/.

# ARCHITECTURE_MIGRATION.md

> **Estado:** PROPUESTA (Blueprint / ADR) — Paso 0, Misión 4
> **Tipo:** Documento de diseño y plan de migración. **NO crea carpetas ni mueve código.**
> **Rama:** `v2-architecture`
> **Alcance:** Transición de la estructura plana actual (`criaturas/`, `oraculo/`) a un **Monolito Modular** con dominios bajo `apps/`.

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

> **Restricción del Paso 0:** este documento es el único entregable de esta misión.
> La creación de `apps/` y los `git mv` quedan **fuera de alcance** y requieren
> aprobación explícita (Paso futuro).

---

## 2. Mapeo Actual → Target

### 2.1 Tabla explícita de módulos/archivos HOY

| Módulo/Archivo (HOY) | Contenido relevante | App destino | Justificación |
|---|---|---|---|
| `criaturas/models.py` | Modelo `Criatura` | `apps/game/` | Entidad central de reglas del juego (stats, tipos). |
| `criaturas/migrations/0001_initial.py`, `0002_criatura_imagen.py` | Migraciones de `Criatura` | `apps/game/migrations/` (se mueven al final de la Fase 1) | Siguen al modelo; se preservan los `CreateModel` históricos con su label `criaturas` (ver Matriz de Riesgos). No se mueven hasta que el código esté migrado. |
| `criaturas/views.py` | `CriaturaViewSet`, `home`, `detalle_criatura` | `apps/game/views.py` | Vistas de exposición de datos del juego. |
| `criaturas/serializers.py` | `CriaturaSerializer` | `apps/game/serializers.py` | Serialización API del dominio game. |
| `criaturas/urls.py` | Rutas API de criaturas | `apps/game/urls.py` | Enrutamiento del dominio game. |
| `criaturas/admin.py` | Registro admin | `apps/game/admin.py` | Panel administrativo del dominio. |
| `criaturas/management/commands/poblar_criaturas.py` | Seed idempotente CSV+imágenes | `apps/game/management/commands/` | ETL de datos maestros del juego (fase inicial de ingesta). |
| `criaturas/tests/` | Pruebas pytest-django (idempotencia, imágenes) | `apps/game/tests/` | Siguen al código que prueban. |
| `oraculo/views.py` | `PrediccionCombateView`, `arena_view`, `get_oraculo_models` | `apps/ml/` (lógica de predicción) + `apps/game/` (arena UI) | La **predicción** es dominio ML; `arena_view` es una página del juego. Se recomienda separar: lógica ML a `apps/ml/services.py`, vista HTML a `apps/game/views.py`. |
| `oraculo/urls.py` | Ruta `predecir/` | `apps/ml/urls.py` | API de predicción ML. |
| `oraculo/ml_models/*.pkl` | `modelo_combate.pkl`, `encoder_tipos.pkl` | `apps/ml/artifacts/` | Artefactos entrenados (registry v1 local). |
| `oraculo/management/commands/simular_batallas.py` | Generación de dataset sintético (10k batallas) | `apps/game/` o `apps/ml/` | Es **generación de datos históricos** del juego → `apps/game` (o `apps/analytics` como semilla del mart). Se decide en fase de diseño detallado. |
| `oraculo/management/commands/entrenar_oraculo.py` | Entrenamiento Random Forest | `apps/ml/` | Pipeline de entrenamiento (origen del registry). |
| `oraculo/tests/` | Pruebas pytest-django (clamp, 503, estructura) | `apps/ml/tests/` | Siguen al código que prueban. |
| `backend/settings.py` | `INSTALLED_APPS`, DB, media | `backend/settings.py` (sin mover) | Punto de configuración; solo cambia la lista de `INSTALLED_APPS`. |
| `backend/urls.py` | Enrutamiento raíz, include de apps | `backend/urls.py` (sin mover) | Se actualizan los `include(...)` a los nuevos `apps.X.urls`. |
| `criaturas.csv`, `imagenes_semilla/` | Datos maestros y binarios | `apps/game/data/` (opcional) o raíz | Fuente de ingesta; mover solo si aporta (el seed usa rutas relativas a `BASE_DIR`). |
| `templates/`, `static/` | Frontend (HTML, JS, CSS) | `templates/`/`static/` (sin mover) | Compartidos entre dominios; se mantienen en la raíz (decisión de diseño). |

> **Nota de decisión abierta (`simular_batallas`):** genera datos *del juego* (batallas)
> que alimentan el ML. Para la migración se sugiere dejar el dataset en `apps/game` y
> que `apps/ml/entrenar_oraculo.py` lo consuma como input. Debatir con CTO en el Paso 1.

### 2.2 Dependencias cruzadas detectadas (para ordenar fases)

- `oraculo/views.py` importa `criaturas.models.Criatura` → **`ml` depende de `game`**.
- `backend/urls.py` importa vistas de `criaturas` y `oraculo`.
- `criaturas` no importa `oraculo` → **`game` es el módulo de menor acoplamiento externo** (solo Django/DRF).
- `oraculo/ml_models/*.pkl` se carga vía `settings.BASE_DIR` → la ruta física cambia al mover; ajustar `get_oraculo_models()`.

**Conclusión de orden:** `game` (menor riesgo) → `ml` (depende de `game`) → `analytics` (futuro, a partir de datos de `game`) → `ai` (futuro, consume `game` + `ml`).

---

## 3. Mapeo de Dominio Target (`apps/`)

Estructura propuesta (monolito modular):

```
backend/
├── settings.py, urls.py            # Config raíz (sin mover)
apps/
├── game/                            # Reglas del juego (Battle Engine)
│   ├── models.py                    # Criatura, y futuros: Batalla, Tipo, Elemento
│   ├── services.py                  # Battle Engine (lógica pura, dataclasses, DI)
│   ├── views.py / serializers.py / urls.py / admin.py
│   ├── management/commands/         # poblar_criaturas.py, simular_batallas.py
│   └── migrations/                  # con manejo de app_label (ver Matriz)
├── analytics/                       # Modelado dimensional (Star Schema)
│   ├── marts/                       # dbt models (semillas SQL de métricas)
│   ├── etl/                         # Jobs de ingesta a partir de game
│   └── migrations/
├── ml/                              # Oráculo: ML/MLOps
│   ├── services.py                  # get_oraculo_models(), predict (desde views)
│   ├── registry/                    # Modelos versionados + metadata (artefactos)
│   ├── management/commands/         # entrenar_oraculo.py
│   ├── validation/                  # Evaluación sin data leakage (hold-out/temporal)
│   └── migrations/
└── ai/                              # Narrador LLM (MCP seguro)
    ├── services.py                  # Narrativa con LLM
    ├── mcp/                         # Servidores MCP seguros
    └── migrations/
```

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

### Fase 1 — `apps/game` (riesgo BAJO)
- Mover `criaturas/*` → `apps/game/` (`models`, `views`, `serializers`, `urls`, `admin`, `management`, `tests`).
- Actualizar `INSTALLED_APPS` (`criaturas` → `apps.game`) y `backend/urls.py` (`include('criaturas.urls')` → `include('apps.game.urls')`).
- **Atención a migraciones:** ver Sección 5 (app_label / db_table) antes de `migrate`.
- Verificación: `manage.py check`, `pytest` (suite actual de criaturas), prueba manual API `/api/criaturas/`.

### Fase 2 — `apps/ml` (riesgo MEDIO, depende de Fase 1)
- Mover lógica ML de `oraculo/views.py` a `apps/ml/services.py`; mover `PrediccionCombateView` a `apps/ml/views.py`.
- Mover `arena_view` (HTML) a `apps/game/views.py` (página del juego).
- Mover `oraculo/ml_models/*.pkl` → `apps/ml/registry/` y **ajustar `get_oraculo_models()`** (la ruta de `settings.BASE_DIR` cambia).
- Actualizar imports de `criaturas.models.Criatura` → `apps.game.models.Criatura`.
- Verificación: `pytest` completo, predicción real en `/api/oraculo/predecir/`.

### Fase 3 — `apps/analytics` (riesgo MEDIO, lectura de `game`)
- Crear dominio con jobs de ingesta y marts dbt sobre tablas de `game`.
- Reubicar `simular_batallas` aquí SOLO si se decide que el dataset histórico es activo analítico (decisión pendiente, §2.1).

### Fase 4 — `apps/ai` (riesgo MEDIO-ALTO, futuro)
- Crear dominio de narrador LLM; consumir `game` (criaturas) y `ml` (resultados).
- Integración MCP segura (sin exponer credenciales).

### Criterios de salida por fase
- `uv run pytest` 100% PASSED.
- `manage.py check --deploy` sin errores nuevos.
- Smoke test manual de los endpoints afectados.

---

## 5. Matriz de Riesgos

| Riesgo | Severidad | Detalle | Mitigación |
|---|---|---|---|
| **`app_label` en migraciones** | **BAJO** | Al mover `models.py` a otra app, el `app_label` implícito cambiaría y Django generaría `DeleteModel` del viejo + `CreateModel` nuevo (recreando la tabla física). | **Mitigado con `GameConfig.label = 'criaturas'`:** Django resuelve el `app_label` desde `AppConfig.label`, no desde la ruta del paquete. El modelo conserva su label, por lo que tabla, migraciones, `ContentType` y permisos quedan intactos **sin tocar la BD**. Ver detalle abajo. |
| **Trade-off cosmético (ruta vs label)** | BAJO | Con `label = 'criaturas'` dentro de `name = 'apps.game'`, la ruta de importación (`apps.game`) no coincide con el `app_label` interno (`criaturas`) que Django usa para tablas/ContentTypes. | Solo afecta a quien inspeccione internals (nombres de tabla `criaturas_*`, `django_content_type.app_label`). No tiene impacto funcional ni de datos; documentarlo en el ADR para evitar confusión futura. |
| **`INSTALLED_APPS` mal actualizado** | ALTO | Dejar el nombre viejo (`criaturas`) provoca `AppRegistryNotReady` o modelos cargados dos veces (App label conflict). | Actualizar la lista completa en un solo commit por fase; verificar con `manage.py check` y `makemigrations --check --dry-run`. |
| **Rutas de importación rotas** | ALTO | Imports tipo `from criaturas.models import Criatura` repartidos por `oraculo/`, `backend/urls.py` y tests. | `rg -l "criaturas\.\|oraculo\."` global después de cada fase; actualizar en el mismo commit; CI/pytest como red de seguridad. |
| **Dependencias circulares** | MEDIO | `ml` importa `game`; si en el futuro `game` importa `ml` (p. ej. narrativa en batalla) se crea ciclo. | Regla de arquitectura: `game` nunca importa `ml/ai`; si necesita predicción, se inyecta por servicio (DI), nunca por import directo. |
| **Rutas físicas de recursos** | MEDIO | `get_oraculo_models()` y `poblar_criaturas.py` usan `settings.BASE_DIR`; al mover carpetas la ruta deja de existir. | Centralizar rutas en `settings.py` (constantes `ML_ARTIFACTS_DIR`, `SEED_IMAGES_DIR`) en vez de `os.path.join(BASE_DIR, ...)` hardcodeado en los comandos. |
| **Duplicación de modelos (double-registration)** | MEDIO | Si en una fase intermedia ambos módulos conviven, Django detecta dos `Criatura` (app labels distintos) → error al arrancar. | Mover siempre como transacción atómica (modelo + migración + INSTALLED_APPS juntos); nunca dejar el repo en estado intermedio. |
| **Migraciones huérfanas** | MEDIO | Mover las migraciones físicamente antes de tiempo puede romper el grafo o confundir a Django con dos rutas. | **NO se mueven de carpeta física hasta que el resto del código esté migrado.** Orden exacto: (1) mover `models.py`/vistas a `apps/game/` con `label = 'criaturas'`; (2) actualizar `INSTALLED_APPS`/imports; (3) verificar con `manage.py check` y `pytest` que todo sigue funcionando con las migraciones aún en `criaturas/migrations/`; (4) solo entonces `git mv criaturas/migrations apps/game/migrations` conservando nombres y dependencias. |
| **Datos de producción** | CRÍTICO | Migración mal hecha = pérdida de la tabla física en el VPS. | Como no se crea tabla ni migración nueva (solo se mueve el paquete conservando el label), el riesgo es bajo; aun así, respaldar (`pg_dump`) antes de `migrate` en producción y verificar que el plan no pide DDL sobre `criaturas_criatura`. |

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
- **D4:** Las rutas físicas de artefactos (`.pkl`, seed) pasan a constantes en `settings.py`.
- **D5:** El contenido del Paso 0 termina con este documento; el movimiento de código
  requiere aprobación explícita para un siguiente Paso.

---

## 7. Siguientes Pasos Propuestos (fuera de alcance de este documento)

1. Aprobar el blueprint (Luis + CTO + Codex).
2. Ejecutar **Fase 1** (`apps/game`) con `git mv` y verificación completa.
3. Resolver la decisión abierta de `simular_batallas` (game vs analytics).
4. Diseñar `apps/ml` services layer (extraer lógica de `PrediccionCombateView`).

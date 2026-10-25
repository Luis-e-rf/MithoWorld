# MithoWorld V2.0 - Architecture Context

## Project Overview
Motor de batallas RPG (simulador) y plataforma de analítica de datos.
El proyecto combina ingeniería de software clásico (Django) con Data Engineering y ML predictivo.

## Current Architecture Status
La migración al **Monolito Modular** está en ejecución sobre la rama `v2-architecture`:

| Dominio | Estado | Responsabilidad actual |
|---|---|---|
| `apps/game` | Completado e integrado | Datos maestros, API CRUD, UI del juego y seed idempotente. |
| `apps/ml` | Completado e integrado | Predicción con Random Forest, artefactos `.pkl`, entrenamiento y simulación. |
| `apps/analytics` | Scaffolding activo | Base para jobs ELT hacia BigQuery y marts de analítica. |
| `apps/ai` | Scaffolding activo | Base para el narrador de combates con LLM (OpenRouter/Gemini). |

La app legacy `criaturas` conserva el `app_label` histórico `criaturas` mediante
`GameConfig.label`, por lo que las tablas y migraciones existentes no cambian.
`oraculo` conserva el label `oraculo` mediante `MlConfig.label`.
El detalle de fases, riesgos y decisiones está en
[`ARCHITECTURE_MIGRATION.md`](./ARCHITECTURE_MIGRATION.md).

## Tech Stack
- **Backend:** Python 3.12, Django 5.2, Django REST Framework.
- **Environment:** `uv` (Gestor de dependencias). Ejecutar comandos siempre con `uv run`.
- **Database:** PostgreSQL 16 (vía Docker).
- **Production:** GCP Compute Engine `e2-micro`, Docker Compose, Gunicorn, WhiteNoise y Cloudflare Zero Trust Tunnel.
- **Architecture Pattern:** Fat Services, Skinny Views/Models. La lógica de negocio pura (ej. Battle Engine) vive en `services.py` usando `dataclasses`.

## AI Coding Guidelines
1. **No Blind Hooks:** No asumir la existencia de variables o tablas de DB sin verificar los modelos primero.
2. **Deterministic Code:** Las funciones de cálculo matemático deben ser puras y fáciles de testear.
3. **No Legacy Tools:** No usar `pip` o `virtualenv`. Todo se gestiona vía `uv`.
4. **Language:** Explicaciones arquitectónicas y comentarios en Español. Código (variables, funciones) en Inglés o Español según el estándar del archivo.

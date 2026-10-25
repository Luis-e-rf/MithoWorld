# MithoWorld V2.0 - Architecture Context

## Project Overview
Motor de batallas RPG (simulador) y plataforma de analítica de datos. 
El proyecto combina ingeniería de software clásico (Django) con Data Engineering y ML predictivo.

## Tech Stack
- **Backend:** Python 3.12, Django 5.2, Django REST Framework.
- **Environment:** `uv` (Gestor de dependencias). Ejecutar comandos siempre con `uv run`.
- **Database:** PostgreSQL 16 (vía Docker).
- **Architecture Pattern:** Fat Services, Skinny Views/Models. La lógica de negocio pura (ej. Battle Engine) vive en `services.py` usando `dataclasses`.

## AI Coding Guidelines
1. **No Blind Hooks:** No asumir la existencia de variables o tablas de DB sin verificar los modelos primero.
2. **Deterministic Code:** Las funciones de cálculo matemático deben ser puras y fáciles de testear.
3. **No Legacy Tools:** No usar `pip` o `virtualenv`. Todo se gestiona vía `uv`.
4. **Language:** Explicaciones arquitectónicas y comentarios en Español. Código (variables, funciones) en Inglés o Español según el estándar del archivo.
# MithoWorld

MithoWorld es un proyecto de ingeniería de datos e IA que permite seguir un combate desde los datos de las criaturas hasta una predicción explicada. La galería sitúa a cada criatura en el catálogo, la Arena compara dos rivales y el panel Analytics muestra cómo se generaron y evaluaron los datos. [Demo pública](https://mithoworld.yurack.com)

| Dominio | Qué se puede explorar |
|---|---|
| Game | Galería en `/`, ficha en `/criatura/<id>/` y catálogo de solo lectura en `/api/criaturas/`. Cada criatura tiene cuatro estadísticas y hasta dos tipos elementales. |
| ML | En `/arena/`, un pipeline de scikit-learn predice el ganador. La Arena presenta confianza, diferenciales, factores elementales y latencia de inferencia. Cada predicción exitosa queda en `CombatLog`. |
| Analytics | La ficha reúne ranking, percentil, medias por elemento y enfrentamientos históricos del lote activo. En `/analytics/` se pueden consultar el balance elemental, las métricas del modelo publicado y el linaje de ambos. |
| AI | «Generar crónica» narra una predicción ya registrada. Un consumidor opcional procesa la solicitud en segundo plano y valida cada línea contra la instantánea del duelo. |

El modelo publicado se entrenó con 10 000 duelos simulados de semilla 42. En los 1 983 duelos de evaluación, cuyas parejas quedaron fuera del entrenamiento, obtuvo **85,17 % de accuracy** y **0,9344 de ROC AUC**. Estas cifras miden cuánto reproduce el modelo al simulador. El dashboard consulta los metadatos del artefacto en cada visita. [Metadatos de evaluación](apps/ml/ml_models/modelo_metadata.json)

La arquitectura describe las dependencias de los cuatro dominios. La bitácora conserva las decisiones, pruebas y resultados de cada fase. [Arquitectura vigente](ARCHITECTURE.md) · [Bitácora de implementación](IMPLEMENTATION_PHASES.md)

## Desarrollo local

Se necesitan Python 3.12, `uv`, Docker y Docker Compose. Desde la raíz del clon, por ejemplo `~/workspace/MithoWorld` en Ubuntu WSL, instala las dependencias bloqueadas y crea la configuración la primera vez.

```bash
uv sync --locked
cp -n .env.example .env
```

Completa `SECRET_KEY` y `DB_PASSWORD` en `.env` antes de iniciar PostgreSQL. Para generar una clave puedes usar `uv run python -c "import secrets; print(secrets.token_urlsafe(64))"`. Conserva la clave entre reinicios. En local, la plantilla usa `DEBUG=True`, `DB_HOST=localhost` y `DB_PORT=5432`. Las credenciales de PostgreSQL se inicializan al crear el volumen. [Plantilla de entorno](.env.example)

```bash
docker compose up -d --wait db
uv run python manage.py migrate
uv run python manage.py poblar_criaturas
uv run python manage.py cargar_combates_simulados
uv run python manage.py runserver
```

Abre `http://127.0.0.1:8000/`. El repositorio incluye el dataset, el manifiesto y el pipeline v2 para este primer arranque. La ingesta busca retratos opcionales en `imagenes_semilla/` y guarda los archivos asociados en `media/`. Para usar `/admin/`, crea el usuario con `uv run python manage.py createsuperuser`.

## Comandos esenciales

| Comando | Cuándo usarlo |
|---|---|
| `uv run python manage.py poblar_criaturas` | Sincronizar por nombre los datos de `criaturas.csv`. Repetir la carga conserva las imágenes ya asociadas. |
| `uv run python manage.py simular_batallas --seed 42` | Regenerar `dataset_batallas.csv` y su manifiesto a partir del catálogo de PostgreSQL. |
| `uv run python manage.py entrenar_oraculo --seed 42` | Validar el dataset, separar parejas, entrenar y publicar juntos el pipeline v2 y sus metadatos en `apps/ml/ml_models/`. |
| `uv run python manage.py cargar_combates_simulados` | Validar las huellas del CSV y del catálogo, cargar los hechos y activar el lote en una transacción. Repetir el comando con el mismo lote conserva el recuento. |
| `uv run python manage.py procesar_cronicas` | Ejecutar el consumidor en otra terminal con las credenciales de IA configuradas. La opción `--once` intenta procesar un trabajo y termina. |
| `uv run python manage.py makemigrations` | Generar migraciones después de modificar modelos. Revisa los archivos generados y aplica los cambios con `uv run python manage.py migrate`. |
| `uv run python manage.py check` | Validar la configuración de Django. Para comprobar además que los modelos tienen su migración, ejecuta `uv run python manage.py makemigrations --check --dry-run`. |
| `uv run pytest` | Ejecutar la suite con PostgreSQL y un proveedor LLM simulado. El usuario de BD necesita permiso para crear la base de pruebas. |

Al cambiar de catálogo o semilla, ejecuta en orden simulación, entrenamiento y carga del lote. La huella del catálogo incluye las PK. Si una instalación existente tiene los mismos nombres con otros IDs, el cargador rechazará el lote publicado. En ese caso genera el dataset con ese catálogo y conserva los artefactos correspondientes para el siguiente despliegue.

## Operación en GCP

El despliegue previsto para Compute Engine `e2-micro` usa Gunicorn, PostgreSQL 16 y un túnel saliente de Cloudflare. En la VM, configura `.env` con `SECRET_KEY`, las credenciales del volumen de PostgreSQL y `CLOUDFLARE_TUNNEL_TOKEN`. Define `ALLOWED_HOSTS=mithoworld.yurack.com` y `CSRF_TRUSTED_ORIGINS=https://mithoworld.yurack.com` si ese es el dominio del túnel. Compose fija `DEBUG=False` y `DB_HOST=db`. El destino HTTP del túnel dentro de la red Docker es `http://web:8000`. [Compose de producción](docker-compose.prod.yml)

| Modalidad | Configuración y arranque desde la raíz del proyecto |
|---|---|
| Demo con predicción ML y Analytics | Deja vacíos `CRONICA_API_KEY` y `CRONICA_MODELO`. Ejecuta `docker compose -f docker-compose.prod.yml up -d --build`. |
| Demo con Crónica del Oráculo | Configura la clave de OpenRouter y el identificador del modelo en esas dos variables. Ejecuta `docker compose -f docker-compose.prod.yml --profile ai up -d --build`. El perfil añade `cronista`. |

El servicio `web` aplica las migraciones y recoge los estáticos al arrancar. En una instalación nueva, una vez que Gunicorn esté en servicio, inicializa el catálogo y los hechos con los artefactos incluidos en la imagen.

```bash
docker compose -f docker-compose.prod.yml exec web uv run python manage.py poblar_criaturas
docker compose -f docker-compose.prod.yml exec web uv run python manage.py cargar_combates_simulados
docker compose -f docker-compose.prod.yml exec web uv run python manage.py check --deploy
```

PostgreSQL y los retratos persisten en volúmenes. Para sustituir el modelo, incorpora el pipeline y los metadatos resultantes a la nueva imagen y recrea los workers. La crónica admite `json_object` y `json_schema`. Los límites iniciales son 15 s por llamada, 256 tokens de salida y 100 intentos por día UTC. Para volver de IA a la demo, detén `cronista` con `docker compose -f docker-compose.prod.yml --profile ai stop cronista`, vacía las dos variables de IA y vuelve a aplicar el comando de la demo. [Opciones del consumidor](.env.example)

### Verificación antes del despliegue

En el cierre local, `uv run pytest` pasó 97/97. Con configuración de producción simulada, `check --deploy` informó cuatro advertencias sobre HSTS, redirección HTTPS y cookies de sesión y CSRF. Las comprobaciones del dominio y del proxy en GCP quedan pendientes para el despliegue. [Resultados y ajustes implicados](IMPLEMENTATION_PHASES.md#cierre-documental-y-verificación-pre-deploy)

## Autor

Luis Ernesto Rodríguez Felacio · Ingeniero Informático y Especialista en Inteligencia Artificial. [LinkedIn](https://www.linkedin.com/in/luis-ernesto-rodriguez-felacio/)

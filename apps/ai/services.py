"""Cliente OpenRouter; solo el consumidor invoca este servicio."""
import asyncio
import json

from django.conf import settings

from .narrativa import HECHOS, hechos_duelo, realizar_plan

URL = 'https://openrouter.ai/api/v1/chat/completions'
ESQUEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['lineas'],
    'properties': {'lineas': {'type': 'array', 'minItems': 2, 'maxItems': 4, 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['hecho', 'variante'],
        'properties': {'hecho': {'type': 'string', 'enum': list(HECHOS)},
                       'variante': {'type': 'integer', 'enum': [0, 1, 2, 3]}},
    }}},
}
SISTEMA = (
    'Eres el editor de una crónica breve en español sobre una predicción. Selecciona de dos a cuatro '
    'hechos distintos del duelo, ordénalos con fluidez y termina con pronostico. Alterna el foco entre '
    'afinidad, contraste estadístico y equilibrio según los datos. Cada línea tiene un hecho y una variante '
    'de redacción de 0 a 3. La confianza pertenece al pronóstico. Devuelve exclusivamente JSON según este esquema: '
    + json.dumps(ESQUEMA, ensure_ascii=False)
)


class ErrorProveedor(Exception):
    """Categoría publicable en el log, sin cuerpo HTTP ni credenciales."""


def configurado():
    return bool(settings.CRONICA_API_KEY and settings.CRONICA_MODELO
                and len(settings.CRONICA_MODELO) <= 200
                and settings.CRONICA_FORMATO in ('json_schema', 'json_object')
                and settings.CRONICA_MAX_TOKENS > 0 and settings.CRONICA_TIMEOUT_S > 0)


async def generar_cronica(combate, *, transport=None):
    import httpx  # Gunicorn solo consulta o encola trabajos.

    hechos = hechos_duelo(combate)
    formato = {'type': settings.CRONICA_FORMATO}
    if settings.CRONICA_FORMATO == 'json_schema':
        formato['json_schema'] = {'name': 'cronica', 'strict': True, 'schema': ESQUEMA}
    solicitud = {
        'model': settings.CRONICA_MODELO, 'stream': False, 'max_tokens': min(512, settings.CRONICA_MAX_TOKENS),
        'response_format': formato,
        'provider': {'require_parameters': settings.CRONICA_REQUIRE_PARAMETERS, 'allow_fallbacks': False},
        'messages': [{'role': 'system', 'content': SISTEMA},
                     {'role': 'user', 'content': json.dumps(hechos, ensure_ascii=False, allow_nan=False)}],
    }
    try:
        async with asyncio.timeout(settings.CRONICA_TIMEOUT_S):
            async with httpx.AsyncClient(transport=transport, trust_env=False,
                                         timeout=httpx.Timeout(settings.CRONICA_TIMEOUT_S, connect=3)) as cliente:
                async with cliente.stream('POST', URL, json=solicitud, headers={
                    'Authorization': f'Bearer {settings.CRONICA_API_KEY}', 'Accept-Encoding': 'identity',
                }) as respuesta:
                    if respuesta.status_code != 200:
                        raise ErrorProveedor(f'http_{respuesta.status_code}')
                    if respuesta.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                        raise ErrorProveedor('codificacion_inesperada')
                    contenido = bytearray()
                    async for parte in respuesta.aiter_bytes(chunk_size=8192):
                        contenido.extend(parte)
                        if len(contenido) > 32768:
                            raise ErrorProveedor('respuesta_demasiado_larga')
        candidato = json.loads(contenido)['choices'][0]
        if candidato['finish_reason'] != 'stop':
            raise ErrorProveedor('respuesta_incompleta')
        plan = json.loads(candidato['message']['content'])
        return realizar_plan(plan, combate, hechos)
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise ErrorProveedor('timeout') from exc
    except httpx.RequestError as exc:
        raise ErrorProveedor('red') from exc
    except (ValueError, KeyError, IndexError, TypeError, RecursionError) as exc:
        raise ErrorProveedor('respuesta_invalida') from exc

from django.shortcuts import render
from django.views.decorators.http import require_safe

from .services import obtener_dashboard


@require_safe
def dashboard_universo(request, leer_metricas_modelo):
    universo = obtener_dashboard()
    modelo = leer_metricas_modelo()
    lote = universo['dataset_sha256']
    return render(request, 'analytics.html', {
        'universo': universo,
        'modelo': modelo,
        'otro_lote': bool(modelo and lote and modelo['dataset_sha256'] != lote),
    })

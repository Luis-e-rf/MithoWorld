from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.game.combates import referencia_valida
from backend.throttling import CloudflareThrottle
from .cola import Resultado, consultar, solicitar


class CronicaView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [CloudflareThrottle]

    def get_throttles(self):
        self.throttle_scope = 'cronica' if self.request.method == 'POST' else 'cronica_lectura'
        return super().get_throttles()

    def finalize_response(self, request, response, *args, **kwargs):
        response['Cache-Control'] = 'private, no-store'
        return super().finalize_response(request, response, *args, **kwargs)

    def handle_exception(self, exc):
        respuesta = super().handle_exception(exc)
        if respuesta.status_code == 429:
            respuesta.data = self._datos(self.kwargs['pk'], Resultado('limite_ip', 429, True))
        return respuesta

    @staticmethod
    def _datos(pk, r):
        return {'combate_id': pk, 'estado': r.estado, 'lineas': r.lineas, 'reintentable': r.reintentable}

    def _responder(self, request, pk, operacion):
        if pk > 2**63 - 1 or not referencia_valida(pk, request.headers.get('X-Combate-Referencia', '')):
            resultado = Resultado('referencia_invalida', 403)
        elif request.query_params or request.stream is not None:
            resultado = Resultado('entrada_invalida', 400)
        else:
            resultado = operacion(pk)
        headers = {'Retry-After': str(resultado.espera)} if resultado.espera else {}
        return Response(self._datos(pk, resultado), status=resultado.status, headers=headers)

    def post(self, request, pk):
        return self._responder(request, pk, solicitar)

    def get(self, request, pk):
        return self._responder(request, pk, consultar)

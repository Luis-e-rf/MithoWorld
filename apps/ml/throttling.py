from ipaddress import ip_address

from rest_framework.throttling import ScopedRateThrottle


class OraculoThrottle(ScopedRateThrottle):
    def get_ident(self, request):
        try:
            origen = ip_address(request.META.get('REMOTE_ADDR'))
            if origen.is_private:
                visitante = request.headers.get('CF-Connecting-IP', '').strip()
                # El túnel envía una dirección sin identificador de interfaz IPv6.
                if '%' not in visitante:
                    return str(ip_address(visitante))
        except ValueError:
            pass
        return super().get_ident(request)

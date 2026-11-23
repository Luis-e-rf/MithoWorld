from backend.throttling import CloudflareThrottle


class OraculoThrottle(CloudflareThrottle):
    """Ámbito de cuota del endpoint ML."""

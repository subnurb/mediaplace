"""Development-only middleware: redirect HTTP to HTTPS when using runsslserver."""

from django.conf import settings
from django.http import HttpResponseRedirect


def _get_redirect_url(request):
    """Build https URL with configured dev port (e.g. https://localhost:8443/path)."""
    host = request.get_host().split(":")[0]
    port = getattr(settings, "HTTPS_DEV_PORT", 8443)
    path = request.get_full_path()
    return f"https://{host}:{port}{path}"


class HTTPSRedirectMiddleware:
    """
    Redirect HTTP requests to HTTPS in development when USE_HTTPS_DEV_REDIRECT is True.

    Use with two processes:
      - Terminal 1: python manage.py runsslserver 8443   (serves HTTPS)
      - Terminal 2: python manage.py runserver 8000       (serves HTTP, redirects to 8443)

    Or run only runsslserver 8000 and use https://localhost:8000 (no redirect).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.DEBUG
            and getattr(settings, "USE_HTTPS_DEV_REDIRECT", False)
            and not request.is_secure()
        ):
            return HttpResponseRedirect(_get_redirect_url(request), status=302)
        return self.get_response(request)

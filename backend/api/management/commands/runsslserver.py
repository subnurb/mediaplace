"""
HTTPS development server compatible with Python 3.12+ (uses ssl.SSLContext).

Overrides django-sslserver's runsslserver, which uses deprecated ssl.wrap_socket
removed in Python 3.12. Use the same CLI and default certs from the sslserver package.
"""

import os
import ssl
import sys
from datetime import datetime
from pathlib import Path

from django.core.management.base import CommandError
from django.core.management.commands import runserver
from django.core.servers.basehttp import (
    ThreadedWSGIServer,
    WSGIRequestHandler as BaseWSGIRequestHandler,
)
from django.contrib.staticfiles.handlers import StaticFilesHandler

try:
    from django.core.servers.basehttp import WSGIServerException
except ImportError:
    from socket import error as WSGIServerException


def _default_ssl_dir():
    """Default cert directory — prefer mkcert certs in frontend/certs/."""
    project_certs = Path(__file__).resolve().parent.parent.parent.parent.parent / "frontend" / "certs"
    if (project_certs / "cert.pem").exists():
        return project_certs
    try:
        import sslserver as app_module
        return Path(app_module.__file__).parent / "certs"
    except ImportError:
        return project_certs


class SecureHTTPServer(ThreadedWSGIServer):
    """Threaded WSGI server with TLS (Python 3.12+ compatible)."""

    def __init__(self, address, handler_cls, certificate, key, ipv6=False):
        self._cert_file = certificate
        self._key_file = key
        self._ipv6 = ipv6
        super().__init__(address, handler_cls, ipv6=ipv6)

    def server_bind(self):
        super().server_bind()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(
            certfile=self._cert_file,
            keyfile=self._key_file,
        )
        self.socket = context.wrap_socket(self.socket, server_side=True)


class WSGIRequestHandler(BaseWSGIRequestHandler):
    """Set HTTPS in environ so request.is_secure() is True."""

    def get_environ(self):
        env = super().get_environ()
        env["HTTPS"] = "on"
        return env


class Command(runserver.Command):
    help = "Run a Django development server over HTTPS (Python 3.12+ compatible)"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        default_dir = _default_ssl_dir()
        mkcert_exists = (default_dir / "cert.pem").exists()
        parser.add_argument(
            "--certificate",
            default=str(default_dir / ("cert.pem" if mkcert_exists else "development.crt")),
            help="Path to the certificate",
        )
        parser.add_argument(
            "--key",
            default=str(default_dir / ("key.pem" if mkcert_exists else "development.key")),
            help="Path to the key file",
        )
        parser.add_argument(
            "--nostatic",
            dest="use_static_handler",
            action="store_false",
            default=None,
            help="Do not use internal static file handler",
        )
        parser.add_argument(
            "--static",
            dest="use_static_handler",
            action="store_true",
            help="Use internal static file handler",
        )

    def get_handler(self, *args, **options):
        handler = super().get_handler(*args, **options)
        if self.should_use_static_handler(options):
            return StaticFilesHandler(handler)
        return handler

    def should_use_static_handler(self, options):
        from django.conf import settings
        use_static_handler = options.get("use_static_handler")
        if use_static_handler:
            return True
        if use_static_handler is None and "django.contrib.staticfiles" in settings.INSTALLED_APPS:
            return True
        return False

    def check_certs(self, key_file, cert_file):
        if not os.path.exists(key_file):
            raise CommandError("Can't find key at %s" % key_file)
        if not os.path.exists(cert_file):
            raise CommandError("Can't find certificate at %s" % cert_file)

    def inner_run(self, *args, **options):
        key_file = options.get("key")
        cert_file = options.get("certificate")
        self.check_certs(key_file, cert_file)

        from django.conf import settings
        from django.utils import translation

        shutdown_message = options.get("shutdown_message", "")
        quit_command = "CTRL-BREAK" if sys.platform == "win32" else "CONTROL-C"

        self.stdout.write("Validating models...\n\n")
        self.check(display_num_errors=True)
        self.stdout.write(
            (
                "%(started_at)s\n"
                "Django version %(version)s, using settings %(settings)r\n"
                "Starting development server at https://%(addr)s:%(port)s/\n"
                "Using SSL certificate: %(cert)s\n"
                "Using SSL key: %(key)s\n"
                "Quit the server with %(quit_command)s.\n"
            )
            % {
                "started_at": datetime.now().strftime("%B %d, %Y - %X"),
                "version": self.get_version(),
                "settings": settings.SETTINGS_MODULE,
                "addr": self._raw_ipv6 and "[%s]" % self.addr or self.addr,
                "port": self.port,
                "quit_command": quit_command,
                "cert": cert_file,
                "key": key_file,
            }
        )
        translation.activate(settings.LANGUAGE_CODE)

        try:
            handler = self.get_handler(*args, **options)
            server = SecureHTTPServer(
                (self.addr, int(self.port)),
                WSGIRequestHandler,
                cert_file,
                key_file,
                ipv6=self.use_ipv6,
            )
            server.set_app(handler)
            server.serve_forever()
        except WSGIServerException as e:
            ERRORS = {
                13: "You don't have permission to access that port.",
                98: "That port is already in use.",
                99: "That IP address can't be assigned to.",
            }
            try:
                error_text = ERRORS.get(e.args[0].args[0], str(e))
            except (AttributeError, KeyError, IndexError):
                error_text = str(e)
            self.stderr.write("Error: %s" % error_text)
            os._exit(1)
        except KeyboardInterrupt:
            if shutdown_message:
                self.stdout.write(shutdown_message)
            sys.exit(0)

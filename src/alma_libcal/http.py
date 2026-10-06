import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import SourceError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward Authorization headers or API keys to another host.
        return None


class HTTPClient:
    def __init__(self, timeout=30, attempts=3, opener=None, sleep=time.sleep):
        self.timeout = timeout
        self.attempts = attempts
        self.opener = opener or build_opener(NoRedirect())
        self.sleep = sleep

    def request(self, method, url, *, params=None, headers=None, form=None, retry=True) -> bytes:
        if urlsplit(url).scheme != "https":
            raise SourceError("Las conexiones de origen requieren HTTPS.")
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params)
        headers = dict(headers or {})
        data = None
        if form is not None:
            data = urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        attempts = self.attempts if retry else 1
        for attempt in range(attempts):
            try:
                req = Request(url, data=data, headers=headers, method=method)
                with self.opener.open(req, timeout=self.timeout) as response:
                    return response.read()
            except HTTPError as error:
                status = error.code
                retry_after = error.headers.get("Retry-After", "") if error.headers else ""
                error.close()
                if status not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                    raise SourceError(f"La API respondió HTTP {status}; revisa acceso y configuración.") from None
                delay = min(float(retry_after), 30) if retry_after.isdigit() else 2 ** attempt
                self.sleep(delay)
            except (URLError, TimeoutError, socket.timeout, OSError):
                if attempt == attempts - 1:
                    raise SourceError("No se pudo conectar con la API tras varios intentos.") from None
                self.sleep(2 ** attempt)
        raise SourceError("La solicitud no terminó.")

    def json(self, method, url, **kwargs):
        raw = self.request(method, url, **kwargs)
        try:
            return json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise SourceError("La API no devolvió JSON válido.") from None

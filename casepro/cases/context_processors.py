import time

import regex
from django.conf import settings


def sentry_dsn(request):
    """
    Includes the public part of our Sentry DSN which is required for the Raven JS library
    """
    dsn = getattr(settings, "SENTRY_DSN", None)
    public_dsn = None
    if dsn:
        match = regex.match(r"^https:\/\/(\w+):\w+@([\w\.\/]+)$", dsn)
        if match:
            public_key = match.group(1)
            path = match.group(2)
            public_dsn = "https://%s@%s" % (public_key, path)

    return {"sentry_public_dsn": public_dsn}


def server_time(request):
    """
    Includes the server time as a millisecond accuracy timestamp
    """
    return {"server_time": int(round(time.time() * 1000))}

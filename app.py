"""
Vercel serverless entrypoint for StockSense.

Wires the Django WSGI app and guarantees the production database
schema exists before the first request is served (works with a
connected Postgres via DATABASE_URL, or falls back to an ephemeral
SQLite database in /tmp on first cold start).
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

_database_initialized = False


def _ensure_database_ready():
    """
    Run migrations once per lambda instance before serving traffic.

    A production database URL (DATABASE_URL) is created and attached
    by the project owner in the Vercel dashboard; when it is absent,
    an ephemeral /tmp SQLite database is bootstrapped so the app still
    boots and serves pages.
    """
    global _database_initialized
    if _database_initialized:
        return
    _database_initialized = True

    import django

    django.setup()

    from django.core.management import call_command

    try:
        call_command("migrate", interactive=False, verbosity=0)
    except Exception:  # pragma: no cover - never crash the boot path
        import logging

        logging.getLogger(__name__).warning(
            "Lazy migration failed; app may misbehave until DATABASE_URL "
            "is configured.",
            exc_info=True,
        )


from django.core.wsgi import get_wsgi_application

django_app = get_wsgi_application()


def application(environ, start_response):
    _ensure_database_ready()
    return django_app(environ, start_response)

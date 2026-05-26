#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rdc_site.settings')
    # Convenience: when running the development server locally, default DEBUG to True
    # if the environment variable hasn't been set. This prevents accidental
    # ImproperlyConfigured errors for missing SECRET_KEY during local runs.
    if 'runserver' in sys.argv and os.environ.get('DEBUG') is None:
        os.environ.setdefault('DEBUG', 'True')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

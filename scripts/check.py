#!/usr/bin/env python
import os
from pathlib import Path
import sys


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    os.environ.setdefault('DJANGO_ENV', 'production')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

    import django
    from django.core.management import call_command

    django.setup()
    call_command('check', '--deploy', fail_level='WARNING')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Infrastructure check failed: {exc}', file=sys.stderr)
        raise SystemExit(1) from exc

from __future__ import annotations

import os

import django

# Ensure Django settings are configured for pytest executions.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings.dev")
django.setup()

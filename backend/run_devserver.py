#!/usr/bin/env python
"""Arranca el servidor de desarrollo en BACKEND_PORT (default 8000)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import environ

ROOT = Path(__file__).resolve().parent
environ.Env.read_env(ROOT.parent / ".env")
environ.Env.read_env(ROOT / ".env")

port = os.environ.get("BACKEND_PORT", "8000")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from django.core.management import execute_from_command_line  # noqa: E402

execute_from_command_line(["manage.py", "runserver", f"0.0.0.0:{port}", *sys.argv[1:]])

#!/usr/bin/env python3
"""Thin launcher so the shell installers can render hooks.json without an installed CLI."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from che_core.hook_config import main  # noqa: E402

raise SystemExit(main())

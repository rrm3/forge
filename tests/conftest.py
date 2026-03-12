"""Root conftest - ensure DEV_MODE is set before any backend imports."""

import os

os.environ.setdefault("DEV_MODE", "true")

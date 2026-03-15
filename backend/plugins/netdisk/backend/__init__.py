"""网盘插件后端包 / Netdisk plugin backend package."""

from __future__ import annotations

import sys

# Keep legacy absolute imports (e.g. `backend.services.*`) working inside plugin modules.
sys.modules.setdefault("backend", sys.modules[__name__])

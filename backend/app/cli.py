"""Thin CLI entry facade that preserves legacy command compatibility."""

from __future__ import annotations

import os
import sys
import types

os.environ.setdefault("NOVUSAI_CLI_DISABLE_FILE_LOGGING", "1")

from app.cli_commands import legacy as _legacy


class _CliFacadeModule(types.ModuleType):
    """Forward app.cli attribute access/mutation to legacy CLI module."""

    def __getattr__(self, name: str):  # pragma: no cover - attribute proxy
        return getattr(_legacy, name)

    def __setattr__(self, name: str, value: object) -> None:
        setattr(_legacy, name, value)
        super().__setattr__(name, value)


_MODULE = sys.modules[__name__]
_MODULE.__class__ = _CliFacadeModule

for _name in dir(_legacy):
    if _name.startswith("__"):
        continue
    setattr(_MODULE, _name, getattr(_legacy, _name))


def main() -> None:
    """CLI module entrypoint."""
    _legacy.cli()


if __name__ == "__main__":
    main()

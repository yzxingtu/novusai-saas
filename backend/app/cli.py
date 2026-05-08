"""Thin CLI entry facade for the supported command surface."""

from __future__ import annotations

import os

os.environ.setdefault("NOVUSAI_CLI_DISABLE_FILE_LOGGING", "1")

from app.cli_commands.entrypoint import cli

__all__ = ["cli", "main"]


def main() -> None:
    """CLI module entrypoint."""
    cli()


if __name__ == "__main__":
    main()

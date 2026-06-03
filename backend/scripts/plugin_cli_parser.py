"""Argument parser for plugin_cli. / plugin_cli 参数解析与派发。"""

from __future__ import annotations

import argparse

from plugin_cli_build import cmd_build
from plugin_cli_create import cmd_create
from plugin_cli_pack import cmd_pack
from plugin_cli_validate import cmd_validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NovusAI Plugin CLI",
        prog="novusai-plugin",
    )
    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser("create", help="Create plugin skeleton")
    create_parser.add_argument("name", help="Plugin name (kebab-case)")
    create_parser.add_argument(
        "--template",
        choices=["minimal", "skill", "full-module", "storage"],
        default="minimal",
    )
    create_parser.add_argument("--output", help="Output directory")
    create_parser.set_defaults(handler=cmd_create)

    validate_parser = subparsers.add_parser("validate", help="Validate plugin")
    validate_parser.add_argument("dir", help="Plugin directory")
    validate_parser.set_defaults(handler=cmd_validate)

    build_subparser = subparsers.add_parser(
        "build",
        help="Build frontend release assets",
    )
    build_subparser.add_argument("dir", help="Plugin directory")
    build_subparser.set_defaults(handler=cmd_build)

    pack_parser = subparsers.add_parser("pack", help="Pack plugin to .zip")
    pack_parser.add_argument("dir", help="Plugin directory")
    pack_parser.add_argument("--output", help="Output .zip path")
    mode_group = pack_parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--release",
        action="store_true",
        help="Pack production release bundle (default)",
    )
    mode_group.add_argument(
        "--source",
        action="store_true",
        help="Pack source/dev bundle",
    )
    pack_parser.set_defaults(handler=cmd_pack)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return
    handler(args)

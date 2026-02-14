#!/usr/bin/env python3
"""
NovusAI Plugin CLI Tool

Usage:
    python -m scripts.novusai_plugin pack <dir> [--output <path>]
    python -m scripts.novusai_plugin validate <file>
    python -m scripts.novusai_plugin init <name> [--type adapter|tool|hook|api|composite] [--author <author>]

Commands:
    pack        Pack a plugin directory into a .nap file
    validate    Validate a .nap package
    init        Scaffold a new plugin project
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def cmd_pack(args: argparse.Namespace) -> int:
    """Pack a plugin directory into .nap"""
    from app.plugins.packaging import PackageError, pack_plugin

    try:
        output = pack_plugin(args.dir, args.output)
        print(f"✓ Plugin packed: {output}")
        return 0
    except PackageError as e:
        print(f"✗ Pack failed: {e}", file=sys.stderr)
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a .nap file"""
    from app.plugins.packaging import validate_package

    errors = validate_package(args.file)
    if errors:
        print(f"✗ Validation failed ({len(errors)} errors):")
        for err in errors:
            print(f"  - {err}")
        return 1

    # Show manifest info
    import zipfile
    with zipfile.ZipFile(args.file, "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
    print(f"✓ Valid package: {manifest['name']} v{manifest['version']}")
    print(f"  Display Name: {manifest.get('display_name', '-')}")
    print(f"  Entry Point:  {manifest.get('entry_point', '-')}")
    print(f"  Author:       {manifest.get('author', '-')}")
    print(f"  Type:         {manifest.get('plugin_type', '-')}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Scaffold a new plugin"""
    from app.plugins.packaging import scaffold_plugin

    try:
        plugin_dir = scaffold_plugin(
            output_dir=args.output or ".",
            name=args.name,
            plugin_type=args.type,
            author=args.author or "",
        )
        print(f"✓ Plugin scaffolded: {plugin_dir}")
        print("  Files created:")
        for f in sorted(plugin_dir.rglob("*")):
            if f.is_file():
                print(f"    {f.relative_to(plugin_dir)}")
        return 0
    except Exception as e:
        print(f"✗ Init failed: {e}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="novusai-plugin",
        description="NovusAI Plugin CLI Tool",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # pack
    pack_parser = subparsers.add_parser("pack", help="Pack plugin directory into .nap")
    pack_parser.add_argument("dir", help="Plugin source directory")
    pack_parser.add_argument("--output", "-o", help="Output .nap file path")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate .nap package")
    validate_parser.add_argument("file", help=".nap file to validate")

    # init
    init_parser = subparsers.add_parser("init", help="Scaffold a new plugin")
    init_parser.add_argument("name", help="Plugin name (e.g. my-plugin)")
    init_parser.add_argument(
        "--type", "-t",
        choices=["adapter", "tool", "hook", "api", "skill", "composite"],
        default="composite",
        help="Plugin type (default: composite)",
    )
    init_parser.add_argument("--author", "-a", help="Plugin author")
    init_parser.add_argument("--output", "-o", help="Output directory (default: current)")

    args = parser.parse_args()

    if args.command == "pack":
        return cmd_pack(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "init":
        return cmd_init(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

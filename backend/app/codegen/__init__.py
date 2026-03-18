"""Code generation helpers. / 代码生成辅助"""

from app.codegen.auto_fix import (
    MAX_FIX_RETRIES,
    AutoFixResult,
    FixAttempt,
    FixContext,
    apply_fix_patch,
    build_fix_context,
    build_fix_instructions,
    run_fix_loop,
    suggest_human_steps,
    validate_project,
)
from app.codegen.config_parser import ConfigParser, ParsedConfig, ValidationError
from app.codegen.db_introspector import ColumnInfo, DbIntrospector, FKInfo, UniqueConstraintInfo
from app.codegen.file_writer import FileWriter, GeneratedFile, SmartAppender, WriteResult
from app.codegen.generator import CodeGenerator
from app.codegen.manifest import MANIFEST_FILENAME, ManifestEntry, ManifestManager
from app.codegen.migration_helper import inject_migration_metadata
from app.codegen.rollback import CodegenRollback, RollbackResult
from app.codegen.type_registry import TypeRegistry, type_registry
from app.codegen.zip_exporter import export_zip, format_code

__all__ = [
    "MAX_FIX_RETRIES",
    "AutoFixResult",
    "FixAttempt",
    "FixContext",
    "apply_fix_patch",
    "build_fix_context",
    "build_fix_instructions",
    "run_fix_loop",
    "suggest_human_steps",
    "validate_project",
    "ConfigParser",
    "ParsedConfig",
    "ValidationError",
    "TypeRegistry",
    "type_registry",
    "DbIntrospector",
    "ColumnInfo",
    "FKInfo",
    "UniqueConstraintInfo",
    "CodeGenerator",
    "GeneratedFile",
    "FileWriter",
    "SmartAppender",
    "WriteResult",
    "ManifestManager",
    "ManifestEntry",
    "MANIFEST_FILENAME",
    "CodegenRollback",
    "RollbackResult",
    "inject_migration_metadata",
    "export_zip",
    "format_code",
]

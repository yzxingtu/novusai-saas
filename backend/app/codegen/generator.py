"""
代码生成器 / Code Generator

Jinja2 模板渲染引擎，根据 ParsedConfig 生成代码文件
Jinja2 template engine, generates code files from ParsedConfig.
"""

from __future__ import annotations

from pathlib import Path

from app.codegen import generator_support as support
from app.codegen.config_parser import ParsedConfig
from app.codegen.generator_context_builder import build_generation_context
from app.codegen.generator_output_assembler import assemble_generation_output
from app.codegen.generator_types import GeneratedFile, GenerateResult
from app.core.logging import LogManager

logger = LogManager.get_logger("codegen")

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class CodegenGeneratorFacade:
    """Stable segmented facade for generation flows / 代码生成流程稳定分段门面."""

    def __init__(self, generator: CodeGenerator):
        self._generator = generator

    def build_context(self, parsed: ParsedConfig) -> dict:
        return self._generator.build_context(parsed)

    def generate_all(self, parsed: ParsedConfig) -> GenerateResult:
        return self._generator.generate(parsed, step=None)

    def generate_model_bundle(self, parsed: ParsedConfig) -> GenerateResult:
        return self._generator.generate(parsed, step="model")

    def generate_controller_bundle(self, parsed: ParsedConfig) -> GenerateResult:
        return self._generator.generate(parsed, step="controller")

    def generate_frontend_bundle(self, parsed: ParsedConfig) -> GenerateResult:
        return self._generator.generate(parsed, step="frontend")

    def generate_test_bundle(self, parsed: ParsedConfig) -> GenerateResult:
        return self._generator.generate(parsed, step="test")


class CodeGenerator:
    """
    代码生成器 / Code generator.

    Thin facade that delegates to:
    - scenario detection
    - template environment helpers
    - context builder
    - output assembler
    """

    def __init__(self, templates_dir: Path | None = None):
        tmpl = templates_dir or _TEMPLATES_DIR
        self.env = support.create_template_environment(tmpl)

    def as_facade(self) -> CodegenGeneratorFacade:
        """Return a stable facade for segmented generation operations."""
        return CodegenGeneratorFacade(self)

    @staticmethod
    def _path_no_leading_slash(s: str) -> str:
        return support.path_no_leading_slash(s)

    @staticmethod
    def _string_max_length(yaml_type: str) -> int | None:
        return support.string_max_length(yaml_type)

    @staticmethod
    def _to_python_literal(val: str) -> str:
        return support.to_python_literal(val)

    @staticmethod
    def _camel(s: str) -> str:
        return support.camel(s)

    @staticmethod
    def _get_column_args(field: dict, reg=None) -> str:
        return support.get_column_args(field, reg=reg)

    @staticmethod
    def _pascal(s: str) -> str:
        return support.pascal(s)

    @staticmethod
    def _fk_ref(yaml_type: str) -> str | None:
        return support.fk_ref(yaml_type)

    @staticmethod
    def _model_to_table(model_name: str) -> str:
        return support.model_to_table(model_name)

    @staticmethod
    def _pluralize(word: str) -> str:
        return support.pluralize(word)

    @staticmethod
    def _singularize(table_name: str) -> str:
        return support.singularize(table_name)

    @staticmethod
    def _model_to_fk(model_name: str) -> str:
        return support.model_to_fk(model_name)

    @staticmethod
    def _derive_workflow_states(workflow: dict | None) -> list[dict]:
        return support.derive_workflow_states(workflow)

    def build_context(self, parsed: ParsedConfig) -> dict:
        return build_generation_context(parsed)

    def generate(
        self, parsed_config: ParsedConfig, step: str | None = None
    ) -> GenerateResult:
        return assemble_generation_output(
            self.env,
            parsed_config,
            step=step,
            logger=logger,
        )


__all__ = [
    "CodeGenerator",
    "CodegenGeneratorFacade",
    "GeneratedFile",
    "GenerateResult",
]

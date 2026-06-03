"""
Toolkit parser helper functions.
"""

from __future__ import annotations

import ast
from typing import Any

# Python type hint → JSON Schema type mapping
_TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "List": "array",
    "Dict": "object",
    "Optional": "string",
}


def parse_module_docstring(tree: ast.Module) -> dict[str, Any]:
    """Extract key: value metadata from module docstring."""
    docstring = ast.get_docstring(tree)
    if not docstring:
        return {}

    meta: dict[str, Any] = {}
    for line in docstring.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if not value:
            continue

        if key == "title":
            meta["title"] = value
        elif key == "description":
            meta["description"] = value
        elif key == "version":
            meta["version"] = value
        elif key == "author":
            meta["author"] = value
        elif key == "requirements":
            meta["requirements"] = [r.strip() for r in value.split(",") if r.strip()]

    return meta


def find_class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    """Find class with specified name at AST top level."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def extract_tools_method_meta(
    cls: ast.ClassDef,
    source: str,
) -> list[dict[str, Any]]:
    """Extract metadata of all public methods in Tools class."""
    _ = source
    methods: list[dict[str, Any]] = []

    for node in ast.iter_child_nodes(cls):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Skip private methods and dunder methods
        if node.name.startswith("_"):
            continue

        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Extract docstring
        docstring = ast.get_docstring(node) or ""
        description, param_docs = _parse_method_docstring(docstring)

        # Extract parameters
        parameters = extract_method_parameters(node, param_docs)

        methods.append(
            {
                "name": node.name,
                "description": description,
                "parameters": parameters,
                "is_async": is_async,
            }
        )

    return methods


def _parse_method_docstring(docstring: str) -> tuple[str, dict[str, str]]:
    desc_lines: list[str] = []
    param_docs: dict[str, str] = {}

    for line in docstring.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith(":param "):
            remainder = stripped[len(":param ") :].strip()
            if ":" in remainder:
                name, _, description = remainder.partition(":")
                if name:
                    param_docs[name.strip()] = description.strip()
        elif stripped and not stripped.startswith(":return"):
            desc_lines.append(stripped)

    description = " ".join(desc_lines).strip()
    return description, param_docs


def extract_method_parameters(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    param_docs: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Extract parameter list from method signature type hints.

    Skips 'self' parameter.
    """
    params: list[dict[str, Any]] = []
    args = func.args

    # Calculate default value offset
    num_args = len(args.args)
    num_defaults = len(args.defaults)
    default_offset = num_args - num_defaults

    for i, arg in enumerate(args.args):
        if arg.arg == "self":
            continue

        # Type inference
        json_type = "string"
        if arg.annotation:
            json_type = annotation_to_json_type(arg.annotation)

        # Default value
        default_idx = i - default_offset
        has_default = default_idx >= 0
        default_value = None
        if has_default:
            default_value = ast_value_to_python(args.defaults[default_idx])

        # Required: no default value = required
        required = not has_default

        param_info: dict[str, Any] = {
            "name": arg.arg,
            "type": json_type,
            "description": param_docs.get(arg.arg, ""),
            "required": required,
        }
        if default_value is not None:
            param_info["default"] = default_value

        params.append(param_info)

    return params


def annotation_to_json_type(annotation: ast.expr) -> str:
    """Convert AST type annotation to JSON Schema type."""
    if isinstance(annotation, ast.Name):
        return _TYPE_MAP.get(annotation.id, "string")

    if isinstance(annotation, ast.Constant):
        return _TYPE_MAP.get(str(annotation.value), "string")

    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        outer = annotation.value.id
        if outer == "Optional":
            if isinstance(annotation.slice, ast.Name):
                return _TYPE_MAP.get(annotation.slice.id, "string")
            return "string"
        if outer == "Union":
            if isinstance(annotation.slice, ast.Tuple):
                for elt in annotation.slice.elts:
                    if isinstance(elt, ast.Constant) and elt.value is None:
                        continue
                    if isinstance(elt, ast.Name) and elt.id == "None":
                        continue
                    return annotation_to_json_type(elt)
            elif isinstance(annotation.slice, ast.Name):
                return _TYPE_MAP.get(annotation.slice.id, "string")
            return "string"
        if outer in ("list", "List"):
            return "array"
        if outer in ("dict", "Dict"):
            return "object"

    # Union type: take the first non-None type
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        left_type = annotation_to_json_type(annotation.left)
        if left_type != "string":
            return left_type
        return annotation_to_json_type(annotation.right)

    if isinstance(annotation, ast.Attribute):
        return _TYPE_MAP.get(annotation.attr, "string")

    return "string"


def ast_value_to_python(node: ast.expr) -> Any:
    """Convert AST default value node to Python value."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [ast_value_to_python(el) for el in node.elts]
    if isinstance(node, ast.Dict):
        return {
            ast_value_to_python(k) if k else None: ast_value_to_python(v)
            for k, v in zip(node.keys, node.values, strict=False)
        }
    if isinstance(node, ast.Name):
        if node.id == "None":
            return None
        if node.id == "True":
            return True
        if node.id == "False":
            return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = ast_value_to_python(node.operand)
        if isinstance(val, (int, float)):
            return -val
    return None


def extract_literal_values(annotation: ast.expr) -> list[str] | None:
    """Extract enum value list from Literal[...] type annotation."""
    if not isinstance(annotation, ast.Subscript):
        return None
    if not isinstance(annotation.value, ast.Name):
        return None
    if annotation.value.id != "Literal":
        return None

    values: list[str] = []
    if isinstance(annotation.slice, ast.Tuple):
        for elt in annotation.slice.elts:
            if isinstance(elt, ast.Constant) and elt.value is not None:
                values.append(str(elt.value))
    elif (
        isinstance(annotation.slice, ast.Constant)
        and annotation.slice.value is not None
    ):
        values.append(str(annotation.slice.value))

    return values if values else None


def extract_valves_schema(cls: ast.ClassDef, source: str) -> dict[str, Any]:
    """
    Extract JSON Schema from Valves(BaseModel) class definition.
    """
    _ = source
    properties: dict[str, Any] = {}
    required_fields: list[str] = []

    for node in ast.iter_child_nodes(cls):
        if not isinstance(node, ast.AnnAssign):
            continue

        if not isinstance(node.target, ast.Name):
            continue
        field_name = node.target.id

        if field_name.startswith("_"):
            continue

        json_type = "string"
        enum_values: list[str] | None = None
        if node.annotation:
            json_type = annotation_to_json_type(node.annotation)
            enum_values = extract_literal_values(node.annotation)

        prop: dict[str, Any] = {"type": json_type}
        if enum_values:
            prop["enum"] = enum_values

        if node.value is not None:
            default = extract_field_default(node.value)
            description = extract_field_description(node.value)

            if default is not None:
                prop["default"] = default
            if description:
                prop["description"] = description
        else:
            required_fields.append(field_name)

        properties[field_name] = prop

    if not properties:
        return {}

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required_fields:
        schema["required"] = required_fields

    return schema


def extract_field_default(value_node: ast.expr) -> Any:
    """Extract default value for Valves field."""
    if isinstance(value_node, ast.Constant):
        return value_node.value

    if isinstance(value_node, ast.Call):
        func_name = get_call_name(value_node)
        if func_name == "Field":
            if value_node.args:
                return ast_value_to_python(value_node.args[0])
            for kw in value_node.keywords:
                if kw.arg == "default":
                    return ast_value_to_python(kw.value)
    return None


def extract_field_description(value_node: ast.expr) -> str:
    """Extract description from Field(..., description="...")."""
    if not isinstance(value_node, ast.Call):
        return ""

    func_name = get_call_name(value_node)
    if func_name != "Field":
        return ""

    for kw in value_node.keywords:
        if kw.arg == "description" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return ""


def get_call_name(node: ast.Call) -> str:
    """Get function call name."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


# Dangerous import module blacklist
_DANGEROUS_MODULES = {"os", "subprocess", "sys", "shutil", "ctypes", "signal"}

# Dangerous function call blacklist
_DANGEROUS_CALLS = {"exec", "eval", "compile", "__import__", "execfile", "globals"}

# Dangerous attribute call patterns (module.func)
_DANGEROUS_ATTR_CALLS = {
    ("os", "system"),
    ("os", "popen"),
    ("os", "exec"),
    ("os", "execvp"),
    ("os", "remove"),
    ("os", "rmdir"),
    ("subprocess", "call"),
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("subprocess", "check_output"),
    ("shutil", "rmtree"),
}


def scan_dangerous_patterns(tree: ast.Module) -> list[str]:
    """
    Scan AST for dangerous patterns, return warning list (non-blocking for uploads).
    """
    warnings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in _DANGEROUS_MODULES:
                    warnings.append(
                        f"[WARNING] Line {node.lineno}: import of '{alias.name}' "
                        f"— may pose security risks in sandbox"
                    )

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod in _DANGEROUS_MODULES:
                    warnings.append(
                        f"[WARNING] Line {node.lineno}: import from '{node.module}' "
                        f"— may pose security risks in sandbox"
                    )

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in _DANGEROUS_CALLS:
                    warnings.append(
                        f"[WARNING] Line {node.lineno}: call to '{node.func.id}()' "
                        f"— potential code execution risk"
                    )
            elif isinstance(node.func, ast.Attribute) and isinstance(
                node.func.value, ast.Name
            ):
                pair = (node.func.value.id, node.func.attr)
                if pair in _DANGEROUS_ATTR_CALLS:
                    warnings.append(
                        f"[WARNING] Line {node.lineno}: call to "
                        f"'{pair[0]}.{pair[1]}()' — potential security risk"
                    )

    return warnings
